"""
Video Description Generator.
Downloads each Drive video to a temp file, uploads to Gemini File API,
and generates a structured description (objects, scene, mood, key moments).
Model: gemini-1.5-flash (cheapest model supporting video via File API)
"""
import json
import logging
import os
import tempfile
import time
from pathlib import Path

import google.generativeai as genai
from googleapiclient.http import MediaIoBaseDownload
from pydantic import BaseModel, Field

from drive.agent import VideoFile, build_drive_service

logger = logging.getLogger(__name__)

_MAX_DOWNLOAD_BYTES = 200 * 1024 * 1024   # 200 MB — skip above this
_POLL_INTERVAL_SECS = 5
_POLL_TIMEOUT_SECS = 180

_DESCRIPTION_PROMPT = """Analyze this video and return a JSON object with exactly these fields:
{
  "objects_detected": ["list of main objects, people, animals, places visible"],
  "scene_description": "2-3 sentence description of the video content and action",
  "mood": "one word or short phrase describing the mood/atmosphere",
  "key_moments": ["brief description of 2-5 key moments in the video"],
  "location_hint": "location name if identifiable from visuals, else 'Unknown'"
}
Return ONLY the JSON object. No markdown fences, no extra text."""


# ── Pydantic model ────────────────────────────────────────────────────────────

class VideoDescription(BaseModel):
    file_id: str
    file_name: str
    duration_seconds: float | None = None
    created_time: str | None = None       # ISO-8601 from Drive
    gps_lat: float | None = None
    gps_lng: float | None = None
    camera_info: str | None = None        # e.g. "Apple iPhone 16 Pro"
    objects_detected: list[str] = Field(default_factory=list)
    scene_description: str
    mood: str
    key_moments: list[str] = Field(default_factory=list)
    location_hint: str = "Unknown"


# ── Internal helpers ──────────────────────────────────────────────────────────

def _download_to_temp(file_id: str, dest: Path) -> None:
    """Stream a Drive file into dest using 8 MB chunks."""
    service = build_drive_service()
    request = service.files().get_media(fileId=file_id)

    with open(dest, "wb") as fh:
        downloader = MediaIoBaseDownload(fh, request, chunksize=8 * 1024 * 1024)
        done = False
        while not done:
            _, done = downloader.next_chunk()


def _upload_and_wait(local_path: Path, mime_type: str):
    """
    Upload a local video to Gemini File API and wait until state == ACTIVE.
    Returns the ready Gemini File object.
    """
    video_file = genai.upload_file(path=str(local_path), mime_type=mime_type)

    elapsed = 0
    while video_file.state.name == "PROCESSING":
        if elapsed >= _POLL_TIMEOUT_SECS:
            raise TimeoutError(
                f"Gemini File API processing timed out after {elapsed}s for {local_path.name}"
            )
        time.sleep(_POLL_INTERVAL_SECS)
        elapsed += _POLL_INTERVAL_SECS
        video_file = genai.get_file(video_file.name)

    if video_file.state.name == "FAILED":
        raise RuntimeError(f"Gemini File API failed to process {local_path.name}")

    return video_file


def _parse_json_response(raw: str) -> dict:
    """Strip optional markdown fences and parse JSON."""
    text = raw.strip()
    if text.startswith("```"):
        parts = text.split("```")
        # parts[1] may start with "json\n"
        text = parts[1].lstrip("json").strip() if len(parts) > 1 else text
    return json.loads(text)


def _fallback_description(video: VideoFile) -> VideoDescription:
    """Minimal description used when analysis is skipped or fails."""
    return VideoDescription(
        file_id=video.file_id,
        file_name=video.name,
        duration_seconds=video.duration_seconds,
        scene_description=f"Video clip: {video.name}",
        mood="unknown",
    )


# ── Public API ────────────────────────────────────────────────────────────────

def describe_video(video: VideoFile) -> VideoDescription:
    """
    Analyze a Drive video using Gemini File API.
    Steps:
      1. Skip oversized files (> 200 MB) with a fallback description.
      2. Download video to a temp file.
      3. Upload to Gemini File API and wait for processing.
      4. Send analysis prompt → parse JSON → return VideoDescription.
      5. Clean up temp file and Gemini file on exit.
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY not configured")

    genai.configure(api_key=api_key)

    size_mb = video.size_bytes / 1024 / 1024
    if video.size_bytes > _MAX_DOWNLOAD_BYTES:
        logger.warning(
            "Skipping Gemini analysis for '%s' — %.0f MB exceeds %.0f MB limit",
            video.name,
            size_mb,
            _MAX_DOWNLOAD_BYTES / 1024 / 1024,
        )
        return _fallback_description(video)

    suffix = Path(video.name).suffix or ".mp4"
    tmp_path: Path | None = None
    gemini_file = None

    try:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp_path = Path(tmp.name)

        logger.info("Downloading '%s' (%.1f MB)...", video.name, size_mb)
        _download_to_temp(video.file_id, tmp_path)

        logger.info("Uploading '%s' to Gemini File API...", video.name)
        gemini_file = _upload_and_wait(tmp_path, video.mime_type)

        model = genai.GenerativeModel("gemini-1.5-flash")
        response = model.generate_content([gemini_file, _DESCRIPTION_PROMPT])

        parsed = _parse_json_response(response.text)

        return VideoDescription(
            file_id=video.file_id,
            file_name=video.name,
            duration_seconds=video.duration_seconds,
            objects_detected=parsed.get("objects_detected", []),
            scene_description=parsed.get("scene_description", ""),
            mood=parsed.get("mood", ""),
            key_moments=parsed.get("key_moments", []),
            location_hint=parsed.get("location_hint", "Unknown"),
        )

    except Exception as exc:
        logger.error("Failed to describe '%s': %s", video.name, exc)
        return _fallback_description(video)

    finally:
        if tmp_path and tmp_path.exists():
            tmp_path.unlink(missing_ok=True)
        if gemini_file is not None:
            try:
                genai.delete_file(gemini_file.name)
            except Exception:
                pass
