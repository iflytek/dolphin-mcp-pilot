#!/usr/bin/env python3
"""Verify request-scoped identity isolation with concurrent official MCP clients."""

from __future__ import annotations

import argparse
import asyncio
from datetime import UTC, datetime
import json
import os
from pathlib import Path
from typing import Any

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--finops-project", required=True)
    parser.add_argument("--marketing-project", required=True)
    parser.add_argument(
        "--mcp-url",
        default=os.environ.get("MCP_URL", "http://127.0.0.1:23643/mcp/"),
    )
    parser.add_argument("--iterations", type=int, default=20)
    parser.add_argument("--concurrency", type=int, default=6)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def required_env(name: str) -> str:
    value = os.environ.get(name, "")
    if not value:
        raise ValueError(f"missing required environment variable: {name}")
    return value


def project_names(result: Any) -> list[str]:
    values: list[Any] = []
    for block in result.content:
        if getattr(block, "type", "") != "text":
            continue
        try:
            values.append(json.loads(block.text))
        except json.JSONDecodeError:
            continue
    if len(values) == 1 and isinstance(values[0], dict):
        values = [values[0]]
    elif len(values) == 1 and isinstance(values[0], list):
        values = values[0]
    return sorted(
        item["name"]
        for item in values
        if isinstance(item, dict) and isinstance(item.get("name"), str)
    )


def observation_ok(names: list[str], expected: str, forbidden: str) -> bool:
    return expected in names and forbidden not in names


async def list_projects(url: str, user: str, password: str) -> list[str]:
    headers = {"X-DS-User": user, "X-DS-Password": password}
    async with streamablehttp_client(
        url,
        headers=headers,
        timeout=30,
        sse_read_timeout=60,
    ) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool("ds_list_projects", {})
            if result.isError:
                raise RuntimeError("ds_list_projects returned an MCP tool error")
            return project_names(result)


async def run(args: argparse.Namespace) -> dict[str, Any]:
    if args.iterations < 1:
        raise ValueError("--iterations must be positive")
    if args.concurrency < 1:
        raise ValueError("--concurrency must be positive")

    roles = {
        "finops": {
            "user": required_env("FINOPS_DS_USER"),
            "password": required_env("FINOPS_DS_PASSWORD"),
            "expected": args.finops_project,
            "forbidden": args.marketing_project,
        },
        "marketing": {
            "user": required_env("MARKETING_DS_USER"),
            "password": required_env("MARKETING_DS_PASSWORD"),
            "expected": args.marketing_project,
            "forbidden": args.finops_project,
        },
    }
    semaphore = asyncio.Semaphore(args.concurrency)

    async def check(role: str, iteration: int) -> dict[str, Any]:
        config = roles[role]
        async with semaphore:
            names = await list_projects(
                args.mcp_url,
                config["user"],
                config["password"],
            )
        return {
            "role": role,
            "iteration": iteration,
            "expected_visible": config["expected"] in names,
            "forbidden_visible": config["forbidden"] in names,
            "ok": observation_ok(names, config["expected"], config["forbidden"]),
        }

    results = await asyncio.gather(
        *(
            check(role, iteration)
            for iteration in range(1, args.iterations + 1)
            for role in roles
        )
    )
    failures = [result for result in results if not result["ok"]]
    evidence = {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "transport": "official MCP Python SDK over Streamable HTTP",
        "credential_delivery": "per-request headers (values omitted)",
        "concurrency": args.concurrency,
        "iterations_per_role": args.iterations,
        "total_calls": len(results),
        "successful_isolation_checks": len(results) - len(failures),
        "credential_bleed_count": len(failures),
        "status": "PASS" if not failures else "FAIL",
        "role_summary": {
            role: {
                "expected_project_visible_in_all_calls": all(
                    result["expected_visible"]
                    for result in results
                    if result["role"] == role
                ),
                "other_project_visible_in_any_call": any(
                    result["forbidden_visible"]
                    for result in results
                    if result["role"] == role
                ),
            }
            for role in roles
        },
    }
    serialized = json.dumps(evidence, ensure_ascii=False, indent=2) + "\n"
    for config in roles.values():
        for secret in (config["user"], config["password"]):
            if secret and secret in serialized:
                raise ValueError(
                    "refusing to write evidence containing a credential value"
                )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(serialized, encoding="utf-8")
    if failures:
        raise RuntimeError(f"request isolation failed in {len(failures)} call(s)")
    return evidence


def main() -> None:
    args = parse_args()
    evidence = asyncio.run(run(args))
    print(json.dumps(evidence, ensure_ascii=False))


if __name__ == "__main__":
    main()
