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
- **工作流创建**：简单 SQL 工作流 + 多任务类型复杂 DAG
- **调度管理**（基于 cron）
- **实例生命周期控制**（暂停 / 恢复 / 重跑 / 从失败处重跑 / 删除）
- **资源内容管理** 与 **版本回滚 / 工作流克隆**
- **原始 API 透传**，覆盖未封装的边缘场景

## 🚀 快速开始

```bash
# 1. 克隆仓库
git clone https://github.com/iflytek/dolphin-mcp-pilot.git
cd dolphin-mcp-pilot

# 2. 配置环境
cp .env.example .env
# 编辑 .env —— 至少设置 DS_URL 和 DS_TOKEN（或 DS_USER/DS_PASSWORD）

# 3. 启动服务（dev 模式）
docker compose --profile dev up -d dolphin-mcp-pilot-dev
```

✅ 服务地址：`http://localhost:8001/mcp/`（注意结尾斜杠）

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

- **引导式排错**：`ds_list_process_instances` 为 RUNNING/FAILURE 实例附加 `next_action`
  提示，引导 Agent 通过 `ds_list_task_instances` 检查具体任务节点。
- **可靠的补数据顺序**：串行补数据使用 `complementStartDate`/`complementEndDate`
  区间格式，保证 DolphinScheduler 按严格日期顺序生成实例。
- **灵活的任务参数**：`ds_update_task_param` 同时支持 `snake_case` 和
  `camelCase` 字段名，并返回被忽略的字段。

## 🤝 参与贡献

欢迎贡献。项目代码修改请阅读 [CONTRIBUTING.zh-CN.md](CONTRIBUTING.zh-CN.md)；如需分享已验证的 MCP 客户端配置，请按照[示例贡献指南](examples/README.md#中文)提交。

## 📄 许可证

[Apache-2.0](LICENSE)

## 🙏 致谢

基于 [FastMCP](https://github.com/jlowin/fastmcp) 构建，灵感来自 Apache DolphinScheduler 社区。 (docs: slim README to OSS essentials; extract detailed content to docs/ (issue #13))
