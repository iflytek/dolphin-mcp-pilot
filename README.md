# dolphin-mcp-pilot

<div align="center">

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![CI](https://github.com/iflytek/dolphin-mcp-pilot/actions/workflows/ci.yml/badge.svg)](https://github.com/iflytek/dolphin-mcp-pilot/actions/workflows/ci.yml)
[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/iflytek/dolphin-mcp-pilot)

[English](README.md) | [简体中文](README.zh-CN.md)

</div>

A production-ready MCP server for Apache DolphinScheduler.

**dolphin-mcp-pilot** exposes **53+ tools** for projects, workflows, DAG creation, schedules, instances, resources, logs, monitoring and raw API passthrough — designed for AI agents that need to operate DolphinScheduler beyond basic read-only usage.

## 🔧 Compatibility

**dolphin-mcp-pilot** targets Apache DolphinScheduler **3.x**. The automated Docker Compose E2E
suite runs against the 3.4.x standalone image on every CI run; the other lines are verified against
the matching upstream API controller source and covered by runtime fallbacks where endpoints differ.

| DolphinScheduler (backend engine) | Status | How it's verified |
|---|---|---|
| 3.4.x standalone | ✅ CI-validated | Automated Docker Compose E2E, default `DS_VERSION=3.4.2` |
| 3.2.2 – 3.3.x / `dev` | ✔️ Source-verified | Monitor listing uses the enum route `/monitor/{nodeType}`; other read-only routes checked against upstream controllers and pinned by unit tests |
| 3.0.x – 3.2.1 | ✔️ Source-verified | Legacy monitor routes (`/monitor/masters`, `/monitor/workers`) reached via automatic 404 fallback in `_list_servers` |

**Legend** — ✅ **CI-validated**: exercised on every CI run against a live DS image · ✔️ **Source-verified**:
endpoint paths checked against the matching upstream `*Controller` source and locked by unit tests, but not
yet part of the CI image matrix.

> **Note:** the `process-*` → `workflow-*` REST path rename that landed in the DS 3.3 line (e.g.
> `workflow-definition`, `workflow-instances`) affects the workflow/instance tools and is tracked
> separately in [#42](https://github.com/iflytek/dolphin-mcp-pilot/issues/42).

## 🎯 Why this project?

Most public DolphinScheduler MCP servers only cover basic read/list/start/stop scenarios.
This project is designed for **real operations work**:

- ✅ Create SQL / DAG workflows in one line
- ✅ Manage schedules (create / online / offline / delete)
- ✅ Control process instances (pause / resume / rerun / rerun-from-failure)
- ✅ View task logs, force task success / skip failed task
- ✅ Manage resources (view/update content)
- ✅ Roll back workflow versions, clone workflows
- ✅ Use raw API as a safety valve
- ✅ Support **multi-tenant per-request auth**

## 🚀 Key features

- **53+ tools** covering most practical DS operations
- **Two auth modes**: API Token (`X-DS-Token`) or User/Password (`X-DS-User` + `X-DS-Password`)
- **Multi-tenant HTTP mode**: each caller can use its own credentials
- **MCP 2.0 stateless HTTP** with automatic compatibility for MCP 1.x clients
- **Workflow creation**: simple SQL and complex DAG workflows with multiple task types
- **Schedule management** (cron-based)
- **Instance lifecycle control** (pause/resume/rerun/rerun-from-failure/delete)
- **Resource content management** and **version rollback / workflow clone**
- **Raw API passthrough** for uncovered edge cases

## 🚀 Quick Start

### Prerequisites

- A running DolphinScheduler 3.x instance whose API is reachable from Docker
- Docker with Compose v2 (`docker compose version`)
- A DolphinScheduler API token (recommended), or a username and password

```bash
# 1. Clone the repository
git clone https://github.com/iflytek/dolphin-mcp-pilot.git
cd dolphin-mcp-pilot

# 2. Configure environment
cp .env.example .env
# Edit .env — set DS_URL and DS_TOKEN (or DS_USER/DS_PASSWORD)
# Example DS_URL: http://your-dolphinscheduler-host:12345/dolphinscheduler

# 3. Build and start the service from this checkout
docker compose --profile dev up -d dolphin-mcp-pilot-dev

# 4. Confirm that the container is healthy
docker compose --profile dev ps
```

The MCP endpoint is now `http://localhost:8001/mcp/` (the trailing slash is required).
Add it to an HTTP/SSE-capable MCP client:

```json
{
  "mcpServers": {
    "dolphinscheduler": {
      "type": "sse",
      "url": "http://localhost:8001/mcp/",
      "headers": { "X-DS-Token": "your_api_token" }
    }
  }
}
```

As a safe first check, ask your agent: **“List my DolphinScheduler projects and workflows. Do
not make any changes.”** For client-specific configuration and username/password auth, see
[Client Config](docs/CLIENT_CONFIG.md).

## 💡 Common use cases

| Scenario | Example request | Main tools |
|---|---|---|
| Investigate a failed run | “Find the latest failed workflow, show the failed task and its log, and suggest the next action without changing anything.” | `ds_list_process_instances`, `ds_list_task_instances`, `ds_get_latest_failure_log` |
| Backfill missing data | “Backfill 2026-08-01 through 2026-08-07 serially, starting from the validation task and including downstream tasks.” | `ds_complement_data` |
| Create and schedule a workflow | “Create a daily SQL workflow, add its cron schedule, and show me the definition before putting it online.” | `ds_create_workflow`, `ds_set_schedule`, `ds_online_schedule` |
| Give multiple agents controlled access | Run one HTTP MCP service while each caller supplies its own DolphinScheduler credentials. | Per-request `X-DS-*` headers |

The tools can also pause, resume, rerun, clone, and roll back workflows; manage resources; and
fall back to raw DolphinScheduler APIs for uncovered operations. Start with `ds_help(category="quickstart")`
inside your MCP client to discover the recommended workflow for each task.

## 📚 Documentation

| Document | Description |
|---|---|
| [📦 Installation](docs/INSTALLATION.md) | Docker Compose (dev/prod), from source, as package, run modes |
| [⚙️ Configuration](docs/CONFIGURATION.md) | Environment variables, auth options, Compose tunables |
| [🚀 Deployment](docs/DEPLOYMENT.md) | Production deployment, Compose reference, verify, troubleshoot |
| [📊 Features](docs/FEATURES.md) | Feature comparison table, tool categories |
| [🔐 Client Config](docs/CLIENT_CONFIG.md) | MCP client setup (CodeBuddy, Claude Desktop, etc.), multi-tenant auth |
| [📖 API Reference](docs/API.md) | All 53+ tools, parameter conventions, error handling (中文) |
| [❓ FAQ](docs/FAQ.md) | Common issues and solutions (中文) |

## ✨ What's new

- **MCP 2.0**: supports the stateless 2026-07-28 protocol while keeping legacy
  handshake clients and stdio configurations working.
- **Guided troubleshooting**: `ds_list_process_instances` attaches a `next_action`
  hint to RUNNING/FAILURE instances, pointing agents to `ds_list_task_instances`
  to inspect individual task nodes.
- **Reliable backfill ordering**: serial complement uses the `complementStartDate`/`complementEndDate`
  range format so DolphinScheduler generates instances in strict day-by-day order.
- **Flexible task params**: `ds_update_task_param` accepts both `snake_case` and
  `camelCase` field names and reports ignored fields.

## 🤝 Contributing

Contributions are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) for project changes, or follow the
[example contribution guide](examples/README.md#how-to-contribute) to share a tested MCP client
configuration.

Used dolphin-mcp-pilot for something real? Write it up in [`cases/`](cases/README.md) — a gallery of
community usage stories (agent-driven DolphinScheduler ops), each linked to a public post.

## 📄 License

[Apache-2.0](LICENSE)

## 🙏 Acknowledgments

Built with the official [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
and inspired by the Apache DolphinScheduler community.
