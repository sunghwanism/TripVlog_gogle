---
allowed-tools: Bash(git:*), Bash(gh:*), Read, Write, Glob, Grep
description: Update Claude Forge installation (v6)
argument-hint: [--preview] [--no-pull] [--no-backup]
---

# /forge-update - Update Claude Forge (v6)

## Goal

Safely update the Claude Forge install and project templates.

## Steps

1. **Collect context**
   - Current version (if available)
   - Git status and remote
   - Installed locations

2. **Preview mode (`--preview`)**
   - Show what would change
   - Do not modify files

3. **Pull updates (unless `--no-pull`)**
   - Fetch latest from upstream
   - Show diff summary

4. **Backup (unless `--no-backup`)**
   - Create a backup of current config and templates

5. **Apply updates**
   - Update commands, skills, hooks, rules
   - Update templates and docs

6. **Post-update checks**
   - Ensure required files exist
   - Report any conflicts or missing items

## Output

Provide:
- Updated components list
- Backup location (if created)
- Any manual steps needed
