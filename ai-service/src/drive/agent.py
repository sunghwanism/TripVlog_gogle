"""
Google Drive Agent — Gemini function-calling agent.
Gemini orchestrates the entire folder search using two Drive tools:
  - search_drive_folder(name)   → returns matching folders
  - list_video_files(folder_id) → returns video files in a folder

Model: gemini-3.1-flash-lite-preview  (thinking=low, budget=512)
"""
import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path

import google.generativeai as genai
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

logger = logging.getLogger(__name__)

_SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
_SUPPORTED_VIDEO_MIME = frozenset({"video/mp4", "video/quicktime", "video/mov"})
_DRIVE_MAX_AGENT_TURNS = 5  # safety limit on agentic loop iterations

# Model config
## For Search Video
_DRIVE_AGENT_MODEL = "gemini-3.1-flash-lite-preview"
_THINKING_BUDGET_LOW = 512

# ── Auth ──────────────────────────────────────────────────────────────────────

def build_drive_service():
    """Build an authenticated Drive v3 service using OAuth2 desktop flow."""
    secret_path = Path(
        os.environ.get("GOOGLE_CLIENT_SECRET_FILE", "client_secret.json")
    ).expanduser().resolve()

    if not secret_path.exists():
        raise FileNotFoundError(
            f"client_secret.json not found at {secret_path}. "
            "Set GOOGLE_CLIENT_SECRET_FILE env var."
        )

    token_path = secret_path.parent / "token.json"
    creds = None

    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), _SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(secret_path), _SCOPES)
            creds = flow.run_local_server(port=0)
        token_path.write_text(creds.to_json())
        logger.info("OAuth2 token saved to %s", token_path)

    return build("drive", "v3", credentials=creds, cache_discovery=False)


# ── Data model ────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class VideoFile:
    file_id: str
    name: str
    mime_type: str
    size_bytes: int
    duration_seconds: float | None
    width: int | None
    height: int | None
    created_time: str | None        # ISO-8601 upload/creation timestamp
    gps_lat: float | None           # GPS latitude from video EXIF (if Drive exposes it)
    gps_lng: float | None           # GPS longitude
    camera_make: str | None         # e.g. "Apple", "Sony"
    camera_model: str | None        # e.g. "iPhone 16 Pro", "A7 IV"

    def to_dict(self) -> dict:
        result: dict = {
            "file_id": self.file_id,
            "name": self.name,
            "mime_type": self.mime_type,
            "size_bytes": self.size_bytes,
        }
        if self.duration_seconds is not None:
            result["duration_seconds"] = self.duration_seconds
        if self.width is not None:
            result["resolution"] = {"width": self.width, "height": self.height}
        if self.created_time is not None:
            result["created_time"] = self.created_time
        if self.gps_lat is not None:
            result["gps"] = {"lat": self.gps_lat, "lng": self.gps_lng}
        if self.camera_make or self.camera_model:
            result["camera"] = f"{self.camera_make or ''} {self.camera_model or ''}".strip()
        return result


# ── Drive tool implementations ─────────────────────────────────────────────────

def _tool_search_drive_folder(service, name: str) -> list[dict]:
    """Drive API: search for folders matching name. Returns serialisable list."""
    q = (
        f"name = '{name}' "
        "and mimeType = 'application/vnd.google-apps.folder' "
        "and trashed = false"
    )
    resp = (
        service.files()
        .list(q=q, fields="files(id, name, createdTime)", pageSize=10)
        .execute()
    )
    folders = resp.get("files", [])
    logger.info("[tool] search_drive_folder('%s') → %d result(s)", name, len(folders))
    return folders


def _tool_list_video_files(service, folder_id: str) -> list[dict]:
    """Drive API: list video files in folder_id. Returns serialisable list."""
    fields = (
        "nextPageToken, files("
        "id, name, mimeType, size, createdTime, "
        "videoMediaMetadata(durationMillis, width, height), "
        "imageMediaMetadata(location, cameraMake, cameraModel)"
        ")"
    )
    q = f"'{folder_id}' in parents and trashed = false"
    results: list[dict] = []
    page_token: str | None = None

    while True:
        kwargs: dict = dict(q=q, fields=fields, pageSize=100, orderBy="createdTime")
        if page_token:
            kwargs["pageToken"] = page_token

        resp = service.files().list(**kwargs).execute()

        for f in resp.get("files", []):
            if f.get("mimeType") not in _SUPPORTED_VIDEO_MIME:
                continue

            vid = f.get("videoMediaMetadata") or {}
            img = f.get("imageMediaMetadata") or {}
            loc = img.get("location") or {}

            results.append({
                "file_id": f["id"],
                "name": f.get("name", ""),
                "mime_type": f["mimeType"],
                "size_bytes": int(f.get("size") or 0),
                "created_time": f.get("createdTime"),
                "duration_ms": int(vid.get("durationMillis") or 0),
                "width": vid.get("width"),
                "height": vid.get("height"),
                "gps_lat": loc.get("latitude"),
                "gps_lng": loc.get("longitude"),
                "camera_make": img.get("cameraMake"),
                "camera_model": img.get("cameraModel"),
            })

        page_token = resp.get("nextPageToken")
        if not page_token:
            break

    logger.info("[tool] list_video_files('%s') → %d video(s)", folder_id, len(results))
    return results


# ── Tool dispatcher ───────────────────────────────────────────────────────────

def _dispatch(service, name: str, args: dict) -> dict:
    """Execute a tool by name and return a JSON-serialisable result dict."""
    if name == "search_drive_folder":
        return {"folders": _tool_search_drive_folder(service, args["name"])}

    if name == "list_video_files":
        return {"videos": _tool_list_video_files(service, args["folder_id"])}

    raise ValueError(f"Unknown tool: {name}")


# ── Gemini tool schema ────────────────────────────────────────────────────────

_DRIVE_TOOLS = genai.types.Tool(
    function_declarations=[
        genai.types.FunctionDeclaration(
            name="search_drive_folder",
            description=(
                "Search Google Drive for folders whose name matches the given string. "
                "Returns a list of folders with id, name, and createdTime."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "The folder name to search for",
                    }
                },
                "required": ["name"],
            },
        ),
        genai.types.FunctionDeclaration(
            name="list_video_files",
            description=(
                "List all video files (mp4, mov) inside a Google Drive folder. "
                "Returns file id, name, mime_type, size, duration, and resolution."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "folder_id": {
                        "type": "string",
                        "description": "The Google Drive folder ID",
                    }
                },
                "required": ["folder_id"],
            },
        ),
    ]
)


# ── Agentic loop ──────────────────────────────────────────────────────────────

def _run_drive_agent(service, folder_name: str) -> list[dict]:
    """
    Run the Gemini function-calling agent.
    Gemini decides when to call search_drive_folder and list_video_files.
    Returns the raw video dicts from the final list_video_files call.
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY not configured")

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(
        model_name=_DRIVE_AGENT_MODEL,
        tools=[_DRIVE_TOOLS],
        generation_config=genai.GenerationConfig(
            thinking_config=genai.types.ThinkingConfig(
                thinking_budget=_THINKING_BUDGET_LOW
            )
        ),
    )

    chat = model.start_chat()
    response = chat.send_message(
        f"Find the Google Drive folder named '{folder_name}' and list all video files in it. "
        f"Use the search_drive_folder tool first, then list_video_files on the chosen folder."
    )

    collected_videos: list[dict] = []

    for turn in range(_DRIVE_MAX_AGENT_TURNS):
        # Collect all function calls from this response
        fn_calls = [
            p.function_call
            for p in response.parts
            if hasattr(p, "function_call") and p.function_call.name
        ]

        if not fn_calls:
            # No more tool calls — agent is done
            logger.info("Drive Agent finished after %d turn(s)", turn + 1)
            break

        # Execute each tool and build function-response parts
        response_parts = []
        for fn_call in fn_calls:
            args = dict(fn_call.args)
            logger.info("Drive Agent calling tool: %s(%s)", fn_call.name, args)

            tool_result = _dispatch(service, fn_call.name, args)

            # Track video results for our return value
            if fn_call.name == "list_video_files":
                collected_videos = tool_result.get("videos", [])

            response_parts.append(
                genai.protos.Part(
                    function_response=genai.protos.FunctionResponse(
                        name=fn_call.name,
                        response=tool_result,
                    )
                )
            )

        response = chat.send_message(response_parts)

    return collected_videos


# ── Public entry point ────────────────────────────────────────────────────────

def list_videos_in_folder(folder_name: str) -> list[VideoFile]:
    """
    Drive Agent entry point.
    Gemini orchestrates folder search + video listing via function calling.
    Returns a list of VideoFile objects.
    """
    service = build_drive_service()
    raw_videos = _run_drive_agent(service, folder_name)

    videos = [
        VideoFile(
            file_id=v["file_id"],
            name=v["name"],
            mime_type=v["mime_type"],
            size_bytes=v["size_bytes"],
            duration_seconds=v["duration_ms"] / 1000.0 if v["duration_ms"] else None,
            width=v.get("width"),
            height=v.get("height"),
            created_time=v.get("created_time"),
            gps_lat=v.get("gps_lat"),
            gps_lng=v.get("gps_lng"),
            camera_make=v.get("camera_make"),
            camera_model=v.get("camera_model"),
        )
        for v in raw_videos
    ]

    logger.info("Drive Agent returned %d video file(s)", len(videos))
    return videos
