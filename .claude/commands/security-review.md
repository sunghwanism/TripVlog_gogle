---
allowed-tools: Bash(npm:*), Bash(npx:*), Bash(pip:*), Bash(cargo:*), Bash(grep:*), Bash(git:*), Read, Glob, Grep
description: CWE-based security review + STRIDE threat modeling (v6, effort:max enforced)
argument-hint: [file/dir] [--auto] [--quick] [--cwe] [--stride] [--deps] [--report markdown|json]
---

## Task

### Step 0: Enforce effort:max

```
Security Review always runs at effort:max.
This is non-negotiable for security quality.
All analysis runs at maximum depth with no shortcuts.
```

### Step 1: Identify Scan Targets

**Parameter parsing:**
- `[path]`: specific file or directory
- `--auto`: scan only changed files from git diff (auto-expand on sensitive patterns)
- `--quick`: quick scan of changed files (CWE Top 10 only)
- `--cwe`: full CWE Top 25 mapping
- `--stride`: add STRIDE threat modeling
- `--deps`: dependency vulnerability scan
- `--report [format]`: generate markdown or json report

**Scan scope examples:**

```bash
# --auto: changed files only
git diff --cached --name-only | grep -E '\.(ts|tsx|js|jsx|py|go|rs|java)$'
git diff --name-only | grep -E '\.(ts|tsx|js|jsx|py|go|rs|java)$'

# --quick: quick scan
git diff --name-only HEAD~1 | grep -E '\.(ts|tsx|js|jsx|py|go|rs|java)$'

# default: all source files
find src/ lib/ app/ -type f -name '*.ts' -o -name '*.tsx' -o -name '*.js' -o -name '*.jsx'
```

**Auto-trigger patterns (expand scan when matched):**

| Pattern | Risk | Description |
|---------|------|-------------|
| `auth` | Critical | Authentication code |
| `payment` | Critical | Payment processing |
| `session` | High | Session management |
| `token` | High | Token issuance/validation |
| `password` | Critical | Password handling |
| `secret` | Critical | Secret/key management |
| `crypto` | High | Cryptography logic |
| `jwt` | High | JWT handling |
| `admin` | High | Admin features |
| `upload` | Medium | File upload |
| `download` | Medium | File download |
| `redirect` | Medium | URL redirect |

### Step 2: CWE Mapping

Run pattern matching based on CWE Top 25. Tag each finding with a CWE ID.

Example grep scans:

```bash
# CWE-79: XSS
grep -rn 'innerHTML\|dangerouslySetInnerHTML\|v-html' src/

# CWE-89: SQL Injection
grep -rn 'query(`\|query(".*\${\|\.raw(' src/

# CWE-78/77: Command Injection
grep -rn 'exec(\|execSync(\|spawn(' src/ | grep -v node_modules

# CWE-798: Hardcoded Credentials
grep -rn 'apiKey.*=.*"\|secret.*=.*"\|password.*=.*"\|token.*=.*"' src/ --include='*.ts' --include='*.js'

# CWE-200: Sensitive Info Exposure
grep -rn 'console\.log.*\(password\|token\|secret\|key\|credential\)' src/

# CWE-327: Broken Crypto
grep -rn 'md5(\|sha1(\|Math\.random()' src/ --include='*.ts' --include='*.js'

# CWE-502: Unsafe Deserialization
grep -rn 'eval(\|new Function(\|JSON\.parse' src/ | grep -v 'JSON\.parse(JSON'

# CWE-918: SSRF
grep -rn 'fetch(\|axios\.\(get\|post\)' src/ | grep 'req\.\|params\.\|query\.'
```

### Step 3: STRIDE Threat Modeling (`--stride`)

If `--stride` is set, classify findings into STRIDE categories:
- Spoofing: auth token forgery, session hijack, missing identity checks
- Tampering: input validation gaps, injection, unsigned data
- Repudiation: missing audit logs, unverifiable transactions
- Information Disclosure: error stacks, sensitive logging, excessive API data
- Denial of Service: missing rate limits, unlimited uploads, ReDoS patterns
- Elevation of Privilege: role escalation, missing authorization checks

### Step 4: Dependency Scan (`--deps`)

Run a dependency vulnerability scan for the project type and include results.

### Step 5: Output

Provide:
- Summary of findings by severity
- CWE IDs and locations
- STRIDE classification (if enabled)
- Concrete remediation steps
- Report file if `--report` was requested
