#!/bin/bash
# work-tracker-stop.sh - Stop Hook
# Record session end event to buffer.jsonl and trigger sync
# [C2 fix] remove eval → handle logic in Python (prevent injection)
# exit 0 required (do not interrupt session)

INPUT=$(cat)
SYNC_SCRIPT="$HOME/.claude/scripts/work-tracker-sync.sh"

echo "$INPUT" | python3 -c "
import sys, json, os, socket
from datetime import datetime, timezone, timedelta

try:
    d = json.load(sys.stdin)
except:
    sys.exit(0)

sid = d.get('session_id', '')
if not sid:
    sys.exit(0)

hostname = socket.gethostname().split('.')[0]
kst = timezone(timedelta(hours=9))
ts = datetime.now(kst).isoformat()

rec = {
    'event': 'session_end',
    'session_id': sid,
    'hostname': hostname,
    'ts': ts
}

buffer = os.path.expanduser('~/.claude/work-log/buffer.jsonl')
with open(buffer, 'a') as f:
    f.write(json.dumps(rec, ensure_ascii=False) + '\n')

# Delete session marker
sessions_dir = os.path.expanduser('~/.claude/work-log/.sessions')
marker = os.path.join(sessions_dir, sid)
try:
    os.remove(marker)
except:
    pass
" 2>/dev/null

# Run sync script in background if present
if [[ -x "$SYNC_SCRIPT" ]]; then
    "$SYNC_SCRIPT" &
fi

exit 0
