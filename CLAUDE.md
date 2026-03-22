# CLAUDE.md

## Project Overview
The Trip Vlog AI Generator is an automated video production service that transforms raw footage stored in Google Drive into professional-grade trip vlogs. By connecting a specific Google Drive folder and providing a "concept prompt," the system analyzes personal media, creates a cinematic storyboard, fetches YouTube references for style, and uses Veo 3 to generate a cohesive final video complete with captions and BGM.

## AI Video Generation Pipeline Reference Guide

| Phase | Action | Primary Assignees |
|:---:|:---|:---|
| **01** | **Data & Analysis** | BackendEngineer, AI Engineer |
| **02** | **Narrative & Reference**| AI Engineer, BackendEngineer |
| **03** | **Synthesis & Audio** | AI Engineer, Devops/QA |
| **04** | **Encoding & Deploy** | Devops/QA, FrontEngineer |


## Tech Stack
- **Frontend**: React/Vue (UI Components, Google Drive Auth logic)
- **Backend**: Node.js / Python (Core API, XMP/EXIF Extraction, Database)
- **AI / LLM**: Gemini 1.5 Pro (Visual Analysis, Storyboard JSON mapping)
- **Video Synthesis**: Veo 3 (Neural Stitching, Cross-dissolve math, Audio Sync)
- **External APIs**: Google Drive OAuth, YouTube Data API v3
- **Infrastructure / QA**: GCP Cloud Run, FFmpeg pipeline, Playwright E2E

---
## Rules (Auto-loaded from `.claude/rules/`)

| Rule | Summary |
|------|---------|
| `golden-principles.md` | Core execution principles for the 6-agent developer squad |
| `coding-style.md` | Immutability, robust error handling, schema validation for AI payloads |
| `interaction.md` | Conclusion-first status updates for complex video synthesis flows |
| `verification.md` | No completion claims without firm Playwright E2E test evidence |
| `security.md` | Strict Google Drive/YouTube API secret management via env vars ONLY |
| `testing.md` | TDD mandatory: 80% coverage on all Python synthesis + TS API routes |
| `git-workflow-v2.md` | Standardized PR flow enforced rigorously by the Team Leader agent |
| `date-calculation.md` | Always use `python3` for exact video duration logic (no LLM mental math) |
| `agents-v2.md` | Agent orchestration protocols delegating to the 5 pipeline engineers |

---
## Agents (`.claude/agents/`)

| Agent | Role / Trigger Scenario |
|-------|---------|
| `team-leader` | Orchestrator. Triggers on new requests / PR reviews. |
| `front-engineer` | UI/UX, React/Vue, and client-side Google Drive auth logic. |
| `backend-engineer`| Core API, DB schema, async API communication. |
| `ai-engineer` | Gemini 1.5 Pro prompts and Veo 3 Video Stitching mathematics. |
| `devops-qa` | GCP Cloud Run FFmpeg, E2E Playwright tests, CI/CD logic. |
| `independent-reviewer`| Devil's Advocate explicitly checking Agents 1-4 for logical flaws and security risks. |

Use `/orchestrate` to coordinate these agents automatically.

---
## Critical Workflow Rules

1. **Agent Orchestration** — The Team Leader MUST decompose tasks before allocating work to Frontend, Backend, AI, or DevOps agents via explicit boundaries.
2. **Review Clearance** — The Independent Reviewer must actively stress-test logic flows and security structures before final architectural approval.
3. **TDD Mandatory** — RED → GREEN → IMPROVE. At least 80% test coverage is required on all video processing pipelines.
4. **Zero Hardcoded Secrets** — Google Drive, Gemini, and YouTube API credentials must ONLY be read from `process.env`.
5. **No AI Mental Math** — Temporal spacing and audio synchronization logic must be explicitly solved via Python calculation scripts.
6. **Surgical Output** — Agents execute only what they are assigned. Do not bleed into another agent's dedicated domain.

---
## When Stack is Defined

Update this file with:
- Build, lint, test commands
- Dev server instructions
- Env var setup (Google Drive API credentials)
- Architecture overview of the video processing pipeline

## Condition
- If you have any question, ask the user
- If you need to use any tool, information, ask the user