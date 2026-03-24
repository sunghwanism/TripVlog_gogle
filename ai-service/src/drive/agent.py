"""
Google Drive Agent — Gemini function-calling agent.
Gemini orchestrates the entire folder search using two Drive tools:
  - search_drive_folder(name)   → returns matching folders
  - list_video_files(folder_id) → returns video files in a folder

Auth: Web OAuth — tokens stored per user in TOKEN_DIR/{user_id}.json
      Call GET /auth/drive/url?user_id=<id> to authorize a new user.

Model: gemini-3.1-flash-lite-preview  (thinking=low, budget=512)
"""
import logging
import os
from dataclasses import dataclass
from pathlib import Path

from google import genai
from google.genai import types
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

logger = logging.getLogger(__name__)

_SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
_SUPPORTED_VIDEO_MIME = frozenset({"video/mp4", "video/quicktime", "video/mov"})
_DRIVE_MAX_AGENT_TURNS = 5

# Model config
_DRIVE_AGENT_MODEL = "gemini-3.1-flash-lite-preview"
_THINKING_BUDGET_LOW = 512

# ── Token storage ─────────────────────────────────────────────────────────────

def _get_token_path(user_id: str) -> Path:
    """Return per-user token path: TOKEN_DIR/{user_id}.json"""
    token_dir = Path(
        os.environ.get("TOKEN_DIR", "~/.tripvlog/tokens")
    ).expanduser().resolve()
    return token_dir / f"{user_id}.json"

# ── Errors ────────────────────────────────────────────────────────────────────

class AuthRequiredError(Exception):
    """Raised when no valid Drive token exists for a user."""
    def __init__(self, user_id: str):
        self.user_id = user_id
        super().__init__(
            f"User '{user_id}' is not authorized. "
            f"Call GET /auth/drive/url?user_id={user_id} to start authorization."
        )


# ── Auth ──────────────────────────────────────────────────────────────────────

def build_drive_service(user_id: str):
    """
    Build an authenticated Drive v3 service for user_id.
    Loads TOKEN_DIR/{user_id}.json — refreshes silently if expired.
    Raises AuthRequiredError if no valid token exists.
    """
    token_path = _get_token_path(user_id)

    if not token_path.exists():
        raise AuthRequiredError(user_id)

    creds = Credentials.from_authorized_user_file(str(token_path), _SCOPES)

    if not creds.valid:
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            token_path.write_text(creds.to_json())
            logger.info("Token refreshed for user '%s'", user_id)
        else:
            raise AuthRequiredError(user_id)

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

_DRIVE_TOOLS = types.Tool(
    function_declarations=[
        types.FunctionDeclaration(
            name="search_drive_folder",
            description=(
                "Search Google Drive for folders whose name matches the given string. "
                "Returns a list of folders with id, name, and createdTime."
            ),
            parameters=types.Schema(
                type="OBJECT",
                properties={
                    "name": types.Schema(
                        type="STRING",
                        description="The folder name to search for",
                    )
                },
                required=["name"],
            ),
        ),
        types.FunctionDeclaration(
            name="list_video_files",
            description=(
                "List all video files (mp4, mov) inside a Google Drive folder. "
                "Returns file id, name, mime_type, size, duration, and resolution."
            ),
            parameters=types.Schema(
                type="OBJECT",
                properties={
                    "folder_id": types.Schema(
                        type="STRING",
                        description="The Google Drive folder ID",
                    )
                },
                required=["folder_id"],
            ),
        ),
    ]
)


# ── Agentic loop ──────────────────────────────────────────────────────────────

def _run_drive_agent(service, folder_name: str, user_id: str) -> list[dict]:
    """
    Run the Gemini function-calling agent.
    Gemini decides when to call search_drive_folder and list_video_files.
    Returns the raw video dicts from the final list_video_files call.
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY not configured")

    # 1. init Client
    client = genai.Client(api_key=api_key)

    # 2. Make Chat Object
    chat = client.chats.create(
        model=_DRIVE_AGENT_MODEL,
        config=types.GenerateContentConfig(
            tools=[_DRIVE_TOOLS],
            thinking_config=types.ThinkingConfig(
                include_thoughts=True,
                thinking_level='low'
            ),
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=False)
        )
    )

    response = chat.send_message(
        message=(
            f"Find the Google Drive folder named '{folder_name}' and list all video files in it. "
            f"Use the search_drive_folder tool first, then list_video_files on the chosen folder."
        )
    )
    print("================================================================")
    print("**Debugging in src.drive.agent.py**")
    for part in response.candidates[0].content.parts:
        if part.text:
            print(f"[Response]: {part.text}")
        
        if part.thought:
            print(f"[Thinking]: {part.thought}")
        
        if part.function_call:
            print(f"[Function Call]: {part.function_call.name}({part.function_call.args})")

    print("================================================================")
    collected_videos = []

    for turn in range(_DRIVE_MAX_AGENT_TURNS):
        fn_calls = [
            part.function_call 
            for part in response.candidates[0].content.parts 
            if part.function_call
        ]

        if not fn_calls:
            logger.info("Drive Agent finished after %d turn(s)", turn + 1)
            break

        response_parts = []
        for fn_call in fn_calls:
            args = fn_call.args 
            logger.info("Drive Agent calling tool: %s(%s)", fn_call.name, args)
            tool_result = _dispatch(service, fn_call.name, args)

            if fn_call.name == "list_video_files":
                collected_videos = tool_result.get("videos", [])

            response_parts.append(
                types.Part(
                    function_response=types.FunctionResponse(
                        name=fn_call.name,
                        response=tool_result,
                    )
                )
            )

        response = chat.send_message(message=response_parts)

    return collected_videos

# ── Public entry point ────────────────────────────────────────────────────────

def list_videos_in_folder(folder_name: str, user_id: str) -> list[VideoFile]:
    """
    Drive Agent Entry Point.
    """
    # Run Agent
    service = build_drive_service(user_id) # Google Drive Servie build(drive, v3, ...)
    raw_videos = _run_drive_agent(service, folder_name, user_id)

    if not raw_videos:
        logger.warning("No videos found by Drive Agent for folder: %s", folder_name)
        return []

    videos = []
    for v in raw_videos:
        try:
            video = VideoFile(
                file_id=v.get("file_id", ""),
                name=v.get("name", "unnamed_video"),
                mime_type=v.get("mime_type", "video/mp4"),
                size_bytes=int(v.get("size_bytes", 0)),
                duration_seconds=float(v["duration_ms"]) / 1000.0 if v.get("duration_ms") else None,
                width=v.get("width"),
                height=v.get("height"),
                created_time=v.get("created_time"),
                gps_lat=v.get("gps_lat"),
                gps_lng=v.get("gps_lng"),
                camera_make=v.get("camera_make"),
                camera_model=v.get("camera_model"),
            )
            videos.append(video)
        except (KeyError, ValueError, TypeError) as e:
            logger.error("Failed to parse video data: %s, Error: %s", v, e)
            continue

    logger.info("Drive Agent returned %d video file(s)", len(videos))
    return videos
