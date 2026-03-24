"""
AI Service FastAPI application.
Endpoints:
  GET  /auth/drive/url       - Start web OAuth: returns Google consent URL
  GET  /auth/drive/callback  - OAuth callback: exchanges code, saves per-user token
  POST /pipeline             - Full pipeline: Drive Agent → descriptions → storyboard
  POST /analyze              - Extract metadata from media files (legacy)
  POST /storyboard           - Gemini analysis + storyboard assembly (legacy)
  GET  /health               - Health check
"""
import os
import secrets
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from clustering.gps_cluster import cluster_by_gps, compute_cluster_centroids
from extractor.geocoding import reverse_geocode
from extractor.metadata import extract_metadata
# from gemini.analyzer import analyze_media_batch
from gemini.validator import MediaBatch

app = FastAPI(title='TripVlog AI Service', version='2.0.0')

# In-memory state store for CSRF (local dev).
# Replace with Redis for production.
_pending_states: dict[str, str] = {}  # state_token → user_id

_DRIVE_SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]


def _client_secret_path() -> Path:
    p = Path(
        os.environ.get("GOOGLE_CLIENT_SECRET_FILE", "client_secret.json")
    ).expanduser().resolve()
    if not p.exists():
        raise FileNotFoundError(
            f"client_secret.json not found at {p}. "
            "Set GOOGLE_CLIENT_SECRET_FILE env var."
        )
    return p


def _redirect_uri() -> str:
    return os.environ.get(
        "GOOGLE_REDIRECT_URI", "http://localhost:8000/auth/drive/callback"
    )


# ── OAuth endpoints ───────────────────────────────────────────────────────────

@app.get('/auth/drive/url')
async def auth_drive_url(user_id: str) -> dict:
    """
    Step 1 of web OAuth flow.
    Returns a Google consent URL the user must open in their browser.
    """
    from google_auth_oauthlib.flow import Flow

    flow = Flow.from_client_secrets_file(
        str(_client_secret_path()),
        scopes=_DRIVE_SCOPES,
        redirect_uri=_redirect_uri(),
    )
    state = secrets.token_urlsafe(16)
    _pending_states[state] = user_id

    auth_url, _ = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true',
        state=state,
        prompt='consent',
    )
    return {"auth_url": auth_url, "user_id": user_id}


@app.get('/auth/drive/callback')
async def auth_drive_callback(code: str, state: str) -> HTMLResponse:
    """
    Step 2 of web OAuth flow.
    Google redirects here with ?code=...&state=...
    Exchanges the code for tokens and saves TOKEN_DIR/{user_id}.json.
    """
    from google_auth_oauthlib.flow import Flow
    from drive.agent import _get_token_path

    user_id = _pending_states.pop(state, None)
    if not user_id:
        raise HTTPException(status_code=400, detail="Invalid or expired state parameter.")

    flow = Flow.from_client_secrets_file(
        str(_client_secret_path()),
        scopes=_DRIVE_SCOPES,
        redirect_uri=_redirect_uri(),
        state=state,
    )
    flow.fetch_token(code=code)

    token_path = _get_token_path(user_id)
    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(flow.credentials.to_json())

    return HTMLResponse(
        content=(
            f"<h2>Authorization successful!</h2>"
            f"<p>User <b>{user_id}</b> is now connected to Google Drive.</p>"
            f"<p>You can close this tab and return to the demo.</p>"
        )
    )

STORYBOARD_SCHEMA_PATH = Path(__file__).parent / 'schemas' / 'storyboard.json'
QUALITY_GATE = 3.0  # Scenes below this score are excluded unless only footage for cluster


# ── Pipeline (v2) ──────────────────────────────────────────────────────────────

class PipelineRequest(BaseModel):
    project_id: str
    user_id: str = Field(min_length=1, description="User ID — must be authorized via /auth/drive/url")
    folder_name: str = Field(min_length=1, description="Google Drive folder name")
    mood: str = Field(min_length=5, max_length=1000, description="Desired mood / atmosphere")


@app.post('/pipeline')
async def run_pipeline(req: PipelineRequest) -> dict:
    """
    v2 pipeline:
      1. Drive Agent (Gemini Flash) → search folder → list video files
      2. Analyze each video with Gemini File API → objects, scene, mood, key moments
      3. All descriptions → Gemini Flash → ordered storyboard JSON
    """
    from drive.agent import AuthRequiredError, list_videos_in_folder
    from gemini.storyboard_gen import generate_storyboard
    from gemini.video_describer import VideoDescription, describe_video

    # Step 1: Drive Agent
    try:
        videos = list_videos_in_folder(req.folder_name, req.user_id)
    except AuthRequiredError as exc:
        raise HTTPException(
            status_code=401,
            detail={
                "message": str(exc),
                "auth_url": f"/auth/drive/url?user_id={req.user_id}",
            },
        )

    if not videos:
        raise HTTPException(
            status_code=422,
            detail=f"No video files found in Drive folder '{req.folder_name}'",
        )

    # Step 2: Analyze each video with Gemini File API
    descriptions = []
    for v in videos:
        desc = describe_video(v, req.user_id)
        descriptions.append(desc.model_copy(update={
            "created_time": v.created_time,
            "gps_lat": v.gps_lat,
            "gps_lng": v.gps_lng,
            "camera_info": (
                f"{v.camera_make or ''} {v.camera_model or ''}".strip() or None
            ),
        }))

    # Step 3: Storyboard
    return generate_storyboard(descriptions, req.mood, req.project_id)


# ── Legacy endpoints (v1) ──────────────────────────────────────────────────────

class AnalyzeRequest(BaseModel):
    project_id: str
    files: list[dict]  # [{file_path, drive_file_id, mime_type}]

# @app.post('/storyboard')
# async def generate_storyboard(batch: MediaBatch) -> dict:
#     """Run Gemini analysis and assemble validated storyboard JSON."""
#     # 1. Run Gemini analysis
#     scene_analyses = analyze_media_batch(batch)

#     if not scene_analyses:
#         raise HTTPException(status_code=422, detail='Gemini analysis returned no results')

#     # 2. GPS clustering on media items
#     items_with_meta = [item.model_dump() for item in batch.media_items]
#     clustered_items = cluster_by_gps(items_with_meta)
#     centroids = compute_cluster_centroids(clustered_items)

#     # 3. Build item -> cluster map
#     item_cluster = {
#         item['file_id']: item.get('cluster_id', -1)
#         for item in clustered_items
#     }

#     # 4. Count items per cluster for quality gate decisions
#     cluster_counts: dict[int, int] = {}
#     for cid in item_cluster.values():
#         cluster_counts[cid] = cluster_counts.get(cid, 0) + 1

#     # 5. Assemble scenes — apply quality gate
#     scenes = _assemble_scenes(scene_analyses, batch, item_cluster, cluster_counts, centroids)

#     if len(scenes) < 3:
#         raise HTTPException(
#             status_code=422,
#             detail=f'Insufficient scenes after quality gate: {len(scenes)}',
#         )

#     # 6. Calculate total_duration via Python (never LLM math)
#     total_duration = _calculate_total_duration(scenes)

#     storyboard = {
#         'project_id': batch.project_id,
#         'concept': batch.concept_prompt[:500],
#         'total_duration_seconds': total_duration,
#         'scenes': scenes,
#         'metadata': {
#             'created_at': datetime.now(timezone.utc).isoformat(),
#             'gemini_model': 'gemini-3.1-flash-lite-preview',
#             'analysis_version': '1.0.0',
#             'total_media_items': len(batch.media_items),
#             'failed_items': len(batch.media_items) - len(scene_analyses),
#             'location_clusters': len(centroids),
#         },
#     }

#     return storyboard


def _assemble_scenes(
    scene_analyses: list,
    batch: MediaBatch,
    item_cluster: dict[str, int],
    cluster_counts: dict[int, int],
    centroids: dict[int, dict],
) -> list[dict]:
    """Build scene list applying quality gate logic. Returns new list."""
    scenes = []
    for i, analysis in enumerate(scene_analyses):
        file_id = batch.media_items[i].file_id if i < len(batch.media_items) else f'file_{i}'
        cluster_id = item_cluster.get(file_id, -1)

        # Quality gate: exclude score < 3.0 unless only footage for cluster
        if analysis.quality_score < QUALITY_GATE and cluster_counts.get(cluster_id, 0) > 1:
            continue

        centroid = centroids.get(cluster_id, {'lat': 0.0, 'lng': 0.0})
        location_name = 'Unknown Location' if cluster_id == -1 else f'Location {cluster_id}'

        scenes.append({
            'scene_id': f'scene_{len(scenes):03d}',
            'order': len(scenes),
            'source_files': [file_id],
            'scene_type': analysis.scene_type.value,
            'location': {
                **centroid,
                'name': location_name,
            },
            'duration_seconds': analysis.suggested_duration_seconds,
            'transition_type': analysis.transition_type.value,
            'transition_duration_ms': 500,
            'emotion_tags': analysis.emotion_tags,
            'quality_score': analysis.quality_score,
            'caption': {
                'text': analysis.caption_suggestion,
                'style': 'cinematic',
            },
        })
    return scenes


def _calculate_total_duration(scenes: list[dict]) -> float:
    """Calculate total video duration in seconds — Python math, no LLM."""
    scene_total = sum(s['duration_seconds'] for s in scenes)
    transition_total = sum(s['transition_duration_ms'] / 1000 for s in scenes[:-1])
    return round(scene_total + transition_total, 2)


@app.get('/health')
async def health() -> dict:
    return {'status': 'ok'}
