---
allowed-tools: Read, Glob, Write
description: Suggest useful automations based on repo context
argument-hint: [--dry-run]
---

# /suggest-automation

## Goal

Propose helpful recurring automations based on project context.

## Steps

1. Inspect project docs and recent activity:
   - CLAUDE.md, spec.md, prompt_plan.md
   - recent commits
   - existing automations (if available)

2. Identify repetitive tasks:
   - daily/weekly reports
   - dependency updates
   - test/verification checks
   - doc syncs
   - issue triage

3. Propose 1-3 automations with clear value.

## Output

For each suggestion, include:
- Name
- Purpose
- Schedule (human-readable)
- Workspace(s) used
- Expected output

If `--dry-run` is set, do not create automations; only show suggestions.
