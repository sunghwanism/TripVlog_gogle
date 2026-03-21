#!/bin/bash
# Rate Limiter - PreToolUse Hook
# Security hook that limits tool call rate in remote sessions
#
# Hook trigger: PreToolUse (all tools)
# Exit codes: 0 = allow, 2 = block (rate limit exceeded)
#
# Limits:
#   - 30 per minute (sliding window)
#   - 500 per hour
#   - 5000 per day
#
# Counter storage: ~/.openclaw/sessions/rate-limits.json
# Logging: ~/.claude/security.log

# Skip checks if not a remote session
if [[ -z "${OPENCLAW_SESSION_ID:-}" ]]; then
    exit 0
fi

# Counter file path
RATE_FILE="$HOME/.openclaw/sessions/rate-limits.json"
SECURITY_LOG="$HOME/.claude/security.log"

# Ensure directory exists
mkdir -p "$(dirname "$RATE_FILE")"

# Pass file path and session ID into Python script
export _RATE_FILE="$RATE_FILE"
export _SECURITY_LOG="$SECURITY_LOG"
export _SESSION_ID="${OPENCLAW_SESSION_ID}"

python3 << 'RATE_SCRIPT'
import os
import sys
import json
import time
import fcntl
from datetime import datetime

rate_file = os.environ.get("_RATE_FILE", "")
security_log = os.environ.get("_SECURITY_LOG", "")
session_id = os.environ.get("_SESSION_ID", "unknown")
# Hardcoded limits (no env override — security policy)
limit_per_min = 30
limit_per_hour = 500
limit_per_day = 5000

now = time.time()

# Read counter file (file lock prevents race conditions)
def load_rate_data():
    if not os.path.exists(rate_file):
        return {}
    try:
        with open(rate_file, "r") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_SH)
            data = json.load(f)
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)
            return data
    except (json.JSONDecodeError, IOError):
        return {}

def save_rate_data(data):
    try:
        with open(rate_file, "a+") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            f.seek(0)
            f.truncate()
            json.dump(data, f, indent=2)
            f.flush()
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)
    except IOError:
        pass

def log_rate_limit(limit_type, count, limit):
    if not security_log:
        return
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        entry = (
            f"{timestamp} | RATE_LIMITED | type={limit_type} | "
            f"count={count}/{limit} | session={session_id}\n"
        )
        with open(security_log, "a") as f:
            f.write(entry)
    except IOError:
        pass

# Load per-session timestamp list
data = load_rate_data()
session_data = data.get(session_id, {"timestamps": []})
timestamps = session_data.get("timestamps", [])

# Prune old timestamps (remove older than 24 hours)
day_ago = now - 86400
timestamps = [t for t in timestamps if t > day_ago]

# Sliding window counting
minute_ago = now - 60
hour_ago = now - 3600

count_min = sum(1 for t in timestamps if t > minute_ago)
count_hour = sum(1 for t in timestamps if t > hour_ago)
count_day = len(timestamps)

# Limit checks
blocked = False
if count_min >= limit_per_min:
    print(f"BLOCKED: per-minute rate limit exceeded ({count_min}/{limit_per_min})", file=sys.stderr)
    log_rate_limit("per_minute", count_min, limit_per_min)
    blocked = True
elif count_hour >= limit_per_hour:
    print(f"BLOCKED: per-hour rate limit exceeded ({count_hour}/{limit_per_hour})", file=sys.stderr)
    log_rate_limit("per_hour", count_hour, limit_per_hour)
    blocked = True
elif count_day >= limit_per_day:
    print(f"BLOCKED: per-day rate limit exceeded ({count_day}/{limit_per_day})", file=sys.stderr)
    log_rate_limit("per_day", count_day, limit_per_day)
    blocked = True

if blocked:
    # Do not add timestamp (blocked requests are not counted)
    session_data["timestamps"] = timestamps
    data[session_id] = session_data
    save_rate_data(data)
    sys.exit(2)

# Add timestamp for current request
timestamps.append(now)
session_data["timestamps"] = timestamps
data[session_id] = session_data
save_rate_data(data)

sys.exit(0)
RATE_SCRIPT
