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

"""User and tenant management tools."""

from mcp.server.mcpserver import MCPServer

from ..client import ds_get
from ..utils import require_ok


def register_user_tools(mcp: MCPServer):
    """Register user and tenant management MCP tools."""

    @mcp.tool()
    def ds_list_users() -> list:
        """List all DS users, administrators included (debug user_id foreign keys)."""
        # /users/list returns general users only, so an admin-owned workflow's
        # user_id would be missing from the result; /users/list-all includes them.
        result = ds_get("/users/list-all")
        require_ok(result, "list users")
        return [
            {
                "id": u.get("id"),
                "userName": u.get("userName"),
                "tenantId": u.get("tenantId"),
            }
            for u in result.get("data", []) or []
        ]

    @mcp.tool()
    def ds_list_tenants() -> list:
        """List all tenants (useful for debugging workflow tenant_id foreign key issues)."""
        result = ds_get("/tenants/list")
        require_ok(result, "list tenants")
        return [
            {
                "id": t.get("id"),
                "tenantCode": t.get("tenantCode"),
                "description": t.get("description", ""),
            }
            for t in result.get("data", []) or []
        ]
