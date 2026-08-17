"""Read-only cluster monitoring end-to-end coverage."""

from ._assertions import parse_successful_tool_text


def test_monitor_masters_returns_json_list(mcp_client):
    response = mcp_client.call_tool("ds_monitor_masters", {})

    payload = parse_successful_tool_text(response)
    assert isinstance(payload, list), f"expected master list, got: {payload}"


def test_monitor_workers_returns_json_list(mcp_client):
    response = mcp_client.call_tool("ds_monitor_workers", {})

    payload = parse_successful_tool_text(response)
    assert isinstance(payload, list), f"expected worker list, got: {payload}"
