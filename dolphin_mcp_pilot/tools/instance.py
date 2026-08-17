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
from datetime import datetime

from mcp.server.mcpserver import MCPServer

from ..client import ds_get, ds_post, ds_delete
from ..utils import require_ok, resolve_project_code


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
        """Pause a running workflow instance."""
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
        """Resume a paused workflow instance."""
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
        """Delete a historical process instance."""
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
        start_task_names: list = None,
        task_depend_type: str = "TASK_POST",
        run_mode: str = "RUN_MODE_SERIAL",
    ) -> dict:
        """Backfill (complement) workflow data for date range or single partition.

        Recommended usage (v2.0.14):
        - Single partition: partition_date="2024-01-01" (clearer semantics, recommended)
        - Date range: start_date + end_date (multi-partition backfill)
        - From specific task: start_task_names + task_depend_type="TASK_POST"
        - Single task only: start_task_names + task_depend_type="TASK_ONLY"

        ⚠️ Important (v2.0.19):
        1. Default mode: RUN_MODE_SERIAL (one partition at a time, safer)
        2. Parallel mode: run_mode="RUN_MODE_PARALLEL" (multiple partitions concurrently, higher risk)
        3. Before backfill: check dependency chain with ds_get_workflow → analyze upstream deps
        4. Minimize scope: prefer start_task_names + TASK_POST to backfill from target task forward
        5. Mandatory standard: don't backfill entire workflow unless full-chain rerun is explicitly needed

        Args:
            project_name: Project name
            workflow_code: Process-definition code
            start_date: Start date yyyy-MM-dd (for range backfill)
            end_date: End date yyyy-MM-dd (for range backfill)
            partition_date: Single partition yyyy-MM-dd (alternative to start_date+end_date, recommended for clarity)
            start_task_names: Optional list of task names to start from (backfills these + their downstream tasks)
            task_depend_type: Dependency type (default TASK_POST: from start tasks forward;
                              TASK_ONLY: start tasks only; TASK_PRE: start tasks + upstream)
            run_mode: RUN_MODE_SERIAL (default, one at a time) or RUN_MODE_PARALLEL (concurrent)

        Serial ordering guarantee (v2.0.18):
            In RUN_MODE_SERIAL, the request is submitted using DS's continuous range
            fields complementStartDate / complementEndDate, so DS generates instances
            strictly in ascending day order. Discrete date-list formats
            (complementScheduleDateList / comma-separated) do not guarantee ordering
            and are only used as fallbacks. The chosen format is reported in the
            return value's "format" field ("date_range" / "comma_separated" / "json_list").

        Examples:
            # Single partition (recommended)
            ds_complement_data(workflow_code=123, partition_date="2024-01-01")

            # Date range (serial mode, safer)
            ds_complement_data(workflow_code=123, start_date="2024-01-01", end_date="2024-01-31")

            # From specific task forward (minimize scope)
            ds_complement_data(workflow_code=123, partition_date="2024-01-01",
                               start_task_names=["ads_table"], task_depend_type="TASK_POST")

            # Parallel mode (higher concurrency, more resource usage)
            ds_complement_data(workflow_code=123, start_date="2024-01-01", end_date="2024-01-10",
                               run_mode="RUN_MODE_PARALLEL")
        """
        if partition_date:
            start_date = partition_date
            end_date = partition_date

        if not start_date or not end_date:
            raise ValueError(
                "Must provide either partition_date or both start_date and end_date"
            )

        pcode = resolve_project_code(project_name)

        sd = datetime.strptime(start_date, "%Y-%m-%d")
        ed = datetime.strptime(end_date, "%Y-%m-%d")
        if ed < sd:
            raise ValueError("end_date must not be earlier than start_date")
        instance_count = (ed - sd).days + 1

        start_node_list = ",".join(start_task_names) if start_task_names else ""
        schedule_time_str = f"{start_date} 00:00:00,{end_date} 00:00:00"

        base_payload = {
            "processDefinitionCode": workflow_code,
            "taskDependType": task_depend_type,
            "runMode": run_mode,
            "failureStrategy": "END",
            "warningType": "NONE",
            "warningGroupId": 0,
            "processInstancePriority": "MEDIUM",
            "workerGroup": "default",
            "environmentCode": -1,
            "startParams": "",
            "dryRun": 0,
        }
        if start_node_list:
            base_payload["startNodeList"] = start_node_list

        # ⚠️ Serial complement ordering fix (v2.0.18):
        # Under RUN_MODE_SERIAL, DS does not guarantee execution order when given a
        # discrete date list (complementScheduleDateList / comma-separated), which
        # manifests as "random backfill".
        # The format DS honors for ordering is the continuous range pair
        # complementStartDate + complementEndDate — DS then generates instances
        # strictly in ascending day order.
        # Therefore: serial mode prefers the range format (order guaranteed);
        # parallel mode, or a failed range attempt, falls back to the list formats.
        start_dt_str = sd.strftime("%Y-%m-%d") + " 00:00:00"
        end_dt_str = ed.strftime("%Y-%m-%d") + " 00:00:00"

        # Format A: continuous range (ordering guaranteed, DS expands day by day)
        range_payload = dict(
            base_payload,
            scheduleTime=json.dumps(
                {
                    "complementStartDate": start_dt_str,
                    "complementEndDate": end_dt_str,
                }
            ),
        )
        # Format B: comma-separated list (legacy format, broader DS version support)
        payload_comma = dict(base_payload, scheduleTime=schedule_time_str)
        # Format C: JSON discrete list (last resort)
        payload_list = dict(
            base_payload,
            scheduleTime=json.dumps({"complementScheduleDateList": schedule_time_str}),
        )

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

        last_result = None
        for fmt_name, payload in attempts:
            try:
                result = ds_post(
                    f"/projects/{pcode}/executors/start-process-instance",
                    data=payload,
                )
                last_result = result
                if result.get("code") == 0:
                    return {
                        "workflow_code": workflow_code,
                        "scheduleTime": payload.get("scheduleTime"),
                        "start_date": start_date,
                        "end_date": end_date,
                        "taskDependType": task_depend_type,
                        "runMode": run_mode,
                        "instanceCount": instance_count,
                        "startNodes": start_task_names or "from the beginning",
                        "status": "submitted",
                        "format": fmt_name,
                        "hint": (
                            "Serial complement submitted as a date range; DS will "
                            "execute day by day in ascending order"
                            if fmt_name == "date_range"
                            else "Complement submitted"
                        )
                        + ". ⚠️ Prefer ds_list_task_instances(process_instance_id=...) "
                        "to inspect task node progress instead of only watching the "
                        "workflow instance state",
                    }
            except Exception:
                continue

        # All formats failed — surface the last error
        require_ok(last_result or {}, "trigger complement")

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
        limit: int = 1000,
    ) -> dict:
        """Fetch task execution log (supports pagination).

        Args:
            task_instance_id: Task instance ID (from ds_list_task_instances)
            skip_line_num: Skip first N lines (for pagination)
            limit: Max lines to fetch (default 1000)

        Returns:
            {
                "task_instance_id": int,
                "log": str,
                "line_start": int,
                "line_count": int,
                "hint": str
            }
        """
        result = ds_get(
            f"/log/detail?taskInstanceId={task_instance_id}"
            f"&skipLineNum={skip_line_num}&limit={limit}"
        )
        require_ok(result, "fetch task log")

        log_data = result.get("data", "")
        if isinstance(log_data, dict):
            log_text = (
                log_data.get("message", "") or log_data.get("log", "") or str(log_data)
            )
        elif isinstance(log_data, str):
            log_text = log_data
        else:
            log_text = str(log_data) if log_data else ""

        return {
            "task_instance_id": task_instance_id,
            "log": log_text,
            "line_start": skip_line_num,
            "line_count": len(log_text.split("\n")) if log_text else 0,
            "hint": f"Fetched {limit} lines starting from line {skip_line_num}. "
            "For more, increase skip_line_num.",
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
    ) -> dict:
        """One-click fetch of all failed task logs from the latest failed instance.

        Combines 3 common troubleshooting steps (list instances → list tasks → fetch logs).

        v2.0.10: Added per-step error handling — returns partial diagnostic info even if some steps fail.

        Args:
            project_name: Project name
            workflow_code: Process-definition code
            log_limit: Lines of log to fetch per failed task (default 500)

        Returns:
            {
                "workflow_code": int,
                "instance_id": int,              # Latest failed instance ID
                "instance_state": "FAILURE",
                "start_time": str,
                "failed_tasks": [                # All failed tasks
                    {
                        "task_instance_id": int,
                        "task_name": str,
                        "task_type": str,
                        "start_time": str,
                        "end_time": str,
                        "log_tail": str          # Last log_limit lines
                    }
                ],
                "errors": [...]                  # v2.0.10: Per-step error messages
                "hint": ...
            }
        """

        pcode = resolve_project_code(project_name)
        step_errors = []

        # 1. Find latest failed instance
        try:
            result = ds_get(
                f"/projects/{pcode}/process-instances?pageNo=1&pageSize=20"
                f"&processDefineCode={workflow_code}&stateType=FAILURE"
            )
            require_ok(result, "query failed instances")
            items = result.get("data", {}).get("totalList", []) or []
            # Fallback filter
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
                "errors": [f"Step 1 (query failed instances) failed: {e}"],
                "hint": "Possible causes: DS service timeout, incorrect workflow_code, network issue",
            }

        if not items:
            return {
                "workflow_code": workflow_code,
                "instance_id": None,
                "failed_tasks": [],
                "hint": "No recent failed instances (or DS query API filter is ineffective for workflow_code)",
            }

        latest = items[0]
        instance_id = latest.get("id")

        # 2. Get all tasks for this instance
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
            step_errors.append(f"Step 2 (get instance tasks) failed: {e}")
            all_tasks = []

        # 3. Filter failed tasks and fetch logs
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

            if tid:
                try:
                    log_result = ds_get(
                        f"/log/detail?taskInstanceId={tid}&skipLineNum=0&limit={log_limit}"
                    )
                    if log_result.get("code") == 0:
                        log_data = log_result.get("data", "")
                        # Handle data as dict (with message field) or string
                        if isinstance(log_data, dict):
                            log_tail = (
                                log_data.get("message", "")
                                or log_data.get("log", "")
                                or ""
                            )
                        elif isinstance(log_data, str):
                            log_tail = log_data
                        else:
                            log_tail = str(log_data) if log_data else ""
                    else:
                        log_error = f"Log fetch failed (code={log_result.get('code')}): {log_result.get('msg', 'unknown')}"
                except Exception as e:
                    log_error = f"Log fetch exception: {str(e)[:200]}"

            # Optimize log truncation: take last 500 lines
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
                    f"Task {t.get('taskName') or t.get('name')}({tid}) log: {log_error}"
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
                "For full logs, use ds_get_task_log(task_instance_id=...); "
                "For rerun, use ds_rerun_from_failure(process_instance_id=...)"
            ),
        }
        if step_errors:
            result["errors"] = step_errors
        return result
