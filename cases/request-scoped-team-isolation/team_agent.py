#!/usr/bin/env python3
"""Run a deliberately small, auditable agent against two safe project tools.

Credentials are read from the environment and used only as local MCP request
headers. They are never included in model messages or public evidence.
"""

from __future__ import annotations

import argparse
import asyncio
from datetime import UTC, datetime
import json
import os
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from openai import AsyncOpenAI


ALLOWED_TOOLS = frozenset({"ds_list_projects", "ds_rename_project"})
SENSITIVE_KEY_PARTS = (
    "api_key",
    "apikey",
    "authorization",
    "cookie",
    "password",
    "secret",
    "token",
    "x-ds-",
)


def redact(value: Any) -> Any:
    """Redact values nested below credential-like keys."""

    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            lowered = str(key).casefold()
            if any(part in lowered for part in SENSITIVE_KEY_PARTS):
                redacted[str(key)] = "<redacted>"
            else:
                redacted[str(key)] = redact(item)
        return redacted
    if isinstance(value, list):
        return [redact(item) for item in value]
    return value


def public_mcp_url(url: str) -> str:
    """Keep localhost URLs reproducible and hide any non-local host."""

    parsed = urlsplit(url)
    if parsed.hostname in {"127.0.0.1", "localhost", "::1"}:
        return url
    port = f":{parsed.port}" if parsed.port else ""
    return urlunsplit((parsed.scheme, f"<redacted-host>{port}", parsed.path, "", ""))


def assert_no_secret(serialized: str, secrets: list[str]) -> None:
    """Fail closed if a configured secret appears in an evidence document."""

    leaked = [
        index for index, secret in enumerate(secrets) if secret and secret in serialized
    ]
    if leaked:
        raise ValueError(
            f"refusing to write evidence containing {len(leaked)} secret value(s)"
        )


def decode_mcp_content(result: Any) -> list[Any]:
    """Decode MCP text blocks while preserving non-JSON text."""

    decoded: list[Any] = []
    for block in result.content:
        if getattr(block, "type", "") != "text":
            continue
        text = block.text
        try:
            decoded.append(json.loads(text))
        except json.JSONDecodeError:
            decoded.append(text)
    return decoded


def openai_tool(tool: Any) -> dict[str, Any]:
    """Convert an official MCP tool definition to OpenAI function format."""

    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description or "",
            "parameters": tool.inputSchema,
        },
    }


def validate_tool_request(
    name: str,
    arguments: Any,
    *,
    successful_list_seen: bool,
) -> dict[str, Any]:
    """Enforce the case's tool and read-before-write policy."""

    if name not in ALLOWED_TOOLS:
        raise RuntimeError(f"model requested disallowed tool: {name}")
    if not isinstance(arguments, dict):
        raise RuntimeError(f"tool arguments for {name} must be an object")
    if name == "ds_rename_project" and not successful_list_seen:
        raise RuntimeError("refusing to rename before a successful project-list check")
    return arguments


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--role", required=True, choices=("finops", "marketing"))
    parser.add_argument("--prompt", required=True)
    parser.add_argument(
        "--mcp-url",
        default=os.environ.get("MCP_URL", "http://127.0.0.1:23643/mcp/"),
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-rounds", type=int, default=6)
    return parser.parse_args()


def required_env(name: str) -> str:
    value = os.environ.get(name, "")
    if not value:
        raise ValueError(f"missing required environment variable: {name}")
    return value


async def run_agent(args: argparse.Namespace) -> dict[str, Any]:
    ds_user = required_env("DS_USER")
    ds_password = required_env("DS_PASSWORD")
    api_key = required_env("OPENAI_API_KEY")
    base_url = required_env("OPENAI_BASE_URL")
    model = required_env("OPENAI_MODEL")

    headers = {"X-DS-User": ds_user, "X-DS-Password": ds_password}
    client = AsyncOpenAI(api_key=api_key, base_url=base_url, timeout=60, max_retries=2)
    evidence: dict[str, Any] = {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "role": args.role,
        "host": "minimal OpenAI-compatible agent using official OpenAI and MCP SDKs",
        "mcp_url": public_mcp_url(args.mcp_url),
        "credential_delivery": "per-request headers (values omitted)",
        "prompt": args.prompt,
        "allowed_tools": sorted(ALLOWED_TOOLS),
        "events": [],
    }

    system_prompt = (
        f"You are the {args.role} on-call operator. Use only the supplied typed "
        "DolphinScheduler project tools. List visible projects before changing state. "
        "Never use raw API passthrough, never guess identifiers, and stop on a tool error. "
        "Summarize what was verified without claiming access you did not observe."
    )
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": args.prompt},
    ]

    async with streamablehttp_client(
        args.mcp_url,
        headers=headers,
        timeout=30,
        sse_read_timeout=60,
    ) as (read, write, _):
        async with ClientSession(read, write) as session:
            initialized = await session.initialize()
            listed = await session.list_tools()
            selected = [tool for tool in listed.tools if tool.name in ALLOWED_TOOLS]
            selected_names = {tool.name for tool in selected}
            if selected_names != ALLOWED_TOOLS:
                missing = sorted(ALLOWED_TOOLS - selected_names)
                raise RuntimeError(f"MCP server is missing required tools: {missing}")
            evidence["mcp_protocol_version"] = initialized.protocolVersion
            model_tools = [openai_tool(tool) for tool in selected]

            tool_call_count = 0
            successful_list_seen = False
            tool_error_seen = False
            final_text = ""
            for _round in range(1, args.max_rounds + 1):
                response = await client.chat.completions.create(
                    model=model,
                    messages=messages,
                    tools=model_tools,
                    tool_choice="none" if tool_error_seen else "auto",
                    temperature=0,
                    max_tokens=900,
                )
                message = response.choices[0].message
                if not message.tool_calls:
                    final_text = message.content or ""
                    evidence["events"].append(
                        {
                            "sequence": len(evidence["events"]) + 1,
                            "type": "assistant_summary",
                            "text": final_text,
                        }
                    )
                    break

                if tool_error_seen:
                    raise RuntimeError(
                        "model requested another tool after a tool error"
                    )
                if len(message.tool_calls) != 1:
                    raise RuntimeError(
                        "agent requires exactly one auditable tool call per round"
                    )
                messages.append(
                    {
                        "role": "assistant",
                        "content": message.content or "",
                        "tool_calls": [
                            call.model_dump(mode="json") for call in message.tool_calls
                        ],
                    }
                )
                for call in message.tool_calls:
                    name = call.function.name
                    try:
                        arguments = json.loads(call.function.arguments or "{}")
                    except json.JSONDecodeError as exc:
                        raise RuntimeError(
                            f"model emitted invalid arguments for {name}"
                        ) from exc
                    arguments = validate_tool_request(
                        name,
                        arguments,
                        successful_list_seen=successful_list_seen,
                    )

                    result = await session.call_tool(name, arguments)
                    decoded = decode_mcp_content(result)
                    is_error = bool(result.isError)
                    tool_call_count += 1
                    event = {
                        "sequence": len(evidence["events"]) + 1,
                        "type": "mcp_tool_call",
                        "tool": name,
                        "arguments": redact(arguments),
                        "is_error": is_error,
                        "result": redact(decoded),
                    }
                    evidence["events"].append(event)
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": call.id,
                            "content": json.dumps(
                                {"is_error": is_error, "content": redact(decoded)},
                                ensure_ascii=False,
                            ),
                        }
                    )
                    if name == "ds_list_projects" and not is_error:
                        successful_list_seen = True
                    if is_error:
                        # The next round is forced to summarize without any tool call.
                        tool_error_seen = True
            else:
                raise RuntimeError(f"agent exceeded {args.max_rounds} model rounds")

    if tool_call_count == 0:
        raise RuntimeError("agent completed without an MCP tool call")
    if not final_text:
        raise RuntimeError("agent did not produce a final summary")

    evidence["tool_call_count"] = tool_call_count
    serialized = json.dumps(redact(evidence), ensure_ascii=False, indent=2) + "\n"
    assert_no_secret(serialized, [ds_user, ds_password, api_key])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(serialized, encoding="utf-8")
    return evidence


def main() -> None:
    args = parse_args()
    evidence = asyncio.run(run_agent(args))
    print(
        json.dumps(
            {
                "role": evidence["role"],
                "tool_call_count": evidence["tool_call_count"],
                "output": str(args.output),
                "status": "PASS",
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
