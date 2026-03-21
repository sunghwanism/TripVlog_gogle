#!/bin/bash
# work-tracker-tool.sh - PostToolUse Hook
# Record tracked tool usage to buffer.jsonl
# [C2 fix] remove eval → handle logic in Python (prevent injection)
# exit 0 required (do not interrupt session)

INPUT=$(cat)

echo "$INPUT" | python3 -c "
import sys, json, os, socket
from datetime import datetime, timezone, timedelta

try:
    d = json.load(sys.stdin)
except:
    sys.exit(0)

sid = d.get('session_id', '')
tool = d.get('tool_name', '')
if not sid or not tool:
    sys.exit(0)

TRACKED = {
    'Bash': 'bash',
    'Write': 'write', 'Edit': 'write', 'NotebookEdit': 'write',
    'Task': 'agent', 'SendMessage': 'agent',
    'TaskCreate': 'agent', 'TaskUpdate': 'agent',
    'EnterPlanMode': 'plan', 'ExitPlanMode': 'plan',
    'Skill': 'interaction',
}

is_mcp = False
mcp_server = None
category = ''

if tool in TRACKED:
    category = TRACKED[tool]
elif tool.startswith('mcp__'):
    is_mcp = True
    parts = tool.split('__')
    mcp_server = parts[1] if len(parts) > 1 else None
    category = 'mcp'
else:
    sys.exit(0)

hostname = socket.gethostname().split('.')[0]
kst = timezone(timedelta(hours=9))
ts = datetime.now(kst).isoformat()

rec = {
    'event': 'tool_use',
    'session_id': sid,
    'hostname': hostname,
    'tool_name': tool,
    'tool_category': category,
    'is_mcp': is_mcp,
    'mcp_server': mcp_server,
    'ts': ts
}

buffer = os.path.expanduser('~/.claude/work-log/buffer.jsonl')
with open(buffer, 'a') as f:
    f.write(json.dumps(rec, ensure_ascii=False) + '\n')
" 2>/dev/null

exit 0
