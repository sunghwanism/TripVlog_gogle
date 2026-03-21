---
allowed-tools: Read, Write, Grep, Glob, Bash(git:*)
description: Post-merge web test checklist + completion tracking (v6)
argument-hint: [--auto-from-handoff] [--detailed] [--save] [--status] [--complete ID]
---

## Task

### Step 0: Collect Context

```bash
git log --oneline -3
git diff HEAD~1 --name-only
git diff HEAD~1 --stat
git branch --show-current
```

Read if present:
- `.claude/handoff.md` (intent, test needs)
- `spec.md` (requirements)
- `prompt_plan.md` (task details)
- `.claude/web-checklist-state.json` (existing checklist)

---

### Step 0.5: Flag Routing

**`--status` -> status mode**

Read `.claude/web-checklist-state.json`:

**If file exists:**
```
===============================================================
Web Checklist Status (v6)
===============================================================

Created: [created timestamp]
Commit: [commit hash]
Branch: [branch name]

Progress: [completion]% ([done]/[total])

## Incomplete
- [ ] [ID: N] [category] [text]
...

## Complete
- [x] [ID: N] [category] [text]
...

Mark complete: /web-checklist --complete [ID]
===============================================================
```
-> Stop

**If file missing:**
```
No saved checklist.

Create: /web-checklist --save
```
-> Stop

---

**`--complete ID` -> mark item complete**

Read `.claude/web-checklist-state.json`:

If ID exists:
- set `items[ID].done = true`
- recompute `completion`
- save file

```
Checklist item completed

ID: [ID]
Text: [text]
Progress: [completion]% ([done]/[total])
```
-> Stop

If ID not found:
```
Checklist item not found: [ID]
```
-> Stop

---

### Step 1: Build Checklist

Use commit diff + handoff/spec/plan to generate items.
If `--auto-from-handoff` is set, prioritize handoff "Tests needed".
If `--detailed` is set, expand into more granular checks.

Categories:
- Functional
- UI/UX
- API
- Data/DB
- Security
- Performance
- Regression

---

### Step 2: Save Checklist (`--save`)

If `--save` is set, write `.claude/web-checklist-state.json` with:
- created timestamp
- commit hash
- branch name
- items array with IDs
- completion = 0

---

### Output (default)

```
===============================================================
Web Checklist (v6)
===============================================================

[ ] [ID: 1] [category] [text]
[ ] [ID: 2] [category] [text]
...

Save checklist: /web-checklist --save
Check status: /web-checklist --status
===============================================================
```
