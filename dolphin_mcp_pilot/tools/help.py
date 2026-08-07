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

"""Help and navigation tools."""

from mcp.server.fastmcp import FastMCP


def register_help_tools(mcp: FastMCP):
    """Register help and navigation MCP tools."""

    @mcp.tool()
    def ds_help(category: str = "") -> dict:
        """Interactive guide to DolphinScheduler MCP tools.

        Call without arguments to see all categories, or pass a category name
        to view tools and workflows for that category.

        Available categories:
        - quickstart: New user onboarding guide with common scenarios
        - project: Project CRUD (list/create/rename/delete)
        - workflow: Basic workflow operations (create/list/get/update/delete/release/run)
        - workflow_advanced: DAG editing, task updates, version management, cloning
        - instance: Process instance management, log retrieval, failure troubleshooting
        - schedule: Schedule configuration (cron/online/offline/delete)
        - resource: File and folder management (upload/download/view/update/delete)
        - monitor: Cluster health monitoring (master/worker status)
        - user: User and tenant queries
        - raw: Raw API passthrough for advanced use

        Args:
            category: Category name (empty string returns all categories)

        Returns:
            If category is empty: overview with tool counts
            If category is specified: {category, name, tools, workflow, hint}
        """
        all_categories = {
            "project": {
                "name": "Project Management",
                "tools": [
                    {
                        "name": "ds_test_connection",
                        "desc": "Test connection and login",
                        "risk": "read-only",
                    },
                    {
                        "name": "ds_list_projects",
                        "desc": "List all projects",
                        "risk": "read-only",
                    },
                    {
                        "name": "ds_create_project",
                        "desc": "Create a new project",
                        "risk": "write",
                    },
                    {
                        "name": "ds_rename_project",
                        "desc": "Rename a project",
                        "risk": "write",
                    },
                    {
                        "name": "ds_delete_project",
                        "desc": "Delete a project (cascades to all workflows)",
                        "risk": "⚠️ dangerous",
                    },
                ],
                "workflow": (
                    "1. List: ds_list_projects\n"
                    "2. Create: ds_create_project(name='...')\n"
                    "3. Rename: ds_rename_project(old_name='...', new_name='...')\n"
                    "4. Delete: ds_delete_project (irreversible)"
                ),
            },
            "workflow": {
                "name": "Workflow Basic Operations",
                "tools": [
                    {
                        "name": "ds_list_workflows",
                        "desc": "List workflows (supports search= for fuzzy matching)",
                        "risk": "read-only",
                    },
                    {
                        "name": "ds_get_workflow",
                        "desc": "Get workflow details (compact=True for metadata only)",
                        "risk": "read-only",
                    },
                    {
                        "name": "ds_create_workflow",
                        "desc": "Create workflow from DS definition JSON",
                        "risk": "write",
                    },
                    {
                        "name": "ds_create_dag_workflow",
                        "desc": "Create workflow from task list + relations (simpler than ds_create_workflow)",
                        "risk": "write",
                    },
                    {
                        "name": "ds_release_workflow",
                        "desc": "Bring workflow online/offline",
                        "risk": "write",
                    },
                    {
                        "name": "ds_run_workflow",
                        "desc": "Manually trigger workflow (supports start_task_names)",
                        "risk": "write",
                    },
                    {
                        "name": "ds_update_workflow",
                        "desc": "Update name/description/global params",
                        "risk": "write",
                    },
                    {
                        "name": "ds_delete_workflow",
                        "desc": "Delete workflow (takes offline first)",
                        "risk": "⚠️ dangerous",
                    },
                    {
                        "name": "ds_get_task_detail",
                        "desc": "Get single task definition",
                        "risk": "read-only",
                    },
                ],
                "workflow": (
                    "1. List: ds_list_workflows(search='keyword')\n"
                    "2. Create: ds_create_dag_workflow (simpler) or ds_create_workflow (full control)\n"
                    "3. Release: ds_release_workflow(online=True)\n"
                    "4. Run: ds_run_workflow(workflow_code=...)\n"
                    "5. Modify: ds_update_workflow or ds_modify_workflow_dag (see workflow_advanced)"
                ),
            },
            "workflow_advanced": {
                "name": "Workflow Advanced Operations",
                "tools": [
                    {
                        "name": "ds_modify_workflow_dag",
                        "desc": "Edit DAG with operations: add_task/delete_task/update_task/add_edge/delete_edge/update_location",
                        "risk": "write",
                    },
                    {
                        "name": "ds_update_task_param",
                        "desc": "Lightweight task parameter update (no full DAG required)",
                        "risk": "write",
                    },
                    {
                        "name": "ds_list_workflow_versions",
                        "desc": "List version history",
                        "risk": "read-only",
                    },
                    {
                        "name": "ds_rollback_workflow_version",
                        "desc": "Rollback to previous version",
                        "risk": "⚠️ dangerous",
                    },
                    {
                        "name": "ds_clone_workflow",
                        "desc": "Clone workflow within or across projects",
                        "risk": "write",
                    },
                ],
                "workflow": (
                    "1. Add task: ds_modify_workflow_dag(operations=[{'action':'add_task',...}])\n"
                    "2. Update task param: ds_update_task_param(task_name='...', updates={...})\n"
                    "3. Delete task: ds_modify_workflow_dag(operations=[{'action':'delete_task','task_name':'...'}])\n"
                    "4. Clone: ds_clone_workflow(new_name='...')"
                ),
            },
            "instance": {
                "name": "Instance & Troubleshooting",
                "tools": [
                    {
                        "name": "ds_list_process_instances",
                        "desc": "List process instances (filter by workflow_code/state/dates)",
                        "risk": "read-only",
                    },
                    {
                        "name": "ds_list_task_instances",
                        "desc": "List task instances for a process instance",
                        "risk": "read-only",
                    },
                    {
                        "name": "ds_get_task_log",
                        "desc": "Fetch task log (supports pagination)",
                        "risk": "read-only",
                    },
                    {
                        "name": "ds_get_latest_failure_log",
                        "desc": "One-click retrieval of failed task logs from latest instance",
                        "risk": "read-only",
                    },
                    {
                        "name": "ds_stop_process_instance",
                        "desc": "Stop running instance",
                        "risk": "write",
                    },
                    {
                        "name": "ds_pause_process_instance",
                        "desc": "Pause instance",
                        "risk": "write",
                    },
                    {
                        "name": "ds_resume_process_instance",
                        "desc": "Resume paused instance",
                        "risk": "write",
                    },
                    {
                        "name": "ds_rerun_process_instance",
                        "desc": "Rerun entire instance",
                        "risk": "write",
                    },
                    {
                        "name": "ds_rerun_from_failure",
                        "desc": "Continue from failed tasks",
                        "risk": "write",
                    },
                    {
                        "name": "ds_force_task_success",
                        "desc": "Force mark task as success",
                        "risk": "⚠️ dangerous",
                    },
                    {
                        "name": "ds_skip_task",
                        "desc": "Skip failed task",
                        "risk": "⚠️ dangerous",
                    },
                    {
                        "name": "ds_delete_process_instance",
                        "desc": "Delete historical instance",
                        "risk": "⚠️ dangerous",
                    },
                    {
                        "name": "ds_complement_data",
                        "desc": "Backfill by date range (default serial; supports partition_date/start_task_names/run_mode)",
                        "risk": "write",
                    },
                ],
                "workflow": (
                    "Troubleshooting workflow:\n"
                    "1. Quick locate: ds_get_latest_failure_log (one-click failure log)\n"
                    "2. Detailed check: ds_list_process_instances(workflow_code=...) → ds_list_task_instances(include_full=True) → ds_get_task_log\n"
                    "3. Fix & rerun: ds_rerun_from_failure (resume from failure) or ds_rerun_process_instance (full rerun)\n"
                    "4. Emergency handling: ds_force_task_success (skip failed node) or ds_skip_task"
                ),
            },
            "schedule": {
                "name": "Schedule Management",
                "tools": [
                    {
                        "name": "ds_list_schedules",
                        "desc": "List schedules (filter by workflow_code; simplify=True for summary)",
                        "risk": "read-only",
                    },
                    {
                        "name": "ds_set_schedule",
                        "desc": "Create schedule (cron required; created OFFLINE by default)",
                        "risk": "write",
                    },
                    {
                        "name": "ds_update_schedule_cron",
                        "desc": "Update cron expression only",
                        "risk": "write",
                    },
                    {
                        "name": "ds_online_schedule",
                        "desc": "Activate schedule",
                        "risk": "write",
                    },
                    {
                        "name": "ds_offline_schedule",
                        "desc": "Deactivate schedule",
                        "risk": "write",
                    },
                    {
                        "name": "ds_delete_schedule",
                        "desc": "Delete schedule",
                        "risk": "⚠️ dangerous",
                    },
                ],
                "workflow": (
                    "1. Query: ds_list_schedules(workflow_code=..., simplify=True) (view current config)\n"
                    '2. Create: ds_set_schedule(cron="...") → ds_online_schedule\n'
                    "3. Modify: ds_update_schedule_cron (change cron only)\n"
                    "4. Deactivate: ds_offline_schedule"
                ),
            },
            "resource": {
                "name": "Resource File Management",
                "tools": [
                    {
                        "name": "ds_list_resources",
                        "desc": "List resources (supports FILE/UDF/ALL)",
                        "risk": "read-only",
                    },
                    {
                        "name": "ds_get_resource_by_name",
                        "desc": "Find resource by path",
                        "risk": "read-only",
                    },
                    {
                        "name": "ds_view_resource",
                        "desc": "View file content (paginated)",
                        "risk": "read-only",
                    },
                    {
                        "name": "ds_download_resource",
                        "desc": "Download file (returns base64)",
                        "risk": "read-only",
                    },
                    {
                        "name": "ds_create_folder",
                        "desc": "Create folder",
                        "risk": "write",
                    },
                    {
                        "name": "ds_online_create_file",
                        "desc": "Create text file inline",
                        "risk": "write",
                    },
                    {
                        "name": "ds_upload_file",
                        "desc": "Upload file (supports binary)",
                        "risk": "write",
                    },
                    {
                        "name": "ds_update_resource_content",
                        "desc": "Update file content",
                        "risk": "write",
                    },
                    {
                        "name": "ds_rename_resource",
                        "desc": "Rename resource",
                        "risk": "⚠️ dangerous",
                    },
                    {
                        "name": "ds_delete_resource",
                        "desc": "Delete resource (supports recursive)",
                        "risk": "⚠️ dangerous",
                    },
                ],
                "workflow": (
                    "1. Query: ds_list_resources (default ALL) → ds_view_resource (view content)\n"
                    "2. Upload: ds_upload_file (binary) or ds_online_create_file (text)\n"
                    "3. Modify: ds_update_resource_content\n"
                    "4. Delete: ds_delete_resource (recursive=True for non-empty folders)"
                ),
            },
            "monitor": {
                "name": "Monitoring",
                "tools": [
                    {
                        "name": "ds_monitor_masters",
                        "desc": "Monitor Master nodes",
                        "risk": "read-only",
                    },
                    {
                        "name": "ds_monitor_workers",
                        "desc": "Monitor Worker nodes",
                        "risk": "read-only",
                    },
                ],
                "workflow": "Call periodically to check cluster health",
            },
            "user": {
                "name": "User/Tenant Management",
                "tools": [
                    {
                        "name": "ds_list_users",
                        "desc": "List users",
                        "risk": "read-only",
                    },
                    {
                        "name": "ds_list_tenants",
                        "desc": "List tenants",
                        "risk": "read-only",
                    },
                ],
                "workflow": "Query user and tenant information",
            },
            "raw": {
                "name": "Raw API (Fallback)",
                "tools": [
                    {"name": "ds_raw_get", "desc": "GET request", "risk": "read-only"},
                    {"name": "ds_raw_post", "desc": "POST request", "risk": "write"},
                    {"name": "ds_raw_put", "desc": "PUT request", "risk": "write"},
                    {
                        "name": "ds_raw_delete",
                        "desc": "DELETE request",
                        "risk": "⚠️ dangerous",
                    },
                    {
                        "name": "ds_test_connection",
                        "desc": "Test connection",
                        "risk": "read-only",
                    },
                ],
                "workflow": "Use raw API when wrapped tools don't meet requirements",
            },
            "quickstart": {
                "name": "Quickstart Guide",
                "tools": [],
                "workflow": (
                    "[Recommended Flow for New Users]\n\n"
                    "1️⃣ View projects and workflows\n"
                    "   ds_list_projects → ds_list_workflows\n\n"
                    "2️⃣ Create a simple SQL workflow\n"
                    "   ds_create_dag_workflow(\n"
                    "       project_name='xxx',\n"
                    "       name='test_workflow',\n"
                    "       tasks=[{'name':'task1', 'type':'SQL', 'datasource_id':1, 'sql':'SELECT 1'}],\n"
                    "       relations=[{'from':'', 'to':'task1'}]\n"
                    "   )\n\n"
                    "3️⃣ Configure schedule\n"
                    "   ds_set_schedule(workflow_code=xxx, cron='0 0 6 * * ? *')\n"
                    "   ds_online_schedule(schedule_id=xxx)\n\n"
                    "4️⃣ Check run status\n"
                    "   ds_list_process_instances(workflow_code=xxx)\n"
                    "   ds_get_latest_failure_log(workflow_code=xxx)  # if failed\n\n"
                    "5️⃣ Modify workflow (add DEPENDENT task)\n"
                    "   ds_modify_workflow_dag(\n"
                    "       workflow_code=xxx,\n"
                    "       operations=[{\n"
                    "           'action':'add_task',\n"
                    "           'task':{'name':'wait','type':'DEPENDENT',...},\n"
                    "           'connect_from':'', 'connect_to':'task1'\n"
                    "       }]\n"
                    "   )\n\n"
                    "[Common Scenarios]\n"
                    "- Troubleshooting: ds_get_latest_failure_log → ds_rerun_from_failure\n"
                    "- Backfill (full workflow, serial): ds_complement_data(start_date='2024-01-01', end_date='2024-01-31')\n"
                    "- Backfill (specific partition): ds_complement_data(partition_date='2024-01-01')  # recommended, clearer semantics\n"
                    "- Backfill (from node forward): ds_complement_data(start_task_names=['check'], task_depend_type='TASK_POST')\n"
                    "- Backfill (single task only): ds_complement_data(start_task_names=['sync'], task_depend_type='TASK_ONLY')\n"
                    "- Backfill (parallel mode): ds_complement_data(start_date='...', end_date='...', run_mode='RUN_MODE_PARALLEL')\n"
                    "- Create workflow with coordinates: ds_create_dag_workflow(tasks=[...], locations=[{'task_name':'t1','x':100,'y':100}])\n"
                    "- Create task with retry: ds_create_dag_workflow(tasks=[{...,'fail_retry_times':4,'fail_retry_interval':4}])\n"
                    "- Change cron: ds_update_schedule_cron(schedule_id=xxx, cron='0 0 8 * * ? *')\n"
                    "- Change node coordinates: ds_modify_workflow_dag(operations=[{'action':'update_location','task_name':'t','x':500,'y':300}])\n"
                    "- Release workflow (auto-reactivate schedule): ds_release_workflow(workflow_code=xxx, online=True)\n"
                    "- Manual trigger (from specific task): ds_run_workflow(workflow_code=xxx, start_task_names=['check'])\n"
                    "- View resources: ds_list_resources() → ds_view_resource(resource_id=xxx)\n\n"
                    "[Workflow Standards (Mandatory)]\n"
                    "1. SQL node naming: Pure SQL write tasks must have task name matching target table name\n"
                    "   Example: task writing to ads_settle_keyword_newuser_detail_mt must be named 'ads_settle_keyword_newuser_detail_mt'\n"
                    "2. Backfill minimization: Prefer start_task_names + task_depend_type='TASK_POST' to backfill from target node forward\n"
                    "   Don't backfill entire workflow unless full-chain rerun is explicitly needed\n"
                    "   Example: ds_complement_data(start_task_names=['ads_settle_keyword_newuser_detail_mt'], task_depend_type='TASK_POST')\n"
                    "3. Backfill default mode: run_mode='RUN_MODE_SERIAL' (default), runs one partition at a time, safer\n"
                    "   For parallel mode, explicitly specify: run_mode='RUN_MODE_PARALLEL'\n\n"
                    "[Retry Configuration Best Practices]\n"
                    "- Dependency check tasks: fail_retry_times=8, fail_retry_interval=1 (fast retry)\n"
                    "- Business compute tasks: fail_retry_times=4, fail_retry_interval=4 (avoid resource waste)\n\n"
                ),
            },
        }

        if not category:
            # Return overview of all categories
            return {
                "total_tools": 58,
                "categories": {
                    k: {
                        "name": v["name"],
                        "tool_count": len(v["tools"]),
                        "description": v["workflow"]
                        if k != "quickstart"
                        else "Quickstart guide",
                    }
                    for k, v in all_categories.items()
                },
                "hint": "Call ds_help(category='xxx') to view tools for a specific category",
                "recommended_categories": [
                    "quickstart",
                    "workflow",
                    "instance",
                    "schedule",
                ],
            }

        cat = category.lower()
        if cat not in all_categories:
            return {
                "error": f"Unknown category: {category}",
                "available_categories": list(all_categories.keys()),
            }

        info = all_categories[cat]
        return {
            "category": cat,
            "name": info["name"],
            "tools": info["tools"],
            "workflow": info["workflow"],
            "hint": "Judge tool safety by the 'risk' field: read-only (safe), write (confirm), ⚠️ dangerous (irreversible)",
        }
