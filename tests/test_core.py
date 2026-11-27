#!/usr/bin/env python3
"""dolphin-mcp-pilot core unit tests.

These tests cover pure logic that does not require a live
DolphinScheduler instance: helpers, credential resolution,
session caching, and tool registration integrity.
"""

import asyncio
import importlib
import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dolphin_mcp_pilot import auth, config, utils


class TestConfig(unittest.TestCase):
    """Configuration module."""

    def test_get_ds_url_strips_trailing_slash(self):
        with patch.object(
            config, "DS_API_BASE", "http://ds.example.com:12345/dolphinscheduler/"
        ):
            self.assertEqual(
                config.get_ds_url(),
                "http://ds.example.com:12345/dolphinscheduler",
            )

    def test_get_ds_url_raises_when_unset(self):
        with patch.object(config, "DS_API_BASE", ""):
            with self.assertRaises(ValueError) as ctx:
                config.get_ds_url()
            self.assertIn("DS_URL", str(ctx.exception))

    def test_get_ds_credentials(self):
        with patch.object(config, "DS_USER", "admin"), patch.object(
            config, "DS_PASSWORD", "secret"
        ):
            self.assertEqual(config.get_ds_credentials(), ("admin", "secret"))

    def test_get_ds_credentials_raises_when_incomplete(self):
        with patch.object(config, "DS_USER", "admin"), patch.object(
            config, "DS_PASSWORD", ""
        ):
            with self.assertRaises(ValueError):
                config.get_ds_credentials()

    def test_tenant_code_defaults_to_default(self):
        reloaded = importlib.reload(config)
        self.assertTrue(reloaded.get_tenant_code())


class TestUtils(unittest.TestCase):
    """Helper functions."""

    def test_require_ok_passes_on_success(self):
        utils.require_ok({"code": 0, "data": {"id": 1}}, "list projects")

    def test_require_ok_raises_with_action_and_message(self):
        with self.assertRaises(RuntimeError) as ctx:
            utils.require_ok(
                {"code": 10001, "msg": "Project not found"}, "query project"
            )
        message = str(ctx.exception)
        self.assertIn("query project", message)
        self.assertIn("Project not found", message)

    @patch("dolphin_mcp_pilot.utils.ds_get")
    def test_resolve_project_code_returns_matching_code(self, mock_ds_get):
        mock_ds_get.return_value = {
            "code": 0,
            "data": [
                {"code": 111, "name": "other_project"},
                {"code": 987654321, "name": "target_project"},
            ],
        }
        self.assertEqual(utils.resolve_project_code("target_project"), 987654321)
        mock_ds_get.assert_called_once_with("/projects/list", timeout=None)

    @patch("dolphin_mcp_pilot.utils.ds_get")
    def test_resolve_project_code_raises_when_absent(self, mock_ds_get):
        mock_ds_get.return_value = {"code": 0, "data": []}
        with self.assertRaises(ValueError) as ctx:
            utils.resolve_project_code("missing_project")
        self.assertIn("missing_project", str(ctx.exception))


class TestAuth(unittest.TestCase):
    """Credential context and session cache."""

    def setUp(self):
        auth.clear_cache()

    def test_current_credentials_take_precedence(self):
        auth.set_current_credentials("ctx_user", "ctx_pass")
        self.assertEqual(auth.get_credentials(), ("ctx_user", "ctx_pass"))

    def test_credentials_fall_back_to_environment(self):
        def read_without_context():
            with patch.object(config, "DS_USER", "env_user"), patch.object(
                config, "DS_PASSWORD", "env_pass"
            ):
                return auth.get_credentials()

        # Run in a fresh context so contextvars are unset.
        result = asyncio.run(asyncio.to_thread(read_without_context))
        self.assertEqual(result, ("env_user", "env_pass"))

    def test_clear_cache_removes_single_user(self):
        auth._session_cache["alice"] = ("sid-a", 1_000_000_000)
        auth._session_cache["bob"] = ("sid-b", 1_000_000_000)
        auth.clear_cache("alice")
        self.assertNotIn("alice", auth._session_cache)
        self.assertIn("bob", auth._session_cache)

    def test_clear_cache_removes_all_users(self):
        auth._session_cache["alice"] = ("sid-a", 1_000_000_000)
        auth.clear_cache()
        self.assertEqual(auth._session_cache, {})

    def test_session_timeout_is_positive(self):
        self.assertGreater(auth.SESSION_TIMEOUT, 0)


class TestToolRegistration(unittest.TestCase):
    """Tool registry integrity."""

    EXPECTED_TOOL_COUNT = 59

    @classmethod
    def setUpClass(cls):
        from dolphin_mcp_pilot import mcp

        cls.tools = asyncio.run(mcp.list_tools())
        cls.names = {tool.name for tool in cls.tools}

    def test_expected_tool_count(self):
        self.assertEqual(len(self.tools), self.EXPECTED_TOOL_COUNT)

    def test_all_tools_use_ds_prefix(self):
        offenders = [name for name in self.names if not name.startswith("ds_")]
        self.assertEqual(offenders, [])

    def test_core_tools_registered(self):
        for name in (
            "ds_test_connection",
            "ds_list_projects",
            "ds_list_workflows",
            "ds_list_process_instances",
            "ds_complement_data",
            "ds_update_task_param",
            "ds_patch_task_content",
            "ds_help",
        ):
            self.assertIn(name, self.names)

    def test_every_tool_has_description(self):
        undocumented = [
            tool.name for tool in self.tools if not (tool.description or "").strip()
        ]
        self.assertEqual(undocumented, [])

    def test_tool_names_are_unique(self):
        self.assertEqual(len(self.names), len(self.tools))


if __name__ == "__main__":
    unittest.main(verbosity=2)
