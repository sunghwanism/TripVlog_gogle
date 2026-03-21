---
allowed-tools: Bash(git:*), Bash(npm:*), Bash(pnpm:*), Bash(npx:*), Read, Write, Edit, Glob, Grep, Task
description: Run build/test/lint verification in one command
argument-hint: [--once] [--loop N] [--security] [--coverage] [--extract] [--skip-handoff]
---

# /handoff-verify - Handoff + Automated Verification (v6)

Combines `/handoff` + `/clear` + `/verify` into a single command.
Key change: no manual `/clear` needed. Subagents provide fresh context while preserving the parent context.

## Step 0: Parse Arguments

Flags from $ARGUMENTS:

| Flag | Default | Description |
|------|---------|-------------|
| `--once` | false | One-shot verification (no loop) |
| `--loop N` | 5 | Max retry count |
| `--security` | false | Include security review |
| `--coverage` | false | Test coverage mode |
| `--extract` | false | Error extraction mode |
| `--skip-handoff` | false | Skip creating handoff.md (if already exists) |
| `--effort` | high | Depth: low / medium / high / max |
| `--only` | all | Only run: build / test / lint / type |

Remaining text is the intent description.

### effort behavior

| effort | Code review scope | Thinking level | Auto-fix scope | Security |
|--------|-------------------|---------------|----------------|----------|
| low | Changed files only | basic | import/lint only | skip |
| medium | Changed + direct deps | think hard | full fixable set | pattern scan |
| high | Changed + dependency graph | think harder | fixables + refactor hints | key pattern scan |
| max | Full impact analysis | ultrathink | fixables + architecture review | security-reviewer agent |

## Step 1: Collect Environment

Collect in parallel:
1. `git status --short`
2. `git diff --name-only`
3. `git log --oneline -10`
4. Read `.claude/handoff.md` if present
5. Read project docs if present: `CLAUDE.md`, `spec.md`, `prompt_plan.md`
6. Detect project type:
   - `package.json` -> Node.js (auto-detect npm/pnpm/yarn)
   - `go.mod` -> Go
   - `Cargo.toml` -> Rust
   - `pyproject.toml` / `requirements.txt` -> Python
   - `Makefile` -> Make

Package manager detection order:
1. `pnpm-lock.yaml` -> pnpm
2. `yarn.lock` -> yarn
3. `bun.lockb` -> bun
4. default -> npm

If not a git repo -> stop with guidance. If no changes -> stop with notice.

## Step 2: Auto-generate Handoff Doc

> Skip if `--skip-handoff` is set.
> If `.claude/handoff.md` exists, append to it.

If `.claude/` is missing, create it. Write the following template:

```markdown
# Handoff Document
Created: [YYYY-MM-DD HH:MM KST]
Effort: [current effort level, or "default"]

## 1. Completed work
- [item: what was implemented/changed and why]

## 2. Changed files summary
| File | Change type | Description |
|------|-------------|-------------|
| src/xxx.ts | modified | [summary] |
| src/yyy.ts | added | [purpose] |

## 3. Tests needed
- [ ] [test item 1: scenario + expected result]
- [ ] [test item 2: edge case]

## 4. Known issues / TODO
- [ ] [issue 1]

## 5. Cautions
- [notes for next session]

## 6. Verification recommendations
- effort: [recommended]
- security: [true/false]
- coverage: [true/false]
- only: [specific step or all]
- loop: [recommended retries]
```

Security recommendation rules:
- If files with `auth`, `login`, `session`, `token`, `password`, `secret`, `key`, `credential`, `middleware` changed -> true
- `.env*` changed -> true
- otherwise -> false

Effort recommendation rules:
- 1-3 files, lint/format only -> low
- 4-10 files -> medium
- 10+ files or refactor -> high
- Architecture/security/DB schema -> max

Coverage recommendation rules:
- Test files changed -> true
- Business logic changed without tests -> true
- otherwise -> false

## Step 3: Merge Intent

Merge CLI flags with handoff recommendations.
**CLI flags win.** Handoff only fills missing values.

Intent priority:
1. Intent from $ARGUMENTS
2. Recommendations in `.claude/handoff.md`
3. Default verification

## Step 4: Subagent Verification (Core)

Use Task to run `verify-agent` with fresh context.
Parent context is preserved while verification runs in a clean subagent.

### Mode selection

- `--extract` -> error extraction mode (no loop)
- `--coverage` -> coverage mode (no loop)
- `--security` -> include security-reviewer agent
- `--once` -> one-shot verification
- default -> verification loop up to N

### Subagent invocation

```
Task (subagent_type: general-purpose, model: sonnet)

Instructions:
1. Read .claude/handoff.md
2. Project type: [detected]
3. Package manager: [detected]
4. Mode: [mode]
5. Effort: [level]
6. Max retries: [N]
7. --only: [all or specific step]
8. --security: [true/false]

Run the verification pipeline and return results.
Fix fixable errors automatically and re-verify.
Report non-fixable errors only.
```

### Verification pipeline

**A. Code review (adaptive thinking)**
- low: obvious issues in changed files
- medium: changed files + direct references
- high: dependency graph impact
- max: architecture impact, edge cases, perf

Checklist:
- [ ] Changes match intent
- [ ] Avoid mutations where appropriate
- [ ] Error handling present
- [ ] No hardcoded secrets
- [ ] No stray console.log (except debug)
- [ ] Functions <= 50 lines
- [ ] Files <= 800 lines
- [ ] Input validation for user inputs

**B. Automated verification**
Run type-specific commands (build/test/lint/type).

## Output

Summarize:
- What ran
- What failed
- What was fixed
- What remains
- Next steps
