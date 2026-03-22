#!/usr/bin/env python3
"""
Phase 01 PoC Demo — TripVlog AI Pipeline
==========================================
Demonstrates: GPS clustering → Gemini analysis → storyboard assembly

No Google Drive, PostgreSQL, Redis, or real media files required.

Usage (mock Gemini — no API key needed):
    cd ai-service
    python demo.py

Usage (real Gemini 1.5 Pro):
    cd ai-service
    GEMINI_API_KEY=your-key python demo.py
"""

import asyncio
import json
import os
import sys
from pathlib import Path
from unittest.mock import patch

# Fix import path: api.py uses bare imports (e.g. "from clustering...")
# Adding src/ to sys.path makes them resolve without modifying production code.
sys.path.insert(0, str(Path(__file__).parent / "src"))

# ── Sample data ───────────────────────────────────────────────────────────────
# 3 photos (2 in Seoul cluster, 1 in Busan) + 2 videos (no GPS)

SAMPLE_FILES = [
    {"file_path": "/demo/seoul_01.jpg",  "drive_file_id": "gdrive-001", "mime_type": "image/jpeg"},
    {"file_path": "/demo/seoul_02.jpg",  "drive_file_id": "gdrive-002", "mime_type": "image/jpeg"},
    {"file_path": "/demo/busan_01.jpg",  "drive_file_id": "gdrive-003", "mime_type": "image/jpeg"},
    {"file_path": "/demo/clip_01.mp4",   "drive_file_id": "gdrive-004", "mime_type": "video/mp4"},
    {"file_path": "/demo/clip_02.mp4",   "drive_file_id": "gdrive-005", "mime_type": "video/mp4"},
]

SAMPLE_MEDIA_ITEMS = [
    {
        "file_id": "gdrive-001",
        "file_type": "image/jpeg",
        "metadata": {"gps_lat": 37.5665, "gps_lng": 126.9780},
    },
    {
        "file_id": "gdrive-002",
        "file_type": "image/jpeg",
        "metadata": {"gps_lat": 37.5700, "gps_lng": 126.9800},
    },
    {
        "file_id": "gdrive-003",
        "file_type": "image/jpeg",
        "metadata": {"gps_lat": 35.1796, "gps_lng": 129.0756},
    },
    {
        "file_id": "gdrive-004",
        "file_type": "video/mp4",
        "duration_seconds": 12.5,
        "resolution": {"width": 1920, "height": 1080},
    },
    {
        "file_id": "gdrive-005",
        "file_type": "video/mp4",
        "duration_seconds": 8.3,
        "resolution": {"width": 1920, "height": 1080},
    },
]

CONCEPT_PROMPT = (
    "A cinematic summer road trip through South Korea — "
    "from the neon streets of Seoul to the coastal beaches of Busan, "
    "capturing the contrast between urban energy and natural serenity."
)

# ── Mock Gemini (used when GEMINI_API_KEY is absent) ──────────────────────────

def _mock_analyze_media_batch(batch):
    """Deterministic SceneAnalysis objects — no API call."""
    from gemini.validator import SceneAnalysis

    templates = [
        {
            "scene_id": f"scene_{i:03d}",
            "scene_type": stype,
            "emotion_tags": tags,
            "quality_score": score,
            "suggested_duration_seconds": dur,
            "transition_type": trans,
            "caption_suggestion": caption,
        }
        for i, (stype, tags, score, dur, trans, caption) in enumerate([
            (
                "establishing", ["serene", "adventurous"], 8.5, 5.0, "dissolve",
                "Han River at golden hour — Seoul stretches endlessly beyond the bridge",
            ),
            (
                "action", ["energetic", "joyful"], 7.8, 3.0, "cut",
                "Weaving through Myeongdong market, colours and sounds collide",
            ),
            (
                "establishing", ["dramatic"], 9.1, 6.0, "dissolve",
                "Busan coastline — the city meets the sea at sunrise",
            ),
            (
                "transition", ["serene"], 6.5, 1.5, "fade",
                "KTX express blur — Seoul to Busan in 2.5 hours",
            ),
            (
                "climax", ["adventurous", "joyful"], 9.4, 7.0, "cut",
                "Haeundae Beach — waves crash as the road trip reaches its peak",
            ),
        ])
    ]
    count = len(batch.media_items)
    return [SceneAnalysis.model_validate(t) for t in templates[:count]]


# ── Mock extract_metadata (avoids needing real files on disk) ─────────────────

_EXIF_MAP = {
    "/demo/seoul_01.jpg": {"gps_lat": 37.5665, "gps_lng": 126.9780, "width": 4032, "height": 3024, "camera_info": "Apple iPhone 16 Pro"},
    "/demo/seoul_02.jpg": {"gps_lat": 37.5700, "gps_lng": 126.9800, "width": 4032, "height": 3024, "camera_info": "Apple iPhone 16 Pro"},
    "/demo/busan_01.jpg": {"gps_lat": 35.1796, "gps_lng": 129.0756, "width": 4032, "height": 3024, "camera_info": "Sony A7 IV"},
    "/demo/clip_01.mp4":  {"duration_ms": 12500, "width": 1920, "height": 1080, "codec": "h264", "fps": 30.0},
    "/demo/clip_02.mp4":  {"duration_ms": 8300,  "width": 1920, "height": 1080, "codec": "h264", "fps": 60.0},
}

def _mock_extract(file_path: str, mime_type: str) -> dict:
    return _EXIF_MAP.get(file_path, {})

def _mock_geocode(lat: float, lng: float) -> str:
    return "Seoul, South Korea" if lat > 36 else "Busan, South Korea"


# ── Output helpers ────────────────────────────────────────────────────────────

def _section(title: str) -> None:
    print(f"\n{'═' * 60}")
    print(f"  {title}")
    print('═' * 60)

def _json(data: dict) -> None:
    print(json.dumps(data, indent=2, ensure_ascii=False))


# ── Main demo ─────────────────────────────────────────────────────────────────

def run_demo() -> None:
    from api import app
    from httpx import AsyncClient, ASGITransport

    gemini_key = os.environ.get("GEMINI_API_KEY")
    mock_mode = not bool(gemini_key)

    _section("TripVlog Phase 01 — AI Pipeline Demo")
    print(f"  Mode     : {'MOCK  (set GEMINI_API_KEY for live Gemini)' if mock_mode else 'LIVE  (Gemini 1.5 Pro)'}")
    print(f"  Items    : {len(SAMPLE_FILES)} media files (3 photos · 2 videos)")
    print(f"  Concept  : {CONCEPT_PROMPT[:75]}…")

    async def _run() -> None:
        transport = ASGITransport(app=app)  # type: ignore[arg-type]
        async with AsyncClient(transport=transport, base_url="http://test") as client:

            # ── Step 1: POST /analyze ──────────────────────────────────────────
            _section("Step 1 — POST /analyze  (EXIF extraction + geocoding)")

            with (
                patch("api.extract_metadata", side_effect=_mock_extract),
                patch("api.reverse_geocode",  side_effect=_mock_geocode),
            ):
                r = await client.post("/analyze", json={
                    "project_id": "demo-project-001",
                    "files": SAMPLE_FILES,
                })

            assert r.status_code == 200, f"/analyze failed ({r.status_code}): {r.text}"
            analyze_data = r.json()
            _json(analyze_data)

            # ── Step 2: POST /storyboard ───────────────────────────────────────
            _section("Step 2 — POST /storyboard  (GPS cluster + Gemini + assembly)")

            payload = {
                "project_id": "demo-project-001",
                "concept_prompt": CONCEPT_PROMPT,
                "media_items": SAMPLE_MEDIA_ITEMS,
            }

            if mock_mode:
                with patch("api.analyze_media_batch", side_effect=_mock_analyze_media_batch):
                    r = await client.post("/storyboard", json=payload)
            else:
                r = await client.post("/storyboard", json=payload)

            assert r.status_code == 200, f"/storyboard failed ({r.status_code}): {r.text}"
            storyboard = r.json()
            _json(storyboard)

            # ── Summary ────────────────────────────────────────────────────────
            _section("Summary")
            meta = storyboard["metadata"]
            print(f"  Project ID        : {storyboard['project_id']}")
            print(f"  Total duration    : {storyboard['total_duration_seconds']}s")
            print(f"  Scenes            : {len(storyboard['scenes'])}")
            print(f"  Location clusters : {meta['location_clusters']}")
            print(f"  Gemini model      : {meta['gemini_model']}")
            print(f"  Failed items      : {meta['failed_items']}")
            print()
            print(f"  {'ID':<12} {'Type':<14} {'Dur':>5}  {'Score':>5}  Caption")
            print(f"  {'─'*12} {'─'*14} {'─'*5}  {'─'*5}  {'─'*45}")
            for s in storyboard["scenes"]:
                caption_short = s["caption"]["text"][:45]
                print(
                    f"  {s['scene_id']:<12} {s['scene_type']:<14}"
                    f" {s['duration_seconds']:>4.1f}s"
                    f"  {s['quality_score']:>5.1f}"
                    f"  {caption_short}"
                )
            print()

    asyncio.run(_run())


if __name__ == "__main__":
    run_demo()
