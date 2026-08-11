"""Lightweight MCP-over-HTTP JSON-RPC client for e2e tests.

Uses only Python stdlib (urllib.request, json) so the e2e suite
has no extra runtime dependencies beyond pytest.
"""

import json
import urllib.request


class MCPClient:
    """Minimal MCP client for tests.

    Supports user/password or token auth and handles both JSON and SSE responses.
    """

    def __init__(self, base_url, user="", password="", token=""):
        self.base_url = base_url.rstrip("/") + "/mcp/"
        self.user = user
        self.password = password
        self.token = token
        self.session_id = None
        self._req_id = 0

    def _next_id(self):
        self._req_id += 1
        return self._req_id

    def _headers(self):
        h = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        if self.user and self.password:
            h["X-DS-User"] = self.user
            h["X-DS-Password"] = self.password
        if self.token:
            h["X-DS-Token"] = self.token
        if self.session_id:
            h["mcp-session-id"] = self.session_id
        return h

    def _call(self, payload):
        req = urllib.request.Request(
            self.base_url,
            data=json.dumps(payload).encode("utf-8"),
            headers=self._headers(),
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            sid = resp.headers.get("mcp-session-id") or resp.headers.get(
                "Mcp-Session-Id"
            )
            if sid:
                self.session_id = sid
            body = resp.read().decode("utf-8")
            ct = resp.headers.get("Content-Type") or ""
            if "text/event-stream" in ct:
                return self._parse_sse(body)
            return json.loads(body) if body else {}

    @staticmethod
    def _parse_sse(body):
        for line in body.strip().split("\n"):
            if line.startswith("data: "):
                return json.loads(line[6:])
        raise ValueError(f"No SSE data found in: {body[:200]}")

    def initialize(self):
        """Perform the MCP initialize handshake."""
        result = self._call(
            {
                "jsonrpc": "2.0",
                "id": self._next_id(),
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "e2e-test", "version": "1.0"},
                },
            }
        )
        # Send the notifications/initialized follow-up (no id, no response expected).
        self._call(
            {
                "jsonrpc": "2.0",
                "method": "notifications/initialized",
                "params": {},
            }
        )
        return result

    def tools_list(self):
        """Return the list of registered tools."""
        resp = self._call(
            {
                "jsonrpc": "2.0",
                "id": self._next_id(),
                "method": "tools/list",
                "params": {},
            }
        )
        return resp.get("result", {}).get("tools", [])

    def call_tool(self, name, arguments=None):
        """Call an MCP tool and return the raw JSON-RPC response."""
        return self._call(
            {
                "jsonrpc": "2.0",
                "id": self._next_id(),
                "method": "tools/call",
                "params": {"name": name, "arguments": arguments or {}},
            }
        )
