---
allowed-tools: Read, Grep, Glob
description: Review code for quality, security, and regressions
argument-hint: [file/dir]
---

# /code-review

## Goal

Perform a focused code review to find bugs, risks, and missing tests.

## Steps

1. Identify target files (argument, git diff, or recent edits)
2. Read relevant code and tests
3. Check for:
   - Correctness and edge cases
   - Security issues
   - Performance regressions
   - Missing tests
   - Style or maintainability risks
4. Summarize findings in order of severity

## Output

- Findings with file/line references
- Risk assessment
- Suggested fixes or tests
