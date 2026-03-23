# Phase 1: Data & Analysis Demo (PoC)

## Pipeline Overview

```
DRIVE_FOLDER_NAME + MOOD + GEMINI_API_KEY
        │
        ▼
① Drive Agent  (gemini-3.1-flash-lite-preview, thinking=low)
   └─ function-calling: search_drive_folder → list_video_files
   └─ returns: file_id, name, duration, resolution, GPS, camera, created_time
        │
        ▼
② Build Descriptions from Drive metadata
   └─ no file download required
   └─ per-video object analysis → added in a later phase
        │
        ▼
③ Storyboard Generator  (gemini-2.5-flash, thinking=medium)
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
3. OAuth consent screen → Desktop app
4. Download `client_secret.json` → place it anywhere (path passed via env var)

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

```bash
cd PoC/phase1

GOOGLE_CLIENT_SECRET_FILE=~/client_secret.json \
DRIVE_FOLDER_NAME="My Trip Videos" \
GEMINI_API_KEY=your-key \
python demo.py
```

**First run:** a browser window opens for Google OAuth consent → `token.json` is saved next to `client_secret.json` and reused on subsequent runs.

### Optional env vars

| Variable | Default | Description |
|----------|---------|-------------|
| `MOOD` | `"A cinematic travel story…"` | Mood / atmosphere for the storyboard |
| `PROJECT_ID` | `poc-phase1-001` | Project identifier in the output JSON |

### Example

```bash
GOOGLE_CLIENT_SECRET_FILE=~/client_secret.json \
DRIVE_FOLDER_NAME="Korea Trip 2025" \
GEMINI_API_KEY=your-key \
MOOD="Serene and cinematic, golden hour vibes along the Korean coast" \
python demo.py
```

---

## Expected Output

```
════════════════════════════════════════════════════════════════
  TripVlog Phase 01 — PoC Demo
════════════════════════════════════════════════════════════════
  Credentials : /Users/.../client_secret.json
  Folder      : Korea Trip 2025
  ...
  Step 1  Drive Agent   : gemini-3.1-flash-lite-preview  (thinking=low,    budget=512)
  Step 2  Descriptions  : Drive metadata only (no download)
  Step 3  Storyboard    : gemini-2.5-flash                (thinking=medium, budget=8192)

════════════════════════════════════════════════════════════════
  POST /pipeline
════════════════════════════════════════════════════════════════
  Searching Drive for folder: 'Korea Trip 2025'...

  ... storyboard JSON ...

════════════════════════════════════════════════════════════════
  Storyboard Summary
════════════════════════════════════════════════════════════════
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
