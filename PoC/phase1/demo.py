#!/usr/bin/env python3
"""
Phase 01 PoC Demo — TripVlog AI Pipeline v2
============================================
Flow:
  1. Drive Agent  (gemini-3.1-flash-lite-preview, thinking=low)
     → function-calling agent searches Drive folder, lists video files

  2. Build descriptions from Drive metadata
     (per-video object analysis will be added in a later phase)

  3. Storyboard generator  (gemini-2.5-flash, thinking=medium)
     → ordered storyboard JSON

Auth: Web OAuth (multi-user).
  - First run for a user: opens browser → Google consent → token saved to TOKEN_DIR/{user_id}.json
  - Subsequent runs: token loaded silently, refreshed if expired.

Required env vars:
    GOOGLE_CLIENT_SECRET_FILE   Path to client_secret.json from GCP Console
                                (default: <repo-root>/client_secret.json)
    DRIVE_FOLDER_NAME           Name of the Drive folder containing videos
    GEMINI_API_KEY              Required for Drive Agent + storyboard generation
    USER_ID                     Identifier for this user (default: demo-user)

Optional env vars:
    TOKEN_DIR     Token storage directory (default: ~/.tripvlog/tokens)
    MOOD          Desired mood / atmosphere for the storyboard
    PROJECT_ID    Project identifier (default: poc-phase1-001)

Usage:
    cd PoC/phase1
    GOOGLE_CLIENT_SECRET_FILE=~/client_secret.json \\
    DRIVE_FOLDER_NAME="My Trip Videos" \\
    GEMINI_API_KEY=your-key \\
    USER_ID=alice \\
    python demo.py
"""

import asyncio
import json
import os
import sys
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

# Resolve ai-service/src so bare imports work
_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "ai-service" / "src"))


# ── Output helpers ────────────────────────────────────────────────────────────

def _section(title: str) -> None:
    print(f"\n{'═' * 64}")
    print(f"  {title}")
    print("═" * 64)


def _json(data: dict) -> None:
    print(json.dumps(data, indent=2, ensure_ascii=False))


# ── Config ────────────────────────────────────────────────────────────────────

def _load_config() -> dict:
    secret_env = os.environ.get("GOOGLE_CLIENT_SECRET_FILE")
    client_secret = (
        Path(secret_env).expanduser().resolve()
        if secret_env
        else (_REPO_ROOT / "client_secret.json").resolve()
    )

    folder_name = os.environ.get("DRIVE_FOLDER_NAME", "").strip()
    gemini_key  = os.environ.get("GEMINI_API_KEY", "").strip()
    user_id     = os.environ.get("USER_ID", "demo-user").strip()
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
        "user_id": user_id,
        "mood": mood,
        "project_id": project_id,
    }


# ── Demo OAuth helper (web flow via temporary local server) ───────────────────

def _ensure_authorized(user_id: str, client_secret: Path, callback_port: int = 8765) -> None:
    """
    Ensures user_id has a valid token in TOKEN_DIR.
    If not, runs a one-shot local HTTP server to handle the web OAuth callback.
    This mirrors what the real server's /auth/drive/url + /auth/drive/callback do.
    """
    from drive.agent import _get_token_path
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import Flow

    token_path = _get_token_path(user_id)

    # Check existing token
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path))
        if creds.valid:
            print(f"  [auth] Token found for '{user_id}' — authorized.")
            return
        if creds.expired and creds.refresh_token:
            from google.auth.transport.requests import Request
            creds.refresh(Request())
            token_path.write_text(creds.to_json())
            print(f"  [auth] Token refreshed for '{user_id}'.")
            return

    # No valid token — run web OAuth flow with a temporary callback server
    redirect_uri = f"http://localhost:{callback_port}/auth/drive/callback"

    flow = Flow.from_client_secrets_file(
        str(client_secret),
        scopes=["https://www.googleapis.com/auth/drive.readonly"],
        redirect_uri=redirect_uri,
    )
    auth_url, _ = flow.authorization_url(
        access_type="offline",
        prompt="consent",
    )

    received: dict = {}

    class _CallbackHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            params = parse_qs(urlparse(self.path).query)
            received["code"] = (params.get("code") or [None])[0]
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(
                b"<h2>Authorization successful!</h2>"
                b"<p>You can close this tab and return to the terminal.</p>"
            )

        def log_message(self, *args):
            pass  # suppress server access logs

    print(f"\n  [auth] No token found for user '{user_id}'.")
    print(f"  [auth] Opening browser for Google Drive authorization...")
    print(f"  [auth] If browser doesn't open, visit:\n  {auth_url}\n")
    webbrowser.open(auth_url)

    server = HTTPServer(("localhost", callback_port), _CallbackHandler)
    server.timeout = 120
    server.handle_request()  # blocks until callback arrives

    code = received.get("code")
    if not code:
        print("\n[error] Authorization timed out or was denied.")
        sys.exit(1)

    flow.fetch_token(code=code)

    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(flow.credentials.to_json())
    print(f"  [auth] Token saved → {token_path}")


# ── Main demo ─────────────────────────────────────────────────────────────────

def run_demo() -> None:
    from api import app
    from httpx import AsyncClient, ASGITransport

    cfg = _load_config()

    _section("TripVlog Phase 01 — PoC Demo")
    print(f"  Credentials : {cfg['client_secret']}")
    print(f"  User ID     : {cfg['user_id']}")
    print(f"  Folder      : {cfg['folder_name']}")
    print(f"  Project     : {cfg['project_id']}")
    print(f"  Mood        : {cfg['mood'][:72]}{'…' if len(cfg['mood']) > 72 else ''}")
    print()
    print(f"  Step 1  Drive Agent   : gemini-3.1-flash-lite-preview  (thinking=low,    budget=512)")
    print(f"  Step 2  Descriptions  : Drive metadata only (no download)")
    print(f"  Step 3  Storyboard    : gemini-2.5-flash                (thinking=medium, budget=8192)")

    # Ensure this user is authorized before hitting the pipeline
    _section("Authorization Check")
    _ensure_authorized(cfg["user_id"], cfg["client_secret"])

    async def _run() -> None:
        transport = ASGITransport(app=app)  # type: ignore[arg-type]
        async with AsyncClient(transport=transport, base_url="http://test") as client:

            _section("POST /pipeline")
            print(f"  Searching Drive for folder: '{cfg['folder_name']}'...")

            r = await client.post(
                "/pipeline",
                json={
                    "project_id": cfg["project_id"],
                    "user_id": cfg["user_id"],
                    "folder_name": cfg["folder_name"],
                    "mood": cfg["mood"],
                },
                timeout=600.0,
            )

            if r.status_code == 401:
                detail = r.json().get("detail", {})
                print(f"\n[error] Not authorized: {detail.get('message', r.text)}")
                sys.exit(1)

            if r.status_code != 200:
                print(f"\n[error] /pipeline returned {r.status_code}:")
                try:
                    _json(r.json())
                except Exception:
                    print(r.text)
                sys.exit(1)

            storyboard = r.json()

            _section("Storyboard JSON")
            _json(storyboard)

            _section("Storyboard Summary")
            meta = storyboard["metadata"]
            scenes = storyboard.get("scenes", [])
            print(f"  Project ID        : {storyboard['project_id']}")
            print(f"  User ID           : {cfg['user_id']}")
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
