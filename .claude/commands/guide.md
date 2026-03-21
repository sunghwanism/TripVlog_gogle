---
description: Interactive quick start guide for new users (roughly 3 minutes)
allowed-tools: Read, Glob, Grep, Bash(git:*), Bash(ls:*)
---

# /guide — Interactive onboarding tour

This guide finishes in about three minutes and is tailored for first-time Claude Forge users.

---

## Step 1: Welcome & environment check

Run a quick audit of the current workspace:

1. **Project files**: Look for `package.json`, `go.mod`, `Cargo.toml`, or `pyproject.toml`.
2. **CLAUDE.md**: Check the current or parent directories for the project config file.
3. **Git status**: Verify that a `.git` folder exists.
4. **Onboarding marker**: See if `~/.claude/.forge-onboarded` already exists.

Print the results like this:

```
Welcome to the Claude Forge guide!

Current state:
  Project:    [detected type or "No project files"]
  CLAUDE.md:  [present / missing]
  Git:        [initialized / not initialized]
  Onboarded:  [already done / pending]
```

---

## Step 2: Tailored recommendations

Branch based on the audit results below.

### No project files found

```
This doesn’t look like a project folder yet.

Choose one:
  1. Switch directories and rerun claude where your project lives.
  2. Start a new project with /init-project.
```

### CLAUDE.md missing

```
CLAUDE.md is missing. It teaches Claude Forge your project’s rules.
Run /init-project to generate CLAUDE.md automatically.
```

### Git not initialized

```
Git is not initialized yet.
Initialize it with git init so you can commit and open PRs.
```

### Everything is ready

```
Your project looks ready! Pick a workflow to begin.
```

---

## Step 3: Choose your workflow

```
What would you like to do?

  1. Build a feature
     -> /plan [feature description]
     Example: /plan build a login flow

  2. Fix a bug
     -> /tdd [bug description]
     Example: /tdd fix payment amount returning zero

  3. Clean up code
     -> /refactor-clean
     Automatically remove unused code, duplicates, and noise.

  4. Run a security review
     -> /security-review
     Discover OWASP + CWE issues automatically.

  5. Use the full automation mode
     -> /auto [task description]
     Runs everything from planning to commit in one go.

Top commands:
  /plan           Drafts an implementation plan before coding.
  /tdd            Write the test first, then the code.
  /code-review    Run security + quality checks.
  /handoff-verify Build, test, and lint in one verification run.
  /commit-push-pr Commit, push, open PR, and optionally merge.
  /sync           Sync project docs at session start or end.
```

---

## Step 4: Create the onboarding marker

After printing the guide, mark the user as onboarded:

```bash
touch ~/.claude/.forge-onboarded
```

---

## Step 5: Additional resources

```
Need more guidance?
  docs/FIRST-STEPS.md       — quick terminology + onboarding sequence
  docs/WORKFLOW-RECIPES.md  — five workflow recipes for common scenarios
  setup/GLOSSARY.md         — comprehensive glossary of terms
```
