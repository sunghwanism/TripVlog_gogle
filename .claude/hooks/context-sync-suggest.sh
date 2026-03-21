#!/bin/bash
# context-sync-suggest.sh - SessionStart Hook
# Suggest /sync if enough time passed since the last session end
# Coexists independently with OMC session-start.mjs and project-memory-session.mjs
# exit 0 required

INPUT=$(cat)

MSG=$(echo "$INPUT" | python3 -c "
import sys, json, os, time
from datetime import datetime, timezone, timedelta

try:
    d = json.load(sys.stdin)
except:
    sys.exit(0)

sid = d.get('session_id', '')
if not sid:
    sys.exit(0)

# Find last session_end in buffer.jsonl
work_log = os.path.expanduser('~/.claude/work-log/buffer.jsonl')
if not os.path.exists(work_log):
    sys.exit(0)

last_end = None
try:
    with open(work_log, 'r') as f:
        for line in f:
            try:
                ev = json.loads(line.strip())
                if ev.get('event') == 'session_end':
                    last_end = ev.get('ts', '')
            except:
                continue
except:
    sys.exit(0)

if not last_end:
    sys.exit(0)

# Suggest if 4+ hours have passed
try:
    last_dt = datetime.fromisoformat(last_end)
    now = datetime.now(timezone(timedelta(hours=9)))
    gap_hours = (now - last_dt).total_seconds() / 3600
    if gap_hours < 4:
        sys.exit(0)
except:
    sys.exit(0)

gap_display = f'{int(gap_hours)} hours' if gap_hours < 48 else f'{int(gap_hours/24)} days'
print(f'[Context Sync] since the last session {gap_display} elapsed. Use /sync to review missed activity.')
" 2>/dev/null)

if [[ -n "$MSG" ]]; then
    echo "$MSG" >&2
fi

# First-time user detection: if onboarding marker is missing, suggest /guide
if [[ ! -f "$HOME/.claude/.forge-onboarded" ]]; then
    echo "[Claude Forge] First time here? Start with /guide." >&2
fi

exit 0
