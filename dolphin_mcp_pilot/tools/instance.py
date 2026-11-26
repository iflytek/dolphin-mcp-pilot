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

"""Instance management tools."""

import json
import re
from datetime import datetime

from mcp.server.mcpserver import MCPServer

from ..client import ds_get, ds_post, ds_delete
from ..utils import require_ok, resolve_project_code


_ERROR_PATTERN = re.compile(
    r"ERROR|Exception|Traceback|Caused by|FAILED", re.IGNORECASE
)


def _log_text(data) -> str:
    """兼容 DS 日志返回字符串或包含 message/log 字段的对象。"""
    if isinstance(data, dict):
        return str(data.get("message") or data.get("log") or "")
    return data if isinstance(data, str) else (str(data) if data else "")


def _filter_log_lines(
    text: str, error_only: bool, grep: str, context_lines: int
) -> tuple[str, int]:
    """在有限日志窗口内提取错误/关键字上下文，不引入任意正则执行。"""
    lines = text.splitlines()
    needle = grep.casefold()
    matches = []
    for index, line in enumerate(lines):
        error_hit = error_only and bool(_ERROR_PATTERN.search(line))
        grep_hit = bool(needle) and needle in line.casefold()
        if error_hit or grep_hit:
            matches.append(index)
    if not matches:
        return "", 0
    selected = set()
    for index in matches:
        selected.update(
            range(
                max(0, index - context_lines),
                min(len(lines), index + context_lines + 1),
            )
        )
    return "\n".join(lines[i] for i in sorted(selected)), len(matches)


def register_instance_tools(mcp: MCPServer):
    """Register instance management MCP tools."""

    @mcp.tool()
    def ds_list_process_instances(
        project_name: str,
        workflow_code: int = 0,
        state: str = "",
        page_size: int = 20,
    ) -> list:
        """List process instances (filter by workflow_code, state).

        v2.0.12: merged ds_list_workflow_instances.
        - workflow_code=0 (default): list all recent instances in the project
        - workflow_code=<value>: list instances for that specific workflow

        Troubleshooting / Progress Tracking (v2.0.18):
        After getting instances, to understand execution details (which tasks running/failed/stuck),
        use ds_list_task_instances(process_instance_id=<id>, include_full=True) to view task states:
        - RUNNING_EXECUTION: instance running but no details → check task list for dispatched/running tasks
          (RUNNING instance with empty task list is normal — DS is initializing DAG)
        - FAILURE: locate failed tasks → find FAILURE tasks, then check their logs
        Each RUNNING/FAILURE instance returned includes a next_action hint.

        Args:
            project_name: Project name
            workflow_code: Process-definition code (0 = no filter, list all instances)
            state: State filter (FAILURE / SUCCESS / RUNNING_EXECUTION / STOP, empty = no filter)
            page_size: Number of items to return
        """
        pcode = resolve_project_code(project_name)
        path = f"/projects/{pcode}/process-instances?pageNo=1&pageSize={page_size}"
        if workflow_code:
            path += f"&processDefineCode={workflow_code}"
        if state:
            path += f"&stateType={state}"
        result = ds_get(path)
        require_ok(result, "list process instances")
        items = result.get("data", {}).get("totalList", []) or []
        # Fallback filter (some DS versions ignore processDefineCode param)
        if workflow_code:
            items = [
                i for i in items if i.get("processDefinitionCode") == workflow_code
            ]

        out = []
        for i in items:
            iid = i.get("id")
            st = i.get("state")
            entry = {
                "id": iid,
                "name": i.get("name"),
                "processDefinitionCode": i.get("processDefinitionCode"),
                "state": st,
                "startTime": i.get("startTime"),
                "endTime": i.get("endTime"),
                "runTimes": i.get("runTimes"),
                "scheduleTime": i.get("scheduleTime"),
            }
            # Provide next-action hints for running/failed instances
            if st == "RUNNING_EXECUTION":
                entry["next_action"] = (
                    f"Instance running, check task progress: "
                    f"ds_list_task_instances(process_instance_id={iid}, include_full=True)"
                )
            elif st == "FAILURE":
                entry["next_action"] = (
                    f"Instance failed, locate failed tasks: "
                    f"ds_list_task_instances(process_instance_id={iid}, state='FAILURE') "
                    f"or use ds_get_latest_failure_log for quick troubleshooting"
                )
            out.append(entry)
        return out

    @mcp.tool()
    def ds_stop_process_instance(project_name: str, process_instance_id: int) -> dict:
        """Stop a running workflow instance (force kill)."""
        pcode = resolve_project_code(project_name)
        result = ds_post(
            f"/projects/{pcode}/executors/execute",
            data={"processInstanceId": process_instance_id, "executeType": "STOP"},
        )
        require_ok(result, "execute instance operation STOP")
        return {
            "process_instance_id": process_instance_id,
            "executeType": "STOP",
            "status": "submitted",
        }

    @mcp.tool()
    def ds_pause_process_instance(project_name: str, process_instance_id: int) -> dict:
        """Pause a RUNNING workflow instance (reversible; not a stop).

        Tasks already running finish, no new tasks are started, and the instance
        ends in PAUSE state. Use ds_resume_process_instance to continue it, or
        ds_stop_process_instance to kill it instead.

        Args:
            project_name: Project name
            process_instance_id: Instance ID (from ds_list_process_instances)

        Returns:
            {"process_instance_id": int, "executeType": "PAUSE",
             "status": "submitted"}; the request is asynchronous, so check the
            state with ds_list_process_instances.
        """
        pcode = resolve_project_code(project_name)
        result = ds_post(
            f"/projects/{pcode}/executors/execute",
            data={"processInstanceId": process_instance_id, "executeType": "PAUSE"},
        )
        require_ok(result, "execute instance operation PAUSE")
        return {
            "process_instance_id": process_instance_id,
            "executeType": "PAUSE",
            "status": "submitted",
        }

    @mcp.tool()
    def ds_resume_process_instance(project_name: str, process_instance_id: int) -> dict:
        """Resume a workflow instance that is in PAUSE state.

        Continues from where ds_pause_process_instance stopped it. Not for failed
        or stopped instances: use ds_rerun_from_failure or ds_rerun_process_instance.

        Args:
            project_name: Project name
            process_instance_id: Instance ID (from ds_list_process_instances)

        Returns:
            {"process_instance_id": int,
             "executeType": "RECOVER_SUSPENDED_PROCESS", "status": "submitted"};
            the request is asynchronous.
        """
        pcode = resolve_project_code(project_name)
        result = ds_post(
            f"/projects/{pcode}/executors/execute",
            data={
                "processInstanceId": process_instance_id,
                "executeType": "RECOVER_SUSPENDED_PROCESS",
            },
        )
        require_ok(result, "execute instance operation RECOVER_SUSPENDED_PROCESS")
        return {
            "process_instance_id": process_instance_id,
            "executeType": "RECOVER_SUSPENDED_PROCESS",
            "status": "submitted",
        }

    @mcp.tool()
    def ds_rerun_process_instance(project_name: str, process_instance_id: int) -> dict:
        """Rerun entire workflow instance (from the beginning)."""
        pcode = resolve_project_code(project_name)
        result = ds_post(
            f"/projects/{pcode}/executors/execute",
            data={
                "processInstanceId": process_instance_id,
                "executeType": "REPEAT_RUNNING",
            },
        )
        require_ok(result, "execute instance operation REPEAT_RUNNING")
        return {
            "process_instance_id": process_instance_id,
            "executeType": "REPEAT_RUNNING",
            "status": "submitted",
        }

    @mcp.tool()
    def ds_rerun_from_failure(project_name: str, process_instance_id: int) -> dict:
        """Resume from failed tasks (rerun only failed and pending tasks, skip succeeded ones)."""
        pcode = resolve_project_code(project_name)
        result = ds_post(
            f"/projects/{pcode}/executors/execute",
            data={
                "processInstanceId": process_instance_id,
                "executeType": "START_FAILURE_TASK_PROCESS",
            },
        )
        require_ok(result, "execute instance operation START_FAILURE_TASK_PROCESS")
        return {
            "process_instance_id": process_instance_id,
            "executeType": "START_FAILURE_TASK_PROCESS",
            "status": "submitted",
        }

    @mcp.tool()
    def ds_delete_process_instance(project_name: str, process_instance_id: int) -> dict:
        """Permanently delete a finished workflow instance and its task records.

        Irreversible. DolphinScheduler rejects deleting a RUNNING instance; stop it
        first with ds_stop_process_instance. Does not affect the workflow definition.

        Args:
            project_name: Project name
            process_instance_id: Instance ID (from ds_list_process_instances)

        Returns:
            {"process_instance_id": int, "status": "deleted"}
        """
        pcode = resolve_project_code(project_name)
        result = ds_delete(f"/projects/{pcode}/process-instances/{process_instance_id}")
        require_ok(result, "delete process instance")
        return {"process_instance_id": process_instance_id, "status": "deleted"}

    @mcp.tool()
    def ds_complement_data(
        project_name: str,
        workflow_code: int,
        start_date: str = "",
        end_date: str = "",
        partition_date: str = "",
        worker_group: str = "default",
        start_task_names: list | None = None,
        task_depend_type: str = "TASK_POST",
        run_mode: str = "RUN_MODE_SERIAL",
        parallelism: int = 0,
        dry_run: bool = False,
    ) -> dict:
        """对工作流按日期范围做补数据运行（支持从指定节点向后补/只补某个节点/串行或并行）。

        ⚠️ DS 时间宏替换规则（必读）：
        - DS 任务里的 $[yyyyMMdd-1] 是按 scheduleTime 计算的，不是按当前实际日期
        - 补 06-15 这一天的数据 → 必须传 partition_date="2026-06-15"
          → 工具内部转 scheduleTime="2026-06-16 00:00:00"
          → DS 把 $[yyyyMMdd-1] 替换为 20260615 ✅
        - 用 start_date / end_date 时同样规则，传的是 scheduleTime（目标分区+1天）
        - 推荐优先用 partition_date 参数，语义直接，工具会自动 +1 天
        - 验证方法：跑完后看任务日志里 raw script 的 SCHEDULE_DATE 实际替换值

        自动处理 50014 错误（form 和 JSON 两种 scheduleTime 格式降级）。

        v2.0.11-hotfix3 改进：
        - 修复补数据 50014 错误：添加缺失的 startParams 字段 + 修正 complementScheduleDateList 为逗号分隔字符串
        - run_mode 默认改为 RUN_MODE_SERIAL（串行补数，按时间顺序一个一个跑，更安全）
        - 降级格式 (JSON) 修复为完整日期列表，不再只传 start_date 一天
        v2.0.11-hotfix6 改进：
        - 修复串行模式乱序：两种格式都完整展开日期列表再传给 DS，不再依赖 DS 内部扩展（可能乱序）

        Args:
            project_name: 项目名称
            workflow_code: 流程定义 code
            start_date: 开始日期 yyyy-MM-dd（**scheduleTime**，对应 $[yyyyMMdd-1] 替换值的前一天）
            end_date: 结束日期 yyyy-MM-dd，留空只补 start_date 一天
            partition_date: 分区日期 yyyy-MM-dd（推荐！直接指定要补的分区，自动+1天转成scheduleTime）
                           优先级高于 start_date，使用此参数时 start_date/end_date 会被忽略
                           例如 partition_date="2026-04-01" → scheduleTime="2026-04-02" → 写入 dt=20260401
            worker_group: worker 分组
            start_task_names: 起始节点任务名列表（留空表示从头开始跑整个工作流）
                             例如：["订单中间层依赖"] 表示从这个节点开始补
            task_depend_type: 任务依赖类型（只在 start_task_names 非空时生效）
                - "TASK_POST"：从起始节点及其所有后继节点（默认，从某节点向后补）
                - "TASK_ONLY"：只跑起始节点（只补某个节点）
                - "TASK_PRE"：起始节点及其所有前置节点
            run_mode: 补数运行模式
                - "RUN_MODE_SERIAL"：串行补数（默认，按时间顺序一个一个跑，更安全）
                - "RUN_MODE_PARALLEL"：并行补数（效率高，但可能产生资源冲突）
            parallelism: 请求的补数流程实例并行度（仅 PARALLEL，非 DAG 内任务并发）
            dry_run: True 时只返回计划日期和首选 payload，不提交执行（默认 False）
                         返回 planned_* 与 requested_parallelism；actual_parallelism 不会被伪造

        使用示例：
            # 1. 补整个工作流（默认串行，如需并行请显式指定 run_mode）
            ds_complement_data(project_name="xx", workflow_code=123, start_date="2024-01-01", end_date="2024-01-31")

            # 2. 直接指定分区日期（推荐，语义更清晰）
            ds_complement_data(
                project_name="xx", workflow_code=123,
                partition_date="2024-01-01"  # 补 dt=20240101，自动转成 scheduleTime=2024-01-02
            )

            # 3. 从某个节点向后补（节点及其下游）
            ds_complement_data(
                project_name="xx", workflow_code=123, partition_date="2024-01-01",
                start_task_names=["partition_check"],
                task_depend_type="TASK_POST"
            )

            # 4. 只补某个节点
            ds_complement_data(
                project_name="xx", workflow_code=123, partition_date="2024-01-01",
                start_task_names=["sync_redis"],
                task_depend_type="TASK_ONLY"
            )

            # 5. 并行补一个月（多日期同时跑，效率高但需注意资源冲突）
            ds_complement_data(
                project_name="xx", workflow_code=123,
                start_date="2024-01-01", end_date="2024-01-31",
                run_mode="RUN_MODE_PARALLEL"
            )
        """
        from datetime import timedelta
        import re

        if run_mode not in ("RUN_MODE_SERIAL", "RUN_MODE_PARALLEL"):
            raise ValueError("run_mode 只支持 RUN_MODE_SERIAL 或 RUN_MODE_PARALLEL")
        if parallelism < 0:
            raise ValueError("parallelism 不能小于 0")
        if run_mode != "RUN_MODE_PARALLEL" and parallelism > 0:
            raise ValueError("parallelism 仅在 RUN_MODE_PARALLEL 下可用，拒绝静默忽略")
        ignored_date_inputs = bool(partition_date and (start_date or end_date))

        def _normalize_date(d: str) -> str:
            """将 yyyyMMdd 或 yyyy-MM-dd 统一为 yyyy-MM-dd"""
            d = d.strip()
            m = re.fullmatch(r"(\d{4})-?(\d{2})-?(\d{2})", d)
            if m:
                return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
            raise ValueError(f"无法解析日期: {d}")

        # 统一日期格式
        if start_date:
            start_date = _normalize_date(start_date)
        if end_date:
            end_date = _normalize_date(end_date)

        pcode = resolve_project_code(project_name)

        # 处理 partition_date 参数（优先级高于 start_date）
        if partition_date:
            # 用户指定分区日期，自动 +1 天转成 scheduleTime
            partition_dt = datetime.strptime(
                _normalize_date(partition_date), "%Y-%m-%d"
            )
            schedule_dt = partition_dt + timedelta(days=1)
            start_date = schedule_dt.strftime("%Y-%m-%d")
            end_date = start_date
        elif not start_date:
            raise ValueError("必须提供 start_date 或 partition_date")

        if not end_date:
            end_date = start_date

        # 展开完整日期列表（按时间正序），DS 串行模式按列表顺序逐个执行
        sd = datetime.strptime(start_date, "%Y-%m-%d")
        ed = datetime.strptime(end_date, "%Y-%m-%d")
        if sd > ed:
            raise ValueError("start_date 不能晚于 end_date")
        instance_count = (ed - sd).days + 1
        date_list_str = []
        planned_biz_dates = []
        cur = sd
        while cur <= ed:
            date_list_str.append(cur.strftime("%Y-%m-%d") + " 00:00:00")
            planned_biz_dates.append((cur - timedelta(days=1)).strftime("%Y%m%d"))
            cur += timedelta(days=1)
        schedule_time_str = ",".join(date_list_str)

        # 处理起始节点：task name -> task code
        start_node_list = ""
        resolved_tasks: list = []
        if start_task_names:
            # 读取当前工作流定义，找到 task name 对应的 code
            wf = ds_get(f"/projects/{pcode}/process-definition/{workflow_code}")
            require_ok(wf, "获取工作流定义")
            task_defs = wf.get("data", {}).get("taskDefinitionList", []) or []
            name_to_code = {
                t.get("name"): t.get("code") for t in task_defs if t.get("name")
            }

            codes = []
            for name in start_task_names:
                code = name_to_code.get(name)
                if code is None:
                    raise ValueError(
                        f"任务 '{name}' 在工作流中不存在。可用任务: {list(name_to_code.keys())}"
                    )
                codes.append(str(code))
                resolved_tasks.append({"name": name, "code": code})
            start_node_list = ",".join(codes)

        base_payload = {
            "processDefinitionCode": workflow_code,
            "failureStrategy": "CONTINUE",
            "warningType": "NONE",
            "warningGroupId": 0,
            "execType": "COMPLEMENT_DATA",
            "taskDependType": task_depend_type,
            "complementDependentMode": "OFF_MODE",
            "runMode": run_mode,
            "processInstancePriority": "MEDIUM",
            "workerGroup": worker_group,
            "environmentCode": -1,
            "startParams": "",
            "dryRun": 0,
        }
        # 并行度（仅 RUN_MODE_PARALLEL 时生效，0 表示 DS 自动决定）
        if run_mode == "RUN_MODE_PARALLEL" and parallelism > 0:
            base_payload["expectedParallelismNumber"] = parallelism
        # 如果指定了起始节点，加到 payload
        if start_node_list:
            base_payload["startNodeList"] = start_node_list

        # ⚠️ 串行补数顺序修复（v2.0.18）：
        # DS 在 RUN_MODE_SERIAL 下，用离散日期列表（complementScheduleDateList/逗号分隔）
        # 时不保证按列表顺序执行，表现为"随机补数"。
        # DS 官方保证顺序的方式是用连续区间字段 complementStartDate + complementEndDate，
        # DS 内部会严格按天正序逐个生成实例。
        # 因此：串行模式优先用区间格式（顺序有保证）；并行模式或区间格式失败时再降级到列表格式。
        start_dt_str = sd.strftime("%Y-%m-%d") + " 00:00:00"
        end_dt_str = ed.strftime("%Y-%m-%d") + " 00:00:00"

        # 格式 A：连续区间格式（串行顺序有保证，DS 内部按天正序展开）
        range_payload = dict(
            base_payload,
            scheduleTime=json.dumps(
                {
                    "complementStartDate": start_dt_str,
                    "complementEndDate": end_dt_str,
                }
            ),
        )
        # 格式 B：逗号分隔列表（旧格式，兼容更多 DS 版本）
        payload_comma = dict(base_payload, scheduleTime=schedule_time_str)
        # 格式 C：JSON 离散列表（最后降级）
        schedule_time_json = json.dumps(
            {"complementScheduleDateList": schedule_time_str}
        )
        payload_list = dict(base_payload, scheduleTime=schedule_time_json)

        # 串行模式：区间格式优先（保证顺序）；并行模式：列表格式优先（可并发展开）
        if run_mode == "RUN_MODE_SERIAL":
            attempts = [
                ("date_range", range_payload),
                ("comma_separated", payload_comma),
                ("json_list", payload_list),
            ]
        else:
            attempts = [
                ("comma_separated", payload_comma),
                ("json_list", payload_list),
                ("date_range", range_payload),
            ]

        planned = {
            "workflow_code": workflow_code,
            "taskDependType": task_depend_type,
            "runMode": run_mode,
            "instanceCount": instance_count,
            "planned_instance_count": instance_count,
            "planned_schedule_dates": date_list_str,
            "planned_biz_dates": planned_biz_dates,
            "requested_parallelism": parallelism
            if run_mode == "RUN_MODE_PARALLEL"
            else None,
            "parallelism_scope": "process_instance_dates",
            "actual_parallelism": "not_observed",
            "startNodes": resolved_tasks or "从头开始",
        }
        if ignored_date_inputs:
            planned["ignored_inputs"] = ["start_date", "end_date"]
        if dry_run:
            return dict(
                planned,
                status="preview",
                format=attempts[0][0],
                scheduleTime=attempts[0][1].get("scheduleTime"),
                candidate_formats=[name for name, _ in attempts],
                hint="仅预检，未提交补数；planned 不代表实际生成或成功",
            )

        last_result = None
        for fmt_name, payload in attempts:
            try:
                result = ds_post(
                    f"/projects/{pcode}/executors/start-process-instance",
                    data=payload,
                )
                last_result = result
                if result.get("code") == 0:
                    return dict(
                        planned,
                        scheduleTime=payload.get("scheduleTime"),
                        status="submitted",
                        format=fmt_name,
                        hint=(
                            "补数已提交，planned 仅为计划日期和实例数，"
                            "请按实际实例及日志核对 generated/missing 业务日期"
                        ),
                    )
            except Exception:
                continue

        # 所有格式都失败，抛出最后一次的错误信息
        require_ok(last_result or {}, "触发补数据")

    @mcp.tool()
    def ds_list_task_instances(
        project_name: str,
        process_instance_id: int,
        state: str = "",
        include_full: bool = False,
    ) -> list:
        """List task instances for a process instance (filter by state, optionally include full details).

        v2.0.18: Added include_full parameter for detailed troubleshooting.

        Args:
            project_name: Project name
            process_instance_id: Process instance ID
            state: State filter (FAILURE / SUCCESS / RUNNING_EXECUTION, empty = no filter)
            include_full: When True, returns full taskParams/SQL/script for each task
                          (useful for detailed analysis but consumes more tokens)

        Returns:
            List of task instances with:
            - Basic info: id, name, taskType, state, startTime, endTime, retryTimes
            - If include_full=True: also includes taskParams (SQL/script/dependency config)
        """
        pcode = resolve_project_code(project_name)
        result = ds_get(
            f"/projects/{pcode}/process-instances/{process_instance_id}/tasks"
        )
        data = result.get("data", {}) or {}
        if isinstance(data, list):
            items = data
        elif isinstance(data, dict):
            items = data.get("taskList", []) or []
        else:
            items = []

        if state:
            items = [
                t for t in items if (t.get("state") or "").upper() == state.upper()
            ]

        out = []
        for t in items:
            entry = {
                "id": t.get("taskInstanceId") or t.get("id"),
                "name": t.get("taskName") or t.get("name"),
                "taskType": t.get("taskType"),
                "state": t.get("state"),
                "startTime": t.get("startTime"),
                "endTime": t.get("endTime"),
                "host": t.get("host"),
                "executePath": t.get("executePath"),
                "retryTimes": t.get("retryTimes", 0),
                "maxRetryTimes": t.get("maxRetryTimes", 0),
            }

            if include_full:
                # Parse taskParams (may be JSON string)
                params_raw = t.get("taskParams") or "{}"
                try:
                    params = (
                        json.loads(params_raw)
                        if isinstance(params_raw, str)
                        else params_raw
                    )
                except Exception:
                    params = {}

                entry["taskParams"] = params
                entry["workerGroup"] = t.get("workerGroup")
                entry["environmentCode"] = t.get("environmentCode")
                entry["varPool"] = t.get("varPool")

            out.append(entry)

        return out

    @mcp.tool()
    def ds_get_task_log(
        task_instance_id: int,
        skip_line_num: int = 0,
        limit: int = 500,
        error_only: bool = False,
        grep: str = "",
        context_lines: int = 20,
        max_scan_lines: int = 2000,
    ) -> dict:
        """获取任务日志，可只在有限窗口内提取错误/关键字上下文。

        默认保持原始单页日志行为。error_only/grep 开启后，limit 是每页读取行数，
        最多扫描 max_scan_lines，避免为找尾部异常反复盲猜 skip_line_num。
        返回 next_skip_line_num 和 truncated；未命中只代表当前扫描窗口，不能推断
        整个日志没有错误。grep 为大小写不敏感的字面量匹配，不执行正则。
        """
        if limit <= 0 or max_scan_lines <= 0:
            raise ValueError("limit 和 max_scan_lines 必须大于 0")
        if context_lines < 0:
            raise ValueError("context_lines 不能小于 0")
        filtering = error_only or bool(grep)
        if not filtering:
            result = ds_get(
                f"/log/detail?taskInstanceId={task_instance_id}"
                f"&skipLineNum={skip_line_num}&limit={limit}"
            )
            require_ok(result, "获取任务日志")
            text = _log_text(result.get("data", ""))
            return {
                "task_instance_id": task_instance_id,
                "log": text,
                "returned_lines": len(text.splitlines()),
                "next_skip_line_num": skip_line_num + len(text.splitlines()),
                "filtered": False,
            }

        chunks = []
        scanned = 0
        cursor = skip_line_num
        truncated = False
        while scanned < max_scan_lines:
            page_size = min(limit, max_scan_lines - scanned)
            result = ds_get(
                f"/log/detail?taskInstanceId={task_instance_id}"
                f"&skipLineNum={cursor}&limit={page_size}"
            )
            require_ok(result, "获取任务日志")
            page_text = _log_text(result.get("data", ""))
            page_lines = page_text.splitlines()
            if not page_lines:
                break
            chunks.extend(page_lines)
            scanned += len(page_lines)
            cursor += len(page_lines)
            if len(page_lines) < page_size:
                break
            if scanned >= max_scan_lines:
                truncated = True
        filtered, match_count = _filter_log_lines(
            "\n".join(chunks), error_only, grep, context_lines
        )
        return {
            "task_instance_id": task_instance_id,
            "log": filtered,
            "returned_lines": len(filtered.splitlines()),
            "match_count": match_count,
            "scanned_lines": scanned,
            "next_skip_line_num": cursor,
            "truncated": truncated,
            "filtered": True,
            "hint": "未命中仅表示当前扫描窗口无匹配" if not match_count else None,
        }

    @mcp.tool()
    def ds_force_task_success(project_name: str, task_instance_id: int) -> dict:
        """Force mark a task as success (dangerous — bypasses actual execution).

        ⚠️ Warning: Use only when task is stuck/failed but you've verified data correctness.
        This does NOT rerun the task — it only changes the state flag.
        """
        pcode = resolve_project_code(project_name)
        result = ds_post(
            f"/projects/{pcode}/task-instances/{task_instance_id}/force-success"
        )
        require_ok(result, "force task success")
        return {
            "task_instance_id": task_instance_id,
            "message": "Task marked as success",
        }

    @mcp.tool()
    def ds_skip_task(project_name: str, task_instance_id: int) -> dict:
        """Skip a task (mark as success without running).

        ⚠️ Warning: Use only for non-critical tasks (e.g., notifications).
        Downstream tasks will proceed as if this task succeeded.
        """
        pcode = resolve_project_code(project_name)
        result = ds_post(
            f"/projects/{pcode}/executors/execute",
            data={"taskInstanceId": task_instance_id, "executeType": "TASK_SKIP"},
        )
        require_ok(result, "skip task")
        return {
            "task_instance_id": task_instance_id,
            "message": "Task skipped",
        }

    @mcp.tool()
    def ds_get_latest_failure_log(
        project_name: str,
        workflow_code: int,
        log_limit: int = 500,
        error_only: bool = True,
    ) -> dict:
        """一键拿到某个工作流最近一次失败实例的所有失败节点日志。

        把排障常用的 3 步（列实例 → 列任务 → 取日志）合并为一步。

        v2.0.10 改进：每步独立错误处理，即使部分步骤失败也返回已有的诊断信息。

        Args:
            project_name: 项目名称
            workflow_code: 流程定义 code
            log_limit: 每个失败节点取多少行日志（默认 500）

        Returns:
            {
                "workflow_code": int,
                "instance_id": int,              # 最近一次失败实例 id
                "instance_state": "FAILURE",
                "start_time": str,
                "failed_tasks": [                # 所有失败节点
                    {
                        "task_instance_id": int,
                        "task_name": str,
                        "task_type": str,
                        "start_time": str,
                        "end_time": str,
                        "log_tail": str          # 日志（最近 log_limit 行）
                    }
                ],
                "errors": [...]                  # v2.0.10: 各步骤的错误信息
                "hint": ...
            }
        """

        pcode = resolve_project_code(project_name)
        step_errors = []

        # 1. 找最近一次失败实例
        try:
            result = ds_get(
                f"/projects/{pcode}/process-instances?pageNo=1&pageSize=20"
                f"&processDefineCode={workflow_code}&stateType=FAILURE"
            )
            require_ok(result, "查询失败实例")
            items = result.get("data", {}).get("totalList", []) or []
            # 兜底再过滤一次
            items = [
                i
                for i in items
                if i.get("processDefinitionCode") == workflow_code
                and (i.get("state") or "").upper() == "FAILURE"
            ]
        except Exception as e:
            return {
                "workflow_code": workflow_code,
                "instance_id": None,
                "failed_tasks": [],
                "errors": [f"步骤1(查询失败实例)失败: {e}"],
                "hint": "可能原因：DS 服务超时、workflow_code 不正确、网络问题",
            }

        if not items:
            return {
                "workflow_code": workflow_code,
                "instance_id": None,
                "failed_tasks": [],
                "hint": "最近没有失败实例（或 DS 查询接口对 workflow_code 过滤不生效）",
            }

        # DS 某些版本/代理不保证按时间排序，不能直接取接口第一条
        latest = max(
            items,
            key=lambda i: (
                str(i.get("endTime") or i.get("startTime") or ""),
                int(i.get("id") or 0),
            ),
        )
        instance_id = latest.get("id")

        # 2. 取该实例的所有任务
        try:
            tasks_result = ds_get(
                f"/projects/{pcode}/process-instances/{instance_id}/tasks"
            )
            tasks_data = tasks_result.get("data", {}) or {}
            if isinstance(tasks_data, list):
                all_tasks = tasks_data
            else:
                all_tasks = tasks_data.get("taskList", []) or []
        except Exception as e:
            step_errors.append(f"步骤2(获取实例任务)失败: {e}")
            all_tasks = []

        # 3. 筛出失败节点，拉日志
        FAILURE_STATES = {
            "FAILURE",
            "FAILED",
            "KILL",
            "NEED_FAULT_TOLERANCE",
            "FAILED_PAUSE",
            "STOP",
            "TIMEOUT",
        }

        failed_tasks = []
        for t in all_tasks:
            st = (t.get("state") or "").upper()
            if st not in FAILURE_STATES:
                continue

            tid = t.get("taskInstanceId") or t.get("id")
            log_tail = ""
            log_error = None
            log_meta = {}

            if tid:
                try:
                    log_view = ds_get_task_log(
                        task_instance_id=tid,
                        limit=log_limit,
                        error_only=error_only,
                        context_lines=20,
                        max_scan_lines=max(log_limit, 2000),
                    )
                    log_tail = log_view.get("log", "")
                    log_meta = {
                        "match_count": log_view.get("match_count"),
                        "scanned_lines": log_view.get("scanned_lines"),
                        "truncated": log_view.get("truncated"),
                    }
                except Exception as e:
                    log_error = f"日志拉取异常: {str(e)[:200]}"

            # 优化日志截断：按行截取最后 500 行
            if log_tail and isinstance(log_tail, str):
                lines = log_tail.split("\n")
                if len(lines) > 500:
                    log_tail = "\n".join(lines[-500:])
                if len(log_tail) > 8000:
                    log_tail = log_tail[-8000:]
            elif log_error:
                log_tail = f"[ERROR] {log_error}"

            if log_error:
                step_errors.append(
                    f"节点 {t.get('taskName') or t.get('name')}({tid}) 日志: {log_error}"
                )

            failed_tasks.append(
                {
                    "task_instance_id": tid,
                    "task_name": t.get("taskName") or t.get("name"),
                    "task_type": t.get("taskType"),
                    "state": st,
                    "start_time": t.get("startTime"),
                    "end_time": t.get("endTime"),
                    "log_tail": log_tail,
                    "log_fetch_error": log_error,
                    **log_meta,
                }
            )

        result = {
            "workflow_code": workflow_code,
            "instance_id": instance_id,
            "instance_name": latest.get("name"),
            "instance_state": latest.get("state"),
            "start_time": latest.get("startTime"),
            "end_time": latest.get("endTime"),
            "failed_task_count": len(failed_tasks),
            "failed_tasks": failed_tasks,
            "hint": (
                "如需完整日志用 ds_get_task_log(task_instance_id=...)；"
                "如需重跑用 ds_rerun_from_failure(process_instance_id=...)"
            ),
        }
        if step_errors:
            result["errors"] = step_errors
        return result
