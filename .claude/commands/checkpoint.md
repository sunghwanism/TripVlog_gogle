---
allowed-tools: Bash(git:*), Bash(mkdir:*), Bash(rm:*), Bash(cp:*), Read, Write
description: Save/restore work state (v6)
argument-hint: save|restore|list|diff|delete ["name"] [--tag tag]
---

# /checkpoint - Save and Restore Work State (v6)

---

## Step 0: Parameter parsing

| Subcommand | Description | Required |
|-----------|-------------|----------|
| `save` | Save current state | "name" |
| `restore` | Restore a saved state | "name" |
| `list` | List saved checkpoints | none |
| `diff` | Compare checkpoints | "name" |
| `delete` | Delete a checkpoint | "name" |

Options:
- `--tag tag`: attach a tag to the checkpoint (e.g., `--tag stable`, `--tag pre-refactor`).

---

## Step 1: Storage path

Checkpoint directory structure:

```
.claude/checkpoints/
  {name}/
    metadata.json
    staged.patch      # staged changes
    unstaged.patch    # unstaged changes
    untracked/        # copies of untracked files
```

Create the directory if it does not exist:

```bash
mkdir -p .claude/checkpoints
```

---

## Step 2: `save` subcommand

### 2-1. Collect current state

```bash
# current branch
git branch --show-current

# current commit
git rev-parse --short HEAD

# staged changes
git diff --cached > .claude/checkpoints/{name}/staged.patch

# unstaged changes
git diff > .claude/checkpoints/{name}/unstaged.patch

# change stats
git diff --stat HEAD

# list untracked files
git ls-files --others --exclude-standard
```

### 2-2. Copy untracked files

If untracked files exist, copy them into the checkpoint:

```bash
mkdir -p .claude/checkpoints/{name}/untracked
# copy each untracked file while preserving directory structure
```

### 2-3. Write metadata

```json
{
  "name": "feature-complete",
  "timestamp": "2026-02-07T15:30:00Z",
  "branch": "feature/auth",
  "commit": "abc1234",
  "files": [
    "src/auth/login.ts",
    "src/auth/register.ts"
  ],
  "stats": {
    "additions": 45,
    "deletions": 12,
    "files_changed": 3,
    "untracked_count": 1
  },
  "tags": ["stable"],
  "auto": false,
  "v6_metadata": {
    "security_status": "pass"
  }
}
```

v6_metadata field:
- `security_status`: last security review result (pass/fail/unknown)

### 2-4. Auto checkpoints

Create automatic checkpoints when:
- before `/commit-push-pr`
- after `/handoff-verify` fails 3 times

Set `auto` to `true`.
Name format: `auto-{YYYYMMDD-HHmmss}`

---

## Step 3: `restore` subcommand

### 3-1. Confirm checkpoint exists

```bash
ls .claude/checkpoints/{name}/metadata.json
```

### 3-2. Backup current state

Before restore, auto-save the current state as `pre-restore-{timestamp}`.

### 3-3. Apply restore

```bash
# restore staged changes
git apply .claude/checkpoints/{name}/staged.patch
git add -A

# restore unstaged changes
git apply .claude/checkpoints/{name}/unstaged.patch

# restore untracked files
cp -r .claude/checkpoints/{name}/untracked/* ./ 2>/dev/null
```

### 3-4. Verify restore

Compare the working tree against metadata to ensure it matches.

---

## Step 4: `list` subcommand

List all checkpoints in time order and print summary info from each `metadata.json`.

---

## Step 5: `diff` subcommand

Show differences between the selected checkpoint and current state:

```bash
# compare checkpoint commit vs current commit
git diff {checkpoint_commit}..HEAD --stat
```

---

## Step 6: `delete` subcommand

Delete the checkpoint directory:

```bash
rm -rf .claude/checkpoints/{name}
```

Show checkpoint contents and ask for confirmation before deletion.

---

## Step 7: Output

### On `save` success

```
════════════════════════════════════════════════════════════════
  Checkpoint v6 - Save
════════════════════════════════════════════════════════════════

  Name: feature-complete
  Branch: feature/auth
  Commit: abc1234
  Changes: +45 -12 (3 files)
  Tags: stable

  Path: .claude/checkpoints/feature-complete/

════════════════════════════════════════════════════════════════
```
