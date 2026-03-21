# CLAUDE.md

## Project Overview

## Tech Stack

---
## Rules (Auto-loaded from `.claude/rules/`)

| Rule | Summary |
|------|---------|
| `golden-principles.md` | 12 core principles — read first |
| `coding-style.md` | Immutability, file size, error handling, validation |
| `interaction.md` | Assumptions first, analogy-led explanations, conclusion first |
| `verification.md` | No completion claims without fresh evidence |
| `security.md` | Pre-commit checklist, secrets in env vars only |
| `testing.md` | TDD mandatory, 80% coverage, unit + integration + E2E |
| `git-workflow-v2.md` | Commit format, PR workflow, feature implementation |
| `date-calculation.md` | Always use `date` or `python3` — never mental math |
| `agents-v2.md` | Agent routing, parallel tasks, agent teams |

---
## Agents (`.claude/agents/`)

| Agent | Trigger |
|-------|---------|
| `planner` | New feature (3+ files), architecture change |
| `tdd-guide` | Writing any new feature — proactive |
| `code-reviewer` | After writing code |
| `security-reviewer` | Security issue found — stop immediately |
| `build-error-resolver` | Build or compile failure |
| `verify-agent` | Verify requirements met |
| `e2e-runner` | Playwright E2E tests |
| `refactor-cleaner` | Dead code removal |
| `doc-updater` | Documentation updates |
| `database-reviewer` | DB schema or query changes |

Use `/agent-router` to auto-route to the right specialist.

---
## Key Slash Commands (`.claude/commands/`)

| Command | Use |
|---------|-----|
| `/plan` | Design before coding (REQUIRED for 3+ file changes) |
| `/auto` | Plan → implement → PR in one flow |
| `/tdd` | TDD workflow for a single unit |
| `/code-review` | Quality + security review |
| `/commit-push-pr` | Commit → push → PR |
| `/quick-commit` | Small edits |
| `/security-review` | CWE-based security + STRIDE |
| `/e2e` | Playwright E2E generation + run |
| `/verify-loop` | Auto-verify up to 3 retries |
| `/build-fix` | Incremental TS/build error fixing |
| `/checkpoint` | Save/restore work state |
| `/worktree-start` | Isolated git worktree for parallel dev |
| `/orchestrate` | Parallel agent team coordination |
| `/explore` | Codebase exploration before implementation |
| `/learn` | Record lessons + suggest automations |

---
## Critical Workflow Rules

1. **Plan first** — run `/plan` before any change touching 3+ files
2. **TDD** — RED → GREEN → IMPROVE, 80%+ coverage required
3. **Verify before claiming done** — run the command, show the output
4. **No secrets in code** — `process.env` only, throw if unset
5. **Immutable patterns** — never mutate, always spread/create new
6. **Surgical changes** — only change what was asked, nothing more

---
## When Stack is Defined

Update this file with:
- Build, lint, test commands
- Dev server instructions
- Env var setup (Google Drive API credentials)
- Architecture overview of the video processing pipeline
