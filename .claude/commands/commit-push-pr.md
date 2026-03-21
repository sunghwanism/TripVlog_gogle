---
allowed-tools: Bash(git:*), Bash(gh:*), Bash(npm:*), Bash(python:*), Bash(go:*), Bash(cargo:*), Bash(make:*), Read, Grep, Glob
description: Commit after verification, create PR, merge, and notify (v6)
argument-hint: [commit message] [--merge|--squash|--rebase] [--draft] [--no-verify] [--no-checklist] [--skip-security] [--notify]
---

## Task

### Step 0: Collect Context

```bash
git status --short
git branch --show-current
git rev-parse --abbrev-ref origin/HEAD 2>/dev/null | sed 's/origin\///' || echo "main"
git log --oneline -3
git diff --staged --stat 2>/dev/null || git diff --stat
git remote get-url origin 2>/dev/null
gh --version 2>/dev/null | head -1 || echo "not installed"
```

---

### Step 1: Parse Arguments

**Options from $ARGUMENTS:**
- `--merge` -> merge commit
- `--squash` -> squash merge
- `--rebase` -> rebase merge
- `--draft` -> draft PR (cannot be combined with merge options)
- `--no-verify` -> skip build/test/lint
- `--no-checklist` -> skip web checklist after merge
- `--skip-security` -> skip pre-merge security scan
- `--notify` -> send MCP notification after merge
- Remaining text -> commit message

**If `--draft` and a merge option are both set:**
```
--draft cannot be combined with --merge/--squash/--rebase.
Draft PRs are created for review only.
```
-> Stop

---

### Step 2: Pre-checks

**If there are no changes:**
```
No changes to commit.

Current state:
- Branch: [branch]
- Last commit: [commit message]
```
-> Stop

**If on main/master:**
```
You are about to commit directly to main.

Recommended: create a branch first
  git checkout -b feature/[name]

Options:
1. "create branch" - create a new branch and continue
2. "continue" - commit directly to main (skip PR)
3. "cancel" - stop
```

---

### Step 3: Build/Test Verification

**Skip if `--no-verify` is set.**

Run verification by project type:

| File | Type | Command |
|------|------|---------|
| package.json | Node.js | `npm run build && npm test` |
| pyproject.toml / setup.py | Python | `python -m pytest` |
| go.mod | Go | `go build ./... && go test ./...` |
| Cargo.toml | Rust | `cargo build && cargo test` |
| Makefile | Make | `make test` |

**On failure:**
```
Verification failed

[error output]

Fix and retry, or:
  /commit-push-pr --no-verify
```
-> Stop

---

### Step 3.5: Merge Gate

Before committing, validate the following **AND** checks. Any FAIL blocks the commit.

| Check | Command | Fail condition | With --no-verify |
|-------|---------|----------------|-----------------|
| Build | `npm run build` | exit code != 0 | can skip |
| Tests | `npm test` | exit code != 0 | can skip |
| Lint | `npm run lint` | exit code != 0 | can skip |
| Security scan | security-reviewer agent | CRITICAL found | cannot skip |

**Failure output example:**
```
┌─────────────┬────────┬──────────────────┐
│ Check       │ Result │ Details          │
├─────────────┼────────┼──────────────────┤
│ Build       │ PASS   │                  │
│ Tests       │ FAIL   │ 2 tests failed   │
│ Lint        │ PASS   │                  │
│ Security    │ PASS   │                  │
└─────────────┴────────┴──────────────────┘
Merge gate FAIL: tests failed. Commit aborted.
```

Rules:
- `--no-verify` may skip build/test/lint
- CRITICAL security findings always block

---

### Step 4: Security Check

> Run only when a merge option is provided. Skip for PR-only creation.
> If `--skip-security` is set, print a warning and skip.

**When `--skip-security` is used:**
```
Skipping security review (--skip-security)
Run a manual security review after merge.
```

**Sensitive file auto-trigger (forces scan even with --skip-security):**
- `auth/*`, `**/auth/**`
- `payment/*`, `**/payment/**`
- `session/*`, `**/session/**`
- `*secret*`, `*token*`, `*password*`
- `middleware*`, `**/middleware/**`
- `.env*`, `*credentials*`
- `**/api/admin/**`

**Scan focus:**
- Hardcoded secrets (CRITICAL)
- SQL injection patterns (CRITICAL)
- XSS (`dangerouslySetInnerHTML`, `innerHTML =`) (HIGH)
- Sensitive logging (`console.log.*password/token`) (HIGH)
- Hardcoded URLs in prod code (MEDIUM)
- Known vulnerable deps (MEDIUM)
- Auth bypass patterns (HIGH)
- Permissive CORS (MEDIUM)

**If CRITICAL is found:**
```
Security review failed - merge blocked

[File:line] [CWE-XXX] [description]

Suggested fix:
  [action]

Retry after fix:
  /commit-push-pr [same options]
```
-> Stop

**If only HIGH/MEDIUM:**
- Warn and continue

---

### Step 5: Commit

```bash
git add -A
git commit -m "{message}"
```

---

### Step 6: Push

```bash
git push -u origin HEAD
```

---

### Step 7: Create PR

If `--draft`:
```bash
gh pr create --draft --title "{title}" --body "{body}"
```

Otherwise:
```bash
gh pr create --title "{title}" --body "{body}"
```

---

### Step 8: Merge (if merge option set)

```bash
# One of:
gh pr merge --merge
gh pr merge --squash
gh pr merge --rebase
```

---

### Step 9: Post-merge Actions

- Create web checklist unless `--no-checklist` is set
- Send MCP notification if `--notify` is set

---

### Step 10: Output Summary

```
===============================================================
Commit + PR + Merge (v6)
===============================================================

Branch: [branch]
Commit: [short hash]
PR: [URL]
Merge: [merge mode or skipped]
Checklist: [created/skipped]
Notify: [sent/skipped]

Next:
  /sync
===============================================================
```
