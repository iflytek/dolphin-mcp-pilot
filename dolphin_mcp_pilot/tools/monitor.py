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

"""Monitoring tools."""

from mcp.server.mcpserver import MCPServer

from ..client import ds_get
from ..utils import require_ok


def register_monitor_tools(mcp: MCPServer):
    """Register monitoring MCP tools."""

    @mcp.tool()
    def ds_monitor_masters() -> list:
        """Check DS master node status (verify scheduler is alive)."""
        result = ds_get("/monitor/MASTER")
        require_ok(result, "get master status")
        return result.get("data", []) or []

    @mcp.tool()
    def ds_monitor_workers() -> list:
        """Check DS worker node status (verify task executors are alive)."""
        result = ds_get("/monitor/WORKER")
        require_ok(result, "get worker status")
        return result.get("data", []) or []
