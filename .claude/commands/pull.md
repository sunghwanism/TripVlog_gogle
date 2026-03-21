---
allowed-tools: Bash(git:*)
description: Run git pull origin main quickly
---

# /pull - Git Pull (Quick)

---

## Step 1: Check Current State

```bash
git branch --show-current
git status --short
```

If there are uncommitted changes, warn:
```
You have uncommitted changes. Stash before pull? (Y/n)
```
- Y: `git stash`, pull, then `git stash pop`
- n: attempt pull as-is

---

## Step 2: Run Pull

```bash
git pull origin main
```

---

## Step 3: Output

### On success

```
===============================================================
  Git Pull
===============================================================

  Branch: {branch}
  Status: {up-to-date | N commits pulled}

===============================================================
```

### On conflict

```
===============================================================
  Git Pull
===============================================================

  Conflict detected! Manual resolution required:
  {conflict files}

===============================================================
```
