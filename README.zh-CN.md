# dolphin-mcp-pilot

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

[English](README.md) | [简体中文](README.zh-CN.md)

> **💡 快速翻译提示**  
> 本文档内容较长，如需其他语言版本，可直接将本文件内容复制给 ChatGPT / Claude / 文心一言等大模型，请求翻译成目标语言（如日语、韩语、德语等）。所有格式和链接都会被保留。

Apache DolphinScheduler 的生产级 MCP 服务器。

**dolphin-mcp-pilot** exposes **53+ tools** for projects, workflows, DAG creation, schedules, instances, resources, logs, monitoring and raw API passthrough — designed for AI agents that need to operate DolphinScheduler beyond basic read-only usage.

## 🎯 Why this project?

Most public DolphinScheduler MCP servers only cover basic read/list/start/stop scenarios.  
This project is designed for **real operations work**:

- ✅ Create SQL workflows in one line
- ✅ Create complex DAG workflows (SQL/SHELL/PYTHON/DEPENDENT/HTTP/...)
- ✅ Manage schedules (create / online / offline / delete)
- ✅ Control process instances (pause / resume / rerun / rerun-from-failure)
- ✅ View task logs
- ✅ Force task success / skip failed task
- ✅ Manage resources (view/update content)
- ✅ Roll back workflow versions
- ✅ Clone workflows
- ✅ Use raw API as a safety valve
- ✅ Support **multi-tenant per-request auth**

## 🚀 Key features

- **53+ tools** covering most practical DS operations
- **Two auth modes**
  - API Token (`X-DS-Token`) — preferred, DolphinScheduler 3.x native
  - User/Password (`X-DS-User` + `X-DS-Password`) — fallback with session cache
- **Multi-tenant HTTP mode**: each caller can use its own credentials
- **Workflow creation**
  - Simple SQL workflows
  - Complex DAG workflows with multiple task types
- **Schedule management** (cron-based)
- **Instance lifecycle control** (pause/resume/rerun/rerun-from-failure/delete)
- **Task log access**
- **Resource content management**
- **Version rollback / workflow clone**
- **Raw API passthrough** for uncovered edge cases

## 📊 Feature comparison

| Capability | dolphin-mcp-pilot | Typical public DS MCP |
|---|:---:|:---:|
| **Tool count** | **53+** | ~10-15 |
| Create project | ✅ | ⚠️ often no |
| Create SQL workflow | ✅ | ❌ |
| Create DAG workflow | ✅ | ❌ |
| Update workflow | ✅ | ❌ |
| Clone workflow | ✅ | ❌ |
| Workflow version rollback | ✅ | ❌ |
| **Schedule management** | ✅ 6 tools | ❌ |
| Pause/Resume/Rerun instances | ✅ | ❌ |
| Task logs | ✅ | ❌ |
| Force success / skip task | ✅ | ❌ |
| Resource content update | ✅ | ❌ |
| **Multi-tenant auth** | ✅ | ⚠️ often single token |
| Raw API passthrough | ✅ | ❌ |

## 🚀 Quick Start

### 3-Step Deployment

```bash
# 1. Clone the repository
git clone https://github.com/iflytek/dolphin-mcp-pilot.git
cd dolphin-mcp-pilot

# 2. Configure environment
cp .env.example .env
# Edit .env and set DS_URL + DS_TOKEN (or DS_USER/DS_PASSWORD)

# 3. 启动服务
./start.sh        # Linux/Mac
# or
start.bat         # Windows
# or
docker compose --profile dev up -d dolphin-mcp-pilot-dev
```

✅ Service will be available at `http://localhost:8001/mcp/` (note the trailing slash)

📖 **Detailed deployment guide**: See [DEPLOYMENT.md](DEPLOYMENT.md)

## 📦 Installation Options

### Option A: Docker Compose (推荐)

#### A1. 开发模式（当前推荐）

基于本地 Dockerfile 构建，将 `./dolphin_mcp_pilot` 以只读方式挂载进容器。源码修改后需重启容器（uvicorn 未启用 `--reload`）：

```bash
# 1. 准备环境配置
cp .env.example .env
# 编辑 .env —— 至少设置 DS_URL 与 DS_TOKEN（详见下方 Configuration）

# 2. 启动服务（dev profile 将本地构建）
docker compose --profile dev up -d dolphin-mcp-pilot-dev

# 3. 验证
docker compose --profile dev ps        # STATUS 应在 ~10s 后显示 (healthy)
docker compose --profile dev logs -f   # 查看启动日志
```

服务地址：`http://localhost:8001/mcp/`（注意结尾斜杠）

#### A2. 生产模式（发布镜像）

> **提示**：`ghcr.io/iflytek/dolphin-mcp-pilot:latest` 镜像会在推送稳定 release tag（如 `v0.2.0`）时自动发布。在首个 release 打标前，请使用上方 **A1** 或下方 **Option B/C**。

镜像发布后，prod 服务会直接从 ghcr.io 拉取：

```bash
# 可选：锁定版本
echo "IMAGE_TAG=0.2.0" >> .env

docker compose up -d
docker compose ps        # STATUS 应显示 (healthy)
```

完整参考（资源限制、日志轮转、健康检查等）见 [`docker-compose.yml`](docker-compose.yml)。

📖 **详细部署指南**：参见 [DEPLOYMENT.md](DEPLOYMENT.md)

### Option B: From source

```bash
git clone https://github.com/iflytek/dolphin-mcp-pilot.git
cd dolphin-mcp-pilot
pip install -r requirements.txt
python -m dolphin_mcp_pilot
```

### Option C: Install as package

```bash
pip install .
dolphin-mcp-pilot
```

## ⚙️ Configuration

Create a `.env` file from `.env.example`.

### Required

```bash
DS_URL=http://your-dolphinscheduler-host:12345/dolphinscheduler
```

### Authentication options

#### Option A: API Token (recommended)

```bash
DS_TOKEN=your_api_token
```

#### Option B: Default username/password

```bash
DS_USER=your_username
DS_PASSWORD=your_password
```

### Optional

```bash
DS_TENANT_CODE=default          # Tenant code for workflow creation
DS_MCP_TRANSPORT=http           # "stdio" or "http"
MCP_HOST=0.0.0.0                # HTTP bind host
MCP_PORT=8001                   # HTTP bind port
```

## 🏃 Run

### stdio mode (for local AI tools)

```bash
python -m dolphin_mcp_pilot
```

### HTTP mode (for remote AI agents)

```bash
DS_MCP_TRANSPORT=http python -m dolphin_mcp_pilot
```

Or with Docker:

```bash
docker-compose up -d
```

## 🔐 Client Configuration

### CodeBuddy / Claude Desktop (HTTP mode)

Add to your MCP client config:

```json
{
  "mcpServers": {
    "dolphinscheduler": {
      "type": "sse",
      "url": "http://localhost:8001/mcp/",
      "headers": {
        "X-DS-Token": "your_api_token"
      }
    }
  }
}
```

> ⚠️ The URL must end with `/`. Without the trailing slash, Starlette returns a 307 redirect, which some MCP clients fail to follow.

更多配置见 [`examples/`](examples/README.md) 目录：
- `codebuddy-config.json` - CodeBuddy configuration
- `claude-desktop-config.json` - Claude Desktop stdio mode
- `http-auth-token.json` - HTTP with token auth
- `http-auth-password.json` - HTTP with username/password

欢迎分享其他 MCP 客户端或部署方式的配置。复制 [`examples/TEMPLATE`](examples/TEMPLATE)，
并按照[示例贡献指南](examples/README.md#中文)提交。

### Multi-tenant per-request auth

In HTTP mode, each caller can pass their own credentials:

**Token mode (preferred):**
```
X-DS-Token: your_api_token
```

**Username/password mode:**
```
X-DS-User: alice
X-DS-Password: alice_password
```

## 📁 Project layout

```text
dolphin-mcp-pilot/
├── dolphin_mcp_pilot/
│   ├── __main__.py          # Entry point
│   ├── auth.py              # Auth & session management
│   ├── client.py            # HTTP client for DS API
│   ├── config.py            # Configuration
│   ├── middleware.py        # HTTP auth middleware
│   ├── utils.py             # Shared helpers
│   ├── server/
│   │   ├── __init__.py
│   │   └── app.py           # FastMCP app
│   └── tools/               # 58 tools organized by category
│       ├── help.py
│       ├── project.py
│       ├── datasource.py
│       ├── workflow.py
│       ├── workflow_advanced.py
│       ├── schedule.py
│       ├── instance.py
│       ├── resource.py
│       ├── monitor.py
│       ├── user.py
│       └── raw.py
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
├── requirements.txt
└── README.md
```

## 🛠️ Main tool categories

### Project management (5 tools)
- Test connection
- List / create / rename / delete projects

### Datasource management (1 tool)
- List datasources

### Workflow management (8 tools)
- List / get / create (SQL) / release / run / status / delete / simple-list

### Advanced workflow management (7 tools)
- Update / clone / batch-delete / list-versions / rollback / create-dag / get-by-name

### Schedule management (6 tools)
- List / set / online / offline / list-in-project / delete

### Process instance management (13 tools)
- List / stop / pause / resume / rerun / rerun-from-failure / delete / complement-data
- Get instance tasks / task log / force-task-success / skip-task

### Resource management (5 tools)
- List / view / update-content / delete / get-by-name

### Monitoring (2 tools)
- Monitor masters / workers

### User / tenant (2 tools)
- List users / tenants

### Raw API passthrough (4 tools)
- GET / POST / PUT / DELETE for any DS API endpoint

### Help & navigation (1 tool)
- `ds_help` — tool navigation guide with categories and quick-start tips

## ✨ What's new

- **Guided troubleshooting**: `ds_list_process_instances` attaches a `next_action`
  hint to RUNNING/FAILURE instances, pointing agents to `ds_list_task_instances`
  to inspect individual task nodes instead of only watching the workflow-level state.
- **Reliable backfill ordering**: serial complement (`ds_complement_data` with
  `RUN_MODE_SERIAL`) uses the `complementStartDate`/`complementEndDate` range format
  so DolphinScheduler generates instances in strict day-by-day order.
- **Flexible task params**: `ds_update_task_param` accepts both `snake_case` and
  `camelCase` field names and reports ignored fields.

## 📦 Packaging & distribution

Build wheel:

```bash
pip install build
python -m build
```

Install locally:

```bash
pip install .
```

Then run:

```bash
dolphin-mcp-pilot
```

## 🤝 Contributing

欢迎贡献。项目代码修改请阅读 [CONTRIBUTING.zh-CN.md](CONTRIBUTING.zh-CN.md)；如需分享已验证的
MCP 客户端配置，请按照[示例贡献指南](examples/README.md#中文)提交。

## 🔍 Verify Deployment

```bash
# Check status
docker ps | grep dolphin-mcp-pilot

# View logs
docker-compose logs -f

# Test MCP handshake (POST JSON-RPC initialize)
curl -X POST http://localhost:8001/mcp/ \
  -H "X-DS-Token: your_token" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"curl","version":"1"}}}'
```

## 🐛 Troubleshooting

See [DEPLOYMENT.md](docs/DEPLOYMENT.md#-troubleshooting) for common issues and solutions.

**Quick checks:**
- Verify `.env` file exists and is configured
- Ensure DolphinScheduler is accessible from the container
- Check logs: `docker-compose logs`
- Verify token/credentials are valid

## 📄 License

Apache-2.0

## 🙏 Acknowledgments

Built with [FastMCP](https://github.com/jlowin/fastmcp) and inspired by the Apache DolphinScheduler community.
