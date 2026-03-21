---
description: Show current Claude Forge install status and project info
argument-hint: ""
allowed-tools: ["Bash", "Read", "Glob"]
---

# /show-setup

Show current Claude Forge install status and project info.

## Instructions

### 1. Claude Forge install status

1. Count agents in ~/.claude/agents/
2. Count commands in ~/.claude/commands/
3. Count skills in ~/.claude/skills/
4. Count hooks in ~/.claude/hooks/
5. Count rules in ~/.claude/rules/

### 2. Current project status (when run in a project folder)

1. Detect project type (package.json / go.mod / Cargo.toml / pyproject.toml)
2. Git status (branch, last commit, number of changed files)
3. Whether CLAUDE.md exists
4. Whether tests are configured

### 3. Recommended next action

Suggest the most suitable next command based on project state:

- If there are changes -> `/handoff-verify`
- If CLAUDE.md is missing -> `/init-project`
- If tests are missing -> `/tdd`
- If all good -> `/plan [next feature]`

## Output Format

```
My Claude Forge Setup
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Agents:   XX
Commands: XX
Skills:   XX
Hooks:    XX
Rules:    XX
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Current project: [project name]
  Type: [Node.js / Go / Python / ...]
  Branch: [main]
  Last commit: [commit message]
  Changed files: [N]

Recommended next action: [command]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
github.com/sangrokjung/claude-forge
```

## Clipboard

After displaying the summary, copy it to the system clipboard:
- macOS: `pbcopy`
- Linux/WSL: `xclip -selection clipboard` or `xsel --clipboard`

Tell the user the summary is copied and ready to share.
