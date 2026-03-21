#!/bin/bash
# Output Secret Filter - PostToolUse Hook
# Detect and mask secrets in tool outputs
#
# Hook trigger: PostToolUse (all tools)
# Exit codes: 0 = always allow (modify output only)
#
# Behavior:
#   - Receive tool result JSON from stdin
#   - Detect secret patterns in tool_result
#   - If detected, output masked result to stdout (Claude sees masked values only)
#   - Log masking events to security.log (never log raw values)

# Skip checks if not a remote session
if [[ -z "${OPENCLAW_SESSION_ID:-}" ]]; then
    exit 0
fi

# Read JSON from stdin
INPUT=$(cat)

# Pass via env var and process in Python
export _FILTER_INPUT="$INPUT"
export _SECURITY_LOG="$HOME/.claude/security.log"

python3 << 'FILTER_SCRIPT'
import os
import sys
import json
import re
from datetime import datetime

input_json = os.environ.get("_FILTER_INPUT", "")
security_log = os.environ.get("_SECURITY_LOG", "")

if not input_json:
    sys.exit(0)

try:
    data = json.loads(input_json)
except (json.JSONDecodeError, ValueError):
    sys.exit(0)

# Extract output text from tool_result
tool_result = data.get("tool_result", "")
if isinstance(tool_result, dict):
    # If dict, convert to string
    tool_result = json.dumps(tool_result, ensure_ascii=False)
elif not isinstance(tool_result, str):
    tool_result = str(tool_result)

if not tool_result:
    sys.exit(0)

# Define masking patterns (pattern, description)
SECRET_PATTERNS = [
    # API key patterns
    (r'\bsk-[a-zA-Z0-9_-]{20,}\b', "OpenAI API Key"),
    (r'\bsk-proj-[a-zA-Z0-9_-]{20,}\b', "OpenAI Project Key"),
    (r'\bAKIA[A-Z0-9]{16,}\b', "AWS Access Key"),
    (r'\bxoxb-[a-zA-Z0-9-]{20,}\b', "Slack Bot Token"),
    (r'\bxoxp-[a-zA-Z0-9-]{20,}\b', "Slack User Token"),
    (r'\bghp_[a-zA-Z0-9]{36,}\b', "GitHub PAT"),
    (r'\bghs_[a-zA-Z0-9]{36,}\b', "GitHub App Token"),
    (r'\bgho_[a-zA-Z0-9]{36,}\b', "GitHub OAuth Token"),
    (r'\bghu_[a-zA-Z0-9]{36,}\b', "GitHub User Token"),
    (r'\bglpat-[a-zA-Z0-9_-]{20,}\b', "GitLab PAT"),
    (r'\bnpm_[a-zA-Z0-9]{36,}\b', "NPM Token"),

    # Bearer/Auth tokens
    (r'(?i)\bBearer\s+[a-zA-Z0-9_.-]{20,}\b', "Bearer Token"),
    (r'(?i)\btoken=[a-zA-Z0-9_.-]{20,}\b', "Token Parameter"),
    (r'(?i)\bauth=[a-zA-Z0-9_.-]{20,}\b', "Auth Parameter"),
    (r'(?i)\bapi[_-]?key=[a-zA-Z0-9_.-]{20,}\b', "API Key Parameter"),

    # Password/secret patterns
    (r'(?i)\bpassword=[^\s&]{8,}\b', "Password Parameter"),
    (r'(?i)\bpasswd=[^\s&]{8,}\b', "Password Parameter"),
    (r'(?i)\bsecret=[^\s&]{20,}\b', "Secret Parameter"),

    # Environment variable values (value portion of KEY=VALUE)
    (r'(?i)\bAWS_SECRET_ACCESS_KEY=[^\s]{20,}\b', "AWS Secret Key"),
    (r'(?i)\bOPENAI_API_KEY=[^\s]{20,}\b', "OpenAI Key Value"),
    (r'(?i)\bANTHROPIC_API_KEY=[^\s]{20,}\b', "Anthropic Key Value"),
    (r'(?i)\bTELEGRAM_BOT_TOKEN=[^\s]{20,}\b', "Telegram Token Value"),
    (r'(?i)\bGITHUB_TOKEN=[^\s]{20,}\b', "GitHub Token Value"),
    (r'(?i)\bSUPABASE_SERVICE_ROLE_KEY=[^\s]{20,}\b', "Supabase Key Value"),
    (r'(?i)\bDATABASE_URL=[^\s]{20,}\b', "Database URL Value"),

    # Private key blocks
    (r'-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----', "Private Key"),

    # Long base64-like strings (40+ alnum chars, context-dependent)
    (r'(?i)(?:key|secret|token|password|credential|auth)[\s=:]+["\']?[a-zA-Z0-9+/]{40,}={0,2}["\']?', "Potential Base64 Secret"),
]

import base64
import urllib.parse

def decode_layers(text):
    """Detect hidden secrets by decoding base64 or URL encoding"""
    decoded_variants = []
    # Attempt base64 decode
    # Find base64-like chunks and decode
    b64_pattern = re.compile(r'[A-Za-z0-9+/]{20,}={0,2}')
    for m in b64_pattern.finditer(text):
        try:
            decoded = base64.b64decode(m.group(0), validate=True).decode("utf-8", errors="ignore")
            if decoded and len(decoded) >= 10:
                decoded_variants.append(decoded)
        except Exception:
            pass
    # Attempt URL decode
    try:
        url_decoded = urllib.parse.unquote(text)
        if url_decoded != text:
            decoded_variants.append(url_decoded)
    except Exception:
        pass
    return decoded_variants

def mask_match(original):
    """Mask matched strings"""
    if len(original) > 16:
        return original[:8] + "***MASKED***" + original[-4:]
    return original[:4] + "***MASKED***"

masked_output = tool_result
masked_count = 0
masked_types = []

# Step 1: direct match in original text
for pattern, desc in SECRET_PATTERNS:
    matches = list(re.finditer(pattern, masked_output))
    if matches:
        for match in reversed(matches):
            original = match.group(0)
            masked_output = masked_output[:match.start()] + mask_match(original) + masked_output[match.end():]
            masked_count += 1
        if desc not in masked_types:
            masked_types.append(desc)

# Step 2: detect encoding bypass (mask original encoded chunks if decoded text reveals a secret)
decoded_variants = decode_layers(tool_result)
for decoded_text in decoded_variants:
    for pattern, desc in SECRET_PATTERNS:
        if re.search(pattern, decoded_text):
            # Secret found in decoded text → mask original base64/URL encoded chunk
            b64_pattern = re.compile(r'[A-Za-z0-9+/]{20,}={0,2}')
            for m in b64_pattern.finditer(masked_output):
                try:
                    d = base64.b64decode(m.group(0), validate=True).decode("utf-8", errors="ignore")
                    if re.search(pattern, d):
                        chunk = m.group(0)
                        masked_output = masked_output[:m.start()] + mask_match(chunk) + masked_output[m.end():]
                        masked_count += 1
                        if desc not in masked_types:
                            masked_types.append(desc)
                        break
                except Exception:
                    pass
            # Detect URL-encoding bypass
            try:
                url_decoded = urllib.parse.unquote(masked_output)
                if url_decoded != masked_output and re.search(pattern, url_decoded):
                    # URL-encoded secret → mask the %XX sequence range
                    pct_pattern = re.compile(r'(?:%[0-9A-Fa-f]{2}[A-Za-z0-9_.~-]*){5,}')
                    for pm in reversed(list(pct_pattern.finditer(masked_output))):
                        decoded_chunk = urllib.parse.unquote(pm.group(0))
                        if re.search(pattern, decoded_chunk):
                            masked_output = masked_output[:pm.start()] + mask_match(pm.group(0)) + masked_output[pm.end():]
                            masked_count += 1
                            if desc not in masked_types:
                                masked_types.append(desc)
            except Exception:
                pass

if masked_count > 0:
    # Write masked output to stdout (Claude sees this value)
    print(masked_output)

    # Write security log (never store raw masked values)
    if security_log:
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            tool_name = data.get("tool_name", "unknown")
            session_id = os.environ.get("OPENCLAW_SESSION_ID", "unknown")
            log_entry = (
                f"{timestamp} | SECRET_MASKED | tool={tool_name} | "
                f"count={masked_count} | types={','.join(masked_types)} | "
                f"session={session_id}\n"
            )
            with open(security_log, "a") as f:
                f.write(log_entry)
        except (IOError, OSError):
            pass

# always allow (exit 0)
sys.exit(0)
FILTER_SCRIPT
