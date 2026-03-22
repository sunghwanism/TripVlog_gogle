#!/usr/bin/env bash
# Phase 01 Unified Test Runner
# Runs backend (Jest) and AI service (pytest) with coverage reporting.
#
# Usage:
#   bash scripts/run-tests.sh
#
# Prerequisites:
#   Backend:    cd backend && npm install
#   AI service: cd ai-service && pip install -r requirements.txt
#               macOS: brew install exempi ffmpeg  (optional — tests skip gracefully without them)

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EXIT_CODE=0

# ── Backend: Jest ─────────────────────────────────────────────────────────────
echo ""
echo "========================================="
echo "  Backend Tests  (Jest + ts-jest)"
echo "========================================="
cd "$REPO_ROOT/backend"

if ! npm test -- --coverage; then
  echo "❌  Backend tests FAILED"
  EXIT_CODE=1
else
  echo "✅  Backend tests PASSED"
fi

# ── AI Service: pytest ────────────────────────────────────────────────────────
echo ""
echo "========================================="
echo "  AI Service Tests  (pytest --cov=src)"
echo "========================================="
cd "$REPO_ROOT/ai-service"

if ! PYTHONPATH=src pytest --cov=src --cov-report=term-missing -v; then
  echo "❌  AI service tests FAILED"
  EXIT_CODE=1
else
  echo "✅  AI service tests PASSED"
fi

# ── Summary ───────────────────────────────────────────────────────────────────
echo ""
echo "========================================="
if [ "$EXIT_CODE" -eq 0 ]; then
  echo "  ✅  All tests complete — both suites passed."
else
  echo "  ❌  One or more test suites FAILED."
fi
echo "========================================="

exit "$EXIT_CODE"
