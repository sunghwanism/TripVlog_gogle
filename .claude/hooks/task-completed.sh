#!/bin/bash
# Task Completed Guard - TaskCompleted Hook
# Log on task completion
#
# Hook trigger: TaskCompleted
# Exit codes: 0 = approve (allow completion), 2 = block (deny completion, feedback to stderr)

# Read hook input JSON from stdin
INPUT=$(cat)

echo "$INPUT" | python3 -c "
import sys, json

try:
    data = json.load(sys.stdin)
except:
    sys.exit(0)

ti = data.get('tool_input', {})
task_id = ti.get('task_id', 'unknown')
subject = ti.get('task_subject', ti.get('subject', 'unknown'))
teammate = ti.get('teammate_name', data.get('teammate_name', 'unknown'))
team = ti.get('team_name', data.get('team_name', 'unknown'))

print(f'[task-completed] Task #{task_id} \"{subject}\" completed by {teammate} (team: {team})', file=sys.stderr)
" 2>/dev/null

exit 0
