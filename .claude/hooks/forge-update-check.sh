#!/bin/bash
# forge-update-check.sh - SessionStart Hook
# Check for a new claude-forge version on remote and suggest /forge-update
# 4-hour cooldown, 4-second network timeout
# exit 0 required

INPUT=$(cat)

MSG=$(echo "$INPUT" | python3 -c "
import sys, json, os, subprocess, time

try:
    d = json.load(sys.stdin)
except Exception:
    sys.exit(0)

sid = d.get('session_id', '')
if not sid:
    sys.exit(0)

# Load metadata file
meta_path = os.path.expanduser('~/.claude/.forge-meta.json')
if not os.path.exists(meta_path):
    sys.exit(0)

try:
    with open(meta_path) as f:
        meta = json.load(f)
except Exception:
    sys.exit(0)

repo_path = meta.get('repo_path', '')
if not repo_path:
    sys.exit(0)

# Normalize path (resolve symlinks) + verify repository
repo_path = os.path.realpath(repo_path)
if not os.path.isdir(os.path.join(repo_path, '.git')):
    sys.exit(0)

# Verify claude-forge repository by signature file
plugin_json = os.path.join(repo_path, '.claude-plugin', 'plugin.json')
if not os.path.isfile(plugin_json):
    sys.exit(0)

# 4-hour cooldown: marker under ~/.claude/ (avoid /tmp for security)
check_marker = os.path.expanduser('~/.claude/.forge-update-last-check')
if os.path.exists(check_marker):
    try:
        with open(check_marker) as f:
            last_check = float(f.read().strip())
        if time.time() - last_check < 14400:  # 4 hours
            sys.exit(0)
    except (ValueError, IOError):
        pass  # If parsing fails, run check

# git fetch (4-second timeout to align with hooks timeout 5s in settings.json)
try:
    result = subprocess.run(
        ['git', '-C', repo_path, 'fetch', 'origin', '--quiet'],
        capture_output=True, text=True, timeout=4
    )
    if result.returncode != 0:
        sys.exit(0)
except subprocess.TimeoutExpired:
    sys.exit(0)
except Exception:
    sys.exit(0)

# Dynamically detect default branch
try:
    default_branch_ref = subprocess.run(
        ['git', '-C', repo_path, 'symbolic-ref', 'refs/remotes/origin/HEAD'],
        capture_output=True, text=True, timeout=2
    ).stdout.strip()
    default_branch = default_branch_ref.replace('refs/remotes/origin/', '') if default_branch_ref else 'main'
except Exception:
    default_branch = 'main'

# Compare HEAD vs origin/{default_branch}
try:
    local_head = subprocess.run(
        ['git', '-C', repo_path, 'rev-parse', 'HEAD'],
        capture_output=True, text=True, timeout=2
    ).stdout.strip()

    remote_head = subprocess.run(
        ['git', '-C', repo_path, 'rev-parse', f'origin/{default_branch}'],
        capture_output=True, text=True, timeout=2
    ).stdout.strip()

    # Update marker only after compare logic succeeds
    try:
        with open(check_marker, 'w') as f:
            f.write(str(time.time()))
    except Exception:
        pass

    if local_head == remote_head:
        sys.exit(0)

    current_ver = meta.get('version', '?')
    print(f'[Claude Forge] New update available (current v{current_ver}). Use /forge-update to Update with /forge-update.')

except Exception:
    sys.exit(0)
" 2>/dev/null)

if [[ -n "$MSG" ]]; then
    echo "$MSG" >&2
fi

exit 0
