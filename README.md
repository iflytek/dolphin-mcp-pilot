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
- **Workflow creation**: simple SQL and complex DAG workflows with multiple task types
- **Schedule management** (cron-based)
- **Instance lifecycle control** (pause/resume/rerun/rerun-from-failure/delete)
- **Resource content management** and **version rollback / workflow clone**
- **Raw API passthrough** for uncovered edge cases

## 🚀 Quick Start

```bash
# 1. Clone the repository
git clone https://github.com/iflytek/dolphin-mcp-pilot.git
cd dolphin-mcp-pilot

# 2. Configure environment
cp .env.example .env
# Edit .env — at minimum set DS_URL and DS_TOKEN (or DS_USER/DS_PASSWORD)

# 3. Start the service (dev mode)
docker compose --profile dev up -d dolphin-mcp-pilot-dev
```

✅ Service will be available at `http://localhost:8001/mcp/` (note the trailing slash)

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

## 📄 License

[Apache-2.0](LICENSE)

## 🙏 Acknowledgments

Built with [FastMCP](https://github.com/jlowin/fastmcp) and inspired by the Apache DolphinScheduler community.
