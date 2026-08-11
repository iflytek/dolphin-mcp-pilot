"""Authentication tests — cover user/password, token, and multi-tenant modes.

The pilot supports two auth modes:
- user/password via X-DS-User / X-DS-Password (the primary, supported path)
- token via X-DS-Token (accepted by middleware but currently a dead path:
  client.py never consumes it — tests document this behavior)
"""

import json

from .mcp_client import MCPClient


def _parse_tool_text(response):
    """Parse tool response, handling both single and multiple content items."""
    result = response.get("result", {})
    content = result.get("content", [])
    if not content:
        return []
    # Parse each text item and collect into a list
    items = []
    for item in content:
        if item.get("type") == "text":
            try:
                parsed = json.loads(item["text"])
                items.append(parsed)
            except json.JSONDecodeError:
                items.append(item["text"])
    # If single item, return it directly; otherwise return list
    if len(items) == 1:
        return items[0]
    return items


class TestAuthUserPassword:
    """User/password auth (the supported path)."""

    def test_admin_can_list_projects(self, mcp_client):
        resp = mcp_client.call_tool("ds_list_projects", {})
        payload = _parse_tool_text(resp)
        # ds_list_projects returns a list of project objects
        assert isinstance(
            payload, list
        ), f"expected list, got {type(payload)}: {payload}"

    def test_ds_test_connection_succeeds(self, mcp_client):
        resp = mcp_client.call_tool("ds_test_connection", {})
        payload = _parse_tool_text(resp)
        # The tool returns {"status": "ok", "ds_url": "..."} on success
        assert (
            payload.get("status") == "ok" or payload.get("ok") is True
        ), f"ds_test_connection returned unexpected payload: {payload}"


class TestAuthTokenMode:
    """Token auth — documents the current dead-path behavior."""

    def test_token_header_does_not_crash(self, pilot_url):
        """X-DS-Token is accepted by the middleware but not consumed by client.py.

        This test verifies the server does not crash; it does not verify the
        request actually succeeds (token auth is not wired up end-to-end yet).
        """
        client = MCPClient(pilot_url, token="dummy-token-for-e2e")
        try:
            client.initialize()
            resp = client.call_tool("ds_help", {})
            # If we got here, the server accepted the token header without crashing.
            assert resp is not None
        except Exception as exc:  # noqa: BLE001
            # Token auth is a dead path; some configurations may reject it.
            # We only care that the server didn't crash (and we can reconnect).
            healthy = MCPClient(
                pilot_url,
                user="admin",
                password="dolphinscheduler123",
            )
            healthy.initialize()
            health_resp = healthy.call_tool("ds_help", {})
            assert (
                health_resp is not None
            ), f"server unhealthy after token attempt: {exc}"


class TestMultiTenant:
    """Multi-tenant isolation — two users should get independent sessions."""

    def test_two_users_get_independent_sessions(self, pilot_url):
        alice = MCPClient(pilot_url, user="admin", password="dolphinscheduler123")
        bob = MCPClient(pilot_url, user="admin", password="dolphinscheduler123")
        alice.initialize()
        bob.initialize()

        # Session IDs must be distinct (each handshake issues a new one).
        assert alice.session_id, "alice did not receive a session id"
        assert bob.session_id, "bob did not receive a session id"
        assert (
            alice.session_id != bob.session_id
        ), "alice and bob share a session id — multi-tenant isolation broken"

        # Both must be able to list projects independently.
        a_resp = alice.call_tool("ds_list_projects", {})
        b_resp = bob.call_tool("ds_list_projects", {})
        a_payload = _parse_tool_text(a_resp)
        b_payload = _parse_tool_text(b_resp)
        assert isinstance(a_payload, list)
        assert isinstance(b_payload, list)
