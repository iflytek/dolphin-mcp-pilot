"""Unit coverage for read-only tool endpoint contracts."""

import asyncio
import json
from unittest.mock import patch

from mcp.client import Client

from dolphin_mcp_pilot import mcp


async def _call_tool(name):
    async with Client(mcp) as client:
        return await client.call_tool(name, {})


def _decoded_text_items(result):
    assert result.is_error is False
    return [json.loads(item.text) for item in result.content if item.type == "text"]


@patch("dolphin_mcp_pilot.tools.monitor.ds_get")
def test_monitor_tools_use_registry_enum_paths(mock_ds_get):
    mock_ds_get.return_value = {"code": 0, "data": [{"host": "127.0.0.1"}]}

    masters = _decoded_text_items(asyncio.run(_call_tool("ds_monitor_masters")))
    workers = _decoded_text_items(asyncio.run(_call_tool("ds_monitor_workers")))

    assert masters == [{"host": "127.0.0.1"}]
    assert workers == [{"host": "127.0.0.1"}]
    assert mock_ds_get.call_args_list[0].args == ("/monitor/MASTER",)
    assert mock_ds_get.call_args_list[1].args == ("/monitor/WORKER",)


@patch("dolphin_mcp_pilot.tools.user.ds_get")
def test_list_users_includes_administrators(mock_ds_get):
    mock_ds_get.return_value = {
        "code": 0,
        "data": [{"id": 1, "userName": "admin", "tenantId": -1}],
    }

    users = _decoded_text_items(asyncio.run(_call_tool("ds_list_users")))

    assert users == [{"id": 1, "userName": "admin", "tenantId": -1}]
    mock_ds_get.assert_called_once_with("/users/list-all")
