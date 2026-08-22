"""Read-only data source end-to-end coverage."""

from ._assertions import parse_successful_tool_items


def test_list_datasources_returns_json_list(mcp_client):
    response = mcp_client.call_tool("ds_list_datasources", {})

    items = parse_successful_tool_items(response)
    for datasource in items:
        assert {"id", "name", "type"} <= datasource.keys()
