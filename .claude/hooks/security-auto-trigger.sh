#!/bin/bash
# security-auto-trigger.sh - PostToolUse Hook (Edit/Write)
# Suggest security review when security-related files change
# exit 0 required (do not block, suggestion only)

INPUT=$(cat)

RESULT=$(echo "$INPUT" | python3 -c "
import sys, json, os, re

try:
    d = json.load(sys.stdin)
except:
    sys.exit(0)

tool = d.get('tool_name', '')
if tool not in ('Edit', 'Write'):
    sys.exit(0)

inp = d.get('tool_input', {})
file_path = inp.get('file_path', '')
if not file_path:
    sys.exit(0)

# Security-sensitive file patterns
SECURITY_PATTERNS = [
    # Auth/permissions
    r'auth',
    r'login',
    r'session',
    r'token',
    r'jwt',
    r'oauth',
    r'credential',
    r'permission',
    r'rbac',
    r'acl',
    r'middleware',
    # Env/config
    r'\.env',
    r'config/security',
    r'security\.ts',
    r'security\.js',
    # DB security
    r'rls',
    r'policy',
    r'migration',
    # API
    r'route\.ts',
    r'route\.js',
    r'api/',
    # Cryptography
    r'encrypt',
    r'decrypt',
    r'hash',
    r'crypto',
]

# Check file path (case-insensitive)
path_lower = file_path.lower()
matched_pattern = None
for pattern in SECURITY_PATTERNS:
    if re.search(pattern, path_lower):
        matched_pattern = pattern
        break

if not matched_pattern:
    sys.exit(0)

# Suggest only once per file per session
sid = d.get('session_id', 'unknown')
marker_dir = '/tmp/security-suggest'
os.makedirs(marker_dir, exist_ok=True)
safe_path = re.sub(r'[^a-zA-Z0-9]', '_', file_path)[:100]
marker = os.path.join(marker_dir, f'{sid}-{safe_path}')
if os.path.exists(marker):
    sys.exit(0)
open(marker, 'w').close()

# Print match results to stdout (converted to stderr in bash)
basename = os.path.basename(file_path)
print(f'{basename}|{matched_pattern}')
" 2>/dev/null)

if [[ -n "$RESULT" ]]; then
    BASENAME=$(echo "$RESULT" | cut -d'|' -f1)
    PATTERN=$(echo "$RESULT" | cut -d'|' -f2)
    echo "[Security] Security-related file change detected: ${BASENAME} (pattern: ${PATTERN}). Recommend running /security-review before commit." >&2
fi

exit 0
