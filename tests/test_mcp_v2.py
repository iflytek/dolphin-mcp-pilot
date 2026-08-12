#!/usr/bin/env python3
"""MCP 2.0 migration and compatibility tests."""

import asyncio

from mcp.client import Client

from dolphin_mcp_pilot import auth, config, mcp
from dolphin_mcp_pilot.__main__ import build_http_app


def test_http_app_uses_stateless_transport():
    app = build_http_app()

    assert app is not None
    assert mcp.session_manager.stateless is True


def test_server_supports_modern_and_legacy_clients():
    async def exercise(mode, expected_version):
        async with Client(mcp, mode=mode) as client:
            result = await client.list_tools()
            assert len(result.tools) == 58
            assert client.protocol_version == expected_version

    asyncio.run(exercise("auto", "2026-07-28"))
    asyncio.run(exercise("legacy", "2025-11-25"))


def test_request_credentials_do_not_leak_between_requests():
    with auth.request_credentials(token="request-token"):
        assert auth.get_current_token() == "request-token"

    fixture_credentials = ("alice", "fixture-value")
    with auth.request_credentials(
        user=fixture_credentials[0], password=fixture_credentials[1]
    ):
        assert auth.get_credentials() == fixture_credentials

    with auth.request_credentials():
        assert auth.get_current_token() == config.get_ds_token_env()
