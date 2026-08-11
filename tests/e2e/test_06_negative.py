"""Negative tests — verify the server handles bad inputs gracefully.

None of these tests should crash the MCP server or leave it in a state
where subsequent well-formed requests fail.
"""

import json
import urllib.request

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


def _is_error(response):
    """Return True if the JSON-RPC response carries an error or isError flag."""
    if "error" in response:
        return True
    # Check for MCP isError flag at result level
    result = response.get("result", {})
    if result.get("isError"):
        return True
    return False


class TestNegative:
    """Malformed inputs and bad auth — server must stay healthy."""

    def test_bad_password_returns_error(self, pilot_url):
        client = MCPClient(pilot_url, user="admin", password="wrong-password-e2e")
        client.initialize()
        resp = client.call_tool("ds_list_projects", {})
        # The server should return a JSON-RPC error or an error payload.
        # It must not return a normal list.
        if _is_error(resp):
            return  # expected
        content = resp.get("result", {}).get("content", [])
        if not content:
            return  # empty content is also acceptable for bad auth
        payload_text = content[0].get("text", "")
        try:
            payload = json.loads(payload_text)
        except Exception:  # noqa: BLE001
            # Not JSON — still, if we got a response the server survived.
            return
        # If it parsed, it should not be a normal projects list.
        assert (
            not isinstance(payload, list) or len(payload) == 0
        ), "bad password unexpectedly succeeded in listing projects"

    def test_server_alive_after_bad_auth(self, pilot_url):
        # First make a bad-auth request.
        bad = MCPClient(pilot_url, user="admin", password="bogus-password-e2e")
        try:
            bad.initialize()
            bad.call_tool("ds_list_projects", {})
        except Exception:  # noqa: BLE001
            pass

        # Now verify a well-formed admin request still works.
        good = MCPClient(pilot_url, user="admin", password="dolphinscheduler123")
        good.initialize()
        resp = good.call_tool("ds_help", {})
        assert not _is_error(resp), f"server unhealthy after bad auth: {resp}"
        payload = _parse_tool_text(resp)
        assert payload, "ds_help returned empty payload after bad-auth attempt"

    def test_unknown_tool_returns_error(self, mcp_client):
        resp = mcp_client.call_tool("ds_nonexistent_tool_xyz", {})
        # Unknown tool should return an error (either JSON-RPC error or isError flag)
        assert _is_error(resp), f"unknown tool should return an error, got: {resp}"

    def test_malformed_json_does_not_crash(self, pilot_url):
        """Send malformed JSON directly; the server must not crash."""
        req = urllib.request.Request(
            pilot_url.rstrip("/") + "/mcp/",
            data=b"{this is not json",
            headers={
                "Content-Type": "application/json",
                "X-DS-User": "admin",
                "X-DS-Password": "dolphinscheduler123",
            },
            method="POST",
        )
        # We don't care what the server returns — it may be 400, 500, or
        # even a JSON-RPC parse error (all acceptable). What matters is
        # the server still answers subsequent well-formed requests.
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                resp.read()
        except urllib.error.HTTPError:
            pass  # expected for malformed input
        except urllib.error.URLError as exc:
            # Connection reset or refused means the server crashed — fail.
            raise AssertionError(
                f"server appears to have crashed after malformed JSON: {exc}"
            ) from exc

        # Verify server is still healthy.
        healthy = MCPClient(pilot_url, user="admin", password="dolphinscheduler123")
        healthy.initialize()
        resp = healthy.call_tool("ds_help", {})
        assert not _is_error(resp), f"server unhealthy after malformed JSON: {resp}"
