---
allowed-tools: Bash(git:*), Read, Grep
description: Create a Git Worktree for parallel development + domain template (v6)
argument-hint: [branch name] [--type feature|bugfix|refactor]
---

## Task

### Step 0: Environment Check

```bash
git rev-parse --git-dir
git worktree list
git branch -a
```

**If not a git repo:**
```
Not a git repo.
Run git init first.
```
-> Stop

### Step 0.5: Conflict Prevention Checks

```bash
# Check if Claude Code auto-generated files are in .gitignore
grep -E "\.claude/context/|\.claude/settings" .gitignore 2>/dev/null

# Check tracked Claude Code files
git ls-files | grep "^\.claude/"
```

**If Claude Code files are missing from .gitignore:**
```
Conflict prevention required
========================================

In parallel worktrees, Claude Code auto-generated files can
cause merge conflicts.

Add to .gitignore:
  .claude/context/
  .claude/settings.json
  .claude/settings.local.json

Auto-add commands:
  cat >> .gitignore << 'EOF'
  # Claude Code auto-generated files (conflict prevention)
  .claude/context/
  .claude/settings.json
  .claude/settings.local.json
  EOF
  git add .gitignore
  git commit -m "chore: add Claude Code generated files to .gitignore"

Continue? [y/N]
========================================
```
-> Wait for user response

**If Claude Code files are tracked by Git:**
```
Claude Code files are tracked by Git
========================================

These files are tracked and can cause merge conflicts:
[git ls-files output]

Untrack commands:
  git rm -r --cached .claude/context/
  git add .gitignore
  git commit -m "chore: stop tracking Claude Code generated files"

Continue? [y/N]
========================================
```
-> Wait for user response

### Step 1: Parse Arguments

**Extract options from $ARGUMENTS:**
- `--type feature` -> workflow type: feature (default)
- `--type bugfix` -> workflow type: bugfix
- `--type refactor` -> workflow type: refactor
- Remaining text -> branch name

**Determine branch name:**

**If branch name is provided:**
- If it lacks `feature/`, `fix/`, or `refactor/`, add a prefix by type:
  - `--type feature` (default) -> `feature/`
  - `--type bugfix` -> `fix/`
  - `--type refactor` -> `refactor/`
- Example: `auth --type bugfix` -> `fix/auth`

**If branch name is missing:**
```
Please provide a branch name.

Usage: /worktree-start auth
       /worktree-start feature/payment
       /worktree-start fix/login-bug
       /worktree-start refactor/utils --type refactor
```
-> Stop

### Step 2: Create Worktree

```bash
# Create in parent directory based on current dir name
# Example: /Users/dev/myproject + feature/auth -> /Users/dev/myproject-auth
BRANCH_NAME="[resolved branch name]"
WORKTREE_DIR="../$(basename $(pwd))-${BRANCH_NAME##*/}"

# Check if branch exists
git show-ref --verify --quiet refs/heads/$BRANCH_NAME
```

**If branch does not exist (new work):**
```bash
git worktree add -b $BRANCH_NAME $WORKTREE_DIR
```

**If branch exists (continue work):**
```bash
git worktree add $WORKTREE_DIR $BRANCH_NAME
```

### Step 3: Domain Detection

After worktree creation, detect project domain:

```bash
# Analyze project files
ls package.json pyproject.toml go.mod Cargo.toml Makefile 2>/dev/null
ls next.config.* nuxt.config.* vite.config.* 2>/dev/null
ls tsconfig.json 2>/dev/null
```

**Domain mapping:**

| Detected files | Domain | Framework |
|---------------|--------|-----------|
| `next.config.*` + `package.json` | Node.js/TypeScript | Next.js |
| `nuxt.config.*` + `package.json` | Node.js/TypeScript | Nuxt.js |
| `vite.config.*` + `package.json` | Node.js/TypeScript | Vite (React/Vue) |
| `package.json` (only) | Node.js | Express/other |
| `pyproject.toml` / `setup.py` | Python | Django/FastAPI/other |
| `go.mod` | Go | Go service |
| `Cargo.toml` | Rust | Rust service |
| `Makefile` (only) | Generic | Make project |

### Step 4: Completion Message

```
===============================================================
Worktree Created (v6)
===============================================================

Path: [WORKTREE_DIR absolute path]
Branch: [BRANCH_NAME]
Domain: [detected domain] ([framework])

Next steps (in a new terminal):
  cd [WORKTREE_DIR absolute path]
  claude

Parallel work tips:
  • Work independently in each worktree
  • When done: /handoff-verify
  • After PR merges: /worktree-cleanup

Current worktrees:
[git worktree list output]
===============================================================
```

### Error Handling

**Worktree directory already exists:**
```
Directory already exists: [path]

Options:
1. Work in that directory: cd [path] && claude
2. Delete and recreate: rm -rf [path] && /worktree-start [branch]
```

**Branch is checked out in another worktree:**
```
Branch '[branch]' is used by another worktree.

[git worktree list output]

Use a different branch name or clean up the existing worktree:
  /worktree-cleanup [branch]
```

---
