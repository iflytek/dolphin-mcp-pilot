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

"""Project management tools."""

from mcp.server.mcpserver import MCPServer

from ..client import ds_get, ds_post, ds_delete, ds_api_request
from ..utils import require_ok, resolve_project_code
from ..auth import login
from ..config import get_ds_url


def register_project_tools(mcp: MCPServer):
    """Register project management MCP tools."""

    @mcp.tool()
    def ds_test_connection() -> dict:
        """Test DolphinScheduler login and connectivity."""
        login()
        return {"status": "ok", "ds_url": get_ds_url()}

    @mcp.tool()
    def ds_list_projects() -> list:
        """List all projects. Returns [{id, code, name, description}]."""
        result = ds_get("/projects?pageNo=1&pageSize=500")
        require_ok(result, "list projects")
        items = result.get("data", {}).get("totalList", [])
        return [
            {
                "id": p["id"],
                "code": p["code"],
                "name": p["name"],
                "description": p.get("description", ""),
            }
            for p in items
        ]

    @mcp.tool()
    def ds_create_project(name: str, description: str = "") -> dict:
        """Create a new project.

        Args:
            name: Project name
            description: Optional description
        """
        result = ds_post(
            "/projects", data={"projectName": name, "description": description}
        )
        require_ok(result, "create project")
        data = result.get("data", {})
        return {
            "id": data.get("id"),
            "code": data.get("code"),
            "name": data.get("name", name),
        }

    @mcp.tool()
    def ds_rename_project(old_name: str, new_name: str, description: str = "") -> dict:
        """Rename a project.

        Args:
            old_name: Current project name
            new_name: New project name
            description: Optional new description; keeps the existing one if omitted
        """
        # Locate the existing project
        result = ds_get("/projects?pageNo=1&pageSize=200")
        require_ok(result, "list projects")
        items = result.get("data", {}).get("totalList", []) or []

        target = None
        for p in items:
            if p.get("name") == old_name:
                target = p
                break

        if not target:
            raise ValueError(f"Project '{old_name}' not found")

        pcode = target.get("code")
        desc = description if description else target.get("description", "")

        # PUT to rename (DolphinScheduler requires the userName field)
        update_result = ds_api_request(
            "PUT",
            f"/projects/{pcode}",
            data={
                "projectName": new_name,
                "description": desc,
                "userName": target.get("userName", ""),
            },
        )
        require_ok(update_result, "rename project")
        return {
            "old_name": old_name,
            "new_name": new_name,
            "code": pcode,
            "status": "renamed",
        }

    @mcp.tool()
    def ds_delete_project(project_name: str) -> dict:
        """Delete an entire project, cascading to all workflows, schedules and
        instances. This is irreversible - use with caution.
        """
        pcode = resolve_project_code(project_name)
        result = ds_delete(f"/projects/{pcode}")
        require_ok(result, "delete project")
        return {"project": project_name, "status": "deleted"}
