---
allowed-tools: Read, Grep, Glob
description: Recommend the next task (v6)
argument-hint: [--from-plan]
---

# /next-task - Prepare to Start the Next Task (v6)

## Step 0: Check Current State

Collect the following:

1. **Git status**
   - Current branch: `git branch --show-current`
   - Last 3 commits: `git log --oneline -3`
   - Staged/modified files: `git status --short`

2. **Project docs**
   - Whether `prompt_plan.md` exists and its last modified time
   - Whether `spec.md` exists
   - Whether `CLAUDE.md` exists

If docs are missing, print a warning:
```
[WARN] prompt_plan.md is missing.
  Run /planner to generate a plan first.
```

## Step 1: Calculate Progress

Parse task checkboxes from `prompt_plan.md`:

```
Parsing rules:
  - [x] or - [X]  -> done
  - [ ]           -> not done
  Nested checkboxes (sub-items) are not counted separately.
  Count only top-level tasks.
```

Progress:
```
completed = number of [x]
total     = [x] + [ ]
rate      = (completed / total) * 100
```

## Step 2: Identify the Next Task

Select a task with the following priority:

1. **User specified**: If a task number/description is provided as an argument
2. **Dependency ready**: Incomplete tasks whose depends are all done
3. **Order based**: The first incomplete `- [ ]` task in prompt_plan.md

For the selected task, find related files:
- File paths mentioned in the task description
- Existing files in the module/directory (via Glob)
- Related test files

## Step 3: Complexity Assessment

Assess task complexity and recommend size.

| Signal | Size | Criteria |
|--------|------|----------|
| Simple edit, config change, docs update | S | 1-2 files, < 50 lines expected |
| Normal implementation, component add, API endpoint | M | 3-5 files, 50-200 lines expected |
| Refactor, complex feature, multi-module changes | L | 6+ files, 200+ lines expected |
| Security/auth/payment, data migration | XL | Security sensitive or hard to roll back |

Recommendation factors:
- Keywords in the task description (`security`, `auth`, `payment` -> size up)
- File count and size
- Depth of depends chain (deeper -> size up)

## Step 4: Output

```
===============================================================
 Next Task (progress: [completed]/[total] = [rate]%)
===============================================================

Next task: [Task number]. [Task name]
Size: [S/M/L]
Reason: [one-line explanation]

Related files:
  - [file path 1]
  - [file path 2]
  - [file path 3]

Prerequisite tasks done:
  [x] [Task A]
  [x] [Task B]

How to start:
  Start in this session
  Or /orchestrate --type feature (Agent Teams parallel build)

===============================================================
```

### If all tasks are complete

```
===============================================================
 All Tasks Complete (progress: [total]/[total] = 100%)
===============================================================

All tasks are complete.

Next steps:
  /handoff-verify     final verification
  /sync-docs          docs sync
  /web-checklist      manual test checklist

===============================================================
```

### Change detection notice

If prompt_plan.md changed since the last commit:
```
[INFO] prompt_plan.md changed recently.
  Changed at: [timestamp]
  The task list may have been updated.
```
