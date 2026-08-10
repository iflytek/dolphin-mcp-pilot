> **Note**: This is an internal governance document (repository proposal for the iflytek open-source community). It is not user-facing documentation.

# Repository Proposal: dolphin-mcp-pilot

**Target Repository Name**: dolphin-mcp-pilot  
**Primary Authors**: @Hui-of-limin  
**Initial Maintainers**: @Hui-of-limin, @charleswillicks  
**Tracking Issue**: https://github.com/iflytek/community/issues/XXXX (fill after Issue created)

---

## 1. Abstract

dolphin-mcp-pilot is a production-ready MCP (Model Context Protocol) server for Apache DolphinScheduler. It exposes 58 tools covering project management, workflow creation, DAG manipulation, schedule configuration, instance control, backfill orchestration, resource management, log retrieval and cluster monitoring, enabling AI agents to operate DolphinScheduler through natural language.

The project solves a concrete operational pain point: DolphinScheduler's REST API is powerful but verbose. Common tasks like "backfill last 5 days in order" or "show me the logs of the most recent failure" require multi-step API calls, manual ID lookups and domain knowledge. By wrapping these patterns into discrete tools with agent-friendly signatures and response guidance, we reduce a 5-minute manual workflow to a 30-second agent interaction.

This is not a replacement for DolphinScheduler itself. It is an integration layer that translates agent intents into validated DS API calls and structures the responses for agent consumption.

---

## 2. Motivation & Goals

### 2.1 Problem Statement

Apache DolphinScheduler is one of the most widely adopted open source data orchestration platforms (Apache top-level project, 12k+ GitHub stars). iflytek uses it extensively. However:

1. **Manual operation overhead**: Creating workflows, setting schedules, running backfills and diagnosing failures all require navigating the UI or crafting REST calls by hand. Data engineers spend 10-20% of their time on repetitive scheduling tasks.
2. **No AI-agent integration**: DolphinScheduler's ecosystem lacks a mature agent-facing API. The closest projects (`ocean-zhc/dolphinscheduler-mcp`, `lukaa077/ds-mcp`) expose only 18-30 tools and lack production fixes (backfill ordering, task-level failure drill-down, parameter snake_case/camelCase dual support).
3. **Tribal knowledge barrier**: New team members take weeks to learn DS's workflow/schedule/instance model. An agent with domain-baked tools can guide users through correct operation sequences.

### 2.2 Goals

1. **Operational efficiency**: Automate high-frequency tasks (workflow creation, schedule config, backfill, log retrieval) so data platform teams can shift time from manual ops to feature work.
2. **Lower learning curve**: Allow users to interact with DolphinScheduler in natural language via AI agents, reducing the ramp-up period from weeks to days.
3. **Give back to the community**: DolphinScheduler is a widely-used open source project. By open sourcing this MCP server, iflytek shares its AI-plus-orchestration practice with the global community and fills a gap in the ecosystem.
4. **Showcase iflytek's agent ecosystem**: Position iflytek as a leader in AI-agent toolchain integration, demonstrating how agents can interface with enterprise middleware.

### 2.3 Why an iflytek Org Repository

1. **Aligns with iflytek's AI-agent strategy**: Fits into the "Model & Agent System > Toolchain" track of iflytek Landscape. Can be integrated into Astran-agent, Skillhub and other iflytek agent platforms as a scheduling capability plugin.
2. **Long-term commitment**: This is not a one-off experiment. iflytek will maintain it for 2+ years, sync it with DolphinScheduler releases and respond to community issues/PRs.
3. **IP clarity**: 100% iflytek-owned code, Apache 2.0 licensed, no third-party code copied in.
4. **Credibility for adoption**: Hosting under `iflytek/dolphin-mcp-pilot` signals enterprise backing and maintenance commitment, encouraging external adoption and contribution.

---

## 3. User Stories

1. **As a data engineer**, I want to backfill a workflow for a 10-day window in strict date order, so downstream dependencies don't get inconsistent data.
   - Before: Write a Python loop to call DS API, manually manage ordering.
   - With MCP: Tell the agent "Backfill workflow X from 2026-01-01 to 2026-01-10, one day at a time." Agent calls `ds_complement_data(run_mode="RUN_MODE_SERIAL")` with range payload.

2. **As a platform operator**, I want to quickly identify which task node failed in a workflow instance, so I can fix and rerun.
   - Before: Open DS UI, click into instance, scroll through task list.
   - With MCP: Agent calls `ds_list_process_instances`, sees `next_action: "2 FAILURE instances detected, call ds_list_task_instances(process_instance_id=X) to see failed nodes"`, drills in automatically.

3. **As a new team member**, I don't know how to set a workflow to run daily at 3 AM.
   - Before: Ask senior engineer, or read DS docs for schedule API format.
   - With MCP: Tell agent "Schedule workflow Y to run every day at 3 AM." Agent calls `ds_set_schedule(cron="0 3 * * *")` + `ds_online_schedule()`.

4. **As a data analyst**, I want to clone a workflow from project A to project B for a similar use case.
   - Before: Export JSON, manually edit IDs, re-import.
   - With MCP: Agent calls `ds_clone_workflow(source_project_code=A, target_project_code=B, new_name="...")`.

---

## 4. Technical Design

### 4.1 Architecture

```
┌─────────────┐
│ AI Agent    │ (Claude Desktop, CodeBuddy, Cursor, etc.)
└──────┬──────┘
       │ MCP protocol (stdio / SSE / HTTP)
       v
┌─────────────────────────────────────┐
│   dolphin-mcp-pilot MCP Server      │
│  ┌────────────────────────────┐     │
│  │ 58 tools (ds_*)            │     │
│  │ - auth layer               │     │
│  │ - session manager          │     │
│  │ - response formatter       │     │
│  └────────────────────────────┘     │
└──────────────┬──────────────────────┘
               │ REST API
               v
       ┌──────────────────┐
       │ DolphinScheduler │
       └──────────────────┘
```

### 4.2 Key Components

1. **Tool registry** (`tools/`): 58 tools organized into 10 categories (connectivity, projects, datasources, workflows, schedules, instances, resources, monitoring, users, raw API passthrough).
2. **Auth layer** (`auth.py`): Per-request authentication via `X-DS-User` / `X-DS-Password` headers or `X-DS-Token`, no persistent credentials.
3. **Session manager**: MCP session ID tracking for multi-turn conversations.
4. **Response formatter**: Wraps DS API JSON into agent-friendly structures, injects `next_action` hints when applicable.
5. **Transport adapters**: stdio (for desktop apps), SSE (for web clients), HTTP (for containerized deployments).

### 4.3 Operational Fixes (vs. raw DS API)

- **Serial backfill ordering**: v2.0.18 switched from date-list to date-range payload, ensuring DolphinScheduler emits instances day-by-day in ascending order (not random).
- **Task-level failure drill-down**: v2.0.19 adds `next_action` hints; when workflow instance is FAILURE, agent is prompted to call `ds_list_task_instances` to see which node failed.
- **Parameter dual syntax**: v2.0.17 accepts both `pre_statements` (snake_case) and `preStatements` (camelCase), reducing agent confusion.

### 4.4 Security

- Credentials are never persisted; each MCP request carries auth headers.
- CI includes `bandit` (static security scan), `pip-audit` (dependency CVE check), secret-scan (regex for hardcoded IPs/passwords).
- All 21 source files have Apache 2.0 copyright headers.

---

## 5. Dependencies & Infrastructure

### 5.1 Runtime Dependencies

| Library | Purpose | License | Version |
|---------|---------|---------|---------|
| mcp | MCP protocol SDK | MIT | latest |
| anyio | Async I/O abstraction | MIT | latest |
| uvicorn | ASGI server | BSD-3 | latest |
| starlette | ASGI framework | BSD-3 | latest |
| pydantic | Data validation | MIT | latest |

All dependencies are MIT or BSD-3-Clause; no copyleft risk.

### 5.2 CI/CD

GitHub Actions workflow (`.github/workflows/ci.yml`):
- **test** job: unit tests on Python 3.10 / 3.11 / 3.12
- **lint** job: `ruff check` + `ruff format`
- **security** job: `bandit -ll` + `pip-audit` + secret-scan (grep for hardcoded credentials)
- **build** job: `pip install` verification

### 5.3 Infrastructure Requirements

- None beyond GitHub repo, Actions and standard container registries. No cloud resources or persistent services.

---

## 6. Maintenance & Governance

### 6.1 Initial Maintainers

- **@Hui-of-limin**: Project lead (approver), 2+ year commitment, responsible for releases, final PR merge and compliance.
- **@charleswillicks**: Reviewer, 2+ year commitment, responsible for code review and quality gate.

Both are iflytek org members.

### 6.2 Maintenance Scope

1. **Monthly patch releases**: Bugfixes, dependency updates, security patches.
2. **Quarterly feature releases**: New tools, DS API version compatibility updates.
3. **Issue/PR response SLA**: 2 business days for initial triage.
4. **Documentation sync**: All code changes require accompanying doc updates (same PR).

### 6.3 SIG Affiliation

- **Primary SIG**: Toolchain (3.2.3)
- Will participate in SIG monthly meetings, sync roadmap and accept SIG-driven feature requests.

### 6.4 Exit Strategy

If active development ceases:
1. Mark repo as "maintenance mode" in README
2. Archive after 6 months of inactivity
3. Publish a migration guide pointing to community forks (if any exist) or recommend users freeze at last stable version

---

## 7. Community & Adoption

### 7.1 Internal Adoption

- Already in use by the iflytek data platform team against an internal DolphinScheduler cluster.
- Planned integration into Astran-agent and Skillhub as a scheduling capability plugin.

### 7.2 External Community

- Target audience: DolphinScheduler users, AI-agent developers, data platform engineers.
- Outreach plan:
  - Submit a link to DolphinScheduler's official documentation "integrations" section.
  - Write a blog post: "Operate DolphinScheduler from AI Agents in 30 Seconds."
  - Present at DolphinScheduler community meetups (online or in-person).

### 7.3 Competitive Landscape

| Project | Stars | Tools | Production Fixes | Maintenance |
|---------|-------|-------|------------------|-------------|
| ocean-zhc/dolphinscheduler-mcp | 27 | ~30 | No | Sporadic |
| lukaa077/ds-mcp | 1 | 18 | No | Inactive |
| **dolphin-mcp-pilot** | 0 (new) | **58** | **Yes** | iflytek-backed |

Our advantage: 2-3x more tools, production-tested fixes (backfill ordering, failure drill-down), enterprise maintenance commitment.

---

## 8. Repository Configuration

- [x] Enable Issues
- [x] Enable Discussions
- [ ] Enable Wiki (not needed; docs are in `docs/`)
- [ ] Transfer existing external repo (N/A; this is a new creation)

---

## 9. Risks & Alternatives

### 9.1 Risks

1. **DolphinScheduler API breaking changes**: Mitigation: monitor DS release notes, run CI against DS dev branches when available, tag releases per DS version (e.g., `v0.2.0-ds3.x`).
2. **Low external adoption**: Mitigation: active marketing (blog post, DS community engagement), showcase at iflytek tech talks.
3. **Maintainer availability**: Mitigation: 2 initial maintainers, both committed for 2+ years. If both leave, iflytek OSPO will recruit replacements from internal DS users.

### 9.2 Alternatives Considered

1. **Keep it internal-only**: Rejected. Open sourcing gives back to the DS community and raises iflytek's profile in the agent ecosystem.
2. **Contribute to an existing project**: ocean-zhc/dolphinscheduler-mcp is unmaintained and has a different architecture (no session mgmt, no response guidance). Merging our fixes upstream would require rewriting their codebase. Creating a new repo is cleaner.
3. **Publish as a PyPI package only**: PyPI is for distribution, not governance. An iflytek org repo signals commitment, makes governance transparent and simplifies CI/CD.

**Conclusion**: An iflytek org public repo is the best option.

---

## 10. Timeline

| Milestone | Target Date | Deliverables |
|-----------|-------------|--------------|
| Proposal submitted | 2026-08-06 | This document |
| OSPO review complete | 2026-08-13 | Approval or revision requests |
| Repository created | 2026-08-15 | `github.com/iflytek/dolphin-mcp-pilot` live |
| Initial release (v0.2.0) | 2026-08-20 | Tag, release notes, PyPI publish |
| External blog post | 2026-09-01 | "Operate DolphinScheduler from AI Agents" |
| First external PR | 2026-10-01 | Community contribution |

---

## 11. References

- **Tracking Issue**: (to be filled after Issue #XXXX is created)
- **Code package**: `dolphin-mcp-pilot-v0.2.0-FINAL.zip` (110 KB, 50 files, attached to tracking issue)
- **DolphinScheduler**: https://github.com/apache/dolphinscheduler
- **MCP Protocol**: https://modelcontextprotocol.io/
- **Competitive analysis**:
  - ocean-zhc/dolphinscheduler-mcp: https://github.com/ocean-zhc/dolphinscheduler-mcp
  - lukaa077/ds-mcp: https://github.com/lukaa077/ds-mcp
