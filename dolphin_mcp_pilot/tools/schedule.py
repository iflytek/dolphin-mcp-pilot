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

"""Schedule management tools."""

import json
import time

from mcp.server.mcpserver import MCPServer

from ..client import ds_get, ds_post, ds_put, ds_delete
from ..utils import require_ok, resolve_project_code


def ds_put_lite(pcode: int, schedule_id: int, schedule_json: str) -> dict:
    """PUT /projects/{pcode}/schedules/{id} — used for cron-only updates."""
    return ds_put(
        f"/projects/{pcode}/schedules/{schedule_id}",
        data={
            "schedule": schedule_json,
            "warningType": "NONE",
            "warningGroupId": 0,
            "failureStrategy": "END",
            "workerGroup": "default",
            "processInstancePriority": "MEDIUM",
        },
    )


def register_schedule_tools(mcp: MCPServer):
    """Register schedule management MCP tools."""

    @mcp.tool()
    def ds_list_schedules(
        project_name: str,
        workflow_code: int = 0,
        simplify: bool = False,
        page_no: int = 1,
        page_size: int = 50,
    ) -> list | dict:
        """List schedule configurations (optionally filtered by workflow_code).

        v2.0.12: merged ds_list_schedules_in_project and ds_get_workflow_schedule.
        - workflow_code=0 (default): list all schedules in the project
        - workflow_code=<value>: list schedules for that specific workflow
        - simplify=True: return a summary dict with has_schedule/cron/release_state

        Args:
            project_name: Project name
            workflow_code: Process-definition code (0 = no filter)
            simplify: Return summary dict instead of raw list
            page_no: Page number
            page_size: Items per page
        """
        pcode = resolve_project_code(project_name)
        path = f"/projects/{pcode}/schedules?pageNo={page_no}&pageSize={page_size}"
        if workflow_code:
            path += f"&processDefinitionCode={workflow_code}"
        result = ds_get(path)
        require_ok(result, "list schedules")
        data = result.get("data", {})
        if isinstance(data, list):
            items = data
        elif isinstance(data, dict):
            items = data.get("totalList", []) or []
        else:
            items = []

        # Fallback filter in case DS ignores the query param
        if workflow_code:
            items = [
                s for s in items if s.get("processDefinitionCode") == workflow_code
            ]

        normalized = [
            {
                "id": s.get("id"),
                "processDefinitionCode": s.get("processDefinitionCode"),
                "crontab": s.get("crontab"),
                "releaseState": s.get("releaseState", "OFFLINE"),
                "startTime": s.get("startTime"),
                "endTime": s.get("endTime"),
            }
            for s in items
        ]

        if simplify:
            if not normalized:
                return {
                    "workflow_code": workflow_code or None,
                    "has_schedule": False,
                    "schedule_id": None,
                    "cron": None,
                    "release_state": None,
                    "schedules": [],
                    "hint": "No schedule found. Use ds_set_schedule to create one."
                    if workflow_code
                    else "No schedules in this project.",
                }
            top = normalized[0]
            return {
                "workflow_code": workflow_code or None,
                "has_schedule": True,
                "schedule_id": top.get("id"),
                "cron": top.get("crontab"),
                "release_state": top.get("releaseState"),
                "start_time": top.get("startTime"),
                "end_time": top.get("endTime"),
                "schedules": normalized,
            }

        return normalized

    @mcp.tool()
    def ds_set_schedule(
        project_name: str,
        workflow_code: int,
        cron: str,
        start_time: str = "",
        end_time: str = "",
    ) -> dict:
        """Create a schedule for a workflow (created OFFLINE; activate with ds_online_schedule).

        v2.0.12: cron is now required (no default) to prevent silent misuse.

        Args:
            project_name: Project name
            workflow_code: Process-definition code
            cron: Quartz 7-field expression (required, e.g. "0 0 6 * * ? *")
            start_time: Start time yyyy-MM-dd HH:mm:ss; defaults to today 00:00:00
            end_time: End time; defaults to 2030-12-31 23:59:59
        """
        if not cron or not cron.strip():
            raise ValueError(
                "cron is required. Provide a Quartz 7-field expression, e.g. '0 0 6 * * ? *'"
            )
        if not start_time:
            start_time = time.strftime("%Y-%m-%d 00:00:00")
        if not end_time:
            end_time = "2030-12-31 23:59:59"

        pcode = resolve_project_code(project_name)
        ds_post(
            f"/projects/{pcode}/process-definition/{workflow_code}/release",
            data={"releaseState": "ONLINE"},
        )
        schedule_json = json.dumps(
            {
                "startTime": start_time,
                "endTime": end_time,
                "crontab": cron,
                "timezoneId": "Asia/Shanghai",
            }
        )
        result = ds_post(
            f"/projects/{pcode}/schedules",
            data={
                "processDefinitionCode": workflow_code,
                "schedule": schedule_json,
                "failureStrategy": "END",
                "warningType": "NONE",
                "processInstancePriority": "MEDIUM",
                "workerGroup": "default",
            },
        )
        require_ok(result, "create schedule")
        sched_data = result.get("data")
        if isinstance(sched_data, dict):
            schedule_id = sched_data.get("id")
        else:
            schedule_id = None
        return {
            "schedule_id": schedule_id,
            "cron": cron,
            "releaseState": "OFFLINE",
            "hint": "Call ds_online_schedule to activate.",
        }

    @mcp.tool()
    def ds_online_schedule(project_name: str, schedule_id: int) -> dict:
        """Activate (bring online) a schedule."""
        pcode = resolve_project_code(project_name)
        result = ds_post(f"/projects/{pcode}/schedules/{schedule_id}/online")
        require_ok(result, "online schedule")
        return {"schedule_id": schedule_id, "status": "ONLINE"}

    @mcp.tool()
    def ds_offline_schedule(project_name: str, schedule_id: int) -> dict:
        """Deactivate (take offline) a schedule."""
        pcode = resolve_project_code(project_name)
        result = ds_post(f"/projects/{pcode}/schedules/{schedule_id}/offline")
        require_ok(result, "offline schedule")
        return {"schedule_id": schedule_id, "status": "OFFLINE"}

    @mcp.tool()
    def ds_delete_schedule(project_name: str, schedule_id: int) -> dict:
        """Delete a schedule (takes it offline first)."""
        pcode = resolve_project_code(project_name)
        try:
            ds_post(f"/projects/{pcode}/schedules/{schedule_id}/offline")
        except Exception:
            pass
        result = ds_delete(f"/projects/{pcode}/schedules/{schedule_id}")
        require_ok(result, "delete schedule")
        return {"schedule_id": schedule_id, "status": "deleted"}

    @mcp.tool()
    def ds_update_schedule_cron(
        project_name: str,
        schedule_id: int,
        cron: str,
        start_time: str = "",
        end_time: str = "",
        auto_online: bool = True,
    ) -> dict:
        """Update only the cron expression of a schedule (keeps all other settings).

        Flow: read current state → offline if needed → update → re-online (default).

        v2.0.10: queries the target schedule directly instead of scanning the full list.

        Args:
            project_name: Project name
            schedule_id: Schedule ID (from ds_list_schedules)
            cron: New Quartz 7-field expression
            start_time: New start time yyyy-MM-dd HH:mm:ss (keep original if empty)
            end_time: New end time (keep original if empty)
            auto_online: Re-activate after update (default True)

        Returns:
            {
                "schedule_id": int,
                "new_cron": str,
                "release_state": "ONLINE" | "OFFLINE",
                "status": "updated",
                "online_retry_detail": str
            }
        """
        pcode = resolve_project_code(project_name)

        # 1. Read current config
        current = ds_get(
            f"/projects/{pcode}/schedules?pageNo=1&pageSize=10"
            f"&processDefinitionCode=0"
        )
        sched = None
        data = current.get("data", {})
        items = (
            data.get("totalList", [])
            if isinstance(data, dict)
            else (data if isinstance(data, list) else [])
        )
        for s in items:
            if s.get("id") == schedule_id:
                sched = s
                break

        # Retry with a larger page if not found
        if not sched:
            current2 = ds_get(f"/projects/{pcode}/schedules?pageNo=1&pageSize=500")
            data2 = current2.get("data", {})
            items2 = (
                data2.get("totalList", [])
                if isinstance(data2, dict)
                else (data2 if isinstance(data2, list) else [])
            )
            for s in items2:
                if s.get("id") == schedule_id:
                    sched = s
                    break

        old_state = (sched or {}).get("releaseState", "OFFLINE")
        old_start = (sched or {}).get("startTime") or ""
        old_end = (sched or {}).get("endTime") or ""

        # 2. Take offline if currently active (DS requires OFFLINE to modify)
        if old_state == "ONLINE":
            try:
                ds_post(f"/projects/{pcode}/schedules/{schedule_id}/offline")
            except Exception:
                pass

        # 3. Build new schedule JSON
        final_start = start_time or old_start or time.strftime("%Y-%m-%d 00:00:00")
        final_end = end_time or old_end or "2030-12-31 23:59:59"
        schedule_json = json.dumps(
            {
                "startTime": final_start,
                "endTime": final_end,
                "crontab": cron,
                "timezoneId": "Asia/Shanghai",
            }
        )

        # 4. PUT update
        result = ds_put_lite(pcode, schedule_id, schedule_json)
        require_ok(result, "update schedule")

        # 5. Re-activate with retry (v2.0.10)
        final_state = "OFFLINE"
        online_detail = ""
        if auto_online and old_state == "ONLINE":
            for attempt in range(2):
                try:
                    rel = ds_post(f"/projects/{pcode}/schedules/{schedule_id}/online")
                    if rel.get("code") == 0:
                        final_state = "ONLINE"
                        online_detail = (
                            f"Re-activated successfully (attempt {attempt + 1})"
                        )
                        break
                    else:
                        online_detail = f"Online failed (code={rel.get('code')}): {rel.get('msg', 'unknown')}"
                        if attempt == 0:
                            time.sleep(1)
                except Exception as e:
                    online_detail = f"Online error (attempt {attempt + 1}): {str(e)}"
                    if attempt == 0:
                        time.sleep(1)
            else:
                online_detail += " — call ds_online_schedule manually"
        elif old_state != "ONLINE":
            online_detail = f"Previous state was {old_state}; not re-activating"
        else:
            online_detail = "auto_online=False; not re-activating"

        return {
            "schedule_id": schedule_id,
            "new_cron": cron,
            "start_time": final_start,
            "end_time": final_end,
            "release_state": final_state,
            "status": "updated",
            "online_retry_detail": online_detail,
        }
