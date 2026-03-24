# Phase 01 Checkpoint — 2026-03-24

## Status: COMPLETE — Full pipeline running with real Google Drive + Gemini File API

---

## Previous Checkpoint (2026-03-23)

<details>
<summary>Pipeline v2 — Drive Agent + Web OAuth (2026-03-23)</summary>

### Pipeline Redesign — v2 Architecture

Replaced mock/local demo with real Google Drive integration.

**Pipeline flow:**
```
USER_ID + DRIVE_FOLDER_NAME + MOOD + GEMINI_API_KEY
  → Auth Check (Web OAuth, multi-user)
  ↓
① Drive Agent  (gemini-3.1-flash-lite-preview, thinking=low, budget=512)
   └─ Gemini function-calling: search_drive_folder → list_video_files
   └─ Returns: file_id, name, duration, resolution, GPS, camera, created_time
  ↓
② Build VideoDescriptions from Drive metadata (no download)
   └─ Per-video object analysis deferred to later phase
  ↓
③ Storyboard Generator  (gemini-3.1-flash-lite-preview, thinking=medium, budget=8192)
   └─ Ordered scenes with captions, transitions, emotion tags
   └─ Python-calculated total duration (no LLM math)
  ↓
   Storyboard JSON
```

### Files Modified / Created

#### `ai-service/src/drive/agent.py` — Major rewrite
- Removed `InstalledAppFlow` (desktop OAuth)
- Added `_get_token_path(user_id)` — `TOKEN_DIR/{user_id}.json`
- Added `AuthRequiredError(user_id)` — raised when no valid token exists
- `build_drive_service(user_id)` — loads token, auto-refreshes, raises `AuthRequiredError`
- `VideoFile` dataclass — new fields: `created_time`, `gps_lat`, `gps_lng`, `camera_make`, `camera_model`
- `_run_drive_agent(service, folder_name, user_id)` — agentic loop, `_DRIVE_MAX_AGENT_TURNS = 5`
- `list_videos_in_folder(folder_name, user_id)` — public entry point

#### `ai-service/src/gemini/video_describer.py` — Created (deferred at the time)
- `VideoDescription` Pydantic model
- `describe_video(video: VideoFile)` — downloads, uploads to Gemini File API, analyzes
- **NOT called in pipeline at this point**

#### `ai-service/src/gemini/storyboard_gen.py` — New
- `generate_storyboard(descriptions, mood, project_id)`
- `_build_user_prompt` — wraps mood in `<user-mood-data>` tags (injection defense)
- `_build_scenes` — caps duration to actual video length, clamps to [2.0, 30.0]
- `_calculate_total_duration` — Python math only

#### `PoC/phase1/demo.py` — New
- `_ensure_authorized(user_id, client_secret)` — one-shot HTTPServer on port 8765
- Calls `POST /pipeline` via `httpx.AsyncClient(ASGITransport)`

</details>

<details>
<summary>Phase 01 initial implementation (2026-03-22)</summary>

### Backend (Node.js/TypeScript) — ALL DONE ✅
- `backend/src/db/schema.sql` — 4-table PostgreSQL DDL
- `backend/src/services/encryption.ts` — AES-256-GCM
- `backend/src/services/drive.ts` — Drive client + file listing
- `backend/src/routes/auth.ts` — OAuth2 callback + /me
- `backend/src/routes/projects.ts` — CRUD + SSE progress
- `backend/tests/` — 5 test files ✅

### AI Service (Python/FastAPI) — ALL DONE ✅
- `ai-service/src/extractor/metadata.py` — EXIF/XMP/ffprobe extraction
- `ai-service/src/clustering/gps_cluster.py` — DBSCAN-inspired GPS clustering
- `ai-service/src/gemini/analyzer.py` — GeminiAnalyzer batched pipeline
- `ai-service/src/api.py` — FastAPI endpoints (/analyze, /storyboard, /health)
- `ai-service/tests/` — 6 test files ✅

</details>

---

## Current Session Changes (2026-03-24)

### Step 2: Per-video Gemini File API Analysis — Now Wired

`describe_video()` was previously implemented but not connected to the pipeline.
It is now called for every video in `POST /pipeline`.

**Updated pipeline flow:**
```
USER_ID + DRIVE_FOLDER_NAME + MOOD + GEMINI_API_KEY
  → Auth Check (Web OAuth, multi-user)
  ↓
① Drive Agent  (gemini-3.1-flash-lite-preview, thinking=low, budget=512)
   └─ Gemini function-calling: search_drive_folder → list_video_files
   └─ Returns: file_id, name, duration, resolution, GPS, camera, created_time
  ↓
② Analyze each video  (gemini-3.1-flash-lite-preview, thinking=low, budget=2048)
   └─ describe_video(video, user_id): download → Gemini File API → objects/scene/mood/key_moments
   └─ Drive metadata (GPS, camera, created_time) merged via model_copy()
   └─ files >200 MB → fallback description (no download)
  ↓
③ Storyboard Generator  (gemini-3.1-flash-lite-preview, thinking=medium, budget=8192)
   └─ Ordered scenes with captions, transitions, emotion tags
   └─ Python-calculated total duration (no LLM math)
  ↓
   Storyboard JSON
```

---

### Files Modified

#### `ai-service/src/gemini/video_describer.py`
- `describe_video(video, user_id)` — added `user_id` parameter
- `_download_to_temp(file_id, dest, user_id)` — passes `user_id` to `build_drive_service()`
- `client.files.upload(path=...)` → `client.files.upload(file=...)` — API fix for google-genai v1.68.0
- Added `from google.genai import types` — was missing, caused `NameError`

#### `ai-service/src/api.py`
- Step 2: replaced Drive-metadata-only `VideoDescription` list with `describe_video(v, req.user_id)` loop
- `desc.model_copy(update={created_time, gps_lat, gps_lng, camera_info})` — merges Drive metadata
- Import updated: `from gemini.video_describer import VideoDescription, describe_video`

#### `PoC/phase1/README.md`
- Pipeline diagram updated to show Step 2 as Gemini File API analysis
- Expected output updated with real run results (3 videos, failed_items: 0)
- Added custom mood example (`MOOD="열심히 자기개발 하는 나"`)
- Removed `pip install git+...` line (not required)

---

### Bug Fixes

| Bug | Root Cause | Fix |
|-----|-----------|-----|
| `build_drive_service() missing user_id` | `_download_to_temp` called without `user_id` | Added `user_id` param through call chain |
| `files.upload() unexpected keyword 'path'` | google-genai v1.68.0 uses `file=` not `path=` | Changed to `file=str(local_path)` |
| `name 'types' is not defined` | `from google.genai import types` missing | Added import |

---

### Verified Run (2026-03-24)

```
Folder        : Vlog_Sample (3 videos)
MOOD          : 열심히 자기개발 하는 나
Videos analyzed   : 3
Failed items      : 0
Location clusters : 3  (Café, Starbucks, Kingston)
Total duration    : 23.3s
Scenes            : 3
```

---

## Environment

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GOOGLE_CLIENT_SECRET_FILE` | Yes | `<repo>/client_secret.json` | GCP OAuth credentials |
| `DRIVE_FOLDER_NAME` | Yes | — | Google Drive folder name |
| `GEMINI_API_KEY` | Yes | — | Gemini API key |
| `USER_ID` | No | `demo-user` | Per-user token identifier |
| `TOKEN_DIR` | No | `~/.tripvlog/tokens` | Token storage directory |
| `MOOD` | No | `"A cinematic travel story…"` | Storyboard mood / concept |
| `PROJECT_ID` | No | `poc-phase1-001` | Output project identifier |

---

## How to Run

```bash
source ai-service/gogle/bin/activate

USER_ID=alice \
GOOGLE_CLIENT_SECRET_FILE=/path/to/client_secret.json \
DRIVE_FOLDER_NAME="Vlog_Sample" \
GEMINI_API_KEY=your-key \
MOOD="열심히 자기개발 하는 나" \
python PoC/phase1/demo.py
```

---

## Next Steps (Phase 02)
- Narrative & Reference: YouTube style references + concept storyboard refinement
- Location name resolution: reverse geocode GPS coordinates from `location_hint`
- Remove legacy v1 endpoints (`/analyze`, `/storyboard`) from `api.py`
