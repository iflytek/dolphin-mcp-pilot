#!/usr/bin/env python3
"""Validate NOTICE and THIRD_PARTY_LICENSES against pyproject.toml deps.

Used by CI to ensure the compliance files stay in sync with the project's
declared runtime dependencies. Fails with a non-zero exit code and a
human-readable error message if any check fails.

Checks performed:
  1. NOTICE and THIRD_PARTY_LICENSES exist at the repo root.
  2. Both files are non-empty.
  3. NOTICE starts with the project name 'dolphin-mcp-pilot'.
  4. THIRD_PARTY_LICENSES contains a 'Package: <name>' entry for every
     direct runtime dependency declared in pyproject.toml's
     [project].dependencies OR requirements.txt.
  5. NOTICE also mentions every direct runtime dependency.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
NOTICE_PATH = REPO_ROOT / "NOTICE"
THIRD_PARTY_PATH = REPO_ROOT / "THIRD_PARTY_LICENSES"
PYPROJECT_PATH = REPO_ROOT / "pyproject.toml"
REQUIREMENTS_PATH = REPO_ROOT / "requirements.txt"


def _read(path: Path) -> str:
    if not path.is_file():
        raise FileNotFoundError(
            f"required file is missing: {path.relative_to(REPO_ROOT)}"
        )
    text = path.read_text(encoding="utf-8")
    if not text.strip():
        raise ValueError(f"required file is empty: {path.relative_to(REPO_ROOT)}")
    return text


def _parse_direct_deps(pyproject_text: str) -> list[str]:
    """Return the bare package names from [project].dependencies.

    Parses PEP 508 dependency specifiers loosely — strips version ranges,
    extras, and environment markers, then lowercases + normalizes
    (PEP 503: underscores and runs of [-_.] collapse to a single '-').
    """
    in_deps = False
    names: list[str] = []
    for raw_line in pyproject_text.splitlines():
        line = raw_line.strip()
        if line.startswith("dependencies") and "=" in line:
            in_deps = True
            # handle inline `dependencies = [...]` on the same line
            if "[" in line:
                # collect everything up to the matching ']'
                rest = line.split("=", 1)[1]
                if "]" in rest:
                    items = rest.split("]", 1)[0]
                    for item in items.split(","):
                        name = _extract_name(item)
                        if name:
                            names.append(name)
                    in_deps = False
                    continue
            continue
        if in_deps:
            if line.startswith("]"):
                in_deps = False
                continue
            if line.startswith('"') or line.startswith("'"):
                name = _extract_name(line.strip("'\" ,"))
                if name:
                    names.append(name)
    return names


def _parse_requirements(text: str) -> list[str]:
    """Parse bare package names from requirements.txt, ignoring comments/blanks."""
    names: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line or line.startswith("-"):
            continue
        name = _extract_name(line)
        if name:
            names.append(name)
    return names


def _extract_name(spec: str) -> str | None:
    spec = spec.strip().strip("\"'")
    if not spec:
        return None
    # strip everything after the first version marker or extra marker
    match = re.match(r"^([A-Za-z0-9]([A-Za-z0-9._-]*[A-Za-z0-9])?)", spec)
    if not match:
        return None
    # PEP 503 normalization
    return re.sub(r"[-_.]+", "-", match.group(1)).lower()


def _packages_in_third_party(text: str) -> set[str]:
    """Extract the 'Package: <name>' values from THIRD_PARTY_LICENSES."""
    return {
        _extract_name(m.group(1))
        for m in re.finditer(r"^Package:\s*(.+?)\s*$", text, flags=re.MULTILINE)
        if _extract_name(m.group(1))
    }


def _normalize(text: str) -> str:
    """Lowercase + collapse non-alphanumerics, for fuzzy matching in NOTICE."""
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def main() -> int:
    errors: list[str] = []

    try:
        notice_text = _read(NOTICE_PATH)
    except (FileNotFoundError, ValueError) as e:
        errors.append(str(e))
        notice_text = ""

    try:
        third_party_text = _read(THIRD_PARTY_PATH)
    except (FileNotFoundError, ValueError) as e:
        errors.append(str(e))
        third_party_text = ""

    if notice_text and not notice_text.lstrip().startswith("dolphin-mcp-pilot"):
        errors.append("NOTICE must start with the project name 'dolphin-mcp-pilot'")

    if not PYPROJECT_PATH.is_file():
        errors.append("required file is missing: pyproject.toml")
        for err in errors:
            print(f"::error::{err}", file=sys.stderr)
        return 1

    direct_deps: list[str] = []
    direct_deps.extend(_parse_direct_deps(PYPROJECT_PATH.read_text(encoding="utf-8")))
    if REQUIREMENTS_PATH.is_file():
        direct_deps.extend(
            _parse_requirements(REQUIREMENTS_PATH.read_text(encoding="utf-8"))
        )
    # dedupe while preserving order
    seen: set[str] = set()
    direct_deps = [d for d in direct_deps if not (d in seen or seen.add(d))]

    if not direct_deps:
        errors.append(
            "could not parse any direct dependencies from pyproject.toml or requirements.txt"
        )
        for err in errors:
            print(f"::error::{err}", file=sys.stderr)
        return 1

    third_party_pkgs = _packages_in_third_party(third_party_text)
    notice_norm = _normalize(notice_text)

    for dep in direct_deps:
        if dep not in third_party_pkgs:
            errors.append(
                f"THIRD_PARTY_LICENSES is missing an entry for direct dep '{dep}'"
            )
        if _normalize(dep) not in notice_norm:
            errors.append(f"NOTICE does not mention direct dep '{dep}'")

    if errors:
        print("::error::NOTICE/THIRD_PARTY_LICENSES validation failed")
        for err in errors:
            print(f"::error::{err}")
        return 1

    print(f"OK: NOTICE + THIRD_PARTY_LICENSES cover all {len(direct_deps)} direct deps")
    return 0


if __name__ == "__main__":
    sys.exit(main())
