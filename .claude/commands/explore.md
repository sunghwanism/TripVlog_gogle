---
allowed-tools: Read, Grep, Glob, Bash(git:*)
description: Explore code and gather context before implementation
argument-hint: [query]
---

# /explore - Code Exploration

## Goal

Quickly locate relevant code, understand structure, and identify change points.

## Steps

1. **Collect context**
   - `git status --short`
   - recent commits (`git log --oneline -5`)
   - project docs if present: `CLAUDE.md`, `spec.md`, `prompt_plan.md`

2. **Search for the query**
   - Use `rg` for symbols/strings
   - Use `rg --files` for file discovery

3. **Map the flow**
   - Identify entry points
   - Trace call sites and dependencies
   - Note relevant tests

4. **Summarize**
   - Key files and responsibilities
   - Potential change locations
   - Risks/unknowns

## Output

Provide:
- Short summary of what you found
- List of key files
- Suggested next action (implement/test/plan)
