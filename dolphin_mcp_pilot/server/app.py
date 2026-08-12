#!/usr/bin/env python3
# Copyright 2026 iFLYTEK CO., LTD.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""MCP server application."""

from mcp.server.mcpserver import MCPServer

from ..tools import (
    register_datasource_tools,
    register_help_tools,
    register_instance_tools,
    register_monitor_tools,
    register_project_tools,
    register_raw_tools,
    register_resource_tools,
    register_schedule_tools,
    register_user_tools,
    register_workflow_advanced_tools,
    register_workflow_tools,
)

# MCP 初始化时返回给客户端的使用指南
# 遵循 MCP 协议的 initialize.result.instructions 字段
_INSTRUCTIONS = """DolphinScheduler MCP v2.0.19 — 58 个工作流运维工具

⚡ 新用户第一步：调用 ds_help() 查看所有分类，或 ds_help(category="quickstart") 看快速上手指南。

📚 8 大分类（调用 ds_help(category="xxx") 看详情）：
  • project      项目管理（4 个工具）
  • workflow     工作流管理（13 个工具，核心）
  • instance     实例管理（13 个工具，排障核心）
  • schedule     调度管理（6 个工具）
  • resource     资源文件管理（10 个工具）
  • monitor      监控管理（2 个工具）
  • user         用户/租户管理（2 个工具）
  • raw          原始 API 兜底（5 个工具）

🎯 常见场景速查：
  • 排障：ds_get_latest_failure_log → ds_rerun_from_failure
  • 改工作流 DAG（追加/删除/修改节点）：ds_modify_workflow_dag
  • 修改 SHELL 任务脚本：ds_modify_workflow_dag(operations=[{"action":"update_task","updates":{"script":"..."}}])
  • 查某工作流最近跑了几次：ds_list_process_instances(workflow_code=...)
  • 查工作流当前调度：ds_list_schedules(workflow_code=..., simplify=True)
  • 只改 cron：ds_update_schedule_cron
  • 列资源（同时查 FILE + UDF）：ds_list_resources（默认 ALL 类型）
  • 上线工作流（自动恢复调度）：ds_release_workflow(online=True)
  • 验证节点改动：ds_get_task_detail(task_name="...")
  • 跟踪运行进度：先 ds_list_process_instances(workflow_code=...) 拿实例 id，再 ds_list_task_instances(process_instance_id=...) 看各节点状态

📋 工作流规范（强制）：
  1. SQL 节点命名：纯 SQL 写入节点的 name 必须与目标表名一致
  2. 补数据最小化：优先用 start_task_names + task_depend_type="TASK_POST" 从目标节点向后补，不要补整个工作流
  3. 补数据默认串行：run_mode="RUN_MODE_SERIAL"（默认），如需并行请显式指定 RUN_MODE_PARALLEL
  4. 触发运行/补数后跟踪进度：优先看任务实例（ds_list_task_instances），不要只等工作流实例状态。
     实例长时间 RUNNING_EXECUTION 但任务列表为空是 DS 正在初始化 DAG 的正常现象，应查任务节点是否已派发

⚠️ 风险工具（返回值带 warning 字段）：
  • ds_rename_resource / ds_update_resource_content / ds_delete_resource
  • ds_delete_workflow / ds_force_task_success / ds_skip_task
  这些工具调用后返回值会带 warning 字段，请读给用户确认后再继续。

详细文档：调用 ds_help() 或加载 ds-workflow-ops skill。
"""

# Create the MCP application. MCPServer v2 serves both the legacy handshake
# protocol and the stateless 2026-07-28 protocol from the same server.
mcp = MCPServer(
    "DolphinScheduler",
    instructions=_INSTRUCTIONS,
    version="0.3.0",
)

# 注册所有工具
register_project_tools(mcp)
register_datasource_tools(mcp)
register_workflow_tools(mcp)
register_workflow_advanced_tools(mcp)
register_instance_tools(mcp)
register_schedule_tools(mcp)
register_resource_tools(mcp)
register_monitor_tools(mcp)
register_user_tools(mcp)
register_raw_tools(mcp)
register_help_tools(mcp)
