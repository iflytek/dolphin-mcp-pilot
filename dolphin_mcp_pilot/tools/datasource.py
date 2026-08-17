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

"""Data source management tools."""

from mcp.server.mcpserver import MCPServer

from ..client import ds_get
from ..utils import require_ok


def register_datasource_tools(mcp: MCPServer):
    """Register data source management MCP tools."""

    @mcp.tool()
    def ds_list_datasources(ds_type: str = "HIVE") -> list:
        """List data sources.

        Args:
            ds_type: HIVE / MYSQL / POSTGRESQL / SPARK / CLICKHOUSE etc.
        """
        result = ds_get(f"/datasources/list?type={ds_type}")
        require_ok(result, "list datasources")
        return [
            {"id": s["id"], "name": s["name"], "type": s.get("type", "")}
            for s in result.get("data", [])
        ]
