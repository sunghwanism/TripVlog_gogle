# Phase 1: Data & Analysis Demo (PoC)

## Pipeline Overview

```
USER_ID + DRIVE_FOLDER_NAME + MOOD + GEMINI_API_KEY
        │
        ▼
[Auth]  Web OAuth  (google-auth-oauthlib)
   └─ first run → browser opens → Google consent → TOKEN_DIR/{user_id}.json saved
   └─ subsequent runs → token loaded silently, refreshed if expired
        │
        ▼
① Drive Agent  (gemini-3.1-flash-lite-preview, thinking=low, budget=512)
   └─ function-calling: search_drive_folder → list_video_files
   └─ returns: file_id, name, duration, resolution, GPS, camera, created_time
        │
        ▼
② Analyze each video with Gemini File API  (gemini-3.1-flash-lite-preview, thinking=low, budget=2048)
   └─ downloads video → uploads to Gemini File API → objects, scene, mood, key moments
   └─ Drive metadata (GPS, camera, created_time) merged into description
   └─ files >200 MB are skipped with a fallback description
        │
        ▼
③ Storyboard Generator  (gemini-3.1-flash-lite-preview, thinking=medium, budget=8192)
   └─ ordered scenes with captions, transitions, emotion tags
   └─ Python-calculated total duration (no LLM math)
        │
        ▼
   Storyboard JSON
```

---

## Auth: How It Works

- **Library**: `google-auth-oauthlib` (no custom OAuth logic)
- **Token storage**: local JSON file per user — `TOKEN_DIR/{user_id}.json` (default: `~/.tripvlog/tokens/`)
- **No database required** — tokens persist on disk and are refreshed automatically when expired
- **Callback**: a one-shot local HTTP server on port 8765 handles the Google redirect

---

## Prerequisites

### 1. GCP Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create a project → Enable **Google Drive API**
3. OAuth consent screen → **Web application**
4. Add Authorized redirect URI: `http://localhost:8765/auth/drive/callback`
5. Download `client_secret.json` → place it anywhere (path passed via env var)

### 2. Install Dependencies

```bash
cd ai-service && pip install -r requirements.txt
```

---

## Run the Demo

### Required env vars

| Variable | Description |
|----------|-------------|
| `GOOGLE_CLIENT_SECRET_FILE` | Path to `client_secret.json` from GCP Console |
| `DRIVE_FOLDER_NAME` | Name of the Google Drive folder containing videos |
| `GEMINI_API_KEY` | Required for all Gemini steps |

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

### Custom mood example

```bash
USER_ID=alice \
GOOGLE_CLIENT_SECRET_FILE=~/client_secret.json \
DRIVE_FOLDER_NAME="Vlog_Sample" \
GEMINI_API_KEY=your-key \
MOOD="열심히 자기개발 하는 나" \
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

## Expected Output

```
════════════════════════════════════════════════════════════════
  TripVlog Phase 01 — PoC Demo
════════════════════════════════════════════════════════════════
  Credentials : /Users/.../client_secret.json
  User ID     : alice
  Folder      : Vlog_Sample
  Step 1  Drive Agent   : gemini-3.1-flash-lite-preview  (thinking=None,   budget=None)
  Step 2  Descriptions  : gemini-3.1-flash-lite-preview  (thinking=low,    budget=2048)
  Step 3  Storyboard    : gemini-3.1-flash-lite-preview  (thinking=medium, budget=8192)

════════════════════════════════════════════════════════════════
  Authorization Check
════════════════════════════════════════════════════════════════
  [auth] Token found for 'alice' — authorized.

════════════════════════════════════════════════════════════════
  POST /pipeline
════════════════════════════════════════════════════════════════
  Searching Drive for folder: 'Vlog_Sample'...

  ... storyboard JSON ...

════════════════════════════════════════════════════════════════
  Storyboard Summary
════════════════════════════════════════════════════════════════
  Project ID        : poc-phase1-001
  User ID           : alice
  Total duration    : 23.3s
  Scenes            : 3
  Videos analyzed   : 3
  Failed items      : 0
  Location clusters : 3
  ...
  ID           Type           Dur    Trans       Caption
  ──────────── ────────────── ─────  ──────────  ──────────────────────────────────────────────────
  scene_000    establishing   10.0s  fade        Starting the day with a journey toward growth.
  scene_001    action          6.1s  cut         Setting the stage for deep work.
  scene_002    climax          6.2s  cut         Every small step counts towards my goals.
```

---

## Run All Tests

```bash
cd /Users/dalssung/Desktop/project/TripVlog_gogle
bash scripts/run-tests.sh
```

Runs Backend (Jest, 5 test files) + AI Service (pytest, 77 tests) with coverage reports.
