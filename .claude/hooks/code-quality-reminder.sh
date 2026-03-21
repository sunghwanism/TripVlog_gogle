#!/bin/bash
# code-quality-reminder.sh - PostToolUse Hook (Edit/Write)
# Print a quality reminder to stderr after code edits
# Short message prompting Claude to self-check
# exit 0 required (do not interrupt session)

INPUT=$(cat)

TOOL_NAME=$(echo "$INPUT" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(d.get('tool_name', ''))
except:
    pass
" 2>/dev/null)

if [[ "$TOOL_NAME" != "Edit" && "$TOOL_NAME" != "Write" ]]; then
    exit 0
fi

FILE_PATH=$(echo "$INPUT" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    inp = d.get('tool_input', {})
    print(inp.get('file_path', ''))
except:
    pass
" 2>/dev/null)

# Only target code files (exclude md, txt, json, yaml, etc.)
case "$FILE_PATH" in
    *.ts|*.tsx|*.js|*.jsx|*.py|*.go|*.rs|*.java|*.rb|*.php|*.swift|*.kt|*.sh)
        ;;
    *)
        exit 0
        ;;
esac

echo "[code-quality] Check error handling, immutability patterns, and input validation in modified files." >&2

exit 0
