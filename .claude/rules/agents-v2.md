# Agent Orchestration

> Team ops details: ~/qjc-office/dotclaude/reference/agents-teams-ref.md
> MCP/config details: ~/qjc-office/dotclaude/reference/agents-config-ref.md
> Agent catalog: ~/qjc-office/dotclaude/reference/agent-catalog.md

## Built-in Skills

| Skill | When to Use |
|-------|-------------|
| /simplify | Clean up code after implementing a feature (3 parallel agents) |
| /batch | Repeat the same pattern change across 5+ files |
| /rc | Remote session access when away |
| /ralph-loop | Multi-turn autonomous loop (`--max-iterations` required) |
| /email-action | 2-phase email processing: empty input -> list, number -> match, query -> 4-Opus team (agents only in Phase 2) |

## Agent Auto-Routing (CRITICAL)

`/agent-router` automatically routes real work requests to specialist domains.
The using-superpowers "1% rule" enforces an agent-router check each turn.
Simple questions or info requests are answered directly (no routing).

Main routing targets (34 agents):
- Dev: planner, code-reviewer, architect, tdd-guide, build-error-resolver, verify-agent, e2e-runner, security-reviewer, database-reviewer, refactor-cleaner, doc-updater
- Business: product-strategist, quotation, crm-manager, qjc-business, qjc-operations
- Legal/Finance: contract-legal, financial-accountant, patent-attorney, gov-support-strategist
- Marketing/Content: seo-geo-aeo-strategist, copywriting, ad-optimizer-team, performance-growth-marketer, qjc-content, storyteller
- Creative: web-designer, remotion-creator
- Research: researcher, ai-researcher, research-pi
- Review: codex-reviewer, gemini-reviewer
- Meta thinking: first-principles-thinker

See `/agent-router` for detailed routing rules.

## Parallel Task Execution

Independent tasks should run in parallel unless sequencing is required.

## Subagents vs Agent Teams

| | Subagents | Agent Teams |
|---|---|---|
| Communication | Report only to main | Via leader (hub-and-spoke) |
| Best for | Focused tasks where only output matters | Complex tasks needing discussion/collab |
| Token cost | Low | High |

Details: agents-teams-ref.md, agents-config-ref.md

## Agent Memory

`~/.claude/agent-memory/{agent-name}/` (see agents-config-ref.md).

## Agent Pipeline / Parallel Agents

- Call order: ~/qjc-office/dotclaude/reference/agent-pipeline.md
- Parallel guide: ~/qjc-office/dotclaude/reference/parallel-agents-guide.md
