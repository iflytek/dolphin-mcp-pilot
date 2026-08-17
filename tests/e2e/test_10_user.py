"""Read-only user and tenant end-to-end coverage."""

from ._assertions import parse_successful_tool_text


def test_list_users_includes_authenticated_user(mcp_client, admin_credentials):
    response = mcp_client.call_tool("ds_list_users", {})

    payload = parse_successful_tool_text(response)
    assert isinstance(payload, list), f"expected user list, got: {payload}"
    assert any(
        user.get("userName") == admin_credentials["user"] for user in payload
    ), f"authenticated user missing from response: {payload}"
    for user in payload:
        assert {"id", "userName", "tenantId"} <= user.keys()


def test_list_tenants_returns_json_list(mcp_client):
    response = mcp_client.call_tool("ds_list_tenants", {})

    payload = parse_successful_tool_text(response)
    assert isinstance(payload, list), f"expected tenant list, got: {payload}"
    for tenant in payload:
        assert {"id", "tenantCode", "description"} <= tenant.keys()
