---
allowed-tools: Read, Write, Edit, Grep, Glob, Bash(git:*)
description: Sync prompt_plan.md, spec.md, CLAUDE.md + rules/ docs (v7)
argument-hint: [--check-only]
---

# /sync-docs - Docs Sync (v7)

---

## Step 0: Confirm Work Description

Use the argument as the work description. If missing, infer from recent commits:

```bash
git log --oneline -5
```

---

## Step 1: Mode Selection (CRITICAL)

If `--check-only` is set:
- **Do not call any Write/Edit tools.**
- Only collect items that need changes.
- Use the check-only output format (Step 9).

This mode applies to all subsequent steps. In check-only mode, only Read/Glob/Grep/Bash(git) are allowed.

---

## Step 2: Analyze Changed Code

Identify changed files and content on the current branch.

**Auto-detect diff scope:**

```bash
# Prefer merge base with main/master
BASE=$(git merge-base HEAD main 2>/dev/null || git merge-base HEAD master 2>/dev/null)
if [ -n "$BASE" ] && [ "$BASE" != "$(git rev-parse HEAD)" ]; then
  git diff --name-only "$BASE"..HEAD
  git diff --stat "$BASE"..HEAD
else
  # If no merge base (on main), use recent commits
  COMMIT_COUNT=$(git rev-list --count HEAD 2>/dev/null || echo "0")
  if [ "$COMMIT_COUNT" -eq 0 ]; then
    echo "NO_COMMITS"
  elif [ "$COMMIT_COUNT" -ge 3 ]; then
    git diff --name-only HEAD~3..HEAD
    git diff --stat HEAD~3..HEAD
  else
    git diff --name-only HEAD~1..HEAD
    git diff --stat HEAD~1..HEAD
  fi
fi
```

If `NO_COMMITS` is printed, there is nothing to sync -> notify and stop.

---

## Conflict Resolution Principle

Source code (git diff) is the source of truth. If docs disagree, update docs to match code.

---

## Step 3: Sync prompt_plan.md

Search for `prompt_plan.md`:
- `./prompt_plan.md`
- `./.claude/prompt_plan.md`
- `./docs/prompt_plan.md`

Update items:
- Check completed tasks (`- [x]`)
- Update progress status
- Update next steps

Skip if file not found.

---

## Step 4: Sync spec.md

Search for `spec.md`:
- `./spec.md`
- `./docs/spec.md`
- `./.claude/spec.md`

Update items:
- Implemented features
- API changes
- Data model changes

Skip if file not found.

---

## Step 5: Sync CLAUDE.md (60-line limit)

Search for `CLAUDE.md`:
- project root
- `.claude/`
- `docs/`

**60-line rule (CRITICAL):**
- Keep CLAUDE.md <= 60 lines
- Only core info: overview, tech stack, essential commands, key directories, Git workflow, rules references
- Detailed coding conventions, test rules, API design, security, DB patterns -> move to rules/

Sync behavior:
1. Read CLAUDE.md and count lines
2. Reflect build commands/file structure/deps changes
3. Route detailed rules to rules/ files (Step 6)
4. If > 60 lines, split details to rules/

---

## Step 6: Sync rules/

Sync `.claude/rules/` files with code changes.

Rules:
- If a relevant rules file exists, update it
- If not, do not create new rules files (only note)
- Exception: if CLAUDE.md exceeds 80 lines and must be split, create a new rules file

---

## Step 7: Final CLAUDE.md Line Check

| Line count | Status | Action |
|------------|--------|--------|
| <= 60 | OK | Done |
| 61-80 | Warning | Warn, suggest split |
| > 80 | Exceeded | Split details to rules/ |

---

## Step 8: Output (Normal)

```
===============================================================
Docs Sync (v7)
===============================================================
Branch: {branch}
Status: {up-to-date | N commits pulled}

Work: {work description}

prompt_plan.md  {updated | none | no changes}
spec.md         {updated | none | no changes}
CLAUDE.md       {updated | none | no changes} (N lines)
rules/          {N updated | no changes}

Summary of changes:
  - {item 1}
  - {item 2}

CLAUDE.md: N lines (OK / Warning: over 60 lines)

Next: /quick-commit
===============================================================
```

---

## Step 9: Output (--check-only)

```
===============================================================
Docs Sync (check-only)
===============================================================

Work: {work description}

Changes needed:
  - [ ] -> [x] Task 3: Implement API endpoint
  - Add POST /api/users to API section

CLAUDE.md (current N lines):
  - Add new command: pnpm db:migrate
  - rules/api-design.md: add POST /api/users

To apply: /sync-docs (without --check-only)
===============================================================
```

---

## If No Docs Found

```
===============================================================
Docs Sync (v7)
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
