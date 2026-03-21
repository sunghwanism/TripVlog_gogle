---
allowed-tools: Bash(git:*), Read, Grep
description: Clean up Git Worktrees after PR completion (v6)
argument-hint: [branch name - defaults to current worktree]
---

## Task

### Step 0: Environment Check

```bash
git rev-parse --git-dir
git worktree list
git branch --show-current
pwd
```

### Step 1: Decide Cleanup Target

**If $ARGUMENTS is provided:**
- Find the worktree for that branch

**If $ARGUMENTS is missing:**
- Check whether the current directory is a worktree
- If this is the main repo:
  ```
  Please specify which worktree to clean up.

  Current worktrees:
  [git worktree list output]

  Usage: /worktree-cleanup feature/auth
  ```
  -> Stop

### Step 2: Check PR Status

```bash
gh pr view --json state,mergedAt 2>/dev/null
```

**PR merged:**
-> Continue cleanup

**PR still open:**
```
PR has not been merged yet.

PR status: [Open/Draft]
PR URL: [URL]

Options:
1. "continue" - force cleanup (risk of losing changes)
2. "cancel" - retry after merge
```

**No PR found (gh CLI missing or no PR):**
```
Unable to check PR status.

Confirm changes are pushed:
  git log origin/[branch]..HEAD

Options:
1. "continue" - force cleanup
2. "cancel" - retry after verification
```

### Step 3: Remove Worktree

**If running inside the target worktree:**
```
Cannot clean up from inside the current worktree.

Move to the main repo and run:
  cd [main repo path]
  /worktree-cleanup [branch]
```
-> Stop

**From the main repo:**
```bash
# Remove worktree
git worktree remove [worktree path]

# Delete branch if merged
git branch -d [branch]

# Delete remote branch (if merged)
git push origin --delete [branch] 2>/dev/null || true
```

### Step 3.5: Checklist State Cleanup

Check `.claude/web-checklist-state.json` in the worktree:

**If the file exists:**
- Read completion rate
- Warn if there are unfinished items

```
Checklist status: [completion]% ([done]/[total])
```

If unfinished items exist:
```
Unfinished checklist items [N]:
  - [ID:N] [text]
  - [ID:N] [text]

After cleanup, this cannot be recovered.
```

### Step 4: Worktree Stats

Collect stats for the worktree session:

```bash
# Number of commits in the worktree branch
git log --oneline [base]...[branch] | wc -l

# Number of changed files
git diff [base]...[branch] --stat | tail -1
```

### Step 5: Completion Message

```
===============================================================
Worktree Cleanup Complete (v6)
===============================================================

Deleted: [worktree path]
Branch: [branch] (deleted)

Worktree stats:
  Commits: [N]
  Changed files: [N]
  Added/Deleted: +[N] / -[N]

Remaining worktrees:
[git worktree list output]

Next:
  /worktree-start [new feature] | /next-task
===============================================================
```

### Error Handling

**Uncommitted changes in the worktree:**
```
There are uncommitted changes.

[git status output]

Options:
1. Commit changes and retry
2. Force delete: git worktree remove --force [path]
```

**Branch not merged (deletion failed):**
```
Branch is not merged, so it was not deleted.

Only the worktree was removed.
Force delete branch: git branch -D [branch]
```

---

## Usage Examples

```bash
# Clean up the current worktree (from main repo)
/worktree-cleanup feature/auth

# Clean up by branch name
/worktree-cleanup fix/login-bug

# List worktrees, then clean up
 git worktree list
/worktree-cleanup [target branch]
```
