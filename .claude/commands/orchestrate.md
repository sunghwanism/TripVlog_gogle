---
allowed-tools: Bash(git:*), Read, Write, Glob, Grep, Task, TeamCreate, TaskCreate, TaskUpdate, TaskList, SendMessage
description: Parallel orchestration with Agent Teams (v6)
argument-hint: [--type feature|bugfix|refactor|review] [--parallel N] [--dry-run]
---

# /orchestrate - Agent Teams Parallel Orchestration (v6)

Replaces v5 worktree-based parallelism with the Agent Teams API.
Uses TeamCreate, TaskCreate, SendMessage for native coordination.

## Prerequisites (CRITICAL)

Agent Teams is experimental and disabled by default.
Set the env var below or TeamCreate tools will be unavailable:

```json
// settings.json (project or global)
{
  "env": {
    "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1"
  }
}
```

### Token cost warning

Agent Teams consume significantly more tokens than a single session.
Use them for research, reviews, and complex features; prefer single-session for routine work.

## Step 0: Parse Arguments

| Flag | Default | Description |
|------|---------|-------------|
| `--dry-run` | false | Print plan only (no execution) |
| `--type` | auto | `feature` / `bugfix` / `refactor` / `review` |
| `--parallel` | 3 | Max members (leader + up to 3) |

Rules:
- If `--type` is omitted, infer from prompt_plan.md keywords.
- `--parallel` is capped at 3.

## Step 1: Detect Project Domain

Detect via root files, first match wins:
- package.json -> Node.js/TypeScript
- go.mod -> Go
- requirements.txt / pyproject.toml -> Python
- Cargo.toml -> Rust
- Makefile -> Make
- *.sln / *.csproj -> .NET

Set build/test/lint commands accordingly. If detection fails, ask explicitly.

## Step 2: Parse Tasks

Read `prompt_plan.md` and collect incomplete tasks:
- `- [ ] Task ...` -> pending
- `- [x] Task ...` -> done (skip)

Extract:
- Task number and name
- Explicit depends
- Mentioned file paths
- Estimated complexity

## Step 3: Dependency Analysis

Analyze:
- Explicit depends (`depends:`)
- File-based dependencies (imports, shared modules)
- Shared resources (DB, config, migrations)
- Integration order (API before UI, schema before usage)

Create an execution graph and group tasks accordingly.

## Step 4: Create Team and Assign Tasks

- Create a team with a leader and up to N members
- Assign tasks by domain and dependency constraints
- Provide each member a focused scope and file list

## Step 5: Execute and Monitor

- Create Task records for each member
- Send task instructions via SendMessage
- Track progress with TaskList
- Resolve blockers and reassign if needed

## Step 6: Collect Results

- Gather summaries from all members
- Integrate outputs and reconcile conflicts
- Produce a combined summary and next steps

## Output

Include:
- Team roster and assignments
- Status per task (done/blocked/needs follow-up)
- Key changes and risks
- Recommended next commands
