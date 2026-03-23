# Phase 1: Data & Analysis Demo (PoC)

## Pipeline Overview

```
USER_ID + DRIVE_FOLDER_NAME + MOOD + GEMINI_API_KEY
        │
        ▼
[Auth]  Web OAuth  (multi-user)
   └─ first run → browser opens → Google consent → TOKEN_DIR/{user_id}.json saved
   └─ subsequent runs → token loaded silently, refreshed if expired
        │
        ▼
① Drive Agent  (gemini-3.1-flash-lite-preview, thinking=low, budget=512)
   └─ function-calling: search_drive_folder → list_video_files
   └─ returns: file_id, name, duration, resolution, GPS, camera, created_time
        │
        ▼
② Build Descriptions from Drive metadata
   └─ no file download required
   └─ per-video object analysis → added in a later phase
        │
        ▼
③ Storyboard Generator  (gemini-2.5-flash, thinking=medium, budget=8192)
   └─ ordered scenes with captions, transitions, emotion tags
   └─ Python-calculated total duration (no LLM math)
        │
        ▼
   Storyboard JSON
```

---

## Prerequisites

### 1. GCP Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create a project → Enable **Google Drive API**
3. OAuth consent screen → **Web application**
4. Add Authorized redirect URI: `http://localhost:8765/auth/drive/callback`
5. Download `client_secret.json` → place it anywhere (path passed via env var)

### 2. Start Infrastructure

```bash
cd /Users/dalssung/Desktop/project/TripVlog_gogle
docker compose up -d
```

### 3. Install Dependencies

```bash
# AI Service
cd ai-service && pip install -r requirements.txt

# macOS optional (for future object analysis phase)
brew install ffmpeg
```

---

## Run the Demo

### Required env vars

| Variable | Description |
|----------|-------------|
| `GOOGLE_CLIENT_SECRET_FILE` | Path to `client_secret.json` from GCP Console |
| `DRIVE_FOLDER_NAME` | Name of the Google Drive folder containing videos |
| `GEMINI_API_KEY` | Required for Drive Agent + storyboard generation |

### Optional env vars

| Variable | Default | Description |
|----------|---------|-------------|
| `USER_ID` | `demo-user` | User identifier — token stored as `TOKEN_DIR/{USER_ID}.json` |
| `TOKEN_DIR` | `~/.tripvlog/tokens` | Directory for per-user OAuth token files |
| `MOOD` | `"A cinematic travel story…"` | Mood / atmosphere for the storyboard |
| `PROJECT_ID` | `poc-phase1-001` | Project identifier in the output JSON |

### Basic run

```bash
cd PoC/phase1

GOOGLE_CLIENT_SECRET_FILE=~/client_secret.json \
DRIVE_FOLDER_NAME="My Trip Videos" \
GEMINI_API_KEY=your-key \
python demo.py
```

### Multi-user example

```bash
# Authorize and run as alice
USER_ID=alice \
GOOGLE_CLIENT_SECRET_FILE=~/client_secret.json \
DRIVE_FOLDER_NAME="Alice Trip 2025" \
GEMINI_API_KEY=your-key \
python demo.py

# Authorize and run as bob (separate token stored automatically)
USER_ID=bob \
GOOGLE_CLIENT_SECRET_FILE=~/client_secret.json \
DRIVE_FOLDER_NAME="Bob Road Trip" \
GEMINI_API_KEY=your-key \
python demo.py
```

### First run — OAuth flow

On first run for a `USER_ID`, a temporary local server starts on port 8765 to handle the callback:

```
[auth] No token found for user 'alice'.
[auth] Opening browser for Google Drive authorization...
[auth] If browser doesn't open, visit:
  https://accounts.google.com/o/oauth2/auth?...

  ← browser opens, user consents →

[auth] Token saved → ~/.tripvlog/tokens/alice.json
```

Subsequent runs skip the browser entirely and load the saved token silently.

---

## API Endpoints (when running as a server)

If you run `uvicorn api:app --port 8000` instead of the demo script, the OAuth flow uses the server endpoints:

```bash
# Step 1 — get consent URL
curl "http://localhost:8000/auth/drive/url?user_id=alice"
# → { "auth_url": "https://accounts.google.com/...", "user_id": "alice" }

# Step 2 — open auth_url in browser → Google redirects to /auth/drive/callback
# → token saved automatically

# Step 3 — run pipeline
curl -X POST http://localhost:8000/pipeline \
  -H "Content-Type: application/json" \
  -d '{
    "project_id": "proj-001",
    "user_id": "alice",
    "folder_name": "Alice Trip 2025",
    "mood": "Serene and cinematic, golden hour vibes"
  }'
```

---

## Expected Output

```
════════════════════════════════════════════════════════════════
  TripVlog Phase 01 — PoC Demo
════════════════════════════════════════════════════════════════
  Credentials : /Users/.../client_secret.json
  User ID     : alice
  Folder      : Korea Trip 2025
  Step 1  Drive Agent   : gemini-3.1-flash-lite-preview  (thinking=low,    budget=512)
  Step 2  Descriptions  : Drive metadata only (no download)
  Step 3  Storyboard    : gemini-2.5-flash                (thinking=medium, budget=8192)

════════════════════════════════════════════════════════════════
  Authorization Check
════════════════════════════════════════════════════════════════
  [auth] Token found for 'alice' — authorized.

════════════════════════════════════════════════════════════════
  POST /pipeline
════════════════════════════════════════════════════════════════
  Searching Drive for folder: 'Korea Trip 2025'...

  ... storyboard JSON ...

════════════════════════════════════════════════════════════════
  Storyboard Summary
════════════════════════════════════════════════════════════════
  Project ID        : poc-phase1-001
  User ID           : alice
  Total duration    : 28.5s
  Scenes            : 5
  ...
  ID           Type           Dur    Trans       Caption
  ──────────── ────────────── ─────  ──────────  ──────────────────────────────────────────────────
  scene_000    establishing    5.0s  dissolve    Han River at golden hour — Seoul glows at dusk
  scene_001    action          3.0s  cut         Weaving through the busy streets of Myeongdong
  ...
```

---

## Run All Tests

```bash
cd /Users/dalssung/Desktop/project/TripVlog_gogle
bash scripts/run-tests.sh
```

Runs Backend (Jest, 5 test files) + AI Service (pytest, 77 tests) with coverage reports.
