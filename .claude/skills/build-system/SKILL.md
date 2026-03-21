---
name: build-system
description: Diagnose and fix build and CI failures
---

# Build System Skill

## When to Use

Use when build, test, or CI pipelines fail.

## What It Does

- Detects project type and build tools
- Runs build/test/lint in a safe order
- Identifies root causes
- Proposes minimal fixes

## Workflow

1. Identify build toolchain (Node/Go/Rust/Python/etc.)
2. Reproduce the failure
3. Inspect logs and failing files
4. Apply the smallest safe fix
5. Re-run build/test to verify
