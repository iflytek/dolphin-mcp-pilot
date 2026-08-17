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

"""Workflow basic operation tools."""

import json
import time

from mcp.server.mcpserver import MCPServer

from ..client import ds_get, ds_post, ds_delete
from ..config import get_tenant_code
from ..utils import require_ok, resolve_project_code


def register_workflow_tools(mcp: MCPServer):
    """Register workflow basic operation MCP tools."""

    @mcp.tool()
    def ds_list_workflows(
        project_name: str,
        page_no: int = 1,
        page_size: int = 100,
        search: str = "",
        name: str = "",
        use_simple: bool = False,
    ) -> list:
        """List workflow definitions with pagination, search and exact-match support.

        v2.0.12: merged ds_list_workflows_simple and ds_get_workflow_by_name.
        - Default: paginated API (auto-falls back to simple-list on failure)
        - search="xx": case-insensitive fuzzy match on name + description
        - name="xxx": exact name match (single-element list or empty list)
        - use_simple=True: use /process-definition/simple-list (bypasses pagination SQL)

        Args:
            project_name: Project name
            page_no: Page number, starting at 1
            page_size: Items per page (max recommended 100)
            search: Fuzzy search keyword (name + description)
            name: Exact workflow name match
            use_simple: Use simple-list endpoint when True
        """
        pcode = resolve_project_code(project_name)

        if use_simple:
            simple_result = ds_get(f"/projects/{pcode}/process-definition/simple-list")
            require_ok(simple_result, "list workflows (simple)")
            data = simple_result.get("data")
            if data is None:
                items = []
            elif isinstance(data, list):
                items = data
            elif isinstance(data, dict):
                items = data.get("list", []) or data.get("data", []) or []
            else:
                items = []
        else:
            result = ds_get(
                f"/projects/{pcode}/process-definition?pageNo={page_no}&pageSize={page_size}"
            )
            # Auto-fallback to simple-list on pagination failure
            if result.get("code") != 0:
                simple_result = ds_get(
                    f"/projects/{pcode}/process-definition/simple-list"
                )
                require_ok(simple_result, "list workflows (simple fallback)")
                items = simple_result.get("data", []) or []
            else:
                items = result.get("data", {}).get("totalList", [])

        workflows = [
            {
                "id": w.get("id"),
                "code": w.get("code"),
                "name": w.get("name"),
                "releaseState": w.get("releaseState", "OFFLINE"),
                "description": w.get("description", ""),
                "projectCode": w.get("projectCode"),
            }
            for w in items
            if w and w.get("code")
        ]

        # Exact match takes precedence
        if name:
            return [w for w in workflows if w.get("name") == name]

        # Fuzzy search
        if search:
            kw = search.lower()
            workflows = [
                w
                for w in workflows
                if kw in (w.get("name") or "").lower()
                or kw in (w.get("description") or "").lower()
            ]

        return workflows

    @mcp.tool()
    def ds_get_workflow(
        project_name: str, workflow_code: int, compact: bool = False
    ) -> dict:
        """Read a single workflow definition (DAG, global params, node coordinates, etc.).

        Args:
            project_name: Project name
            workflow_code: Process-definition code (from ds_list_workflows)
            compact: Compact mode (default False). When True, returns only metadata
                     and task summary without full taskParams/SQL, greatly reducing
                     token usage. Suitable when you only need to understand DAG structure.
        """
        pcode = resolve_project_code(project_name)
        result = ds_get(f"/projects/{pcode}/process-definition/{workflow_code}")
        require_ok(result, "get workflow definition")
        data = result.get("data", {})
        pd = data.get("processDefinition", {})
        tasks = data.get("processTaskRelationList", [])
        task_defs = data.get("taskDefinitionList", [])

        # Parse locations (may be JSON string)
        locations_raw = pd.get("locations", "[]") or "[]"
        try:
            locations = (
                json.loads(locations_raw)
                if isinstance(locations_raw, str)
                else list(locations_raw)
            )
        except Exception:
            locations = []

        # Compact mode: return metadata + task summary only, without full taskParams/SQL
        if compact:
            compact_tasks = []
            for t in task_defs or []:
                ttype = t.get("taskType", "")
                params = t.get("taskParams", {}) or {}
                summary = {}
                if ttype == "SQL":
                    sql = (params.get("sql") or "")[:100]
                    summary["sql_preview"] = sql + (
                        "..." if len(params.get("sql") or "") > 100 else ""
                    )
                    summary["datasource_id"] = params.get("datasource")
                elif ttype in ("SHELL", "PYTHON"):
                    script = (params.get("rawScript") or "")[:100]
                    summary["script_preview"] = script + (
                        "..." if len(params.get("rawScript") or "") > 100 else ""
                    )
                elif ttype == "DEPENDENT":
                    deps = params.get("dependence", {})
                    items_list = deps.get("dependTaskList", [{}])[0].get(
                        "dependItemList", []
                    )
                    summary["depend_count"] = len(items_list)
                compact_tasks.append(
                    {
                        "code": t.get("code"),
                        "name": t.get("name"),
                        "taskType": ttype,
                        "description": t.get("description", ""),
                        "workerGroup": t.get("workerGroup"),
                        "failRetryTimes": t.get("failRetryTimes", 0),
                        "failRetryInterval": t.get("failRetryInterval", 1),
                        "timeout": t.get("timeout", 0),
                        **summary,
                    }
                )
            return {
                "code": pd.get("code"),
                "name": pd.get("name"),
                "description": pd.get("description", ""),
                "releaseState": pd.get("releaseState"),
                "globalParams": pd.get("globalParams"),
                "locations": locations,
                "task_count": len(compact_tasks),
                "taskRelations": [
                    {"from": r.get("preTaskCode"), "to": r.get("postTaskCode")}
                    for r in (tasks or [])
                ],
                "tasks": compact_tasks,
            }

        return {
            "code": pd.get("code"),
            "name": pd.get("name"),
            "description": pd.get("description", ""),
            "releaseState": pd.get("releaseState"),
            "globalParams": pd.get("globalParams"),
            "locations": locations,  # node coordinates [{taskCode, x, y}]
            "taskRelations": tasks,
            "taskDefinitions": task_defs,
        }

    @mcp.tool()
    def ds_create_workflow(
        project_name: str,
        name: str,
        description: str = "",
        sql_statements: str = "",
        datasource_id: int = 0,
        sql_ds_type: str = "HIVE",
        tasks_json: str = "",
        relations_json: str = "",
        schedule: bool = True,
        schedule_cron: str = "0 0 6 * * ? *",
        schedule_start: str = "",
        schedule_end: str = "",
        auto_online: bool = True,
    ) -> dict:
        """Create a workflow (supports simple SQL mode and complex DAG mode).

        Mode 1 - Simple SQL (backward compatible):
        - Provide sql_statements + datasource_id
        - Multiple SQL separated by ";;;" are executed serially

        Mode 2 - Complex DAG:
        - Provide tasks_json + relations_json
        - tasks_json: JSON array string, each task contains name, taskType, taskParams etc.
        - relations_json: JSON array string defining task dependencies (preTaskName -> postTaskName)

        Args:
            project_name: Project name
            name: Workflow name
            description: Description
            sql_statements: [Mode 1] SQL, multiple separated by ";;;"
            datasource_id: [Mode 1] Datasource ID
            sql_ds_type: [Mode 1] SQL type (HIVE/MYSQL)
            tasks_json: [Mode 2] Task definition JSON array string
            relations_json: [Mode 2] Task relation JSON array string
            schedule: Whether to create a schedule
            schedule_cron: Quartz 7-field cron expression
            schedule_start: Schedule start time (defaults to today)
            schedule_end: Schedule end time (defaults to 2030-12-31)
            auto_online: Whether to auto-release workflow and schedule
        """
        pcode = resolve_project_code(project_name)

        if tasks_json:
            # Mode 2: complex DAG
            tasks = json.loads(tasks_json)
            relations_input = json.loads(relations_json) if relations_json else []
        elif sql_statements:
            # Mode 1: simple SQL (backward compatible)
            sqls = [s.strip() for s in sql_statements.split(";;;") if s.strip()]
            if not sqls:
                raise ValueError("sql_statements cannot be empty")

            tasks = []
            for i, sql in enumerate(sqls):
                task_name = f"{name}_sql_{i + 1}" if len(sqls) > 1 else f"{name}_sql"
                tasks.append(
                    {
                        "name": task_name,
                        "taskType": "SQL",
                        "taskParams": {
                            "type": sql_ds_type,
                            "datasource": datasource_id,
                            "sql": sql,
                            "sqlType": "1",
                            "preStatements": [],
                            "postStatements": [],
                            "localParams": [],
                            "resourceList": [],
                            "displayRows": 10,
                            "segmentSeparator": "",
                            "udfs": "",
                        },
                    }
                )

            # Serial dependencies
            relations_input = []
            for i in range(len(tasks)):
                relations_input.append(
                    {
                        "preTaskName": tasks[i - 1]["name"] if i > 0 else "",
                        "postTaskName": tasks[i]["name"],
                    }
                )
        else:
            raise ValueError("Must provide either sql_statements or tasks_json")

        # Generate task codes
        gen_result = ds_get(
            f"/projects/{pcode}/task-definition/gen-task-codes?genNum={len(tasks)}"
        )
        require_ok(gen_result, "generate task codes")
        task_codes = gen_result.get("data", [])
        if len(task_codes) < len(tasks):
            raise RuntimeError("Not enough task codes generated")

        task_definitions = []
        locations = []
        task_name_to_code = {}

        for i, task in enumerate(tasks):
            task_code = task_codes[i]
            task_name_to_code[task["name"]] = task_code

            task_def = {
                "code": task_code,
                "name": task["name"],
                "description": task.get("description", ""),
                "taskType": task["taskType"],
                "taskParams": task["taskParams"],
                "flag": task.get("flag", "YES"),
                "taskPriority": task.get("taskPriority", "MEDIUM"),
                "workerGroup": task.get("workerGroup", "default"),
                "failRetryTimes": task.get("failRetryTimes", 4),
                "failRetryInterval": task.get("failRetryInterval", 1),
                "timeoutFlag": task.get("timeoutFlag", "CLOSE"),
                "timeoutNotifyStrategy": task.get("timeoutNotifyStrategy", ""),
                "timeout": task.get("timeout", 0),
                "delayTime": task.get("delayTime", 0),
                "environmentCode": task.get("environmentCode", -1),
                "taskExecuteType": task.get("taskExecuteType", "BATCH"),
            }
            task_definitions.append(task_def)

            # Node coordinates (horizontal layout, wider spacing)
            locations.append({"taskCode": task_code, "x": 100 + i * 300, "y": 100})

        # Build task relations (name -> code)
        relations = []
        for rel in relations_input:
            pre_name = rel.get("preTaskName", "")
            post_name = rel["postTaskName"]

            relations.append(
                {
                    "name": "",
                    "preTaskCode": task_name_to_code.get(pre_name, 0),
                    "preTaskVersion": 1 if pre_name else 0,
                    "postTaskCode": task_name_to_code[post_name],
                    "postTaskVersion": 1,
                    "conditionType": rel.get("conditionType", "NONE"),
                    "conditionParams": rel.get("conditionParams", {}),
                }
            )

        # Create workflow
        payload = {
            "name": name,
            "description": description,
            "globalParams": "[]",
            "locations": json.dumps(locations),
            "taskDefinitionJson": json.dumps(task_definitions),
            "taskRelationJson": json.dumps(relations),
            "tenantCode": get_tenant_code(),
            "executionType": "PARALLEL",
            "timeout": 0,
        }

        result = ds_post(f"/projects/{pcode}/process-definition", data=payload)
        require_ok(result, "create workflow")
        wf_data = result.get("data", {})
        wf_code = wf_data.get("code")

        # Release workflow
        schedule_info: str | dict = "not created"
        if wf_code and auto_online:
            ds_post(
                f"/projects/{pcode}/process-definition/{wf_code}/release",
                data={"releaseState": "ONLINE"},
            )

            if schedule:
                if not schedule_start:
                    schedule_start = time.strftime("%Y-%m-%d 00:00:00")
                if not schedule_end:
                    schedule_end = "2030-12-31 23:59:59"

                sched_payload = {
                    "processDefinitionCode": wf_code,
                    "schedule": json.dumps(
                        {
                            "startTime": schedule_start,
                            "endTime": schedule_end,
                            "crontab": schedule_cron,
                            "timezoneId": "Asia/Shanghai",
                        }
                    ),
                    "failureStrategy": "END",
                    "warningType": "NONE",
                    "processInstancePriority": "MEDIUM",
                    "workerGroup": "default",
                }
                sched_result = ds_post(
                    f"/projects/{pcode}/schedules", data=sched_payload
                )
                require_ok(sched_result, "create schedule")
                sched_data = sched_result.get("data")
                if isinstance(sched_data, dict):
                    sched_id = sched_data.get("id")
                else:
                    sched_id = None

                if sched_id:
                    ds_post(f"/projects/{pcode}/schedules/{sched_id}/online")
                    schedule_info = {
                        "schedule_id": sched_id,
                        "cron": schedule_cron,
                        "start_time": schedule_start,
                        "end_time": schedule_end,
                        "state": "ONLINE",
                    }
            else:
                schedule_info = "disabled (schedule=False)"

        return {
            "success": True,
            "workflow_code": wf_code,
            "name": name,
            "project_name": project_name,
            "task_count": len(tasks),
            "release": "ONLINE" if (wf_code and auto_online) else "OFFLINE",
            "schedule": schedule_info,
        }

    @mcp.tool()
    def ds_release_workflow(
        project_name: str,
        workflow_code: int,
        online: bool = True,
        auto_online_schedule: bool = True,
    ) -> dict:
        """Bring a workflow online or offline.

        When bringing online (online=True), auto_online_schedule will also
        re-activate the associated schedule if it was taken offline (DS takes
        schedules offline when the workflow goes offline).

        Args:
            project_name: Project name
            workflow_code: Process-definition code
            online: True=online, False=offline
            auto_online_schedule: Auto-reactivate associated schedule when going online (default True)

        Returns:
            {
                "workflow_code": int,
                "releaseState": "ONLINE" / "OFFLINE",
                "schedule_action": str,
                "schedule_id": int,
            }
        """
        pcode = resolve_project_code(project_name)
        state = "ONLINE" if online else "OFFLINE"
        result = ds_post(
            f"/projects/{pcode}/process-definition/{workflow_code}/release",
            data={"releaseState": state},
        )
        require_ok(result, "update release state")

        ret = {"workflow_code": workflow_code, "releaseState": state}

        if online and auto_online_schedule:
            try:
                sch_result = ds_get(
                    f"/projects/{pcode}/schedules?pageNo=1&pageSize=10"
                    f"&processDefinitionCode={workflow_code}"
                )
                if sch_result.get("code") == 0:
                    schedules = sch_result.get("data", {}).get("totalList", []) or []
                    target_schedule = None
                    for s in schedules:
                        if s.get("processDefinitionCode") == workflow_code:
                            target_schedule = s
                            break

                    if target_schedule:
                        sid = target_schedule.get("id")
                        sstate = target_schedule.get("releaseState", "OFFLINE")
                        if sstate != "ONLINE":
                            online_sch = ds_post(
                                f"/projects/{pcode}/schedules/{sid}/online"
                            )
                            if online_sch.get("code") == 0:
                                ret["schedule_action"] = (
                                    f"Auto-activated schedule schedule_id={sid}"
                                )
                                ret["schedule_id"] = sid
                            else:
                                ret["schedule_action"] = (
                                    f"Failed to auto-activate schedule schedule_id={sid}: "
                                    f"{online_sch.get('msg')}"
                                )
                                ret["schedule_id"] = sid
                        else:
                            ret["schedule_action"] = (
                                f"Schedule already ONLINE schedule_id={sid}"
                            )
                            ret["schedule_id"] = sid
                    else:
                        ret["schedule_action"] = "No associated schedule found"
                else:
                    ret["schedule_action"] = (
                        "Failed to query schedules; skipping auto-activation"
                    )
            except Exception as e:
                ret["schedule_action"] = f"Schedule activation error: {str(e)}"

        return ret

    @mcp.tool()
    def ds_run_workflow(
        project_name: str,
        workflow_code: int,
        start_task_names: list = None,
    ) -> dict:
        """Manually trigger a workflow run (brings it online first).

        Args:
            project_name: Project name
            workflow_code: Process-definition code
            start_task_names: Optional list of task names to start from (including their
                              downstream tasks). Leave empty to run the entire workflow.
                              Example: ["partition_check"] starts from that task and all its successors.
        """
        pcode = resolve_project_code(project_name)
        ds_post(
            f"/projects/{pcode}/process-definition/{workflow_code}/release",
            data={"releaseState": "ONLINE"},
        )
        payload = {
            "processDefinitionCode": workflow_code,
            "failureStrategy": "END",
            "warningType": "NONE",
            "warningGroupId": 0,
            "processInstancePriority": "MEDIUM",
            "workerGroup": "default",
            "runMode": "RUN_MODE_SERIAL",
            "taskDependType": "TASK_POST",
            "scheduleTime": "",
            "startParams": "",
            "dryRun": 0,
            "environmentCode": -1,
        }
        if start_task_names:
            payload["startNodeList"] = ",".join(start_task_names)
        result = ds_post(
            f"/projects/{pcode}/executors/start-process-instance",
            data=payload,
        )
        require_ok(result, "trigger workflow")
        ret = {
            "status": "submitted",
            "workflow_code": workflow_code,
            "hint": (
                "Workflow triggered. "
                "Track progress with ds_list_task_instances(project_name=..., process_instance_id=<id>) "
                "to see individual task states (RUNNING/SUCCESS/FAILURE). "
                "An instance showing RUNNING_EXECUTION with an empty task list is normal "
                "(DS is initializing the DAG). "
                "First get the instance id with ds_list_process_instances(workflow_code=...)."
            ),
        }
        if start_task_names:
            ret["start_task_names"] = start_task_names
            ret["task_depend_type"] = "TASK_POST"
        return ret

    @mcp.tool()
    def ds_delete_workflow(project_name: str, workflow_code: int | list) -> dict:
        """Delete workflow(s) by code (takes offline first). Supports single or batch delete.

        v2.0.12: merged ds_batch_delete_workflows.
        - workflow_code=12345: delete single workflow
        - workflow_code=[12345, 67890]: batch delete (each independent; one failure doesn't block others)

        Args:
            project_name: Project name
            workflow_code: Process-definition code (int for single, list for batch)

        Returns:
            Single: {"workflow_code": int, "status": "deleted"}
            Batch: {"total": int, "deleted": int, "failed": int, "deleted_codes": [...], "failed_details": [...]}
        """
        pcode = resolve_project_code(project_name)

        # Single delete
        if isinstance(workflow_code, int):
            try:
                ds_post(
                    f"/projects/{pcode}/process-definition/{workflow_code}/release",
                    data={"releaseState": "OFFLINE"},
                )
            except Exception:
                pass
            result = ds_delete(f"/projects/{pcode}/process-definition/{workflow_code}")
            require_ok(result, "delete workflow")
            return {"workflow_code": workflow_code, "status": "deleted"}

        # Batch delete
        if not isinstance(workflow_code, list):
            raise ValueError("workflow_code must be int or list")

        results = []
        for code in workflow_code:
            item = {"code": code, "status": "deleted", "error": None}
            try:
                try:
                    ds_post(
                        f"/projects/{pcode}/process-definition/{code}/release",
                        data={"releaseState": "OFFLINE"},
                    )
                except Exception:
                    pass
                del_result = ds_delete(f"/projects/{pcode}/process-definition/{code}")
                if del_result.get("code") != 0:
                    item["status"] = "failed"
                    item["error"] = del_result.get("msg", "unknown")
            except Exception as e:
                item["status"] = "failed"
                item["error"] = str(e)[:200]
            results.append(item)

        deleted = [r["code"] for r in results if r["status"] == "deleted"]
        failed = [r for r in results if r["status"] == "failed"]
        return {
            "total": len(workflow_code),
            "deleted": len(deleted),
            "failed": len(failed),
            "deleted_codes": deleted,
            "failed_details": failed or None,
        }
