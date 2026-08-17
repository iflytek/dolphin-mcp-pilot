"""Synchronous test facade over the official MCP 2.0 client."""

import asyncio

import httpx2
from mcp.client import Client
from mcp.client.streamable_http import streamable_http_client


class MCPClient:
    """Minimal synchronous facade for the stateless MCP E2E tests."""

    def __init__(self, base_url, user="", password="", token=""):
        self.base_url = base_url.rstrip("/") + "/mcp/"
        self.user = user
        self.password = password
        self.token = token
        self.protocol_version = None

    def _headers(self):
        headers = {}
        if self.user and self.password:
            headers["X-DS-User"] = self.user
            headers["X-DS-Password"] = self.password
        if self.token:
            headers["X-DS-Token"] = self.token
        return headers

    async def _run(self, operation):
        async with httpx2.AsyncClient(headers=self._headers()) as http_client:
            transport = streamable_http_client(
                self.base_url,
                http_client=http_client,
            )
            async with Client(transport, read_timeout_seconds=30) as client:
                self.protocol_version = client.protocol_version
                return await operation(client)

    def initialize(self):
        """Verify that the official client can negotiate with the server."""

        async def negotiated_protocol(client):
            return {
                "jsonrpc": "2.0",
                "result": {"protocolVersion": client.protocol_version},
            }

        return asyncio.run(self._run(negotiated_protocol))

    def tools_list(self):
        """Return registered tools using their JSON wire representation."""

        async def list_tools(client):
            result = await client.list_tools()
            return [
                tool.model_dump(mode="json", by_alias=True) for tool in result.tools
            ]

        return asyncio.run(self._run(list_tools))

    def call_tool(self, name, arguments=None):
        """Call a tool and preserve the legacy JSON-RPC-shaped test result."""

        async def call(client):
            result = await client.call_tool(name, arguments or {})
            return {
                "jsonrpc": "2.0",
                "result": result.model_dump(mode="json", by_alias=True),
            }

        return asyncio.run(self._run(call))
