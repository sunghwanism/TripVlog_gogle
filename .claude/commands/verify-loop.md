---
allowed-tools: Bash(npm:*), Bash(npx:*), Bash(python:*), Bash(go:*), Bash(cargo:*), Bash(make:*), Bash(git:*), Bash(rm:*), Read, Edit, Grep, Glob
description: Automated verification loop (up to 3 retries with automatic fixes on failure)
argument-hint: [intent description – mandatory if handoff.md is missing] [--max-retries N] [--only build|test|lint]
---

## Task

### Step 0: Parse flags
- `--max-retries N`: limit the retry count (default: 3)
- `--only [type]`: run only a specific validation category
- Remaining arguments describe the intent

### Step 1: Collect the initial environment
1. Run `git status --short` to confirm there are changes (abort if none).
2. Run `git diff --name-only` to list touched files.
3. Read `.claude/handoff.md` if it exists.
4. Read any of `CLAUDE.md`, `spec.md`, `prompt_plan.md` that are present.

### Step 2: Determine the intent
- Prefer `.claude/handoff.md` if available.
- Otherwise rely on the passed intent arguments.
- If both are missing, stop and ask for clarification:
  ```
  ⚠️ Unable to determine intent.
  Retry with `/verify-loop "describe the intent"`.
  ```

### Step 3: Start the verification loop
```
════════════════════════════════════════════════════════════════
🔄 Starting Verification Loop (max_retries: [N])
════════════════════════════════════════════════════════════════
```

Each attempt consists of:

**[Attempt X/N]**

1. **Code review (think carefully)**
   - Inspect `git diff`.
   - Ask: does the change fulfill the intent?
   - Look for logic issues, edge cases, dead code (e.g., stray `console.log`).
   - Watch for security findings.

2. **Automated validation (per project type)**
   - Node.js: `npm run build && npm test && npm run lint`
   - Python: `python -m pytest && python -m flake8`
   - Go: `go build ./... && go test ./...`
   - Rust: `cargo build && cargo test`

3. **Print results**
   ```
   ├── Build: ✅/❌
   ├── Test: ✅/❌ (N errors)
   ├── Lint: ✅/⚠️ (N fixable)
   └── TypeCheck: ✅/❌
   ```

### Step 4: Analyze failures
```
🔍 Analyzing errors...
├── Fixable: N (type)
└── Manual: N (type)
```

**Fixable issues (auto-apply)**
- Missing imports → insert automatically.
- Lint formatting → run `eslint --fix` or `prettier`.
- Unused variables → remove or rename with `_`.
- Simple type mistakes → adjust type hints.

```
🔧 Applying automatic fixes...
├── [description]
└── Done
```

**Manual findings (report only)**
```
⚠️ Manual action required:
  1. [file:line] – [error message]
  2. ...

💡 Suggestion: [resolution advice]
```

### Step 5: Retry or exit

**If retries remain:** after applying fixable changes, continue to the next attempt.

**If `max_retries` is reached:**
```
════════════════════════════════════════════════════════════════
❌ Verification Loop failed after N attempts
════════════════════════════════════════════════════════════════

Repeated failures:
  1. [detailed error]
  2. ...

Recommended actions:
  1. Run /handoff to capture the current state.
  2. /clear and approach with a fresh perspective.
  3. Use /learn --from-error to log lessons.

🎓 Auto-learning trigger: add a pattern to CLAUDE.md
════════════════════════════════════════════════════════════════
```

Append to CLAUDE.md’s `## Learned Rules` section:
```markdown
- [date] [error pattern]: [prevention rule]
```

### Step 6: Success path
1. Remove `.claude/handoff.md` if it exists.
2. Propose saving an automatic checkpoint.
3. Notify the user:
```
════════════════════════════════════════════════════════════════
✅ Verification Loop completed in N attempts
════════════════════════════════════════════════════════════════

Next step: /commit-push-pr --merge
```
