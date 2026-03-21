#!/bin/bash
# Remote Command Guard - PreToolUse Hook
# Block dangerous Bash commands in remote Claude Code sessions
#
# Hook trigger: PreToolUse, matcher: Bash
# Exit codes: 0 = allow, 2 = block
#
# Blocked categories:
#   1. Destructive deletion (rm -rf /, rm -rf ~, rm -rf *)
#   2. Env var/secret exfiltration (env, printenv, echo $SECRET etc.)
#   3. Path traversal (/etc/passwd, /etc/shadow etc.)
#   4. External network access (curl, wget, nc, ncat etc.)
#   5. Permission changes (chmod 777, chown, mount etc.)
#   6. Process termination (kill -9, pkill etc.)
#   7. Command injection (eval, exec etc.)

# Skip checks if not a remote session
if [[ -z "${OPENCLAW_SESSION_ID:-}" ]]; then
    exit 0
fi

# Read JSON from stdin
INPUT=$(cat)

# Extract command (python3 -c + single quotes to avoid shell expansion)
COMMAND=$(echo "$INPUT" | python3 -c '
import sys, json
data = json.load(sys.stdin)
print(data.get("tool_input", {}).get("command", ""))
' 2>/dev/null)

if [[ -z "$COMMAND" ]]; then
    exit 0
fi

# Pass command via env var → inject Python check logic via heredoc
export _GUARD_CMD="$COMMAND"
python3 << 'GUARD_SCRIPT'
import os
import sys
import re

command = os.environ.get("_GUARD_CMD", "")
if not command:
    sys.exit(0)

# Normalize command (multiple spaces → single space)
cmd = re.sub(r'\s+', ' ', command.strip())
cmd_lower = cmd.lower()

blocked_reason = None

# === 1. Destructive deletion ===
# rm -rf / , rm -rf ~ , rm -rf * etc. block only broad deletions
# rm /tmp/specific-file.txt deleting specific files is allowed
destructive_patterns = [
    r'\brm\s+-[a-zA-Z]*r[a-zA-Z]*f[a-zA-Z]*\s',  # rm -rf, rm -rfi etc.
    r'\brm\s+-[a-zA-Z]*f[a-zA-Z]*r[a-zA-Z]*\s',  # rm -fr, rm -fri etc.
    r'\brm\b.*\s+/$',                              # rm / (root)
    r'\brm\b.*\s+/\s',                             # rm / something
    r'\brm\b.*\s+~/?(\s|$)',                        # rm ~ or rm ~/
    r'\brm\b.*\s+\*(\s|$)',                         # rm * (entire current directory)
    r'\bmkfs\b',
    r'\bdd\s+.*of=/dev/',
    r'\b:\s*\(\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;',
]
for pat in destructive_patterns:
    if re.search(pat, cmd_lower):
        blocked_reason = "Destructive deletion command detected"
        break

# === 2. Env var/secret exfiltration ===
# Secret patterns match the original cmd with re.IGNORECASE (preserve env var casing)
if not blocked_reason:
    secret_patterns = [
        r'\b(env|printenv|set)\s*$',
        r'\b(env|printenv|set)\s*\|',
        r'\becho\s+.*\$[A-Z_]*KEY\b',
        r'\becho\s+.*\$[A-Z_]*SECRET\b',
        r'\becho\s+.*\$[A-Z_]*TOKEN\b',
        r'\becho\s+.*\$[A-Z_]*PASSWORD\b',
        r'\becho\s+.*\$[A-Z_]*PASSWD\b',
        r'\becho\s+.*\$[A-Z_]*API\b',
        r'\becho\s+.*\$[A-Z_]*CREDENTIAL\b',
        r'\becho\s+.*\$(AWS_|OPENAI_|ANTHROPIC_|TELEGRAM_|GITHUB_|SUPABASE_)',
        r'\bcat\s+.*\.env\b',
        r'\bcat\s+.*\.netrc\b',
        r'\bcat\s+.*credentials\b',
        r'\bcat\s+.*/\.ssh/',
        r'\bexport\s+-p\s*$',
        r'\bexport\s+-p\s*\|',
    ]
    for pat in secret_patterns:
        if re.search(pat, cmd, re.IGNORECASE):
            blocked_reason = "Secret/env var exfiltration attempt detected"
            break

# === 3. Path traversal ===
if not blocked_reason:
    path_traversal_patterns = [
        r'/etc/passwd',
        r'/etc/shadow',
        r'/etc/sudoers',
        r'/etc/master\.passwd',
        r'\.\./(\.\./)*(etc|proc|sys|dev)/',
        r'/proc/self/',
        r'/proc/\d+/',
        r'/sys/class/',
    ]
    for pat in path_traversal_patterns:
        if re.search(pat, cmd_lower):
            blocked_reason = "Sensitive system path access detected"
            break

# === 4. External network access ===
if not blocked_reason:
    network_patterns = [
        r'\bcurl\s',
        r'\bwget\s',
        r'\bnc\s',
        r'\bncat\s',
        r'\bnetcat\s',
        r'\btelnet\s',
        r'\bssh\s',
        r'\bscp\s',
        r'\brsync\s.*:',
        r'\bftp\s',
        r'\bsftp\s',
        r'\bsocat\s',
        r'\bpython3?\s+-m\s+http\.server',
        r'\bphp\s+-S\s',
        r'\bnpm\s+publish\b',
        r'\bnpx\s.*ngrok',
    ]
    # localhost/127.0.0.1 curl/wget to localhost is allowed (dev only)
    is_local = bool(re.search(
        r'\bcurl\s+.*\b(localhost|127\.0\.0\.1|0\.0\.0\.0)\b', cmd_lower
    ))
    if not is_local:
        for pat in network_patterns:
            if re.search(pat, cmd_lower):
                blocked_reason = "External network access attempt detected"
                break

# === 5. Permission changes ===
if not blocked_reason:
    permission_patterns = [
        r'\bchmod\s+777\b',
        r'\bchmod\s+666\b',
        r'\bchmod\s+[0-7]*[67][0-7]{2}\b.*/(etc|usr|var|sys)',
        r'\bchown\s',
        r'\bmount\s',
        r'\bumount\s',
        r'\bsudo\s',
        r'\bsu\s+-?\s',
        r'\bdscl\s',
    ]
    for pat in permission_patterns:
        if re.search(pat, cmd_lower):
            blocked_reason = "Permission change command detected"
            break

# === 6. Process termination ===
if not blocked_reason:
    process_patterns = [
        r'\bkill\s+-9\b',
        r'\bkill\s+-KILL\b',
        r'\bkill\s+-SIGKILL\b',
        r'\bkillall\s',
        r'\bpkill\s',
        r'\bxkill\b',
        r'\bshutdown\b',
        r'\breboot\b',
        r'\bhalt\b',
        r'\binit\s+[06]\b',
    ]
    for pat in process_patterns:
        if re.search(pat, cmd_lower):
            blocked_reason = "Process termination/system control command detected"
            break

# === 7. Command injection ===
if not blocked_reason:
    injection_patterns = [
        r'\beval\s',
        r'\bexec\s',
        r'\bsource\s+/dev/',
        r'\bbash\s+-c\s.*\$\(',
        r'\bsh\s+-c\s.*\$\(',
        r'`[^`]*\$\([^)]+\)[^`]*`',
        r'\|\s*sh\b',
        r'\|\s*bash\b',
        r'\|\s*zsh\b',
        r'>\s*/dev/sd[a-z]',
        r'>\s*/dev/nvme',
        r'\bbase64\s+-d\s*\|\s*(sh|bash|zsh)',
    ]
    for pat in injection_patterns:
        if re.search(pat, cmd_lower):
            blocked_reason = "Command injection pattern detected"
            break

if blocked_reason:
    safe_cmd = cmd[:200]
    print(f"BLOCKED: {blocked_reason}", file=sys.stderr)
    print(f"Command: {safe_cmd}", file=sys.stderr)
    sys.exit(2)

sys.exit(0)
GUARD_SCRIPT
