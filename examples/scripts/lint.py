#!/usr/bin/env python3
"""Validate built-in and community MCP configuration examples."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any


EXAMPLES_DIR = Path(__file__).resolve().parent.parent
SKIP_DIRECTORIES = {"TEMPLATE", "scripts", "__pycache__"}
REQUIRED_FIELDS = {
    "id",
    "title",
    "description",
    "client",
    "transport",
    "authentication",
    "author",
    "testedWith",
}
TRANSPORTS = {"http", "stdio"}
AUTHENTICATION_MODES = {"token", "password", "none", "other"}
KEBAB_CASE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
FRONTMATTER = re.compile(r"\A---\r?\n(?P<body>.*?)\r?\n---(?:\r?\n|\Z)", re.DOTALL)
SENSITIVE_KEY = re.compile(r"(?:token|password|secret|api[_-]?key)", re.IGNORECASE)
PLACEHOLDER = re.compile(
    r"(?:your|example|placeholder|replace|\$\{|<[^>]+>)", re.IGNORECASE
)
SECRET_PATTERNS = {
    "OpenAI-style API key": re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b"),
    "AWS access key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "Bearer token": re.compile(r"\bBearer\s+[A-Za-z0-9._-]{16,}\b", re.IGNORECASE),
    "private IPv4 address": re.compile(
        r"\b(?:10(?:\.\d{1,3}){3}|192\.168(?:\.\d{1,3}){2}|"
        r"172\.(?:1[6-9]|2\d|3[01])(?:\.\d{1,3}){2})\b"
    ),
}


def parse_frontmatter(markdown: str) -> dict[str, str] | None:
    """Parse the scalar frontmatter used by the example template."""
    match = FRONTMATTER.match(markdown)
    if not match:
        return None

    data: dict[str, str] = {}
    for raw_line in match.group("body").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        data[key.strip()] = value.strip().strip("\"'")
    return data


def find_credential_errors(value: Any, path: str = "$") -> list[str]:
    """Find credential fields whose values are not obvious placeholders."""
    errors: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if (
                isinstance(child, str)
                and child
                and SENSITIVE_KEY.search(str(key))
                and not PLACEHOLDER.search(child)
            ):
                errors.append(f"{child_path} must use an obvious placeholder")
            errors.extend(find_credential_errors(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            errors.extend(find_credential_errors(child, f"{path}[{index}]"))
    return errors


def main() -> int:
    """Run all example checks and return a process exit code."""
    errors: list[str] = []
    community_examples = 0

    def fail(location: Path, message: str) -> None:
        relative = location.relative_to(EXAMPLES_DIR).as_posix()
        errors.append(f"examples/{relative}: {message}")

    for directory in sorted(EXAMPLES_DIR.iterdir()):
        if not directory.is_dir() or directory.name in SKIP_DIRECTORIES:
            continue

        community_examples += 1
        if not KEBAB_CASE.fullmatch(directory.name):
            fail(directory, "directory name must be a kebab-case id")

        readme_path = directory / "README.md"
        config_path = directory / "config.json"
        if not readme_path.is_file():
            fail(directory, "missing README.md")
        else:
            metadata = parse_frontmatter(readme_path.read_text(encoding="utf-8"))
            if metadata is None:
                fail(readme_path, "missing YAML frontmatter")
            else:
                for field in sorted(REQUIRED_FIELDS):
                    if not metadata.get(field):
                        fail(
                            readme_path, f"frontmatter missing required field: {field}"
                        )

                example_id = metadata.get("id")
                if example_id and example_id != directory.name:
                    fail(
                        readme_path,
                        f"frontmatter id {example_id!r} does not match directory name",
                    )

                transport = metadata.get("transport")
                if transport and transport not in TRANSPORTS:
                    allowed = ", ".join(sorted(TRANSPORTS))
                    fail(readme_path, f"transport must be one of: {allowed}")

                authentication = metadata.get("authentication")
                if authentication and authentication not in AUTHENTICATION_MODES:
                    allowed = ", ".join(sorted(AUTHENTICATION_MODES))
                    fail(readme_path, f"authentication must be one of: {allowed}")

        if not config_path.is_file():
            fail(directory, "missing config.json")

    json_files = 0
    for config_path in sorted(EXAMPLES_DIR.rglob("*.json")):
        json_files += 1
        raw = config_path.read_text(encoding="utf-8")
        try:
            config = json.loads(raw)
        except json.JSONDecodeError as exc:
            fail(
                config_path,
                f"invalid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}",
            )
            continue

        servers = config.get("mcpServers") if isinstance(config, dict) else None
        if not isinstance(servers, dict) or not servers:
            fail(config_path, "must contain a non-empty mcpServers object")

        for message in find_credential_errors(config):
            fail(config_path, message)
        for label, pattern in SECRET_PATTERNS.items():
            if pattern.search(raw):
                fail(
                    config_path,
                    f"appears to contain a {label}; replace it with a placeholder",
                )

    summary = (
        f"{community_examples} community example(s) and "
        f"{json_files} JSON file(s) checked"
    )
    if errors:
        print(
            f"examples lint failed: {len(errors)} issue(s); {summary}:\n",
            file=sys.stderr,
        )
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 1

    print(f"examples lint passed: {summary}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
