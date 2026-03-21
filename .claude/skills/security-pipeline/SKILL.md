---
name: security-pipeline
description: End-to-end security review pipeline
---

# Security Pipeline Skill

## When to Use

Use for security-sensitive changes or before merging critical code.

## What It Does

- Scans code for common vulnerabilities
- Tags findings with CWE IDs
- Suggests fixes and mitigation
- Produces a clear summary report

## Workflow

1. Identify changed files and sensitive areas
2. Run pattern-based scans and targeted checks
3. Evaluate severity (Critical/High/Medium/Low)
4. Recommend remediation steps
5. Provide a final pass/fail assessment
