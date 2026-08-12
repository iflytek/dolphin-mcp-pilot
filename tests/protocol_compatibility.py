#!/usr/bin/env python3
"""Smoke-test a running MCP 2.0 server with the installed MCP client version."""

import asyncio
import importlib.metadata
import os

SERVER_URL = os.environ.get("MCP_TEST_URL", "http://127.0.0.1:18001/mcp/")
CLIENT_VERSION = importlib.metadata.version("mcp")


async def exercise_v1() -> None:
    from mcp.client.session import ClientSession
    from mcp.client.streamable_http import streamable_http_client

    async with (
        streamable_http_client(SERVER_URL) as (read, write, _),
        ClientSession(read, write) as session,
    ):
        await session.initialize()
        result = await session.list_tools()
        assert len(result.tools) == 58


async def exercise_v2() -> None:
    from mcp.client import Client

    async with Client(SERVER_URL) as client:
        result = await client.list_tools()
        assert len(result.tools) == 58
        assert client.protocol_version == "2026-07-28"


async def main() -> None:
    major = int(CLIENT_VERSION.split(".", 1)[0])
    if major == 1:
        await exercise_v1()
    elif major == 2:
        await exercise_v2()
    else:
        raise AssertionError(f"Unsupported MCP client version: {CLIENT_VERSION}")
    print(f"MCP client {CLIENT_VERSION} compatibility check passed")


if __name__ == "__main__":
    asyncio.run(main())
