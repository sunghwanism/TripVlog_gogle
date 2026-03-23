#!/usr/bin/env python3
"""
Phase 01 PoC Demo — TripVlog AI Pipeline v2
============================================
Flow:
  1. Drive Agent  (gemini-3.1-flash-lite-preview, thinking=low)
     → function-calling agent searches Drive folder, lists video files
     → returns: file_id, name, duration, resolution, GPS, camera, created_time

  2. Build descriptions from Drive metadata
     (per-video object analysis will be added in a later phase)

  3. Storyboard generator  (gemini-2.5-flash, thinking=medium)
     → ordered storyboard JSON with scenes, captions, transitions

Required env vars:
    GOOGLE_CLIENT_SECRET_FILE   Path to client_secret.json from GCP Console
                                (default: <repo-root>/client_secret.json)
    DRIVE_FOLDER_NAME           Name of the Drive folder containing videos
    GEMINI_API_KEY              Required for Drive Agent + storyboard generation

Optional env vars:
    MOOD        Desired mood / atmosphere for the storyboard
                (default: "A cinematic travel story capturing the journey and landscapes")
    PROJECT_ID  Project identifier (default: poc-phase1-001)

Usage:
    cd PoC/phase1
    GOOGLE_CLIENT_SECRET_FILE=~/client_secret.json \\
    DRIVE_FOLDER_NAME="My Trip Videos" \\
    GEMINI_API_KEY=your-key \\
    python demo.py
"""

import asyncio
import json
import os
import sys
from pathlib import Path

# Resolve ai-service/src so bare imports (drive.agent, gemini.*, api) work
_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "ai-service" / "src"))


# ── Output helpers ────────────────────────────────────────────────────────────

def _section(title: str) -> None:
    print(f"\n{'═' * 64}")
    print(f"  {title}")
    print("═" * 64)


def _json(data: dict) -> None:
    print(json.dumps(data, indent=2, ensure_ascii=False))


# ── Config validation ─────────────────────────────────────────────────────────

def _load_config() -> dict:
    secret_env = os.environ.get("GOOGLE_CLIENT_SECRET_FILE")
    client_secret = (
        Path(secret_env).expanduser().resolve()
        if secret_env
        else (_REPO_ROOT / "client_secret.json").resolve()
    )

    folder_name = os.environ.get("DRIVE_FOLDER_NAME", "").strip()
    gemini_key  = os.environ.get("GEMINI_API_KEY", "").strip()
    mood        = os.environ.get(
        "MOOD",
        "A cinematic travel story capturing the journey and landscapes.",
    )
    project_id  = os.environ.get("PROJECT_ID", "poc-phase1-001")

    errors = []
    if not client_secret.exists():
        errors.append(
            f"client_secret.json not found at: {client_secret}\n"
            "  → Set GOOGLE_CLIENT_SECRET_FILE=<path>"
        )
    if not folder_name:
        errors.append(
            "DRIVE_FOLDER_NAME is not set.\n"
            '  → Example: DRIVE_FOLDER_NAME="My Trip Videos"'
        )
    if not gemini_key:
        errors.append(
            "GEMINI_API_KEY is not set.\n"
            "  → Required for Drive Agent and storyboard generation."
        )

    if errors:
        print("\n[error] Missing required configuration:")
        for e in errors:
            print(f"  • {e}")
        sys.exit(1)

    return {
        "client_secret": client_secret,
        "folder_name": folder_name,
        "gemini_key": gemini_key,
        "mood": mood,
        "project_id": project_id,
    }


# ── Main demo ─────────────────────────────────────────────────────────────────

def run_demo() -> None:
    from api import app
    from httpx import AsyncClient, ASGITransport

    cfg = _load_config()

    _section("TripVlog Phase 01 — PoC Demo")
    print(f"  Credentials : {cfg['client_secret']}")
    print(f"  Folder      : {cfg['folder_name']}")
    print(f"  Project     : {cfg['project_id']}")
    print(f"  Mood        : {cfg['mood'][:72]}{'…' if len(cfg['mood']) > 72 else ''}")
    print()
    print(f"  Step 1  Drive Agent   : gemini-3.1-flash-lite-preview  (thinking=low,    budget=512)")
    print(f"  Step 2  Descriptions  : Drive metadata only (no download)")
    print(f"  Step 3  Storyboard    : gemini-2.5-flash                (thinking=medium, budget=8192)")

    async def _run() -> None:
        transport = ASGITransport(app=app)  # type: ignore[arg-type]
        async with AsyncClient(transport=transport, base_url="http://test") as client:

            # ── POST /pipeline ─────────────────────────────────────────────────
            _section("POST /pipeline")
            print(f"  Searching Drive for folder: '{cfg['folder_name']}'...")
            print("  (browser will open on first run for Google OAuth consent)")

            r = await client.post(
                "/pipeline",
                json={
                    "project_id": cfg["project_id"],
                    "folder_name": cfg["folder_name"],
                    "mood": cfg["mood"],
                },
                timeout=600.0,
            )

            if r.status_code != 200:
                print(f"\n[error] /pipeline returned {r.status_code}:")
                try:
                    _json(r.json())
                except Exception:
                    print(r.text)
                sys.exit(1)

            storyboard = r.json()

            # ── Raw storyboard JSON ────────────────────────────────────────────
            _section("Storyboard JSON")
            _json(storyboard)

            # ── Video metadata table ───────────────────────────────────────────
            _section("Video Files (from Drive Agent)")
            scenes = storyboard.get("scenes", [])
            if scenes:
                print(f"  {'file_id':<28}  {'name':<35}  {'dur':>6}  GPS")
                print(f"  {'─'*28}  {'─'*35}  {'─'*6}  {'─'*24}")
                for s in scenes:
                    fid = (s["source_files"] or ["—"])[0]
                    loc = s.get("location", {})
                    lat = loc.get("lat")
                    lng = loc.get("lng")
                    gps_str = f"{lat:.4f}, {lng:.4f}" if lat else "—"
                    dur_str = f"{s['duration_seconds']:.1f}s"
                    # file name not stored in storyboard scenes, show file_id only
                    print(f"  {fid:<28}  {'(see JSON above)':<35}  {dur_str:>6}  {gps_str}")

            # ── Summary table ──────────────────────────────────────────────────
            _section("Storyboard Summary")
            meta = storyboard["metadata"]
            print(f"  Project ID        : {storyboard['project_id']}")
            print(f"  Total duration    : {storyboard['total_duration_seconds']}s")
            print(f"  Scenes            : {len(scenes)}")
            print(f"  Videos analyzed   : {meta['total_media_items']}")
            print(f"  Failed items      : {meta['failed_items']}")
            print(f"  Location clusters : {meta['location_clusters']}")
            print(f"  Gemini model      : {meta['gemini_model']}")
            print(f"  Created at        : {meta['created_at']}")
            print()
            print(f"  {'ID':<12} {'Type':<14} {'Dur':>5}  {'Trans':<10}  Caption")
            print(f"  {'─'*12} {'─'*14} {'─'*5}  {'─'*10}  {'─'*50}")
            for s in scenes:
                caption = s["caption"]["text"][:50]
                print(
                    f"  {s['scene_id']:<12} {s['scene_type']:<14}"
                    f" {s['duration_seconds']:>4.1f}s"
                    f"  {s['transition_type']:<10}"
                    f"  {caption}"
                )
            print()

    asyncio.run(_run())


if __name__ == "__main__":
    run_demo()
