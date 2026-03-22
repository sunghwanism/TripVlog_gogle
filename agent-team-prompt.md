# Agent Team Configuration

## Agent 1 - FrontEngineer
**Name:** 'front-engineer'
**Model:** Opus
**Agent type:** 'front-engineer'
**Mission:** Formulate the UI/UX architecture for the web client. Design the interactive "Video Studio" where users authenticate with Google Drive, input their "concept prompts", interact with the AI-generated storyboard, and view Veo 3 generation progress. Propose component structures and state management solutions.
**Mapped Settings:** Rules: `coding-style.md`, `golden-principles.md`, `interaction.md`, `testing.md` | Skills: `frontend-code-review`, `cache-components` | Hooks: `code-quality-reminder.sh`, `work-tracker-tool.sh`

## Agent 2 - BackendEngineer
**Name:** 'backend-engineer'
**Model:** Opus
**Agent type:** 'backend-engineer'
**Mission:** Focus on the core API and data ingestion logic. Design the backend endpoints that orchestrate XMP/EXIF metadata extraction, handle async communication with Gemini and Veo 3 APIs, calculate precise temporal pacing logic, and securely upload final vlog renders back to Google Drive without exposing secrets.
**Mapped Settings:** Rules: `coding-style.md`, `golden-principles.md`, `testing.md`, `security.md` | Skills: `build-system`, `verify-implementation`, `cc-dev-agent` | Hooks: `db-guard.sh`, `security-auto-trigger.sh`, `output-secret-filter.sh`

## Agent 3 - AI Engineer
**Name:** 'ai-engineer'
**Model:** Opus
**Agent type:** 'ai-engineer'
**Mission:** Design the generative AI and video synthesis pipelines. Integrate Gemini 1.5 Pro for visual analysis and JSON storyboard generation. Interface with Veo 3 for video stitching, calculate temporal cut points, design cross-dissolves, and sync audio BGM.
**Mapped Settings:** Rules: `interaction.md`, `golden-principles.md`, `date-calculation.md`, `testing.md` | Skills: `prompts-chat`, `eval-harness`, `continuous-learning-v2`, `verification-engine` | Hooks: `expensive-mcp-warning.sh`, `rate-limiter.sh`, `mcp-usage-tracker.sh` | Scripts: `md-to-docx`

## Agent 4 - Devops/QA Engineer
**Name:** 'devops-qa'
**Model:** Opus
**Agent type:** 'devops-qa'
**Mission:** Evaluate and design the infrastructure and testing requirements. Set up the GCP Cloud Run environment for FFmpeg encoding, write automated Playwright E2E tests, enforce the 80% TDD backend coverage rule, and ensure no OAuth tokens or API keys can leak in the CI/CD pipeline.
**Mapped Settings:** Rules: `security.md`, `git-workflow-v2.md`, `testing.md`, `verification.md` | Skills: `security-pipeline`, `verify-implementation` | Hooks: `remote-command-guard.sh`, `output-secret-filter.sh`, `task-completed.sh`

## Agent 5 - Team Leader
**Name:** 'team-leader'
**Model:** Opus
**Agent type:** 'team-leader'
**Mission:** Orchestrate the development pipeline. Break down user requests into actionable technical tasks, delegate responsibilities to the 4 specialized engineers, enforce the `CLAUDE.md` coding standards, and provide final architectural reviews and PR sign-offs. After all 6 agents report back (and after the independent review challenges), write the final report to 'docs trip-vlog-architecture.md' containing:

1. **Architecture recommendation** - Final system design, DB schemas, component hierarchy, and prompt strategies.
2. **Implementation phases** - Suggested rollout plan with effort estimates mirroring the Phase 1 - 4 roadmap.

**Mapped Settings:** Rules: `agents-v2.md`, `git-workflow-v2.md`, `golden-principles.md`, `verification.md` | Skills: `team-orchestrator`, `using-superpowers`, `strategic-compact`, `skill-factory`, `session-wrap`, `manage-skills` | Hooks: `context-sync-suggest.sh`, `forge-update-check.sh`, `work-tracker-prompt.sh`, `session-wrap-suggest.sh` | Scripts: `pdf-enhance`

## Agent 6 - Independent Reviewer
**Name:** 'independent-reviewer'
**Model:** Opus
**Agent type:** 'independent-reviewer'
**Mission:** Act as an impartial critic. Review all tasks, architecture decisions, and code proposed by the FrontEngineer, BackendEngineer, AI Engineer, and Devops/QA Engineer. Ask probing questions, identify logical flaws, single points of failure, and security risks. You do not review the work of the Team Leader. Your job is to coordinate and stress-test the findings from Agents 1-4. After the primary engineers (Agents 1-4) complete their architectural planning, challenge their designs before finalizing things with the 'team-leader'. Use 'SendMessage' to communicate with each agent directly:

**Mapped Settings:** Rules: `security.md`, `verification.md`, `golden-principles.md` | Skills: `frontend-code-review`, `security-pipeline`, `verification-engine` | Hooks: `code-quality-reminder.sh`, `expensive-mcp-warning.sh`
