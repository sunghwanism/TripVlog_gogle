---
allowed-tools: Bash(git:*), Read, Edit, Write, Grep, Glob
description: Record lessons and suggest automations (v6, includes suggest-automation behavior)
argument-hint: ["lesson text"] [--from-error] [--from-session] [--suggest] [--list] [--edit N] [--remove N]
---

# /learn – Lesson Capture & Automation Suggestions (v6)

## Step 0: Parse parameters
Determine the mode from the provided flags.

| Flag | Description |
|------|-------------|
| (none) | Record the provided lesson text directly |
| `--from-error` | Extract a pattern from the most recent error |
| `--from-session` | Extract a pattern from the current session |
| `--suggest` | Suggest automations based on git history |
| `--list` | List stored lessons |
| `--edit N` | Edit lesson entry N |
| `--remove N` | Delete lesson entry N |

Parsing rules:
- `--list`, `--edit`, and `--remove` must run alone (no other flags).
- `--suggest` can run alone or alongside `--from-session`.
- No flags + free text triggers direct entry mode.

## Step 1: Analyze the lesson source

### Direct entry mode (default)

Record the user-provided text as a lesson.

```
/learn "Remember to add migration files when changing Supabase RLS policies"
```

### `--from-error` mode

1. Scan recent terminal output for error messages.
2. Analyze the root cause.
3. Summarize the resolution as a lesson.

```bash
# Inspect recent context
git log --oneline -5
git diff HEAD~1
```

### `--from-session` mode

1. Summarize actions taken during the current session.
2. Extract repeated patterns, mistakes, or discoveries.
3. Record each item as a lesson.

### `--list` mode

Read the `# Lessons Learned` section of `CLAUDE.md` and display the entries.

### `--edit N`

Show entry N, ask the user for edits, and apply them.

### `--remove N`

Display entry N, confirm, and delete it.

## Step 2: Pattern classification
Tag each lesson according to this taxonomy:

```
pattern categories:
  error-pattern:       recurring errors (build failures, type errors, runtime issues)
  performance-pattern: performance concerns (query speed, bundle size, rendering)
  security-pattern:    security failures (auth, permissions, input validation)
  automation-pattern: repetitive manual work (used by --suggest mode)
```

Classification guidelines:
- If an error message is mentioned → `error-pattern`
- If the lesson mentions speed, size, or memory → `performance-pattern`
- If it relates to auth, tokens, or validation → `security-pattern`
- If it describes a repetitive manual workflow → `automation-pattern`
- Multiple tags allowed (comma-separated).

## Step 3: `--suggest` mode (automation proposals)

### 3-1. Analyze git history

```bash
git log --oneline -50
```

Identify repeated patterns in the most recent 50 commits.

### 3-2. Detect repeated commit signals

Look for:
- The same prefix appearing 3+ times (e.g., `fix: lint`).
- The same file modified in 5+ commits.
- Repeated keywords such as `migration`, `config`, or `env`.

### 3-3. Spot file change groups

```bash
git log --name-only --oneline -50
```

Identify files that frequently change together.

### 3-4. Check for existing automations

Avoid duplicating existing automation by listing current commands, agents, and skills:

```bash
ls .claude/commands/ 2>/dev/null
ls .claude/agents/ 2>/dev/null
ls .claude/skills/ 2>/dev/null
```

### 3-5. Generate proposals

For each detected pattern, propose an automation:

| Pattern Type | Proposal |
|--------------|----------|
| Simple repeated commits | Custom command (`.claude/commands/`) |
| Complex repeated work | Custom skill (`.claude/skills/`) |
| Recurring error | Agent (`.claude/agents/`) |
| File group changes | Hook (PreToolUse/PostToolUse) |

Output example:
```
Automation suggestions:
  1. [command] /fix-lint – auto-fix lint errors (observed 8 times)
  2. [skill]  db-migrate – create+apply migrations (5 occurrences)
  3. [hook]   validate env on config changes (4 simultaneous edits)
```

### 3-6. Optional creation
If the user selects a suggestion, generate the corresponding automation file. Otherwise, keep the insight as a lesson.

## Step 4: Update CLAUDE.md

Append the lesson to the project’s `CLAUDE.md`.

### Section placement
Create a `# Lessons Learned` section at the end if it doesn’t exist.

### Entry template

```markdown
# Lessons Learned

## [N]. [Title] – [Pattern Category]
- **Date**: 2026-02-07
- **Category**: error-pattern
- **Lesson**: [content]
- **Action**: [taken or recommended action]
```

### Agent memory linkage

If the lesson pertains to a specific agent, append it to that agent’s memory directory:

| Category | Agent | Memory path |
|----------|-------|-------------|
| error-pattern (build) | build-error-resolver | `~/.claude/agent-memory/build-error-resolver/` |
| error-pattern (tests) | tdd-guide | `~/.claude/agent-memory/tdd-guide/` |
| security-pattern | security-reviewer | `~/.claude/agent-memory/security-reviewer/` |
| performance-pattern | architect | `~/.claude/agent-memory/architect/` |
| automation-pattern | planner | `~/.claude/agent-memory/planner/` |

Memory entry format:
```
## Learnings
- [date] [project] discovery: [summary]
```

This ensures agents can reference lessons in future sessions.
