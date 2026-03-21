#!/bin/bash
# session-wrap-suggest.sh - Stop Hook
# Suggest /session-wrap the first time the session goes idle after enough activity
# Coexists with OMC persistent-mode.cjs: if OMC blocks, this message is ignored
# exit 0 required

INPUT=$(cat)

echo "$INPUT" | python3 -c "
import sys, json, os

try:
    d = json.load(sys.stdin)
except:
    sys.exit(0)

sid = d.get('session_id', '')
if not sid:
    sys.exit(0)

# Use a marker file to suggest only once per session
marker = f'/tmp/session-wrap-suggested-{sid}'
if os.path.exists(marker):
    sys.exit(0)

# Check session stats
stats_file = os.path.expanduser('~/.claude/.session-stats.json')
try:
    with open(stats_file) as f:
        stats = json.load(f)
    session = stats.get('sessions', {}).get(sid, {})
    total_calls = session.get('total_calls', 0)
except:
    sys.exit(0)

# Suggest only after at least 30 tool calls
if total_calls < 30:
    sys.exit(0)

# Create marker (once per session)
open(marker, 'w').close()

# Print JSON to stdout (Stop hook format)
print(json.dumps({
    'continue': True,
    'systemMessage': '[Session Wrap] Substantial work was done in this session. '
        'Running /session-wrap at the end updates docs, captures learnings, '
        'and organizes follow-up tasks automatically.'
}))
" 2>/dev/null

exit 0
