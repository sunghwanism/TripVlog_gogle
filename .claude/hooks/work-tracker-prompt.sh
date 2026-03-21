#!/bin/bash
# work-tracker-prompt.sh - UserPromptSubmit Hook
# Record session start/prompt events to buffer.jsonl
# [C2 fix] remove eval → handle logic in Python (prevent injection)
# exit 0 required (do not interrupt session)

INPUT=$(cat)
BUFFER="$HOME/.claude/work-log/buffer.jsonl"
SESSIONS_DIR="$HOME/.claude/work-log/.sessions"

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

cwd = d.get('cwd', '')
prompt = d.get('prompt', '')[:500].replace('\n', ' ')
hostname = socket.gethostname().split('.')[0]
kst = timezone(timedelta(hours=9))
ts = datetime.now(kst).isoformat()

sessions_dir = os.path.expanduser('~/.claude/work-log/.sessions')
os.makedirs(sessions_dir, exist_ok=True)
marker = os.path.join(sessions_dir, sid)
buffer = os.path.expanduser('~/.claude/work-log/buffer.jsonl')

if not os.path.exists(marker):
    project_name = os.path.basename(cwd) if cwd else ''
    open(marker, 'w').close()
    rec = {
        'event': 'session_start',
        'session_id': sid,
        'hostname': hostname,
        'cwd': cwd,
        'project_name': project_name,
        'prompt': prompt,
        'ts': ts
    }
else:
    rec = {
        'event': 'prompt',
        'session_id': sid,
        'hostname': hostname,
        'prompt': prompt,
        'ts': ts
    }

with open(buffer, 'a') as f:
    f.write(json.dumps(rec, ensure_ascii=False) + '\n')
" 2>/dev/null

exit 0
