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

import json
import time

from mcp.server.mcpserver import MCPServer

from ..client import ds_get, ds_post, ds_put
from ..config import get_tenant_code
from ..utils import require_ok, resolve_project_code
from .resource import normalize_resource_list


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
        """List historical versions of a workflow.

        Args:
            project_name: Project name
            workflow_code: Process-definition code
            page_size: Number of items to return
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
            "tenantCode": "iflyrd",
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

    @mcp.tool()
    def ds_modify_workflow_dag(
        project_name: str,
        workflow_code: int,
        operations: list,
        auto_offline: bool = True,
        auto_online: bool = True,
        auto_online_schedule: bool = True,
    ) -> dict:
        """Modify existing workflow DAG (add/delete/update tasks + adjust dependencies).

        Implementation: read current DAG → apply operations → write back.

        ⚠️ Risk warning:
        - Modifications create a new version; old versions preserved and rollback-able
        - If workflow is running, it will be taken offline first (auto_offline=True by default)
        - Auto-re-online after modification (auto_online=True by default)
        - DS has no native "add single task" API; this tool simulates it via "read → modify → full update"

        Args:
            project_name: Project name
            workflow_code: Workflow code
            operations: Operation list (supports 5 action types)
            auto_offline: Auto-offline before modification (default True)
            auto_online: Auto-online after modification (default True)
            auto_online_schedule: Auto-restore associated schedule after onlining (default True)
                ⚠️ DS offlines the schedule when workflow goes offline;
                set False only if schedule auto-restore is not needed.

        Supported operation types:

        [1] Add task (add_task):
            {
                "action": "add_task",
                "task": {
                    "name": "wait_upstream",
                    "type": "DEPENDENT",
                    "depend_items": [{
                        "project_code": 123,
                        "definition_code": 456,
                        "dep_task_code": 0,    # 0=entire workflow, nonzero=specific task
                        "cycle": "day",         # day/hour/week/month
                        "date_value": "today"   # today/yesterday/last7days
                    }],
                    "dep_relation": "AND"       # multi-dep relation: AND/OR
                    # other fields same as ds_create_dag_workflow
                },
                "connect_from": "task_a",       # predecessor task name (empty=start node)
                "connect_to": "task_b"          # successor task name (empty=end node)
            }

        [2] Delete task (delete_task):
            {
                "action": "delete_task",
                "task_name": "old_task",
                "reconnect": true               # auto-reconnect predecessor/successor to prevent DAG break
            }

        [3] Update task parameters (update_task):
            {
                "action": "update_task",
                "task_name": "my_sql",
                "updates": {
                    # ===== Common fields (snake_case / camelCase aliases supported) =====
                    "name": "new_task_name",           # v2.0.11: rename node
                    "description": "Updated description",
                    "fail_retry_times": 3,             # or "failRetryTimes"
                    "fail_retry_interval": 4,          # or "failRetryInterval" (v2.0.10 fixed)
                    "timeout": 300,                    # timeout duration (minutes)
                    "timeout_flag": "OPEN",            # or "timeoutFlag": "OPEN"/"CLOSE" or True/False
                    "timeout_notify_strategy": "FAILED",  # or "timeoutNotifyStrategy": "FAILED"/"WARNING"
                    "worker_group": "default",         # or "workerGroup"
                    "task_priority": "HIGH",           # or "taskPriority": "HIGH"/"MEDIUM"/"LOW"
                    "delay_time": 0,                   # or "delayTime" (delay in minutes)
                    "flag": "YES",                     # "YES"=enabled "NO"=disabled

                    # ===== SQL task =====
                    "sql": "SELECT * FROM new_table WHERE dt='$[yyyyMMdd-1]'",
                    "datasource_id": 1,                # or "datasource"
                    "sql_type": "HIVE",                # "HIVE"/"MYSQL"/"POSTGRESQL" etc.
                    "sql_type_select": 0,              # or "sqlType": 0=query 1=non-query
                    "pre_statements": [                # or "preStatements" (pre-SQL list)
                        "SET hive.exec.dynamic.partition=true",
                        "SET spark.sql.sources.partitionOverwriteMode=dynamic"
                    ],
                    "post_statements": ["SELECT 1"],   # or "postStatements" (post-SQL list)

                    # ===== SHELL/PYTHON task =====
                    "script": "#!/bin/bash\nexport PATH=/xxx/bin:$PATH\npython3 script.py",
                    # or "rawScript"

                    # ===== Resource refs (usable by SHELL/PYTHON/SQL) =====
                    "resource_list": [67, 58],         # or "resourceList" (int ID recommended)
                    # or ["/public/check_partition.py"] (full path, starting with /)

                    # ===== Local params =====
                    "local_params": [{"prop":"dt","value":"$[yyyyMMdd-1]"}]  # or "localParams"
                }
            }

            ⚠️ resource_list format:
            - Recommended: resource_id (int): [67, 58]
            - Or full path (str): ["/public/check_partition.py", "/scripts/sync.py"]
            - Paths must start with /, e.g. /public/xxx.py not public/xxx.py
            - Use ds_list_resources() to view all resources with ids and paths

            ⚠️ Field naming compatibility:
            - Supports both snake_case (e.g. pre_statements) and camelCase (e.g. preStatements)
            - Both styles work identically; snake_case recommended
            - Unrecognized fields logged in return value's ignored_fields

        [4] Update node coordinates (update_location):
            {
                "action": "update_location",
                "task_name": "my_task",
                "x": 500,
                "y": 300
            }

        [5] Adjust dependencies (update_relations):
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
                "warning": risk notice
            }

        Typical scenario: append a DEPENDENT node so the workflow waits on upstream
            ds_modify_workflow_dag(
                project_name="my_project",
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
                    "connect_from": "",               # start node
                    "connect_to": "existing_task_1"   # connect to an existing task
                }]
            )
        """
        pcode = resolve_project_code(project_name)

        # 1. Read current workflow definition
        current = ds_get(f"/projects/{pcode}/process-definition/{workflow_code}")
        require_ok(current, "get current workflow definition")

        data = current.get("data", {}) or {}
        pd = data.get("processDefinition", {}) or {}
        tasks = list(data.get("taskDefinitionList", []) or [])
        relations = list(data.get("processTaskRelationList", []) or [])

        if not tasks:
            raise RuntimeError("Workflow has no task definitions; cannot modify")

        tasks_before = len(tasks)

        # Parse locations
        locations_raw = pd.get("locations", "[]") or "[]"
        try:
            locations = (
                json.loads(locations_raw)
                if isinstance(locations_raw, str)
                else list(locations_raw)
            )
        except Exception:
            locations = []

        # Build indexes
        name_to_task = {t.get("name"): t for t in tasks if t.get("name")}
        name_to_code = {t.get("name"): t.get("code") for t in tasks if t.get("name")}
        code_to_name = {t.get("code"): t.get("name") for t in tasks if t.get("code")}

        # 2. Apply operations
        applied_count = 0
        ignored_fields = []  # Collect unrecognized updates fields in update_task (for warning)
        current_state = pd.get("releaseState", "OFFLINE")
        was_online = current_state == "ONLINE"

        # Take offline first if online and auto_offline=True
        if was_online and auto_offline:
            ds_post(
                f"/projects/{pcode}/process-definition/{workflow_code}/release",
                data={"releaseState": "OFFLINE"},
            )

        for op in operations:
            action = (op.get("action") or "").lower()

            # ============ Add task ============
            if action == "add_task":
                task_def = op.get("task", {})
                task_name = task_def.get("name")
                if not task_name:
                    continue
                if task_name in name_to_code:
                    raise ValueError(
                        f"Task {task_name!r} already exists; use update_task to modify it"
                    )

                # Generate a new task code
                gen_result = ds_get(
                    f"/projects/{pcode}/task-definition/gen-task-codes?genNum=1"
                )
                require_ok(gen_result, "generate task code")
                new_codes = gen_result.get("data") or []
                if not new_codes:
                    raise RuntimeError("Failed to generate task code")
                new_code = new_codes[0]

                # Build task definition
                new_task = _build_task_definition(new_code, task_def)
                tasks.append(new_task)
                name_to_task[task_name] = new_task
                name_to_code[task_name] = new_code
                code_to_name[new_code] = task_name

                # Coordinates: auto-place to the lower right (wider spacing)
                max_x = max((loc.get("x", 100) for loc in locations), default=100)
                max_y = max((loc.get("y", 100) for loc in locations), default=100)
                locations.append(
                    {"taskCode": new_code, "x": max_x + 300, "y": max_y + 150}
                )

                # Dependencies
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
                        raise ValueError(
                            f"connect_to references a nonexistent task: {connect_to}"
                        )
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

            # ============ Delete task ============
            elif action == "delete_task":
                task_name = op.get("task_name")
                if not task_name or task_name not in name_to_code:
                    continue
                target_code = name_to_code[task_name]
                reconnect = bool(op.get("reconnect", True))

                # Find incoming edges (pre) and outgoing edges (post) for this task
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

                # Remove all edges involving this task
                relations = [
                    r
                    for r in relations
                    if r.get("preTaskCode") != target_code
                    and r.get("postTaskCode") != target_code
                ]

                # If reconnect requested: wire upstream directly to downstream
                if reconnect and pre_codes and post_codes:
                    for pc in pre_codes:
                        for sc in post_codes:
                            # Avoid duplicates
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

                # If a successor is left orphaned (no incoming edge), add a start edge
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

                # Remove task definition and coordinates
                tasks = [t for t in tasks if t.get("code") != target_code]
                locations = [
                    loc for loc in locations if loc.get("taskCode") != target_code
                ]
                del name_to_task[task_name]
                del name_to_code[task_name]
                code_to_name.pop(target_code, None)

                applied_count += 1

            # ============ Update task ============
            elif action == "update_task":
                old_task_name = op.get("task_name")
                updates = op.get("updates", {}) or {}
                if not old_task_name or old_task_name not in name_to_task:
                    continue

                target = name_to_task[old_task_name]
                target_code = name_to_code[old_task_name]

                # ===== Handle "name" field separately: needs to update all indexes =====
                if "name" in updates and updates["name"] != old_task_name:
                    new_name = updates["name"]
                    if new_name in name_to_task:
                        raise ValueError(
                            f"Cannot rename: target name '{new_name}' is already used by another task. "
                            f"Existing task names: {list(name_to_task.keys())}"
                        )
                    # Update name in task definition
                    target["name"] = new_name
                    # Update all three indexes
                    del name_to_task[old_task_name]
                    name_to_task[new_name] = target
                    del name_to_code[old_task_name]
                    name_to_code[new_name] = target_code
                    # Also update code_to_name (may be used later)
                    code_to_name[target_code] = new_name
                    applied_count += 1

                # ===== Field normalization: accept both snake_case and DS native camelCase =====
                # Fixes: preStatements/timeoutFlag etc. being silently ignored
                # key = canonical alias, value = any user-supplied variant
                ALIAS = {
                    # Top-level (taskDefinition) fields
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
                    # taskParams inner fields
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
                    """Pick a canonical field value from updates; match any alias."""
                    for alias in ALIAS[canonical]:
                        if alias in updates:
                            return True, updates[alias]
                    return False, None

                # Track which updates keys were recognized; unrecognized = silently dropped
                recognized_keys = set()
                for aliases in ALIAS.values():
                    for alias in aliases:
                        if alias in updates:
                            recognized_keys.add(alias)
                # "name" handled separately above
                recognized_keys.add("name")
                ignored_keys = [k for k in updates.keys() if k not in recognized_keys]
                if ignored_keys:
                    ignored_fields.append(
                        {
                            "task_name": code_to_name.get(target_code, old_task_name),
                            "keys": ignored_keys,
                        }
                    )

                # ===== Top-level (taskDefinition) fields =====
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
                    # Compatible with bool/string: True/"OPEN" → OPEN, else → CLOSE
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

                # ===== taskParams fields =====
                # ⚠️ taskParams may be a JSON string (DS API returns inconsistent formats)
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

            # ============ Update node coordinates ============
            elif action == "update_location":
                task_name = op.get("task_name")
                if not task_name or task_name not in name_to_code:
                    continue
                target_code = name_to_code[task_name]
                new_x = op.get("x")
                new_y = op.get("y")
                if new_x is None or new_y is None:
                    raise ValueError(
                        "update_location requires both x and y coordinates"
                    )

                # Find and update the corresponding location
                found = False
                for loc in locations:
                    if loc.get("taskCode") == target_code:
                        loc["x"] = new_x
                        loc["y"] = new_y
                        found = True
                        break

                if not found:
                    # If not found, add new location entry
                    locations.append({"taskCode": target_code, "x": new_x, "y": new_y})

                applied_count += 1

            # ============ Adjust dependencies ============
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
                    f"Unknown action: {action} (supported: add_task/delete_task/update_task/update_location/update_relations)"
                )

        if applied_count == 0:
            raise RuntimeError("No operations applied; check the operations parameter")

        # 3. Ensure every task has an incoming edge (orphan tasks get start edge auto-added)
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

        # 4. Write back workflow definition
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
        update_result = ds_put(
            f"/projects/{pcode}/process-definition/{workflow_code}",
            data=payload,
        )
        require_ok(update_result, "update workflow definition")

        # 5. Re-online if was online
        release_state = "OFFLINE"
        schedule_action = ""
        if was_online and auto_online:
            rel_result = ds_post(
                f"/projects/{pcode}/process-definition/{workflow_code}/release",
                data={"releaseState": "ONLINE"},
            )
            if rel_result.get("code") == 0:
                release_state = "ONLINE"

        # 6. Restore schedule (v2.0.11: DS offlines schedule when workflow goes offline)
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
                                        f"Auto-restored schedule schedule_id={sid}"
                                    )
                                else:
                                    schedule_action = (
                                        f"Schedule restore failed schedule_id={sid}: "
                                        f"{online_sch.get('msg')}. Call ds_online_schedule manually"
                                    )
                            else:
                                schedule_action = (
                                    f"Schedule already ONLINE (schedule_id={sid})"
                                )
                            break
                if not schedule_action:
                    schedule_action = (
                        "Workflow has no associated schedule; no restore needed"
                    )
            except Exception as e:
                schedule_action = f"Schedule restore exception: {str(e)[:100]}"

        return {
            "workflow_code": workflow_code,
            "operations_applied": applied_count,
            "task_count_before": tasks_before,
            "task_count_after": len(tasks),
            "release_state": release_state,
            "schedule_action": schedule_action or None,
            "status": "updated",
            "ignored_fields": ignored_fields or None,
            "warning": (
                "⚠️ Workflow definition updated, a new version will be created (check ds_list_workflow_versions)."
                " Monitor the next execution if the workflow was running."
                + (
                    f". ⚠️ Unrecognized updates fields ignored: {ignored_fields}. "
                    "Check field name spelling."
                    if ignored_fields
                    else ""
                )
            ),
        }

    @mcp.tool()
    def ds_update_task_param(
        project_name: str,
        workflow_code: int,
        task_name: str,
        updates: dict,
        auto_offline: bool = True,
        auto_online: bool = True,
        auto_online_schedule: bool = True,
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
        )
