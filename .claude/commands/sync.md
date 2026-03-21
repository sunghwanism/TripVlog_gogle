---
description: Git pull + docs sync (pull -> sync-docs v7)
argument-hint: [--no-pull] [--check-only] [work description]
---

# /sync - Git Pull + Docs Sync

## Flags

| Flag | Description |
|------|-------------|
| `--no-pull` | Skip pull and run docs sync only (same as `/sync-docs`) |
| `--check-only` | Show required doc changes without editing |
| (none) | Run pull + docs sync |

## Phase 1: Git Pull (skipped with `--no-pull`)

### 1-1. Check current state

If there are uncommitted changes, warn:
```
You have uncommitted changes. Stash before pull? (Y/n)
```
- Y: `git stash`, pull, then `git stash pop`
- n: attempt pull as-is

### 1-2. Run pull

If conflicts occur, stop and report conflicts. Do not proceed to Phase 2.

## Phase 2: Docs Sync (sync-docs v7)

### 2-0. Mode selection (CRITICAL)

If `--check-only` is set:
- Do not call Write/Edit tools
- Collect only items that require changes
- Use the check-only output format

### 2-1. Work description

Use the argument as the work description.
If missing, infer from the recent commit message.

### 2-2. Analyze changed code

Auto-detect diff range (see `/sync-docs`).
If `NO_COMMITS` is produced, stop with notice.

### 2-3. Sync prompt_plan.md

Search via glob:
- `./prompt_plan.md`
- `./.claude/prompt_plan.md`
- `./docs/prompt_plan.md`

Update:
- Completed task checkmarks
- Progress
- Next steps

### 2-4. Sync spec.md

Search via glob:
- `./spec.md`
- `./docs/spec.md`
- `./.claude/spec.md`

Update:
- Implemented features
- API changes
- Data model changes

### 2-5. Sync CLAUDE.md (60-line limit)

CLAUDE.md must stay <= 60 lines.
If details exceed the limit, move them to rules/.

### 2-6. Sync rules/

Update relevant rules files based on code changes.
Do not create new rules files unless CLAUDE.md must be split (80+ lines).

### 2-7. Final line count check

- <= 60: OK
- 61-80: warning
- > 80: split to rules/

## Output

### Full run (pull + sync)

```
===============================================================
Sync (pull + docs)
===============================================================
Branch: {branch}
Status: {up-to-date | N commits pulled}

Work: {description}

prompt_plan.md  {updated | none | no changes}
spec.md         {updated | none | no changes}
CLAUDE.md       {updated | none | no changes} (N lines)
rules/          {N updated | no changes}

Summary:
  - {item 1}
  - {item 2}

CLAUDE.md: N lines (OK / warning)

Next: /quick-commit
===============================================================
```

### --no-pull (docs only)

```
===============================================================
Sync (docs only)
===============================================================

Work: {description}

Results:
  prompt_plan.md  {updated | none | no changes}
  spec.md         {updated | none | no changes}
  CLAUDE.md       {updated | none | no changes} (N lines)
  rules/          {N updated | no changes}

CLAUDE.md: N lines (OK / warning)

Next: /quick-commit
===============================================================
```

### --check-only

```
===============================================================
Sync (check-only)
===============================================================

Changes needed:
  - [ ] -> [x] Task 3: Implement API endpoint
  - Add POST /api/users to API section

CLAUDE.md (current N lines):
  - Add new command: pnpm db:migrate
  - rules/api-design.md: add POST /api/users

To apply: /sync (without --check-only)
===============================================================
```

### Conflicts during pull

```
Sync (stopped)

[Pull] conflict detected! Resolve manually:
  {conflict files}

After resolution, run:
  /sync --no-pull
```

### No docs to sync

```
===============================================================
Sync
===============================================================
Branch: {branch}
Status: {up-to-date | N commits pulled}

No documents to sync were found.
Check:
  - prompt_plan.md (project root, .claude/, docs/)
  - spec.md (project root, docs/, .claude/)
  - CLAUDE.md (project root, .claude/)
===============================================================
```
