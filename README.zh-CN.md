# dolphin-mcp-pilot

<div align="center">

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![CI](https://github.com/iflytek/dolphin-mcp-pilot/actions/workflows/ci.yml/badge.svg)](https://github.com/iflytek/dolphin-mcp-pilot/actions/workflows/ci.yml)

[English](README.md) | [简体中文](README.zh-CN.md)

</div>

Apache DolphinScheduler 的生产级 MCP 服务器。

**dolphin-mcp-pilot** 提供 **53+ 工具**，覆盖项目管理、工作流、DAG 创建、调度、实例、资源、日志、监控以及原始 API 透传 —— 专为需要超越只读操作的 AI Agent 设计。

## 🎯 为什么需要这个项目？

目前公开的 DolphinScheduler MCP 服务器大多只覆盖基础的读/列/启停场景。
本项目面向**真实运维场景**：

- ✅ 一行创建 SQL / DAG 工作流
- ✅ 管理调度（创建 / 上线 / 下线 / 删除）
- ✅ 控制流程实例（暂停 / 恢复 / 重跑 / 从失败处重跑）
- ✅ 查看任务日志，强制任务成功 / 跳过失败任务
- ✅ 管理资源（查看 / 更新内容）
- ✅ 工作流版本回滚、克隆工作流
- ✅ 使用原始 API 作为兜底
- ✅ 支持**多租户每请求鉴权**

## 🚀 核心特性

- **53+ 工具**，覆盖 DS 大部分实用操作
- **两种鉴权模式**：API Token（`X-DS-Token`）或用户名密码（`X-DS-User` + `X-DS-Password`）
- **多租户 HTTP 模式**：每个调用方可使用自己的凭据
- **MCP 2.0 无状态 HTTP**：同时自动兼容 MCP 1.x 客户端
- **工作流创建**：简单 SQL 工作流 + 多任务类型复杂 DAG
- **调度管理**（基于 cron）
- **实例生命周期控制**（暂停 / 恢复 / 重跑 / 从失败处重跑 / 删除）
- **资源内容管理** 与 **版本回滚 / 工作流克隆**
- **原始 API 透传**，覆盖未封装的边缘场景

## 🚀 快速开始

### 前置条件

- 已运行的 DolphinScheduler 3.x，且其 API 可从 Docker 容器访问
- Docker 与 Compose v2（可通过 `docker compose version` 检查）
- DolphinScheduler API Token（推荐），或用户名和密码

```bash
# 1. 克隆仓库
git clone https://github.com/iflytek/dolphin-mcp-pilot.git
cd dolphin-mcp-pilot

# 2. 配置环境
cp .env.example .env
# 编辑 .env —— 设置 DS_URL 和 DS_TOKEN（或 DS_USER/DS_PASSWORD）
# DS_URL 示例：http://your-dolphinscheduler-host:12345/dolphinscheduler

# 3. 从当前源码构建并启动服务
docker compose --profile dev up -d dolphin-mcp-pilot-dev

# 4. 确认容器状态为 healthy
docker compose --profile dev ps
```

MCP 地址为 `http://localhost:8001/mcp/`（必须保留结尾斜杠）。将它加入支持
HTTP/SSE 的 MCP 客户端：

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

首次连接建议先进行安全的只读检查：**“列出我的 DolphinScheduler 项目和工作流，不要做任何
修改。”** 不同客户端的详细配置和用户名/密码鉴权方式请参阅[客户端配置](docs/CLIENT_CONFIG.md)。

## 💡 常见使用场景

| 场景 | 示例请求 | 主要工具 |
|---|---|---|
| 定位失败任务 | “找出最近失败的工作流，显示失败节点和日志，并给出下一步建议，不要执行修改。” | `ds_list_process_instances`、`ds_list_task_instances`、`ds_get_latest_failure_log` |
| 补跑缺失数据 | “按串行方式补跑 2026-08-01 至 2026-08-07，从校验节点开始并包含下游任务。” | `ds_complement_data` |
| 创建并调度工作流 | “创建一个每日 SQL 工作流并添加 cron 调度，上线前先展示定义让我确认。” | `ds_create_workflow`、`ds_set_schedule`、`ds_online_schedule` |
| 为多个 Agent 提供受控访问 | 运行一个 HTTP MCP 服务，由每个调用方提供各自的 DolphinScheduler 凭据。 | 每请求 `X-DS-*` 请求头 |

此外还可暂停、恢复、重跑、克隆和回滚工作流，管理资源，并通过原始 API 处理尚未封装的操作。
在 MCP 客户端中先调用 `ds_help(category="quickstart")`，可查看各类任务的推荐操作流程。

## 📚 文档

| 文档 | 说明 |
|---|---|
| [📦 安装指南](docs/INSTALLATION.md) | Docker Compose（dev/prod）、源码安装、包安装、运行模式 |
| [⚙️ 配置参考](docs/CONFIGURATION.md) | 环境变量、鉴权选项、Compose 可调参数 |
| [🚀 部署指南](docs/DEPLOYMENT.md) | 生产部署、Compose 参考、验证、排错 |
| [📊 功能特性](docs/FEATURES.md) | 功能对比表、工具分类 |
| [🔐 客户端配置](docs/CLIENT_CONFIG.md) | MCP 客户端接入（CodeBuddy、Claude Desktop 等）、多租户鉴权 |
| [📖 API 参考](docs/API.md) | 全部 53+ 工具、参数规范、错误处理 |
| [❓ 常见问题](docs/FAQ.md) | 常见问题与解决方案 |

## ✨ 最新动态

- **MCP 2.0**：支持 2026-07-28 无状态协议，同时保持旧版握手客户端和
  stdio 配置兼容。
- **引导式排错**：`ds_list_process_instances` 为 RUNNING/FAILURE 实例附加 `next_action`
  提示，引导 Agent 通过 `ds_list_task_instances` 检查具体任务节点。
- **可靠的补数据顺序**：串行补数据使用 `complementStartDate`/`complementEndDate`
  区间格式，保证 DolphinScheduler 按严格日期顺序生成实例。
- **灵活的任务参数**：`ds_update_task_param` 同时支持 `snake_case` 和
  `camelCase` 字段名，并返回被忽略的字段。

## 🤝 参与贡献

欢迎贡献。项目代码修改请阅读 [CONTRIBUTING.zh-CN.md](CONTRIBUTING.zh-CN.md)；如需分享已验证的 MCP 客户端配置，请按照[示例贡献指南](examples/README.md#中文)提交。

用 dolphin-mcp-pilot 做成过真实的事？欢迎写进 [`cases/`](cases/README.md)——一个社区使用故事画廊（智能体驱动的 DolphinScheduler 运维），每个案例都附一条公开帖子链接。

## 📄 许可证

[Apache-2.0](LICENSE)

## 🙏 致谢

基于官方 [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
构建，灵感来自 Apache DolphinScheduler 社区。
