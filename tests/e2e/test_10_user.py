"""Read-only user and tenant end-to-end coverage."""

from ._assertions import parse_successful_tool_items


def test_list_users_includes_authenticated_user(mcp_client, admin_credentials):
    response = mcp_client.call_tool("ds_list_users", {})

    items = parse_successful_tool_items(response)
    assert any(
        user.get("userName") == admin_credentials["user"] for user in items
    ), f"authenticated user missing from response: {items}"
    for user in items:
        assert {"id", "userName", "tenantId"} <= user.keys()


def test_list_tenants_returns_json_list(mcp_client):
    response = mcp_client.call_tool("ds_list_tenants", {})

    items = parse_successful_tool_items(response)
    assert items, "expected at least one DolphinScheduler tenant"
    for tenant in items:
        assert {"id", "tenantCode", "description"} <= tenant.keys()
