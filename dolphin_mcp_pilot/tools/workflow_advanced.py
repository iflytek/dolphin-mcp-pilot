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

"""Workflow advanced operation tools."""

import difflib
import json
import time
import urllib.error

from mcp.server.mcpserver import MCPServer

from ..client import ds_get, ds_post, ds_put
from ..client import ds_get as client_get, ds_post as client_post, ds_put as client_put
from ..config import get_tenant_code
from ..utils import require_ok, resolve_project_code
from .resource import normalize_resource_list


class _EditTimeout(RuntimeError):
    """编辑预算耗尽；write_started 用于区分可安全重试与结果未知。"""

    def __init__(self, stage: str, write_started: bool, write_succeeded: bool):
        self.stage = stage
        self.write_started = write_started
        self.write_succeeded = write_succeeded
        super().__init__(f"编辑操作在 {stage} 阶段超时")


class _EditDeadline:
    """跨登录、读取、写入、上线和回读共享的单次编辑时间预算。"""

    def __init__(self, timeout_seconds: float):
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds 必须大于 0")
        self.timeout_seconds = float(timeout_seconds)
        self.started_at = time.monotonic()
        self.stage = "resolve_project"
        self.write_started = False
        self.write_succeeded = False

    def remaining(self) -> float:
        left = self.timeout_seconds - (time.monotonic() - self.started_at)
        if left <= 0:
            raise _EditTimeout(self.stage, self.write_started, self.write_succeeded)
        return left

    def request(self, func, *args, **kwargs):
        if self.stage == "write":
            self.write_started = True
        try:
            return func(*args, timeout=self.remaining(), **kwargs)
        except Exception as exc:
            is_timeout = isinstance(exc, TimeoutError) or (
                isinstance(exc, urllib.error.URLError)
                and isinstance(exc.reason, TimeoutError)
            )
            if is_timeout:
                raise _EditTimeout(
                    self.stage, self.write_started, self.write_succeeded
                ) from exc
            raise


def _timeout_edit_result(exc: _EditTimeout, workflow_code: int) -> dict:
    if exc.write_succeeded:
        status = "partially_applied"
    elif exc.write_started:
        status = "unknown"
    else:
        status = "timeout"
    return {
        "workflow_code": workflow_code,
        "status": status,
        "phase": exc.stage,
        "persisted": True if exc.write_succeeded else None,
        "retry_safe": not exc.write_started,
        "error": str(exc),
        "recovery": (
            "先回读 ds_get_workflow / ds_get_task_detail 确认写入结果；"
            "结果未知时禁止直接重复提交，随后再核对 release_state 和调度状态"
        ),
    }


def _build_task_definition(task_code: int, task: dict) -> dict:
    """Build native DS taskDefinition from simplified task config.

    Supported task fields:
        name, type (SQL/SHELL/PYTHON/DEPENDENT/SUB_PROCESS/SWITCH/HTTP etc.)
        # Common
        fail_retry_times (default 0), fail_retry_interval (default 1 min), timeout, description, worker_group
        # SQL
        datasource_id, sql, sql_type (HIVE/MYSQL/...), sql_type_select (0=query 1=non-query)
        # SHELL / PYTHON
        script, resource_list, local_params
        # DEPENDENT
        depend_items ([{project_code, definition_code, dep_task_code, cycle, date_value}])
        # SUB_PROCESS
        sub_process_code
        # HTTP
        http_url, http_method, http_params, condition_result

    resource_list supports three formats:
        - [67, 58]                              # resource_id list (recommended)
        - ["/public/check_partition.py"]        # full path (starts with /)
        - [{"id": 67}]                          # dict format
        DS only reads the id; name field will be auto-filled with empty string.
        Use ds_list_resources() to view all resources with their ids and paths.
    """
    ttype = task.get("type", "SQL").upper()
    # timeout_flag compatible with bool/string
    _tflag = task.get("timeout_flag", task.get("timeoutFlag", "CLOSE"))
    if isinstance(_tflag, bool):
        _tflag = "OPEN" if _tflag else "CLOSE"
    else:
        _tflag = str(_tflag).upper()
    base = {
        "code": task_code,
        "name": task["name"],
        "description": task.get("description", ""),
        "taskType": ttype,
        "flag": task.get("flag", "YES"),
        "taskPriority": task.get("task_priority", task.get("taskPriority", "MEDIUM")),
        "workerGroup": task.get("worker_group", task.get("workerGroup", "default")),
        "failRetryTimes": task.get("fail_retry_times", task.get("failRetryTimes", 0)),
        "failRetryInterval": task.get(
            "fail_retry_interval", task.get("failRetryInterval", 1)
        ),
        "timeoutFlag": _tflag,
        "timeoutNotifyStrategy": task.get(
            "timeout_notify_strategy", task.get("timeoutNotifyStrategy", "")
        ),
        "timeout": task.get("timeout", 0),
        "delayTime": task.get("delay_time", task.get("delayTime", 0)),
        "environmentCode": -1,
        "taskExecuteType": "BATCH",
    }

    if ttype == "SQL":
        base["taskParams"] = {
            "type": task.get("sql_type", "HIVE"),
            "datasource": task.get("datasource_id", task.get("datasource")),
            "sql": task["sql"],
            "sqlType": str(task.get("sql_type_select", task.get("sqlType", 1))),
            "preStatements": task.get("pre_statements", task.get("preStatements", [])),
            "postStatements": task.get(
                "post_statements", task.get("postStatements", [])
            ),
            "localParams": task.get("local_params", task.get("localParams", [])),
            "resourceList": normalize_resource_list(
                task.get("resource_list", task.get("resourceList", []))
            ),
            "displayRows": 10,
            "segmentSeparator": "",
            "udfs": "",
        }
    elif ttype in ("SHELL", "PYTHON"):
        base["taskParams"] = {
            "rawScript": task.get("script", task.get("rawScript", "")),
            "localParams": task.get("local_params", task.get("localParams", [])),
            "resourceList": normalize_resource_list(
                task.get("resource_list", task.get("resourceList", []))
            ),
        }
    elif ttype == "DEPENDENT":
        depend_items = task.get("depend_items", [])
        base["taskParams"] = {
            "dependence": {
                "relation": task.get("dep_relation", "AND"),
                "dependTaskList": [
                    {
                        "relation": "AND",
                        "dependItemList": [
                            {
                                "projectCode": d["project_code"],
                                "definitionCode": d["definition_code"],
                                "depTaskCode": d.get("dep_task_code", 0),
                                "cycle": d.get("cycle", "day"),
                                "dateValue": d.get("date_value", "today"),
                            }
                            for d in depend_items
                        ],
                    }
                ],
            },
            "localParams": [],
            "resourceList": [],
        }
    elif ttype == "SUB_PROCESS":
        base["taskParams"] = {
            "processDefinitionCode": task["sub_process_code"],
            "localParams": [],
        }
    elif ttype == "HTTP":
        base["taskParams"] = {
            "url": task["http_url"],
            "httpMethod": task.get("http_method", "GET"),
            "httpParams": task.get("http_params", []),
            "httpCheckCondition": task.get("condition_result", "STATUS_CODE_DEFAULT"),
            "condition": task.get("condition", ""),
            "connectTimeout": 60000,
            "socketTimeout": 60000,
            "localParams": [],
            "resourceList": [],
        }
    else:
        # Fallback: use user-provided taskParams directly
        base["taskParams"] = task.get("task_params", {})

    return base


def register_workflow_advanced_tools(mcp: MCPServer):
    """Register workflow advanced operation MCP tools."""

    @mcp.tool()
    def ds_update_workflow(
        project_name: str,
        workflow_code: int,
        task_definitions: list | str,
        task_relations: list | str,
        locations: list | str = "[]",
        name: str = "",
        description: str = "",
        auto_offline: bool = True,
        auto_online: bool = True,
    ) -> dict:
        """Update workflow definition (PUT method, preserves code, auto-increments version).

        This is a fallback when ds_modify_workflow_dag cannot handle the change.
        Supports full task definition override with complete replacement.

        Args:
            project_name: Project name
            workflow_code: Process-definition code
            task_definitions: Task definition list (list or JSON string)
            task_relations: Task relation list (list or JSON string)
            locations: Node coordinates (list or JSON string, default "[]")
            name: Workflow name (empty = keep original)
            description: Description (empty = keep original)
            auto_offline: Auto-offline before update (default True)
            auto_online: Auto-online after update (default True)
        """
        pcode = resolve_project_code(project_name)

        # Read current workflow definition
        current = ds_get(f"/projects/{pcode}/process-definition/{workflow_code}")
        require_ok(current, "get current workflow definition")
        current_data = current.get("data", {})
        current_pd = current_data.get("processDefinition", {})
        current_version = current_pd.get("version", 1)
        current_state = current_pd.get("releaseState", "OFFLINE")

        # Take offline if online and auto_offline=True
        was_online = current_state == "ONLINE"
        if was_online and auto_offline:
            ds_post(
                f"/projects/{pcode}/process-definition/{workflow_code}/release",
                data={"releaseState": "OFFLINE"},
            )

        # Accept JSON string input
        if isinstance(task_definitions, str):
            task_definitions = json.loads(task_definitions)
        if isinstance(task_relations, str):
            task_relations = json.loads(task_relations)
        if isinstance(locations, str):
            locations = json.loads(locations)

        # Use original name/description/tenantCode if not provided
        final_name = name if name else current_pd.get("name", "")
        final_desc = description if description else current_pd.get("description", "")
        tenant_code = current_pd.get("tenantCode") or get_tenant_code()

        payload = {
            "name": final_name,
            "description": final_desc,
            "globalParams": current_pd.get("globalParamStr", "[]") or "[]",
            "locations": json.dumps(locations),
            "taskDefinitionJson": json.dumps(task_definitions),
            "taskRelationJson": json.dumps(task_relations),
            "tenantCode": tenant_code,
            "executionType": current_pd.get("executionType", "PARALLEL") or "PARALLEL",
            "timeout": current_pd.get("timeout", 0) or 0,
            "processDefinitionVersion": current_version,
        }
        result = ds_put(
            f"/projects/{pcode}/process-definition/{workflow_code}",
            data=payload,
        )
        require_ok(result, "update workflow definition")

        # Auto-online if was online and auto_online=True
        if was_online and auto_online:
            ds_post(
                f"/projects/{pcode}/process-definition/{workflow_code}/release",
                data={"releaseState": "ONLINE"},
            )

        return {
            "workflow_code": workflow_code,
            "name": final_name,
            "previous_version": current_version,
            "release_state": "ONLINE" if (was_online and auto_online) else "OFFLINE",
            "status": "updated",
        }

    @mcp.tool()
    def ds_get_task_detail(
        project_name: str,
        workflow_code: int,
        task_name: str,
    ) -> dict:
        """Read full parameters of a single task (returns only that task, not the whole DAG).

        Added in v2.0.12 for the "verify a task change took effect" scenario,
        avoiding pulling a huge DAG payload.

        Args:
            project_name: Project name
            workflow_code: Process-definition code
            task_name: Task name (exact match)

        Returns:
            {
                "task_code": int,
                "task_name": str,
                "task_type": str,
                "task_params": {...},  # Full taskParams (preStatements/postStatements/sql/script etc.)
                "description": str,
                "fail_retry_times": int,
                "timeout": int,
                ...
            }
        """
        pcode = resolve_project_code(project_name)
        result = ds_get(f"/projects/{pcode}/process-definition/{workflow_code}")
        require_ok(result, "get workflow definition")
        task_defs = result.get("data", {}).get("taskDefinitionList", []) or []

        for t in task_defs:
            if t.get("name") == task_name:
                # Parse taskParams (may be a JSON string)
                params_raw = t.get("taskParams", {})
                if isinstance(params_raw, str):
                    try:
                        params = json.loads(params_raw)
                    except (ValueError, TypeError):
                        params = {}
                else:
                    params = params_raw or {}

                return {
                    "task_code": t.get("code"),
                    "task_name": t.get("name"),
                    "task_type": t.get("taskType"),
                    "task_params": params,
                    "description": t.get("description", ""),
                    "fail_retry_times": t.get("failRetryTimes", 0),
                    "fail_retry_interval": t.get("failRetryInterval", 1),
                    "timeout": t.get("timeout", 0),
                    "worker_group": t.get("workerGroup", "default"),
                    "environment_code": t.get("environmentCode", -1),
                }

        # Not found
        all_task_names = [t.get("name") for t in task_defs if t.get("name")]
        raise ValueError(
            f"Task '{task_name}' not found in workflow {workflow_code}. "
            f"Available tasks: {all_task_names}"
        )

    @mcp.tool()
    def ds_list_workflow_versions(
        project_name: str,
        workflow_code: int,
        page_size: int = 20,
    ) -> list:
        """List saved versions of a workflow definition (read-only).

        Each save of the workflow creates a version. Use the returned version
        number with ds_rollback_workflow_version.

        Args:
            project_name: Project name
            workflow_code: Workflow (process-definition) code from ds_list_workflows
            page_size: Maximum number of versions to return (first page, default 20)

        Returns:
            [{"version": int, "description": str, "createTime": str,
              "updateTime": str}, ...]
        """
        pcode = resolve_project_code(project_name)
        result = ds_get(
            f"/projects/{pcode}/process-definition/{workflow_code}/versions"
            f"?pageNo=1&pageSize={page_size}"
        )
        require_ok(result, "get version list")
        items = result.get("data", {}).get("totalList", []) or []
        return [
            {
                "version": v.get("version"),
                "description": v.get("description", ""),
                "createTime": v.get("createTime"),
                "updateTime": v.get("updateTime"),
            }
            for v in items
        ]

    @mcp.tool()
    def ds_rollback_workflow_version(
        project_name: str,
        workflow_code: int,
        version: int,
    ) -> dict:
        """Roll back a workflow to a specific historical version.

        Args:
            project_name: Project name
            workflow_code: Process-definition code
            version: Target version number (from ds_list_workflow_versions)
        """
        pcode = resolve_project_code(project_name)
        result = ds_post(
            f"/projects/{pcode}/process-definition/{workflow_code}/versions/{version}"
        )
        require_ok(result, "roll back version")
        return {
            "workflow_code": workflow_code,
            "rolled_back_to_version": version,
            "status": "ok",
        }

    @mcp.tool()
    def ds_clone_workflow(
        project_name: str,
        source_workflow_code: int,
        new_name: str,
        description: str = "",
        auto_online: bool = False,
    ) -> dict:
        """Clone/copy a workflow.

        Args:
            project_name: Project name
            source_workflow_code: Source workflow code
            new_name: New workflow name
            description: New workflow description (empty = copy source description)
            auto_online: Auto-release after cloning

        Returns:
            {
                'success': True,
                'workflow_code': int,  # New workflow code
                'source_code': int,
                'name': str,
                ...
            }
        """
        pcode = resolve_project_code(project_name)

        # 1. Read source workflow
        source_result = ds_get(
            f"/projects/{pcode}/process-definition/{source_workflow_code}"
        )
        require_ok(source_result, "read source workflow")
        source_data = source_result.get("data", {})
        source_pd = source_data.get("processDefinition", {})
        source_tasks = source_data.get("taskDefinitionList", [])
        source_relations = source_data.get("processTaskRelationList", [])

        if not source_tasks:
            raise RuntimeError("Source workflow has no tasks")

        # 2. Generate new task codes
        gen_result = ds_get(
            f"/projects/{pcode}/task-definition/gen-task-codes?genNum={len(source_tasks)}"
        )
        require_ok(gen_result, "generate task codes")
        new_task_codes = gen_result.get("data", [])
        if len(new_task_codes) < len(source_tasks):
            raise RuntimeError("Not enough task codes generated")

        # 3. Build new task definitions (replace codes)
        old_to_new_code = {}
        new_tasks = []
        new_locations = []

        # Parse source locations
        locations_raw = source_pd.get("locations", "[]")
        try:
            source_locations = (
                json.loads(locations_raw)
                if isinstance(locations_raw, str)
                else locations_raw
            )
        except Exception:
            source_locations = []

        for i, old_task in enumerate(source_tasks):
            new_code = new_task_codes[i]
            old_code = old_task["code"]
            old_to_new_code[old_code] = new_code

            # Copy task definition
            new_task = old_task.copy()
            new_task["code"] = new_code
            new_tasks.append(new_task)

            # Copy coordinates
            for loc in source_locations:
                if loc.get("taskCode") == old_code:
                    new_locations.append(
                        {
                            "taskCode": new_code,
                            "x": loc.get("x", 100),
                            "y": loc.get("y", 100),
                        }
                    )
                    break

        # 4. Build new relations (replace codes)
        new_relations = []
        for old_rel in source_relations:
            new_rel = old_rel.copy()
            old_pre = old_rel.get("preTaskCode", 0)
            old_post = old_rel["postTaskCode"]

            new_rel["preTaskCode"] = old_to_new_code.get(old_pre, 0)
            new_rel["postTaskCode"] = old_to_new_code[old_post]
            new_relations.append(new_rel)

        # 5. Create new workflow
        new_description = (
            description if description else source_pd.get("description", "")
        )

        payload = {
            "name": new_name,
            "description": new_description,
            "globalParams": source_pd.get("globalParams", "[]"),
            "locations": json.dumps(new_locations),
            "taskDefinitionJson": json.dumps(new_tasks),
            "taskRelationJson": json.dumps(new_relations),
            "tenantCode": source_pd.get("tenantCode") or get_tenant_code(),
            "executionType": source_pd.get("executionType", "PARALLEL"),
            "timeout": source_pd.get("timeout", 0),
        }

        result = ds_post(f"/projects/{pcode}/process-definition", data=payload)
        require_ok(result, "create workflow")
        wf_data = result.get("data", {})
        new_wf_code = wf_data.get("code")

        # 6. Release if needed
        if new_wf_code and auto_online:
            ds_post(
                f"/projects/{pcode}/process-definition/{new_wf_code}/release",
                data={"releaseState": "ONLINE"},
            )

        return {
            "success": True,
            "workflow_code": new_wf_code,
            "source_code": source_workflow_code,
            "name": new_name,
            "task_count": len(new_tasks),
            "release": "ONLINE" if auto_online else "OFFLINE",
        }

    @mcp.tool()
    def ds_create_dag_workflow(
        project_name: str,
        name: str,
        tasks: list,
        relations: list,
        description: str = "",
        schedule: bool = False,
        schedule_cron: str = "0 0 6 * * ? *",
        locations: list = None,
    ) -> dict:
        """Create a generic DAG workflow supporting any task type
        (SQL/SHELL/PYTHON/DEPENDENT/SUB_PROCESS/HTTP etc.).

        Args:
            project_name: Project name
            name: Workflow name
            tasks: Task definition list (see examples below)
            relations: Dependency list [{"from": "taskA", "to": "taskB"}]; empty "from" = start node
            description: Description
            schedule: Whether to create a schedule
            schedule_cron: Cron expression (7-field Quartz style)
            locations: Optional node coordinates [{"task_name": "check", "x": 100, "y": 100}]
                       Leave empty for auto-layout (horizontal, 300x200 spacing)

        tasks example:
            [
                # SHELL task (script required, resource_list optional)
                {"name": "check", "type": "SHELL",
                 "script": "#!/bin/bash\npython3 /public/check_partition.py table_name $[yyyyMMdd-1]",
                 "resource_list": [67],           # optional: referenced resource id or path
                 "fail_retry_times": 3},          # optional: retry count on failure

                # SQL task (datasource_id + sql required)
                {"name": "sql1", "type": "SQL",
                 "datasource_id": 1, "sql": "SELECT 1",
                 "sql_type": "HIVE",              # optional, default HIVE
                 "sql_type_select": 1},           # optional, 0=query 1=non-query (default 1)

                # DEPENDENT task (wait for upstream workflow completion)
                {"name": "wait", "type": "DEPENDENT",
                 "depend_items": [{"project_code": 123, "definition_code": 456,
                                   "cycle": "day", "date_value": "today"}]},

                # SUB_PROCESS task (invoke a sub-workflow)
                {"name": "sub", "type": "SUB_PROCESS",
                 "sub_process_code": 21505676237440},

                # HTTP task
                {"name": "notify", "type": "HTTP",
                 "http_url": "https://api.example.com/callback",
                 "http_method": "POST"}
            ]
        relations example:
            [
                {"from": "", "to": "check"},      # check is a start node (empty "from")
                {"from": "check", "to": "sql1"},
                {"from": "wait", "to": "sql1"}    # wait and check run in parallel, both feed sql1
            ]

        resource_list format:
            - Recommended: resource_id (int): [67, 58]
            - Or full path (str): ["/public/check_partition.py"]
            - Paths must start with /
            - Use ds_list_resources() to view all resources with their ids and paths
        """
        pcode = resolve_project_code(project_name)
        if not tasks:
            raise ValueError("tasks cannot be empty")

        # Generate task codes
        gen_result = ds_get(
            f"/projects/{pcode}/task-definition/gen-task-codes?genNum={len(tasks)}"
        )
        require_ok(gen_result, "generate task codes")
        codes = gen_result.get("data", [])
        if len(codes) < len(tasks):
            raise RuntimeError("Not enough task codes generated")

        # Build name -> code mapping
        name_to_code = {}
        task_defs = []
        auto_locations = []
        for i, task in enumerate(tasks):
            code = codes[i]
            name_to_code[task["name"]] = code
            task_defs.append(_build_task_definition(code, task))
            auto_locations.append(
                {"taskCode": code, "x": 100 + (i % 5) * 300, "y": 100 + (i // 5) * 200}
            )

        # Apply user-provided locations (if given)
        if locations:
            # User provided coordinates, map task_name -> taskCode
            final_locations = []
            for loc in locations:
                task_name = loc.get("task_name")
                if task_name and task_name in name_to_code:
                    final_locations.append(
                        {
                            "taskCode": name_to_code[task_name],
                            "x": loc.get("x", 100),
                            "y": loc.get("y", 100),
                        }
                    )
            # Add auto-layout coordinates for tasks without explicit locations
            specified_names = {
                loc.get("task_name") for loc in locations if loc.get("task_name")
            }
            for i, task in enumerate(tasks):
                if task["name"] not in specified_names:
                    final_locations.append(auto_locations[i])
            locations = final_locations
        else:
            # Use auto-layout
            locations = auto_locations

        # Build task relations
        rels = []
        for r in relations:
            from_name = r.get("from", "")
            to_name = r["to"]
            pre_code = name_to_code.get(from_name, 0) if from_name else 0
            post_code = name_to_code.get(to_name)
            if post_code is None:
                raise ValueError(f"relation references undefined task: {to_name}")
            rels.append(
                {
                    "name": "",
                    "preTaskCode": pre_code,
                    "preTaskVersion": 1 if pre_code else 0,
                    "postTaskCode": post_code,
                    "postTaskVersion": 1,
                    "conditionType": "NONE",
                    "conditionParams": {},
                }
            )

        # Ensure every task has at least one incoming relation (tasks without = start nodes)
        has_incoming = {r["postTaskCode"] for r in rels}
        for code in codes[: len(tasks)]:
            if code not in has_incoming:
                rels.insert(
                    0,
                    {
                        "name": "",
                        "preTaskCode": 0,
                        "preTaskVersion": 0,
                        "postTaskCode": code,
                        "postTaskVersion": 1,
                        "conditionType": "NONE",
                        "conditionParams": {},
                    },
                )

        payload = {
            "name": name,
            "description": description,
            "globalParams": "[]",
            "locations": json.dumps(locations),
            "taskDefinitionJson": json.dumps(task_defs),
            "taskRelationJson": json.dumps(rels),
            "tenantCode": get_tenant_code(),
            "executionType": "PARALLEL",
            "timeout": 0,
        }

        result = ds_post(f"/projects/{pcode}/process-definition", data=payload)
        require_ok(result, "create DAG workflow")
        wf_code = result.get("data", {}).get("code")

        schedule_info: str | dict = "not created"
        if wf_code:
            ds_post(
                f"/projects/{pcode}/process-definition/{wf_code}/release",
                data={"releaseState": "ONLINE"},
            )
            if schedule:
                sched_payload = {
                    "processDefinitionCode": wf_code,
                    "schedule": json.dumps(
                        {
                            "startTime": time.strftime("%Y-%m-%d 00:00:00"),
                            "endTime": "2030-12-31 23:59:59",
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
                sched_id = sched_result.get("data", {}).get("id")
                if sched_id:
                    ds_post(f"/projects/{pcode}/schedules/{sched_id}/online")
                    schedule_info = {
                        "schedule_id": sched_id,
                        "cron": schedule_cron,
                        "state": "ONLINE",
                    }

        return {
            "workflow_code": wf_code,
            "name": name,
            "task_count": len(tasks),
            "release": "ONLINE" if wf_code else "unknown",
            "schedule": schedule_info,
        }

    def _modify_workflow_dag(
        project_name: str,
        workflow_code: int,
        operations: list,
        auto_offline: bool = True,
        auto_online: bool = True,
        auto_online_schedule: bool = True,
        expected_version: int = 0,
        deadline: _EditDeadline | None = None,
    ) -> dict:
        """修改现有工作流的 DAG 结构（追加/删除/修改任务 + 调整依赖关系）。

        本工具是通用 DAG 编辑器，内部实现：读取当前 DAG → 应用 operations → 整体回写。

        ⚠️ 风险警告（必读）：
        - 修改工作流会生成新版本，旧版本保留可回滚
        - 如果工作流正在运行，建议先下线（本工具默认 auto_offline=True 会自动处理）
        - 修改完成后会自动重新上线（auto_online=True）
        - DS 没有"追加单个任务"的原生 API，本工具是通过"读 → 改 → 整体更新"模拟

        Args:
            project_name: 项目名称
            workflow_code: 工作流 code
            operations: 操作列表，每项是一个操作对象（支持 5 种动作）
            auto_offline: 修改前是否自动下线工作流（默认 True）
            auto_online: 修改后是否自动重新上线（默认 True）
            auto_online_schedule: 上线工作流后是否自动恢复关联调度（默认 True）
                ⚠️ DS 下线工作流会连带下线调度，所以重新上线时需同步恢复调度，
                否则定时任务不会触发。如果确认不需要调度自动恢复可设为 False。

        operations 支持的操作类型：

        【1】追加任务（add_task）：
            {
                "action": "add_task",
                "task": {
                    "name": "wait_upstream",
                    "type": "DEPENDENT",
                    "depend_items": [{
                        "project_code": 123,
                        "definition_code": 456,
                        "dep_task_code": 0,    # 0=整个工作流, 非0=特定任务
                        "cycle": "day",         # day/hour/week/month
                        "date_value": "today"   # today/yesterday/last7days
                    }],
                    "dep_relation": "AND"       # 多依赖项关系: AND/OR
                    # 其他字段同 ds_create_dag_workflow
                },
                "connect_from": "task_a",       # 前置任务名（空=起点）
                "connect_to": "task_b"          # 后续任务名（空=终点）
            }

        【2】删除任务（delete_task）：
            {
                "action": "delete_task",
                "task_name": "old_task",
                "reconnect": true               # 自动重连前后任务，避免 DAG 断裂
            }

        【3】修改任务参数（update_task）：
            {
                "action": "update_task",
                "task_name": "my_sql",
                "updates": {
                    # ===== 通用字段（支持 snake_case / camelCase 别名）=====
                    "name": "new_task_name",           # v2.0.11: 重命名节点
                    "description": "更新后的描述",
                    "fail_retry_times": 3,             # 或 "failRetryTimes"
                    "fail_retry_interval": 4,          # 或 "failRetryInterval" (v2.0.10 修复)
                    "timeout": 300,                    # 超时时长（分钟）
                    "timeout_flag": "OPEN",            # 或 "timeoutFlag": "OPEN"/"CLOSE" 或 True/False
                    "timeout_notify_strategy": "FAILED",  # 或 "timeoutNotifyStrategy": "FAILED"/"WARNING"
                    "worker_group": "default",         # 或 "workerGroup"
                    "task_priority": "HIGH",           # 或 "taskPriority": "HIGH"/"MEDIUM"/"LOW"
                    "delay_time": 0,                   # 或 "delayTime"（延迟执行分钟数）
                    "flag": "YES",                     # "YES"=启用 "NO"=禁用

                    # ===== SQL 任务 =====
                    "sql": "SELECT * FROM new_table WHERE dt='$[yyyyMMdd-1]'",
                    "datasource_id": 1,                # 或 "datasource"
                    "sql_type": "HIVE",                # "HIVE"/"MYSQL"/"POSTGRESQL" 等
                    "sql_type_select": 0,              # 或 "sqlType": 0=查询 1=非查询
                    "pre_statements": [                # 或 "preStatements"（前置SQL列表）
                        "SET hive.exec.dynamic.partition=true",
                        "SET spark.sql.sources.partitionOverwriteMode=dynamic"
                    ],
                    "post_statements": ["SELECT 1"],   # 或 "postStatements"（后置SQL列表）

                    # ===== SHELL/PYTHON 任务 =====
                    "script": "#!/bin/bash\nexport PATH=/xxx/bin:$PATH\npython3 script.py",
                    # 或 "rawScript"

                    # ===== 资源引用（SHELL/PYTHON/SQL 都可用）=====
                    "resource_list": [67, 58],         # 或 "resourceList"（整数ID推荐）
                    # 或 ["/public/check_partition.py"] （完整路径，以 / 开头）

                    # ===== 局部参数 =====
                    "local_params": [{"prop":"dt","value":"$[yyyyMMdd-1]"}]  # 或 "localParams"
                }
            }

            ⚠️ resource_list 格式说明：
            - 推荐用 resource_id（整数）：[67, 58]
            - 或用完整路径（字符串）：["/public/check_partition.py", "/scripts/sync.py"]
            - 路径必须以 / 开头，如 /public/xxx.py 而不是 public/xxx.py
            - 可通过 ds_list_resources() 查看所有资源及其 id 和路径

            ⚠️ 字段命名兼容性：
            - 同时支持 Python 风格 snake_case（如 pre_statements）和 DS API 原生 camelCase（如 preStatements）
            - 两种写法效果相同，推荐用 snake_case（与其他工具字段风格一致）
            - 无法识别的字段会被记录在返回值 ignored_fields 字段中，便于排查拼写错误

        【4】修改节点坐标（update_location）：
            {
                "action": "update_location",
                "task_name": "my_task",
                "x": 500,
                "y": 300
            }

        【5】调整依赖关系（update_relations）：
            {
                "action": "update_relations",
                "changes": [
                    {"op": "add", "from": "task_a", "to": "task_b"},
                    {"op": "remove", "from": "task_c", "to": "task_d"}
                ]
            }

        Returns:
            {
                "workflow_code": int,
                "operations_applied": int,
                "task_count_before": int,
                "task_count_after": int,
                "status": "updated",
                "warning": 风险提示
            }

        典型场景：追加 DEPENDENT 节点让工作流依赖上游
            ds_modify_workflow_dag(
                project_name="流量广告",
                workflow_code=21505676237440,
                operations=[{
                    "action": "add_task",
                    "task": {
                        "name": "wait_upstream_flow",
                        "type": "DEPENDENT",
                        "depend_items": [{
                            "project_code": 21582927260160,
                            "definition_code": 21505676200000,
                            "cycle": "day",
                            "date_value": "today"
                        }]
                    },
                    "connect_from": "",               # 起点
                    "connect_to": "existing_task_1"   # 连到现有任务
                }]
            )
        """
        deadline = deadline or _EditDeadline(90)

        # 局部同名包装只影响本函数，给全部串行 DS 调用套同一个时间预算
        def ds_get(path: str) -> dict:
            return deadline.request(client_get, path)

        def ds_post(
            path: str, data: dict | None = None, json_body: dict | None = None
        ) -> dict:
            return deadline.request(client_post, path, data=data, json_body=json_body)

        def ds_put(
            path: str, data: dict | None = None, json_body: dict | None = None
        ) -> dict:
            return deadline.request(client_put, path, data=data, json_body=json_body)

        pcode = resolve_project_code(project_name, timeout=deadline.remaining())

        # 1. 读取当前工作流定义
        deadline.stage = "read_workflow"
        current = ds_get(f"/projects/{pcode}/process-definition/{workflow_code}")
        require_ok(current, "获取当前工作流定义")

        data = current.get("data", {}) or {}
        pd = data.get("processDefinition", {}) or {}
        if expected_version and pd.get("version") != expected_version:
            raise ValueError(
                f"工作流版本已变化：期望 {expected_version}，实际 {pd.get('version')}。"
                "请重新读取并生成 diff，禁止覆盖他人修改"
            )
        tasks = list(data.get("taskDefinitionList", []) or [])
        relations = list(data.get("processTaskRelationList", []) or [])

        if not tasks:
            raise RuntimeError("工作流没有任务定义，无法修改")

        tasks_before = len(tasks)

        # 解析 locations
        locations_raw = pd.get("locations", "[]") or "[]"
        try:
            locations = (
                json.loads(locations_raw)
                if isinstance(locations_raw, str)
                else list(locations_raw)
            )
        except Exception:
            locations = []

        # 构建索引
        name_to_task = {t.get("name"): t for t in tasks if t.get("name")}
        name_to_code = {t.get("name"): t.get("code") for t in tasks if t.get("name")}
        code_to_name = {t.get("code"): t.get("name") for t in tasks if t.get("code")}

        # 2. 应用操作
        applied_count = 0
        ignored_fields = []  # 收集 update_task 中无法识别的 updates 字段（用于告警）
        current_state = pd.get("releaseState", "OFFLINE")
        was_online = current_state == "ONLINE"

        # 如果在线且允许自动下线，先下线
        deadline.stage = "offline"
        if was_online and auto_offline:
            ds_post(
                f"/projects/{pcode}/process-definition/{workflow_code}/release",
                data={"releaseState": "OFFLINE"},
            )

        deadline.stage = "apply_operations"
        for op in operations:
            action = (op.get("action") or "").lower()

            # ============ 追加任务 ============
            if action == "add_task":
                task_def = op.get("task", {})
                task_name = task_def.get("name")
                if not task_name:
                    continue
                if task_name in name_to_code:
                    raise ValueError(
                        f"任务 {task_name!r} 已存在，请用 update_task 修改"
                    )

                # 生成新 task code
                gen_result = ds_get(
                    f"/projects/{pcode}/task-definition/gen-task-codes?genNum=1"
                )
                require_ok(gen_result, "生成任务 code")
                new_codes = gen_result.get("data") or []
                if not new_codes:
                    raise RuntimeError("生成任务 code 失败")
                new_code = new_codes[0]

                # 构建任务定义
                new_task = _build_task_definition(new_code, task_def)
                tasks.append(new_task)
                name_to_task[task_name] = new_task
                name_to_code[task_name] = new_code
                code_to_name[new_code] = task_name

                # 坐标：自动放到右下（间距加大）
                max_x = max((loc.get("x", 100) for loc in locations), default=100)
                max_y = max((loc.get("y", 100) for loc in locations), default=100)
                locations.append(
                    {"taskCode": new_code, "x": max_x + 300, "y": max_y + 150}
                )

                # 依赖关系
                connect_from = op.get("connect_from", "") or ""
                connect_to = op.get("connect_to", "") or ""

                pre_code = name_to_code.get(connect_from, 0) if connect_from else 0
                relations.append(
                    {
                        "name": "",
                        "preTaskCode": pre_code,
                        "preTaskVersion": 1 if pre_code else 0,
                        "postTaskCode": new_code,
                        "postTaskVersion": 1,
                        "conditionType": "NONE",
                        "conditionParams": {},
                    }
                )

                if connect_to:
                    post_code = name_to_code.get(connect_to)
                    if post_code is None:
                        raise ValueError(f"connect_to 指向不存在的任务: {connect_to}")
                    relations.append(
                        {
                            "name": "",
                            "preTaskCode": new_code,
                            "preTaskVersion": 1,
                            "postTaskCode": post_code,
                            "postTaskVersion": 1,
                            "conditionType": "NONE",
                            "conditionParams": {},
                        }
                    )

                applied_count += 1

            # ============ 删除任务 ============
            elif action == "delete_task":
                task_name = op.get("task_name")
                if not task_name or task_name not in name_to_code:
                    continue
                target_code = name_to_code[task_name]
                reconnect = bool(op.get("reconnect", True))

                # 找出指向该任务的边（pre）和从该任务出发的边（post）
                pre_codes = [
                    r.get("preTaskCode")
                    for r in relations
                    if r.get("postTaskCode") == target_code and r.get("preTaskCode")
                ]
                post_codes = [
                    r.get("postTaskCode")
                    for r in relations
                    if r.get("preTaskCode") == target_code
                ]

                # 删除与该任务相关的所有边
                relations = [
                    r
                    for r in relations
                    if r.get("preTaskCode") != target_code
                    and r.get("postTaskCode") != target_code
                ]

                # 如果需要重连：把上游直接连到下游
                if reconnect and pre_codes and post_codes:
                    for pc in pre_codes:
                        for sc in post_codes:
                            # 避免重复
                            dup = any(
                                r.get("preTaskCode") == pc
                                and r.get("postTaskCode") == sc
                                for r in relations
                            )
                            if not dup:
                                relations.append(
                                    {
                                        "name": "",
                                        "preTaskCode": pc,
                                        "preTaskVersion": 1,
                                        "postTaskCode": sc,
                                        "postTaskVersion": 1,
                                        "conditionType": "NONE",
                                        "conditionParams": {},
                                    }
                                )

                # 如果重连后有孤儿后续任务（没有入边），加起点边
                if reconnect and post_codes and not pre_codes:
                    for sc in post_codes:
                        has_in = any(r.get("postTaskCode") == sc for r in relations)
                        if not has_in:
                            relations.append(
                                {
                                    "name": "",
                                    "preTaskCode": 0,
                                    "preTaskVersion": 0,
                                    "postTaskCode": sc,
                                    "postTaskVersion": 1,
                                    "conditionType": "NONE",
                                    "conditionParams": {},
                                }
                            )

                # 删除任务定义和坐标
                tasks = [t for t in tasks if t.get("code") != target_code]
                locations = [
                    loc for loc in locations if loc.get("taskCode") != target_code
                ]
                del name_to_task[task_name]
                del name_to_code[task_name]
                code_to_name.pop(target_code, None)

                applied_count += 1

            # ============ 修改任务 ============
            elif action == "update_task":
                old_task_name = op.get("task_name")
                updates = op.get("updates", {}) or {}
                if not old_task_name or old_task_name not in name_to_task:
                    continue

                target = name_to_task[old_task_name]
                target_code = name_to_code[old_task_name]

                # ===== name 字段特殊处理：需要更新所有索引 =====
                if "name" in updates and updates["name"] != old_task_name:
                    new_name = updates["name"]
                    if new_name in name_to_task:
                        raise ValueError(
                            f"无法重命名：目标名称 '{new_name}' 已被另一个节点使用。"
                            f"已存在节点列表: {list(name_to_task.keys())}"
                        )
                    # 更新任务定义中的 name
                    target["name"] = new_name
                    # 更新三个索引
                    del name_to_task[old_task_name]
                    name_to_task[new_name] = target
                    del name_to_code[old_task_name]
                    name_to_code[new_name] = target_code
                    # code_to_name 也要更新（后面可能用到）
                    code_to_name[target_code] = new_name
                    applied_count += 1

                # ===== 字段归一化：同时接受 snake_case 和 DS 原生 camelCase =====
                # 解决"传了 preStatements/timeoutFlag 等却被静默忽略"的问题
                # key = 统一后的内部别名，value = 用户可能传入的任意写法
                ALIAS = {
                    # 顶层（taskDefinition）字段
                    "description": ("description",),
                    "fail_retry_times": ("fail_retry_times", "failRetryTimes"),
                    "fail_retry_interval": ("fail_retry_interval", "failRetryInterval"),
                    "timeout": ("timeout",),
                    "timeout_flag": ("timeout_flag", "timeoutFlag"),
                    "timeout_notify_strategy": (
                        "timeout_notify_strategy",
                        "timeoutNotifyStrategy",
                    ),
                    "worker_group": ("worker_group", "workerGroup"),
                    "task_priority": ("task_priority", "taskPriority"),
                    "delay_time": ("delay_time", "delayTime"),
                    "flag": ("flag",),
                    # taskParams 内字段
                    "sql": ("sql",),
                    "pre_statements": ("pre_statements", "preStatements"),
                    "post_statements": ("post_statements", "postStatements"),
                    "script": ("script", "rawScript"),
                    "datasource_id": ("datasource_id", "datasource"),
                    "sql_type": ("sql_type",),  # → params["type"]
                    "sql_type_select": ("sql_type_select", "sqlType"),
                    "resource_list": ("resource_list", "resourceList"),
                    "local_params": ("local_params", "localParams"),
                }

                def _pick(canonical: str):
                    """从 updates 取某个规范字段的值，返回 (命中, 值)。命中任一别名即可。"""
                    for alias in ALIAS[canonical]:
                        if alias in updates:
                            return True, updates[alias]
                    return False, None

                # 记录哪些 updates key 被识别了，剩下的就是被忽略的（用于告警）
                recognized_keys = set()
                for aliases in ALIAS.values():
                    for alias in aliases:
                        if alias in updates:
                            recognized_keys.add(alias)
                # name 在前面已单独处理
                recognized_keys.add("name")
                ignored_keys = [k for k in updates.keys() if k not in recognized_keys]
                if ignored_keys:
                    ignored_fields.append(
                        {
                            "task_name": code_to_name.get(target_code, old_task_name),
                            "keys": ignored_keys,
                        }
                    )

                # ===== 顶层（taskDefinition）字段 =====
                hit, val = _pick("description")
                if hit:
                    target["description"] = val
                hit, val = _pick("fail_retry_times")
                if hit:
                    target["failRetryTimes"] = val
                hit, val = _pick("fail_retry_interval")
                if hit:
                    target["failRetryInterval"] = val
                hit, val = _pick("timeout")
                if hit:
                    target["timeout"] = val
                hit, val = _pick("timeout_flag")
                if hit:
                    # 兼容布尔/字符串：True/"OPEN" → OPEN，其余 → CLOSE
                    if isinstance(val, bool):
                        target["timeoutFlag"] = "OPEN" if val else "CLOSE"
                    else:
                        target["timeoutFlag"] = str(val).upper()
                hit, val = _pick("timeout_notify_strategy")
                if hit:
                    target["timeoutNotifyStrategy"] = val
                hit, val = _pick("worker_group")
                if hit:
                    target["workerGroup"] = val
                hit, val = _pick("task_priority")
                if hit:
                    target["taskPriority"] = val
                hit, val = _pick("delay_time")
                if hit:
                    target["delayTime"] = val
                hit, val = _pick("flag")
                if hit:
                    target["flag"] = val

                # ===== taskParams 内字段 =====
                # ⚠️ taskParams 可能是 JSON 字符串（DS API 返回格式不一致）
                params_raw = target.get("taskParams", {}) or {}
                if isinstance(params_raw, str):
                    try:
                        params = json.loads(params_raw)
                    except Exception:
                        params = {}
                else:
                    params = params_raw

                hit, val = _pick("sql")
                if hit:
                    params["sql"] = val
                hit, val = _pick("pre_statements")
                if hit:
                    params["preStatements"] = val
                hit, val = _pick("post_statements")
                if hit:
                    params["postStatements"] = val
                hit, val = _pick("script")
                if hit:
                    params["rawScript"] = val
                hit, val = _pick("datasource_id")
                if hit:
                    params["datasource"] = val
                hit, val = _pick("sql_type")
                if hit:
                    params["type"] = val
                hit, val = _pick("sql_type_select")
                if hit:
                    params["sqlType"] = str(val)
                hit, val = _pick("resource_list")
                if hit:
                    params["resourceList"] = normalize_resource_list(val)
                hit, val = _pick("local_params")
                if hit:
                    params["localParams"] = val
                target["taskParams"] = params

                applied_count += 1

            # ============ 修改节点坐标 ============
            elif action == "update_location":
                task_name = op.get("task_name")
                if not task_name or task_name not in name_to_code:
                    continue
                target_code = name_to_code[task_name]
                new_x = op.get("x")
                new_y = op.get("y")
                if new_x is None or new_y is None:
                    raise ValueError("update_location 需要同时提供 x 和 y 坐标")

                # 找到对应的 location 并更新
                found = False
                for loc in locations:
                    if loc.get("taskCode") == target_code:
                        loc["x"] = new_x
                        loc["y"] = new_y
                        found = True
                        break

                if not found:
                    # 如果不存在，添加新坐标
                    locations.append({"taskCode": target_code, "x": new_x, "y": new_y})

                applied_count += 1

            # ============ 调整依赖关系 ============
            elif action == "update_relations":
                changes = op.get("changes", []) or []
                for ch in changes:
                    ch_op = (ch.get("op") or "").lower()
                    from_name = ch.get("from", "") or ""
                    to_name = ch.get("to", "")
                    if not to_name:
                        continue
                    pre_code = name_to_code.get(from_name, 0) if from_name else 0
                    post_code = name_to_code.get(to_name)
                    if post_code is None:
                        continue

                    if ch_op == "add":
                        dup = any(
                            r.get("preTaskCode") == pre_code
                            and r.get("postTaskCode") == post_code
                            for r in relations
                        )
                        if not dup:
                            relations.append(
                                {
                                    "name": "",
                                    "preTaskCode": pre_code,
                                    "preTaskVersion": 1 if pre_code else 0,
                                    "postTaskCode": post_code,
                                    "postTaskVersion": 1,
                                    "conditionType": "NONE",
                                    "conditionParams": {},
                                }
                            )
                            applied_count += 1
                    elif ch_op == "remove":
                        before = len(relations)
                        relations = [
                            r
                            for r in relations
                            if not (
                                r.get("preTaskCode") == pre_code
                                and r.get("postTaskCode") == post_code
                            )
                        ]
                        if len(relations) != before:
                            applied_count += 1

            else:
                raise ValueError(
                    f"未知的 action: {action}（支持：add_task/delete_task/update_task/update_location/update_relations）"
                )

        if applied_count == 0:
            raise RuntimeError("没有应用任何操作，请检查 operations 参数")

        # 3. 确保每个任务都有入边（孤儿任务自动加起点）
        has_incoming = {r.get("postTaskCode") for r in relations}
        for t in tasks:
            tc = t.get("code")
            if tc not in has_incoming:
                relations.insert(
                    0,
                    {
                        "name": "",
                        "preTaskCode": 0,
                        "preTaskVersion": 0,
                        "postTaskCode": tc,
                        "postTaskVersion": 1,
                        "conditionType": "NONE",
                        "conditionParams": {},
                    },
                )

        # 4. 回写工作流定义
        current_version = pd.get("version", 1)
        payload = {
            "name": pd.get("name"),
            "description": pd.get("description", ""),
            "globalParams": pd.get("globalParamStr", "[]") or "[]",
            "locations": json.dumps(locations),
            "taskDefinitionJson": json.dumps(tasks),
            "taskRelationJson": json.dumps(relations),
            "tenantCode": pd.get("tenantCode") or get_tenant_code(),
            "executionType": pd.get("executionType", "PARALLEL") or "PARALLEL",
            "timeout": pd.get("timeout", 0) or 0,
            "processDefinitionVersion": current_version,
        }
        deadline.stage = "write"
        update_result = ds_put(
            f"/projects/{pcode}/process-definition/{workflow_code}",
            data=payload,
        )
        require_ok(update_result, "更新工作流定义")
        deadline.write_succeeded = True

        # 写入后立即回读，不能仅凭 PUT code=0 就声称已持久化
        deadline.stage = "verify"
        verified_result = ds_get(
            f"/projects/{pcode}/process-definition/{workflow_code}"
        )
        require_ok(verified_result, "回读工作流定义")
        verified_pd = (verified_result.get("data", {}) or {}).get(
            "processDefinition", {}
        ) or {}
        persisted_version = verified_pd.get("version")

        # 5. 如果之前在线，重新上线
        deadline.stage = "online"
        release_state = "OFFLINE"
        schedule_action = ""
        if was_online and auto_online:
            rel_result = ds_post(
                f"/projects/{pcode}/process-definition/{workflow_code}/release",
                data={"releaseState": "ONLINE"},
            )
            if rel_result.get("code") == 0:
                release_state = "ONLINE"

        # 6. 恢复调度（v2.0.11: DS 下线工作流会连带下线调度）
        deadline.stage = "schedule"
        if release_state == "ONLINE" and auto_online_schedule:
            try:
                sch_result = ds_get(
                    f"/projects/{pcode}/schedules?pageNo=1&pageSize=10"
                    f"&processDefinitionCode={workflow_code}"
                )
                if sch_result.get("code") == 0:
                    schedules = sch_result.get("data", {}).get("totalList", []) or []
                    for s in schedules:
                        if s.get("processDefinitionCode") == workflow_code:
                            sid = s.get("id")
                            sstate = s.get("releaseState", "OFFLINE")
                            if sstate != "ONLINE":
                                online_sch = ds_post(
                                    f"/projects/{pcode}/schedules/{sid}/online"
                                )
                                if online_sch.get("code") == 0:
                                    schedule_action = (
                                        f"已自动恢复调度 schedule_id={sid}"
                                    )
                                else:
                                    schedule_action = (
                                        f"调度恢复失败 schedule_id={sid}: "
                                        f"{online_sch.get('msg')}。请手动 ds_online_schedule"
                                    )
                            else:
                                schedule_action = f"调度已是 ONLINE (schedule_id={sid})"
                            break
                if not schedule_action:
                    schedule_action = "工作流没有关联调度，无需恢复"
            except _EditTimeout:
                raise
            except Exception as e:
                schedule_action = f"调度恢复异常: {str(e)[:100]}"

        expected_release = "ONLINE" if was_online and auto_online else "OFFLINE"
        schedule_failed = schedule_action.startswith(("调度恢复失败", "调度恢复异常"))
        completed = release_state == expected_release and not schedule_failed
        return {
            "workflow_code": workflow_code,
            "operations_applied": applied_count,
            "task_count_before": tasks_before,
            "task_count_after": len(tasks),
            "previous_version": current_version,
            "version": persisted_version,
            "persisted": True,
            "release_state": release_state,
            "schedule_action": schedule_action or None,
            "status": "updated" if completed else "partially_applied",
            "ignored_fields": ignored_fields or None,
            "warning": (
                "⚠️ 工作流定义已写入并回读确认。"
                + (
                    ""
                    if completed
                    else "但上线或调度恢复未完成，请按 phase/release_state 处理。"
                )
                + "如果工作流正在运行，建议观察下一次执行是否正常"
                + (
                    f"。⚠️ 检测到无法识别的 updates 字段被忽略: {ignored_fields}，"
                    "请检查字段名是否正确"
                    if ignored_fields
                    else ""
                )
            ),
        }

    @mcp.tool()
    def ds_modify_workflow_dag(
        project_name: str,
        workflow_code: int,
        operations: list,
        auto_offline: bool = True,
        auto_online: bool = True,
        auto_online_schedule: bool = True,
        expected_version: int = 0,
        timeout_seconds: float = 90,
    ) -> dict:
        """修改工作流 DAG，支持版本防覆盖、总时间预算和写入回读。

        expected_version>0 时，当前版本不一致会拒绝写入。timeout_seconds 覆盖
        项目解析、读取、下线、写入、上线、调度和回读全过程。写请求超时返回
        unknown，不自动重试；写成功后的恢复/回读失败返回 partially_applied。
        """
        deadline = _EditDeadline(timeout_seconds)
        try:
            return _modify_workflow_dag(
                project_name=project_name,
                workflow_code=workflow_code,
                operations=operations,
                auto_offline=auto_offline,
                auto_online=auto_online,
                auto_online_schedule=auto_online_schedule,
                expected_version=expected_version,
                deadline=deadline,
            )
        except _EditTimeout as exc:
            return _timeout_edit_result(exc, workflow_code)
        except Exception as exc:
            if deadline.write_succeeded:
                return {
                    "workflow_code": workflow_code,
                    "status": "partially_applied",
                    "phase": deadline.stage,
                    "persisted": True,
                    "retry_safe": False,
                    "error": str(exc),
                    "recovery": "定义已写入；先回读版本、release_state 和调度状态，不要直接重复提交",
                }
            raise

    @mcp.tool()
    def ds_patch_task_content(
        project_name: str,
        workflow_code: int,
        task_name: str,
        old_str: str,
        new_str: str,
        field: str = "sql",
        expected_version: int = 0,
        dry_run: bool = True,
        auto_offline: bool = True,
        auto_online: bool = True,
        auto_online_schedule: bool = True,
        timeout_seconds: float = 90,
    ) -> dict:
        """局部替换单节点 SQL 或 SHELL 脚本，默认只预检不写入。

        old_str 必须在目标字段中恰好出现一次。先用 dry_run=True 获取 diff 和
        current_version，再以 expected_version=current_version、dry_run=False
        提交，防止覆盖他人修改。正式写入后回读目标字段验证。
        """
        if not old_str:
            raise ValueError("old_str 不能为空")
        if old_str == new_str:
            raise ValueError("new_str 与 old_str 相同，无需修改")
        if field not in ("sql", "script"):
            raise ValueError("field 只支持 sql 或 script")
        if not dry_run and not expected_version:
            raise ValueError("正式写入必须传 dry_run 预检返回的 expected_version")

        preview_deadline = _EditDeadline(timeout_seconds)
        pcode = resolve_project_code(project_name, timeout=preview_deadline.remaining())
        preview_deadline.stage = "read_task"
        current = preview_deadline.request(
            client_get,
            f"/projects/{pcode}/process-definition/{workflow_code}",
        )
        require_ok(current, "读取待修改工作流")
        data = current.get("data", {}) or {}
        current_version = (data.get("processDefinition", {}) or {}).get("version")
        if expected_version and current_version != expected_version:
            raise ValueError(
                f"工作流版本已变化：期望 {expected_version}，实际 {current_version}"
            )
        target = next(
            (
                t
                for t in (data.get("taskDefinitionList", []) or [])
                if t.get("name") == task_name
            ),
            None,
        )
        if target is None:
            raise ValueError(f"任务 {task_name!r} 不存在")
        params_raw = target.get("taskParams", {}) or {}
        params = json.loads(params_raw) if isinstance(params_raw, str) else params_raw
        key = "sql" if field == "sql" else "rawScript"
        original = params.get(key)
        if field == "script" and original is None:
            original = params.get("script", "")
        if not isinstance(original, str):
            raise ValueError(f"节点 {task_name!r} 没有可编辑的 {field} 内容")
        occurrences = original.count(old_str)
        if occurrences != 1:
            raise ValueError(
                f"old_str 必须恰好匹配一次，实际匹配 {occurrences} 次；未执行任何写入"
            )
        updated = original.replace(old_str, new_str, 1)
        diff = "\n".join(
            difflib.unified_diff(
                original.splitlines(),
                updated.splitlines(),
                fromfile=f"{task_name}.before.{field}",
                tofile=f"{task_name}.after.{field}",
                lineterm="",
            )
        )
        preview = {
            "workflow_code": workflow_code,
            "task_name": task_name,
            "field": field,
            "current_version": current_version,
            "diff": diff,
            "match_count": occurrences,
        }
        if dry_run:
            return dict(preview, status="preview", persisted=False)

        result = ds_update_task_param(
            project_name=project_name,
            workflow_code=workflow_code,
            task_name=task_name,
            updates={field: updated},
            auto_offline=auto_offline,
            auto_online=auto_online,
            auto_online_schedule=auto_online_schedule,
            expected_version=expected_version,
            timeout_seconds=timeout_seconds,
        )
        result.update(preview)
        if result.get("status") != "updated":
            return result

        # 再读一次目标字段，防止只确认版本号而节点内容未按预期落盘
        try:
            verify_deadline = _EditDeadline(timeout_seconds)
            verify_deadline.stage = "verify_task_content"
            verify_pcode = resolve_project_code(
                project_name, timeout=verify_deadline.remaining()
            )
            verified = verify_deadline.request(
                client_get,
                f"/projects/{verify_pcode}/process-definition/{workflow_code}",
            )
            require_ok(verified, "回读节点修改内容")
            verified_tasks = (verified.get("data", {}) or {}).get(
                "taskDefinitionList", []
            ) or []
            verified_target = next(
                (t for t in verified_tasks if t.get("name") == task_name), None
            )
            verified_params_raw = (verified_target or {}).get("taskParams", {}) or {}
            verified_params = (
                json.loads(verified_params_raw)
                if isinstance(verified_params_raw, str)
                else verified_params_raw
            )
            actual = verified_params.get(key)
            if field == "script" and actual is None:
                actual = verified_params.get("script", "")
            result["content_verified"] = actual == updated
            if actual != updated:
                result["status"] = "partially_applied"
                result["error"] = "工作流已写入，但回读的目标字段与预期不一致"
        except Exception as exc:
            result["status"] = "partially_applied"
            result["phase"] = "verify_task_content"
            result["content_verified"] = False
            result["error"] = f"工作流已写入，目标字段回读未完成: {exc}"
            result["recovery"] = "用 ds_get_task_detail 回读目标字段，不要直接重复提交"
        return result

    @mcp.tool()
    def ds_update_task_param(
        project_name: str,
        workflow_code: int,
        task_name: str,
        updates: dict,
        auto_offline: bool = True,
        auto_online: bool = True,
        auto_online_schedule: bool = True,
        expected_version: int = 0,
        timeout_seconds: float = 90,
    ) -> dict:
        """Lightweight single-task parameter update — no need to pass full DAG definition.

        This tool is a convenience wrapper around ds_modify_workflow_dag's update_task,
        automatically handling the "read → modify → write → online/offline" flow.

        Use case: Change a single task's SQL/script/name/retry params without constructing a full operations list.

        Args:
            project_name: Project name
            workflow_code: Workflow code
            task_name: Task name to modify (exact match)
            updates: Fields to update (flat dict, field names same as update_task's updates)
            auto_offline: Auto-offline before modification (default True)
            auto_online: Auto-online after modification (default True)
            auto_online_schedule: Auto-restore schedule after onlining (default True, v2.0.11)
            expected_version: Reject the write if the current workflow version differs
            timeout_seconds: Total edit budget; write timeouts are not retried automatically

        Supported updates fields (snake_case and camelCase both accepted):
            Common: name, description, fail_retry_times(failRetryTimes),
                    fail_retry_interval(failRetryInterval), timeout,
                    timeout_flag(timeoutFlag), timeout_notify_strategy(timeoutNotifyStrategy),
                    worker_group(workerGroup), task_priority(taskPriority),
                    delay_time(delayTime), flag
            SQL: sql, datasource_id(datasource), sql_type, sql_type_select(sqlType),
                 pre_statements(preStatements), post_statements(postStatements),
                 local_params(localParams), resource_list(resourceList)
            SHELL/PYTHON: script(rawScript), resource_list(resourceList), local_params(localParams)

        ⚠️ Unrecognized fields are reported in the return value's ignored_fields (not silently dropped).

        Returns:
            {
                "workflow_code": int,
                "task_name": str,
                "schedule_action": str,
                "status": "updated",
            }

        Examples:
            # Change a single task's retry params
            ds_update_task_param(
                project_name="my_project",
                workflow_code=21583255237888,
                task_name="check_partition",
                updates={"fail_retry_times": 8, "fail_retry_interval": 1}
            )

            # Rename a task (v2.0.11)
            ds_update_task_param(
                project_name="my_project", workflow_code=..., task_name="old_sql",
                updates={"name": "new_sql_v2"}
            )

            # Change SQL only
            ds_update_task_param(
                project_name="my_project", workflow_code=..., task_name="sql1",
                updates={"sql": "SELECT * FROM new_table WHERE dt='$[yyyyMMdd-1]'"}
            )
        """
        # Directly reuse ds_modify_workflow_dag's update_task logic
        return ds_modify_workflow_dag(
            project_name=project_name,
            workflow_code=workflow_code,
            operations=[
                {
                    "action": "update_task",
                    "task_name": task_name,
                    "updates": updates,
                }
            ],
            auto_offline=auto_offline,
            auto_online=auto_online,
            auto_online_schedule=auto_online_schedule,
            expected_version=expected_version,
            timeout_seconds=timeout_seconds,
        )
