---
allowed-tools: Bash(git:*), Read, Grep
description: Quick commit for small edits (v6)
argument-hint: [commit message]
---

# /quick-commit - Quick Commit (v6)

---

## Step 0: Message Check

Confirm a commit message was provided as an argument.
If missing, print an error and exit.

```
Usage: /quick-commit "commit message"
```

---

## Step 1: Check Changes

```bash
git status --short
git diff --stat
```

If there are no changes, print an error and exit.

Change size check:
- If more than 3 files or more than 20 lines changed, warn:
  ```
  This is a large change. Full workflow recommended:
  /handoff-verify -> /commit-push-pr

  If you still want a quick commit, type "continue".
  ```

---

## Step 2: Quick Verification

Review the change with `git diff`:
- Check only for obvious errors
- If issues exist, explain and stop

---

## Step 3: Commit

```bash
git add -A
git commit -m "{message}"
git push
```

---

## Step 4: Output

### On success

```
===============================================================
  Quick Commit v6
===============================================================

  Commit: {short_hash}
  Message: {message}
  Changes: +{N} -{N} ({N} files)

  Next step: /sync (git pull + docs sync)

===============================================================
```

### If message is missing

```
===============================================================
  Quick Commit v6
===============================================================

  A commit message is required.

  Usage: /quick-commit "fix: typo"

===============================================================
```

### If there are no changes

```
===============================================================
  Quick Commit v6
===============================================================

  No changes to commit.
  git status: clean

===============================================================
```
