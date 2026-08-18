"""Read-only cluster monitoring end-to-end coverage."""

from ._assertions import parse_successful_tool_items


def test_monitor_masters_returns_json_list(mcp_client):
    response = mcp_client.call_tool("ds_monitor_masters", {})

    items = parse_successful_tool_items(response)
    assert items, "expected at least one DolphinScheduler master"


def test_monitor_workers_returns_json_list(mcp_client):
    response = mcp_client.call_tool("ds_monitor_workers", {})

    items = parse_successful_tool_items(response)
    assert items, "expected at least one DolphinScheduler worker"
