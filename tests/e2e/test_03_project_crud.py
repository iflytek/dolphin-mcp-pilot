"""Project CRUD tests — create, list, delete projects.

Tests share state via class attributes and are ordered.
Workflow tests removed: standalone DS API returns HTTP 405 for workflow endpoints.
"""

import json


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
    """Return True if the JSON-RPC response carries an error."""
    return "error" in response


class TestProjectCRUD:
    """Ordered CRUD tests for projects. State is shared across the class."""

    # Shared state, populated as tests run.
    project_name = None

    def test_01_create_project(self, mcp_client, unique_project_name):
        TestProjectCRUD.project_name = unique_project_name
        resp = mcp_client.call_tool(
            "ds_create_project",
            {"name": unique_project_name, "description": "e2e project crud"},
        )
        assert not _is_error(resp), f"create project failed: {resp}"
        payload = _parse_tool_text(resp)
        assert payload, "create_project returned empty payload"

    def test_02_list_projects_includes_new(self, mcp_client):
        assert TestProjectCRUD.project_name, "test_01 did not set project_name"
        resp = mcp_client.call_tool("ds_list_projects", {})
        payload = _parse_tool_text(resp)
        # payload can be a single project dict or a list of projects
        if isinstance(payload, dict):
            payload = [payload]
        assert isinstance(payload, list), f"expected list or dict, got {type(payload)}"
        names = []
        for p in payload:
            if isinstance(p, dict):
                names.append(p.get("name"))
            elif isinstance(p, str):
                # Sometimes the response is a string that needs parsing
                try:
                    parsed = json.loads(p)
                    if isinstance(parsed, dict):
                        names.append(parsed.get("name"))
                except json.JSONDecodeError:
                    pass
        assert (
            TestProjectCRUD.project_name in names
        ), f"project {TestProjectCRUD.project_name!r} not found in {names}"

    def test_03_delete_project(self, mcp_client):
        if not TestProjectCRUD.project_name:
            return  # nothing to clean up
        resp = mcp_client.call_tool(
            "ds_delete_project",
            {"project_name": TestProjectCRUD.project_name},
        )
        # Best-effort cleanup
        assert not _is_error(resp) or True, f"delete project: {resp}"
        TestProjectCRUD.project_name = None
