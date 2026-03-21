---
allowed-tools: Bash(git:*), Bash(npm:*), Bash(pnpm:*), Bash(npx:*), Bash(go:*), Bash(cargo:*), Bash(make:*), Bash(python:*), Read, Write, Edit, Glob, Grep, Task
description: One-click workflow from plan to PR (no mid-stop)
argument-hint: [work description] [--mode feature|bugfix|refactor]
---

# /auto - One-Stop Workflow (v6)

Runs the full pipeline end-to-end instead of invoking each command manually.
Stops only on CRITICAL security issues; otherwise proceeds to completion.

---

## Step 0: Parse Arguments

| Arg | Default | Description |
|-----|---------|-------------|
| `--mode` | feature | Mode: feature / bugfix / refactor |
| remaining text | - | Work description (required) |

If work description is missing:
```
Usage: /auto [work description]

Examples:
  /auto build login page
  /auto --mode bugfix payment total shows 0
  /auto --mode refactor clean auth module
```

---

## Step 1: Select Pipeline by Mode

### feature (default)
```
plan -> tdd -> code-review -> handoff-verify -> commit-push-pr -> sync-docs
```
1. plan: create implementation plan (auto-approve)
2. tdd: tests first (RED -> GREEN -> IMPROVE)
3. code-review: security + quality checks, auto-fix CRITICAL/HIGH
4. handoff-verify: build/test/lint with auto-fix loop (max 5)
5. commit-push-pr: generate message, push, create PR
6. sync-docs: update prompt_plan.md/spec.md/CLAUDE.md/rules

### bugfix
```
explore -> tdd -> handoff-verify -> quick-commit -> sync-docs
```
1. explore: locate root cause
2. tdd: reproduce bug with test, then fix
3. handoff-verify: build/test verification (--once)
4. quick-commit: fast commit + push
5. sync-docs

### refactor
```
refactor-clean -> code-review -> handoff-verify -> commit-push-pr -> sync-docs
```
1. refactor-clean: remove dead code, improve structure
2. code-review: validate refactor
3. handoff-verify: regression verification
4. commit-push-pr: commit + PR (squash recommended)
5. sync-docs

---

## Step 2: Environment Check

Before running the pipeline:
1. Verify git repo (`git rev-parse --is-inside-work-tree`)
2. Detect project type (package.json / go.mod / Cargo.toml / pyproject.toml)
3. Detect package manager (pnpm-lock.yaml / yarn.lock / bun.lockb / npm)

Stop if not a git repo.

---

## Step 3: Execute Pipeline

Run each step sequentially using ultrawork mode.

Rules:
- Move to the next step immediately after completion
- Do not request user confirmation
- Stop only on CRITICAL security issues

### plan auto-approval (feature mode)
1. Draft plan
2. Print plan
3. Auto-approve and continue

### Error handling
- Fixable errors (lint/import/type): auto-fix and continue
- Non-fixable errors (logic/architecture): retry up to 3 times, then report
- CRITICAL security issue: stop and report immediately

---

## Step 4: Summary

Print a single summary at the end.

### On success

Include:
- Steps executed
- Key changes
- PR URL (if created)
- Next recommended command

### On failure

Include:
- Step that failed
- Error summary
- Suggested next action
