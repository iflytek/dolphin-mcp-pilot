"""Authentication and request-isolation E2E tests."""

import json

from .mcp_client import MCPClient


def _parse_tool_text(response):
    """Parse text content from a tool response."""
    result = response.get("result", {})
    content = result.get("content", [])
    if not content:
        return []
    items = []
    for item in content:
        if item.get("type") == "text":
            try:
                items.append(json.loads(item["text"]))
            except json.JSONDecodeError:
                items.append(item["text"])
    return items[0] if len(items) == 1 else items


class TestAuthUserPassword:
    """User/password authentication."""

    def test_admin_can_list_projects(self, mcp_client):
        resp = mcp_client.call_tool("ds_list_projects", {})
        payload = _parse_tool_text(resp)
        assert isinstance(payload, list), (
            f"expected list, got {type(payload)}: {payload}"
        )

    def test_ds_test_connection_succeeds(self, mcp_client):
        resp = mcp_client.call_tool("ds_test_connection", {})
        payload = _parse_tool_text(resp)
        assert payload.get("status") == "ok" or payload.get("ok") is True, (
            f"ds_test_connection returned unexpected payload: {payload}"
        )


class TestAuthTokenMode:
    """Token requests must not leave the stateless server unhealthy."""

    def test_token_header_does_not_crash(self, pilot_url):
        client = MCPClient(pilot_url, token="dummy-token-for-e2e")
        try:
            client.initialize()
            resp = client.call_tool("ds_help", {})
            assert resp is not None
        except Exception as exc:  # noqa: BLE001
            healthy = MCPClient(
                pilot_url,
                user="admin",
                password="dolphinscheduler123",
            )
            healthy.initialize()
            health_resp = healthy.call_tool("ds_help", {})
            assert health_resp is not None, (
                f"server unhealthy after token attempt: {exc}"
            )


class TestMultiTenant:
    """Request-scoped credentials must remain usable across independent clients."""

    def test_two_clients_keep_independent_request_context(self, pilot_url):
        alice = MCPClient(pilot_url, user="admin", password="dolphinscheduler123")
        bob = MCPClient(pilot_url, user="admin", password="dolphinscheduler123")

        alice_protocol = alice.initialize()["result"]["protocolVersion"]
        bob_protocol = bob.initialize()["result"]["protocolVersion"]
        assert alice_protocol
        assert alice_protocol == bob_protocol

        a_payload = _parse_tool_text(alice.call_tool("ds_list_projects", {}))
        b_payload = _parse_tool_text(bob.call_tool("ds_list_projects", {}))
        assert isinstance(a_payload, list)
        assert isinstance(b_payload, list)
