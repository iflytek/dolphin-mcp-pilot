"""Read-only data source end-to-end coverage."""

from ._assertions import parse_successful_tool_text


def test_list_datasources_returns_json_list(mcp_client):
    response = mcp_client.call_tool("ds_list_datasources", {})

    payload = parse_successful_tool_text(response)
    assert isinstance(payload, list), f"expected data source list, got: {payload}"
    for datasource in payload:
        assert {"id", "name", "type"} <= datasource.keys()
