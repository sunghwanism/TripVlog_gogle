---
allowed-tools: Bash(git:*), Bash(mkdir:*), Read, Write, Glob
description: Project initialization (v6)
argument-hint: [project name] [--type next|vite|go|python|rust]
---

# /init-project - Project Init (v6)

One-time setup checklist to create CLAUDE.md, spec.md, and prompt_plan.md.

## Step 0: Parse Parameters

Parse $ARGUMENTS:

| Flag | Description |
|------|-------------|
| `[project name]` | Project name (defaults to directory name) |
| `--type [type]` | Force project type (next/vite/go/python/rust) |

## Step 1: Detect Project Context

Collect automatically from the current directory:

```
1. package.json / go.mod / Cargo.toml / pyproject.toml -> tech stack
2. .git presence -> git init status
3. README.md -> project description
4. existing CLAUDE.md -> already initialized
5. directory structure -> architecture patterns
```

If CLAUDE.md already exists, ask whether to overwrite/merge/cancel.

## Step 2: Create CLAUDE.md

Generate CLAUDE.md using collected info + user input.

### Included sections

```markdown
# [Project Name]

## Overview
[Project description]

## Tech Stack
- [Detected stack]

## Build & Test
- Build: [npm run build / go build / ...]
- Test: [npm test / go test / ...]
- Lint: [eslint / golangci-lint / ...]

## Directory Structure
[Key directories and roles]

## Coding Conventions
[Detected conventions or user input]
```

## Step 3: Create spec.md

Generate a feature spec template.

```markdown
# [Project Name] - Feature Spec

## Feature 1: [Feature name]
### Requirements
1. [Requirement]
### API Spec
- [Endpoint]
### Data Model
- [Model]
### Business Logic
- [Core logic]
```

Ask the user for key features and fill them in.

## Step 4: Create prompt_plan.md

Create an implementation plan by phases.

```markdown
# [Project Name] - Implementation Plan

## Phase 1: [Phase name]
- [ ] [Task 1]
- [ ] [Task 2]

## Phase 2: [Phase name]
- [ ] [Task 1]
- [ ] [Task 2]

## Dependencies
- Phase 2 runs after Phase 1
```

Derive phases from spec.md features.

## Step 5: Check .gitignore

Ensure these entries exist; suggest adding if missing:

```
# Claude Code (v6 Post-Dev Workflow)
.claude/handoff.md
.claude/checkpoints/
.claude/web-checklist-state.json
```

## Step 6: Output

Summarize what was created and where.
