# API Reference

dolphin-mcp-pilot v0.4.0 工具 API 参考文档。

完整的 59 个工具按功能分类，每个工具通过 MCP 协议调用。

---

## 快速导航

运行时可以调用 `ds_help()` 获取交互式导航和分类列表。

```python
# MCP 调用示例
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/call",
  "params": {
    "name": "ds_help",
    "arguments": {}
  }
}
```

---

## 工具分类

### 1. 连通性测试（1 个工具）

- **ds_test_connection**：测试与 DolphinScheduler 的连接是否正常。

### 2. 项目管理（5 个工具）

- **ds_list_projects**：列出所有项目。
- **ds_create_project**：创建新项目。
- **ds_rename_project**：重命名项目。
- **ds_delete_project**：删除项目。

### 3. 数据源（1 个工具）

- **ds_list_datasources**：列出所有数据源配置。

### 4. 工作流管理（8 个工具）

- **ds_list_workflows**：列出指定项目的工作流。
- **ds_get_workflow**：获取工作流详细信息。
- **ds_create_workflow**：创建工作流（JSON 配置）。
- **ds_release_workflow**：发布工作流（上线）。
- **ds_run_workflow**：手动触发工作流运行。
- **ds_delete_workflow**：删除工作流。
- **ds_update_workflow**：更新工作流配置。
- **ds_get_task_detail**：获取任务节点详细信息。

### 5. 工作流高级操作（8 个工具）

- **ds_list_workflow_versions**：查看工作流版本历史。
- **ds_rollback_workflow_version**：回滚到指定版本。
- **ds_clone_workflow**：克隆工作流。
- **ds_create_dag_workflow**：可视化创建 DAG 工作流。
- **ds_modify_workflow_dag**：修改 DAG 结构（支持 `expected_version`、`timeout_seconds` 和写后回读）。
- **ds_update_task_param**：更新任务参数（支持 snake_case 和 camelCase）。
- **ds_patch_task_content**：局部替换 SQL/SHELL；默认 dry-run 返回 diff，正式写入防版本覆盖并回读验证内容。

### 6. 调度管理（6 个工具）

- **ds_list_schedules**：列出调度配置。
- **ds_set_schedule**：设置或更新调度（CRON 表达式）。
- **ds_online_schedule**：启用调度（上线）。
- **ds_offline_schedule**：停用调度（下线）。
- **ds_delete_schedule**：删除调度。
- **ds_update_schedule_cron**：更新调度时间。

### 7. 实例管理（13 个工具）

- **ds_list_process_instances**：列出工作流实例（带 `next_action` 引导提示）。
- **ds_stop_process_instance**：停止运行中的实例。
- **ds_pause_process_instance**：暂停实例。
- **ds_resume_process_instance**：恢复暂停的实例。
- **ds_rerun_process_instance**：重新运行实例。
- **ds_rerun_from_failure**：从失败节点重跑。
- **ds_delete_process_instance**：删除实例。
- **ds_complement_data**：补数据（支持串行/并行，v2.0.18 修复顺序问题）。
- **ds_list_task_instances**：列出任务节点实例。
- **ds_get_task_log**：获取任务日志。
- **ds_force_task_success**：强制任务成功。
- **ds_skip_task**：跳过任务。
- **ds_get_latest_failure_log**：获取最新失败日志。

### 8. 资源管理（5 个工具）

- **ds_list_resources**：列出资源文件。
- **ds_view_resource**：查看资源文件内容。
- **ds_get_resource_by_name**：根据名称获取资源。
- **ds_create_folder**：创建资源目录。
- **ds_online_create_file**：在线创建资源文件。
- **ds_upload_file**、**ds_update_resource_content**、**ds_rename_resource**、**ds_delete_resource**、**ds_download_resource**（其他 5 个资源操作工具）

### 9. 监控（2 个工具）

- **ds_monitor_masters**：查询 Master 节点状态。
- **ds_monitor_workers**：查询 Worker 节点状态。

### 10. 用户与租户（2 个工具）

- **ds_list_users**：列出用户。
- **ds_list_tenants**：列出租户。

### 11. 原始 API 透传（4 个工具）

- **ds_raw_get**：GET 请求透传。
- **ds_raw_post**：POST 请求透传。
- **ds_raw_put**：PUT 请求透传。
- **ds_raw_delete**：DELETE 请求透传。

### 12. 帮助导航（1 个工具）

- **ds_help**：交互式工具导航，支持分类过滤。

---

## 认证

所有工具调用需要在 HTTP 请求头中提供 DolphinScheduler 凭据：

**方式一：用户名密码**
```
X-DS-User: your-username
X-DS-Password: your-password
```

**方式二：Token**
```
X-DS-Token: your-session-token
```

---

## 参数规范

### snake_case vs camelCase

`ds_update_task_param` 等工具同时支持两种命名风格：
- `pre_statements` 和 `preStatements` 等价
- `post_statements` 和 `postStatements` 等价
- `timeout_flag` 和 `timeoutFlag` 等价

如果同时提供两者，优先使用 snake_case。

### 补数据顺序保证（v2.0.18 修复）

`ds_complement_data` 串行模式（`RUN_MODE_SERIAL`）使用区间格式：
```json
{
  "complementStartDate": "2024-01-01",
  "complementEndDate": "2024-01-05"
}
```

DolphinScheduler 会按天正序生成实例（01-01 → 01-02 → 01-03...），不会随机顺序。

---

## 错误处理

所有工具在 DolphinScheduler API 返回错误时会抛出 `RuntimeError`，包含：
- 错误码（`code`）
- 错误信息（`msg`）
- 操作描述

示例错误：
```
RuntimeError: 查询项目失败 (code=10001): Project 'my_project' not found
```

---

## 完整工具列表（按字母序）

1. ds_clone_workflow
2. ds_complement_data
3. ds_create_dag_workflow
4. ds_create_folder
5. ds_create_project
6. ds_create_workflow
7. ds_delete_process_instance
8. ds_delete_project
9. ds_delete_resource
10. ds_delete_schedule
11. ds_delete_workflow
12. ds_download_resource
13. ds_force_task_success
14. ds_get_latest_failure_log
15. ds_get_resource_by_name
16. ds_get_task_detail
17. ds_get_task_log
18. ds_get_workflow
19. ds_help
20. ds_list_datasources
21. ds_list_process_instances
22. ds_list_projects
23. ds_list_resources
24. ds_list_schedules
25. ds_list_task_instances
26. ds_list_tenants
27. ds_list_users
28. ds_list_workflow_versions
29. ds_list_workflows
30. ds_modify_workflow_dag
31. ds_monitor_masters
32. ds_monitor_workers
33. ds_offline_schedule
34. ds_online_create_file
35. ds_online_schedule
36. ds_pause_process_instance
37. ds_raw_delete
38. ds_raw_get
39. ds_raw_post
40. ds_raw_put
41. ds_rename_project
42. ds_rename_resource
43. ds_rerun_from_failure
44. ds_rerun_process_instance
45. ds_resume_process_instance
46. ds_rollback_workflow_version
47. ds_run_workflow
48. ds_set_schedule
49. ds_skip_task
50. ds_stop_process_instance
51. ds_test_connection
52. ds_update_resource_content
53. ds_update_schedule_cron
54. ds_update_task_param
55. ds_update_workflow
56. ds_upload_file
57. ds_view_resource
58. ds_release_workflow
59. ds_patch_task_content

---

## 版本历史

- **v0.4.0**：当前版本，59 工具
- **v0.2.0**：58 工具
- **v0.1.0**：初始版本，53 工具

详见 [CHANGELOG.md](../CHANGELOG.md)
