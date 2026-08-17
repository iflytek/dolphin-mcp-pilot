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

"""Raw API passthrough tools."""

import json

from mcp.server.mcpserver import MCPServer

from ..client import ds_get, ds_post, ds_put, ds_delete


def register_raw_tools(mcp: MCPServer):
    """Register raw API passthrough MCP tools."""

    @mcp.tool()
    def ds_raw_get(path: str) -> dict:
        """Pass GET through to DolphinScheduler API (path must start with /,
        excluding the /dolphinscheduler prefix).
        """
        return ds_get(path)

    @mcp.tool()
    def ds_raw_delete(path: str) -> dict:
        """Pass DELETE through to DolphinScheduler API."""
        return ds_delete(path)

    @mcp.tool()
    def ds_raw_post(
        path: str, form_data_json: str = "", json_body_json: str = ""
    ) -> dict:
        """Pass POST through to DolphinScheduler API.

        Args:
            path: API path (starting with /)
            form_data_json: form-urlencoded params as a JSON string (choose one)
            json_body_json: JSON body as a JSON string (choose one)
        """
        data = json.loads(form_data_json) if form_data_json else None
        body = json.loads(json_body_json) if json_body_json else None
        return ds_post(path, data=data, json_body=body)

    @mcp.tool()
    def ds_raw_put(
        path: str, form_data_json: str = "", json_body_json: str = ""
    ) -> dict:
        """Pass PUT through to DolphinScheduler API."""
        data = json.loads(form_data_json) if form_data_json else None
        body = json.loads(json_body_json) if json_body_json else None
        return ds_put(path, data=data, json_body=body)
