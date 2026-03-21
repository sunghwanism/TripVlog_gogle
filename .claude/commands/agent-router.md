---
name: agent-router
description: "Automatic specialist routing across 34 domains (legal, finance, patent, SEO, marketing, planning, code review, architecture, estimates, CRM, research, first-principles, etc.)"
---

<SUBAGENT-STOP>
If running inside a subagent, skip this skill to prevent recursive spawns.
</SUBAGENT-STOP>

# Agent Router

> Analogy: hospital intake desk. If someone says "my stomach hurts", route to internal medicine; if "I broke a bone", route to orthopedics. The desk does not treat directly.

## Rules (CRITICAL)

1. If a matching agent exists in the routing table -> **must spawn via Agent tool**
2. If no match -> ignore this skill and handle directly
3. If the user says "do it yourself" or "no agent" -> skip routing
4. If multiple agents match -> choose the most specific
5. When spawning, pass the user's original request verbatim (no summarization)

## Routing Table

| Keyword (any match) | Agent |
|---------------------|-------|
| implementation plan, complex feature, design | planner |
| code review, review my code | code-reviewer |
| architecture, design decision, tech debt | architect |
| TDD, test first, write tests | tdd-guide |
| build error, build fail, type error | build-error-resolver |
| security review, vulnerability | security-reviewer |
| DB review, SQL query, migration, index | database-reviewer |
| dead code, refactor, unused code, cleanup | refactor-cleaner |
| docs update, codemap, docs sync | doc-updater |
| contract, NDA, legal, terms, damages | contract-legal |
| tax, accounting, finance, VAT, cashflow | financial-accountant |
| patent, invention, claims, trademark, IP | patent-attorney |
| SEO, GEO, AEO, search ranking, SERP | seo-geo-aeo-strategist |
| product strategy, roadmap, market analysis, MVP | product-strategist |
| copy, headline, CTA, ad copy | copywriting |
| estimate, quote, pricing proposal | quotation |
| government grant, subsidy, program, TIPS | gov-support-strategist |
| ad optimization, ROAS | ad-optimizer-team |
| marketing strategy, growth marketing | performance-growth-marketer |
| content planning, YouTube planning | qjc-content |
| automation consulting, training design, VOD | qjc-operations |
| sales, leads, CRM, pipeline, follow-up | crm-manager |
| UI, UX, design, landing page, dashboard | web-designer |
| video production, Remotion, intro/outro | remotion-creator |
| research, market research, trend analysis | researcher |
| E2E test, Playwright, user journey | e2e-runner |
| verify, build check, test check | verify-agent |
| AI research, paper analysis, ablation | ai-researcher |
| Codex review, cross-model review, second opinion | codex-reviewer |
| Gemini review, frontend review, React review, accessibility | gemini-reviewer |
| QJC business strategy, sales strategy, proposals | qjc-business |
| deep research, policy research, industry analysis | research-pi |
| storytelling, brand story, case study, pitch narrative | storyteller |
| first principles, root cause, cost breakdown, simplify | first-principles-thinker |

## Team Subagents (no direct routing)

The following are managed by parent teams and should not be called directly:
- ad-compass, ad-scout-google, ad-scout-meta -> **ad-optimizer-team**
- action-architect, folder-hunter, mail-scout -> **email-action-team** (via /email-action)
- auto-experimenter -> **ai-researcher** or **research-pi**

## Exceptions (skip routing)

- Simple question/info request -> handle directly
- One-line fix/typo -> handle directly
- Agent already running -> avoid duplicate spawn
- User explicitly requests no agent -> handle directly
- Running inside a subagent -> skip (prevent recursion)
