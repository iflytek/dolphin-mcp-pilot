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

import urllib.error

from mcp.server.mcpserver import MCPServer

from ..client import ds_get
from ..utils import require_ok


def _list_servers(node_type: str) -> list:
    """List registry nodes of one type, across DolphinScheduler lines.

    DS >= 3.2.2 serves ``/monitor/{RegistryNodeType}`` (``MASTER`` / ``WORKER``);
    3.2.1 and older only expose ``/monitor/masters`` and ``/monitor/workers``.
    Try the current path first and fall back when the server does not know it.
    """
    try:
        result = ds_get(f"/monitor/{node_type}")
    except urllib.error.HTTPError:
        result = ds_get(f"/monitor/{node_type.lower()}s")
    require_ok(result, f"get {node_type.lower()} status")
    return result.get("data", []) or []


def register_monitor_tools(mcp: MCPServer):
    """Register monitoring MCP tools."""

    @mcp.tool()
    def ds_monitor_masters() -> list:
        """Check DS master node status (verify scheduler is alive)."""
        return _list_servers("MASTER")

    @mcp.tool()
    def ds_monitor_workers() -> list:
        """Check DS worker node status (verify task executors are alive)."""
        return _list_servers("WORKER")
