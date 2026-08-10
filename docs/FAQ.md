# FAQ - 常见问题

dolphin-mcp-pilot 使用过程中的常见问题与解决方案。

---

## 部署与连接

### Q1：启动后无法连接 DolphinScheduler，报 Connection refused

**原因**：
- DolphinScheduler API 地址配置错误
- 网络不通（防火墙 / 容器网络隔离）
- DolphinScheduler 服务未启动

**解决**：
1. 检查 `.env` 中的 `DS_URL` 是否正确（格式：`http://host:port/dolphinscheduler`）
2. 在服务器上 `curl http://your-ds-host:12345/dolphinscheduler/ui/` 确认可访问
3. 检查防火墙规则：`sudo firewall-cmd --list-ports`
4. Docker 部署时确认网络模式（`--network host` 或桥接网络）

---

### Q2：认证失败，报 "User name or password incorrect"

**原因**：
- 账号密码错误
- DolphinScheduler 版本不兼容（API 路径变化）

**解决**：
1. 用浏览器登录 DolphinScheduler UI 确认账号可用
2. 检查 `.env` 的 `DS_USER` 和 `DS_PASSWORD`
3. 调用 `ds_test_connection` 测试认证
4. 如果是 3.x 版本，确认 API 前缀是否需要 `/api` 而非 `/dolphinscheduler`

---

### Q3：如何在 Claude Desktop / Cursor / Windsurf 中使用？

**解决**：
参考 [examples/](../examples/) 目录的配置示例：

**Claude Desktop**（Windows）：
```json
{
  "mcpServers": {
    "dolphin-mcp": {
      "command": "uvx",
      "args": ["--from", "dolphin-mcp-pilot", "dolphin-mcp-pilot"],
      "env": {
        "DS_URL": "http://your-ds-host:12345/dolphinscheduler",
        "DS_USER": "admin",
        "DS_PASSWORD": "your-password"
      }
    }
  }
}
```

**CodeBuddy**（stdio 模式）：
```json
{
  "mcpServers": {
    "dolphin-mcp": {
      "command": "python",
      "args": ["-m", "dolphin_mcp_pilot"],
      "env": {...}
    }
  }
}
```

**Cursor / Windsurf**（SSE 模式）：
启动 HTTP 服务器，配置 `http://localhost:8001/mcp/` 作为 MCP endpoint。

---

## 工作流操作

### Q4：创建工作流后无法运行，报 "workflow not online"

**原因**：
工作流创建后默认是草稿状态（offline），必须先上线。

**解决**：
```python
ds_release_workflow(project_code=xxx, workflow_code=xxx, release_state="ONLINE")
```

v2.0.8 增强：上线工作流时会自动检查关联调度，如果调度是 offline 状态会同步恢复。

---

### Q5：补数据时日期顺序错乱，如何保证串行执行？

**原因**：
v2.0.17 及更早版本的 `ds_complement_data` 在串行模式下使用日期列表格式，DolphinScheduler 后端会随机顺序执行。

**解决**：
升级到 v2.0.18+，串行补数据会自动使用区间格式：
```python
ds_complement_data(
    project_code=xxx,
    workflow_code=xxx,
    complement_start_date="2024-01-01",
    complement_end_date="2024-01-05",
    run_mode="RUN_MODE_SERIAL"  # 保证 01→02→03→04→05 正序
)
```

---

### Q6：修改任务参数时，preStatements 不生效

**原因**：
v2.0.16 及更早版本只支持 `pre_statements`（snake_case），传 `preStatements`（camelCase）会被忽略。

**解决**：
升级到 v2.0.17+，同时支持两种写法：
```python
ds_update_task_param(
    updates={
        "preStatements": ["SET hive.exec.parallel=true;"],  # ✅ 有效
        "pre_statements": ["SET ..."],                       # ✅ 也有效
    }
)
```

---

### Q7：如何查看失败工作流的日志？

**解决**：
使用 `ds_get_latest_failure_log` 一键获取：
```python
ds_get_latest_failure_log(project_code=xxx, workflow_code=xxx, limit=1)
```

返回最近一次失败实例的所有失败节点日志。

手动方式：
1. `ds_list_process_instances` 找到失败实例的 `id`
2. `ds_list_task_instances` 找到失败任务的 `id`
3. `ds_get_task_log` 获取日志

---

### Q8：ds_list_process_instances 返回很多实例，如何知道哪些需要处理？

**解决**：
v2.0.19 新增 `next_action` 引导机制。当实例状态为 `RUNNING_EXECUTION` 或 `FAILURE`，返回值会包含：
```json
{
  "instances": [...],
  "next_action": "检测到 2 个需要关注的实例（状态: FAILURE），建议调用 ds_list_task_instances(process_instance_id=xxx) 查看具体哪些节点失败"
}
```

按提示操作即可快速定位问题。

---

## 资源管理

### Q9：上传资源后，任务引用时找不到文件

**原因**：
- 资源路径不对（需要完整路径）
- 资源 ID 引用错误
- Worker 节点未挂载资源目录

**解决**：
1. 用 `ds_list_resources` 确认资源已上传，记录 `id`
2. 任务配置中用 `resource_list: [资源id]` 引用（是整数，不是路径字符串）
3. SHELL 任务中，DS 会把资源下载到当前目录，脚本里直接用文件名：
   ```bash
   python3 my_script.py  # 不要写 ./my_script.py
   ```

---

### Q10：更新资源文件后，任务还是用旧内容

**原因**：
Worker 缓存了资源文件。

**解决**：
- 使用 `ds_update_resource_content` 更新内容（会自动触发重新下载）
- 或删除重建资源（但会导致 `resource_id` 变化，所有引用任务要更新）

**推荐**：用 `ds_update_resource_content` 保持 ID 不变。

---

## 调度与补数据

### Q11：设置调度后不生效，工作流没有按时运行

**原因**：
调度创建后默认是 offline 状态。

**解决**：
```python
ds_set_schedule(...)       # 创建调度
ds_online_schedule(...)     # 激活调度
```

或直接用 `ds_release_workflow(release_state="ONLINE", auto_online_schedule=True)`，会自动激活关联调度。

---

### Q12：补数据时如何只补某个节点，不跑整个 DAG？

**解决**：
v2.0.7+ 支持 `task_depend_type` 参数：
```python
ds_complement_data(
    start_task_names=["sync_task"],
    task_depend_type="TASK_ONLY"  # 只跑这一个节点
)
```

`TASK_POST` 会跑该节点及其后续依赖。

---

## 版本回滚与克隆

### Q13：误修改工作流，如何恢复？

**解决**：
1. `ds_list_workflow_versions` 查看历史版本
2. `ds_rollback_workflow_version(version=上一个版本号)` 回滚

**注意**：回滚会创建新版本（不会删除错误版本），历史版本永久保留可追溯。

---

### Q14：如何复制工作流到另一个项目？

**解决**：
```python
ds_clone_workflow(
    source_project_code=xxx,
    source_workflow_code=xxx,
    target_project_code=yyy,
    new_name="克隆的工作流"
)
```

会完整复制 DAG 结构、任务配置、全局参数，但不会复制调度和实例历史。

---

## 错误排查

### Q15：任务一直卡在 SUBMITTED_SUCCESS，不执行

**原因**：
- Worker 节点挂了或队列满了
- 任务的 worker_group 配置错误（指定的组不存在）

**解决**：
1. `ds_monitor_workers` 确认 Worker 是否在线
2. 检查任务配置的 `workerGroup` 是否存在
3. 查看 DolphinScheduler Master 日志：`/opt/dolphinscheduler/logs/master-server.log`

---

### Q16：任务报 "NullPointerException"，但 SQL 单独跑没问题

**原因**：
- 数据源配置错误（`datasource_id` 不存在）
- preStatements / postStatements 格式错误

**解决**：
1. `ds_list_datasources` 确认数据源 ID
2. `ds_get_task_detail` 检查任务配置的 `taskParams.datasource`
3. 用 `ds_update_task_param` 修正配置

---

### Q17：补数据时实例创建了，但没有任何日志

**原因**：
补数据的日期范围超出工作流调度的有效期（`start_time` / `end_time`）。

**解决**：
检查调度配置：
```python
ds_list_schedules(workflow_code=xxx)
```

确认 `startTime` / `endTime` 包含补数据的日期范围。

---

## 性能与限制

### Q18：补数据时能同时跑多少个实例？

**限制**：
- 串行模式（`RUN_MODE_SERIAL`）：一次只跑 1 个
- 并行模式（`RUN_MODE_PARALLEL`）：默认并行度由 DolphinScheduler 配置决定

**调优**：
- 修改 Master 配置：`master.exec.threads` 和 `master.dispatch.task.number`
- 补数据时通过 `parallelism` 参数限制并行度（v2.0.9+）

---

### Q19：一次性补 100 天数据，如何避免压垮集群？

**解决**：
分批补数据，每次补 10-20 天：
```python
for start in ["2024-01-01", "2024-01-21", "2024-02-11", ...]:
    ds_complement_data(
        complement_start_date=start,
        complement_end_date=add_days(start, 20),
        run_mode="RUN_MODE_PARALLEL",
        parallelism=5  # 限制并行度
    )
    time.sleep(300)  # 等 5 分钟再补下一批
```

---

## 安全与权限

### Q20：如何限制 MCP 工具的权限，避免误删工作流？

**解决**：
1. 创建只读账号（DolphinScheduler 用户管理），只给查询权限
2. `.env` 配置用该账号：
   ```
   DS_USER=readonly_user
   DS_PASSWORD=xxx
   ```
3. 危险操作（删除工作流/项目）会因权限不足被 DS 拒绝

---

### Q21：多租户环境下，如何确保工作流隔离？

**解决**：
1. 每个 MCP 实例用独立的 `.env` 配置不同账号
2. DolphinScheduler 按项目授权，确保账号只能访问特定项目
3. 通过 `ds_list_tenants` 确认租户隔离配置

---

## 其他

### Q22：如何查看 MCP Server 支持哪些工具？

**解决**：
调用 `ds_help()` 获取交互式导航。或参考 [docs/API.md](API.md)。

---

### Q23：工具报错后如何查看详细日志？

**解决**：
1. 启动时设置 `LOG_LEVEL=DEBUG`
2. 查看容器日志：`docker logs dolphin-mcp-pilot`
3. 或查看本地日志：`logs/dolphin-mcp-pilot.log`（如果配置了文件日志）

---

### Q24：发现 bug 或需要新功能，如何反馈?

**解决**：
1. 在 GitHub 仓库提 Issue：`https://github.com/iflytek/dolphin-mcp-pilot/issues`
2. 描述问题时提供：
   - DolphinScheduler 版本
   - dolphin-mcp-pilot 版本
   - 完整错误日志
   - 重现步骤

---

## 版本兼容性

| dolphin-mcp-pilot | DolphinScheduler | Python |
|-------------------|------------------|--------|
| v0.2.0            | 2.x / 3.x        | 3.10+  |
| v0.1.0            | 2.x              | 3.10+  |

**注意**：DolphinScheduler 3.x 的 API 路径可能有变化，需要调整 `DS_URL`。

---

**更多问题？** 查看 [DEPLOYMENT.md](DEPLOYMENT.md) 或提 Issue。
