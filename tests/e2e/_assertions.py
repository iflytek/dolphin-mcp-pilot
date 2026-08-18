"""Assertions shared by MCP end-to-end tool tests."""

import json


def parse_successful_tool_items(response):
    """Validate the MCP wire envelope and decode every text item."""
    assert response.get("jsonrpc") == "2.0", f"invalid JSON-RPC envelope: {response}"
    assert "error" not in response, f"tool call returned JSON-RPC error: {response}"

    result = response.get("result")
    assert isinstance(result, dict), f"tool result must be an object: {response}"
    assert (
        result.get("isError") is not True
    ), f"tool call returned MCP error: {response}"

    assert result.get("resultType") == "complete", f"incomplete tool result: {result}"
    content = result.get("content")
    assert isinstance(content, list), f"tool content must be a list: {response}"

    items = []
    for item in content:
        assert item.get("type") == "text", f"expected text content: {item}"
        item_text = item.get("text")
        assert isinstance(item_text, str), f"text content must be a string: {item}"
        try:
            items.append(json.loads(item_text))
        except json.JSONDecodeError as exc:
            raise AssertionError(f"tool text is not valid JSON: {item_text!r}") from exc
    return items
