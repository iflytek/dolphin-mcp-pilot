"""Assertions shared by MCP end-to-end tool tests."""

import json


def parse_successful_tool_text(response):
    """Validate the MCP wire envelope and decode its first text item."""
    assert response.get("jsonrpc") == "2.0", f"invalid JSON-RPC envelope: {response}"
    assert "error" not in response, f"tool call returned JSON-RPC error: {response}"

    result = response.get("result")
    assert isinstance(result, dict), f"tool result must be an object: {response}"
    assert (
        result.get("isError") is not True
    ), f"tool call returned MCP error: {response}"

    content = result.get("content")
    assert (
        isinstance(content, list) and content
    ), f"tool returned no content: {response}"
    first = content[0]
    assert first.get("type") == "text", f"expected text content: {first}"

    text = first.get("text")
    assert isinstance(text, str), f"text content must be a string: {first}"
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise AssertionError(f"tool text is not valid JSON: {text!r}") from exc
