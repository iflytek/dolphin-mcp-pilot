"""Smoke tests — verify the MCP server is alive and well-formed.

These tests do not mutate DolphinScheduler state and are safe to run
against any environment (including shared staging). They are the first
thing to run in CI to fail fast on deploy/regressions.
"""

import json


def _parse_tool_text(response):
    """Extract the JSON payload from an MCP tool-call response.

    Tool responses arrive as {"content": [{"type": "text", "text": "..."}]};
    the inner text is itself a JSON-encoded string.
    """
    return json.loads(response["result"]["content"][0]["text"])


class TestSmoke:
    """Basic health checks for the MCP server."""

    def test_tool_count_is_58(self, mcp_client):
        tools = mcp_client.tools_list()
        assert len(tools) == 58, f"expected 58 tools, got {len(tools)}"

    def test_all_tools_have_ds_prefix(self, mcp_client):
        tools = mcp_client.tools_list()
        bad = [t["name"] for t in tools if not t["name"].startswith("ds_")]
        assert not bad, f"tools without ds_ prefix: {bad}"

    def test_all_tools_have_description(self, mcp_client):
        tools = mcp_client.tools_list()
        missing = [t["name"] for t in tools if not t.get("description")]
        assert not missing, f"tools missing description: {missing}"

    def test_ds_help_returns_categories(self, mcp_client):
        resp = mcp_client.call_tool("ds_help", {})
        payload = _parse_tool_text(resp)
        assert (
            "categories" in payload or "help" in payload
        ), f"unexpected ds_help payload keys: {list(payload.keys())}"

    def test_ds_help_with_category(self, mcp_client):
        resp = mcp_client.call_tool("ds_help", {"category": "workflow"})
        payload = _parse_tool_text(resp)
        # The payload must contain some content (either tool list or guidance).
        assert payload, "ds_help with category returned empty payload"

    def test_ds_help_unknown_category(self, mcp_client):
        resp = mcp_client.call_tool("ds_help", {"category": "nonexistent_category"})
        payload = _parse_tool_text(resp)
        # Should not crash; returns an informative message.
        assert isinstance(payload, dict), "unknown category should still return a dict"

    def test_key_tools_exist(self, mcp_client):
        names = {t["name"] for t in mcp_client.tools_list()}
        expected = {
            "ds_help",
            "ds_test_connection",
            "ds_list_projects",
            "ds_create_project",
            "ds_delete_project",
            "ds_list_workflows",
            "ds_create_workflow",
            "ds_create_dag_workflow",
            "ds_release_workflow",
            "ds_run_workflow",
            "ds_delete_workflow",
            "ds_list_schedules",
            "ds_set_schedule",
            "ds_online_schedule",
            "ds_offline_schedule",
            "ds_delete_schedule",
            "ds_list_process_instances",
            "ds_pause_process_instance",
            "ds_resume_process_instance",
            "ds_stop_process_instance",
            "ds_rerun_process_instance",
        }
        missing = expected - names
        assert not missing, f"missing key tools: {sorted(missing)}"
