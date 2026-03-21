---
description: Safely identify and remove dead code with test verification
---

# Refactor Clean

> **Note**: For large refactors (expected 3+ files), run `/plan` first (Golden Principle #9: HARD-GATE).

Safely identify and remove dead code with test verification:

1. Run dead code analysis tools:
   - knip: Find unused exports and files
   - depcheck: Find unused dependencies
   - ts-prune: Find unused TypeScript exports

2. Generate a comprehensive report in `.reports/dead-code-analysis.md`

3. Categorize findings by severity:
   - SAFE: Test files, unused utilities
   - CAUTION: API routes, components
   - DANGER: Config files, main entry points

4. Propose safe deletions only

5. Before each deletion:
   - Run full test suite
   - Verify tests pass
   - Apply change
   - Re-run tests
   - Roll back if tests fail

6. Show summary of cleaned items

Never delete code without running tests first.

---

## Next steps

| After refactoring | Command |
|:-----------------|:--------|
| Code review | `/code-review` |
| Build/test verification | `/handoff-verify` |
| Docs sync | `/sync` |
