---
description: Incrementally fix TypeScript and build errors one at a time
---

# Build and Fix

> **Note**: If build errors come from an architectural issue, use `/plan` to establish a structural solution first.

Incrementally fix TypeScript and build errors:

1. Run build: npm run build or pnpm build

2. Parse error output:
   - Group by file
   - Sort by severity

3. For each error:
   - Show error context (5 lines before/after)
   - Explain the issue
   - Propose fix
   - Apply fix
   - Re-run build
   - Verify error resolved

4. Stop if:
   - Fix introduces new errors
   - Same error persists after 3 attempts
   - User requests pause

5. Show summary:
   - Errors fixed
   - Errors remaining
   - New errors introduced

Fix one error at a time for safety.

---

## Next steps

| After build fixes | Command |
|:-----------------|:--------|
| Full verification | `/handoff-verify` |
| Quick commit | `/quick-commit` |
| Docs sync | `/sync` |
