"""Offline regression tests for the case's evidence safety helpers."""

from __future__ import annotations

import unittest
from unittest.mock import Mock

import team_agent
import verify_isolation


class RedactionTests(unittest.TestCase):
    def test_nested_credentials_are_redacted(self) -> None:
        value = {
            "headers": {
                "X-DS-User": "alice",
                "X-DS-Password": "not-public",
                "Accept": "application/json",
            },
            "project": "finance-ready",
        }
        self.assertEqual(team_agent.redact(value)["headers"]["X-DS-User"], "<redacted>")
        self.assertEqual(
            team_agent.redact(value)["headers"]["X-DS-Password"], "<redacted>"
        )
        self.assertEqual(team_agent.redact(value)["project"], "finance-ready")

    def test_secret_scan_fails_closed(self) -> None:
        with self.assertRaises(ValueError):
            team_agent.assert_no_secret('{"value":"needle"}', ["needle"])

    def test_remote_mcp_host_is_hidden(self) -> None:
        public = team_agent.public_mcp_url("https://internal.example:8443/mcp/?debug=1")
        self.assertEqual(public, "https://<redacted-host>:8443/mcp/")

    def test_local_mcp_url_remains_reproducible(self) -> None:
        url = "http://127.0.0.1:23643/mcp/"
        self.assertEqual(team_agent.public_mcp_url(url), url)


class MCPContentTests(unittest.TestCase):
    def test_json_and_text_blocks_are_decoded(self) -> None:
        result = Mock(
            content=[
                Mock(type="text", text='{"status":"renamed"}'),
                Mock(type="text", text="plain error"),
                Mock(type="image", data="ignored"),
            ]
        )
        self.assertEqual(
            team_agent.decode_mcp_content(result),
            [{"status": "renamed"}, "plain error"],
        )


class ToolPolicyTests(unittest.TestCase):
    def test_rename_requires_successful_list(self) -> None:
        with self.assertRaises(RuntimeError):
            team_agent.validate_tool_request(
                "ds_rename_project",
                {"old_name": "old", "new_name": "new"},
                successful_list_seen=False,
            )

    def test_rename_after_list_is_allowed(self) -> None:
        arguments = {"old_name": "old", "new_name": "new"}
        self.assertIs(
            team_agent.validate_tool_request(
                "ds_rename_project",
                arguments,
                successful_list_seen=True,
            ),
            arguments,
        )

    def test_raw_api_tool_is_rejected(self) -> None:
        with self.assertRaises(RuntimeError):
            team_agent.validate_tool_request(
                "ds_raw_post",
                {"path": "/projects"},
                successful_list_seen=True,
            )


class IsolationEvaluationTests(unittest.TestCase):
    def test_expected_only_passes(self) -> None:
        self.assertTrue(
            verify_isolation.observation_ok(
                ["finance-ready"], "finance-ready", "marketing-ready"
            )
        )

    def test_forbidden_visibility_fails(self) -> None:
        self.assertFalse(
            verify_isolation.observation_ok(
                ["finance-ready", "marketing-ready"],
                "finance-ready",
                "marketing-ready",
            )
        )

    def test_missing_expected_project_fails(self) -> None:
        self.assertFalse(
            verify_isolation.observation_ok([], "finance-ready", "marketing-ready")
        )


if __name__ == "__main__":
    unittest.main()
