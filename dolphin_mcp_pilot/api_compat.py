#!/usr/bin/env python3
# Copyright 2026 iFLYTEK CO., LTD.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""DolphinScheduler API path-compatibility helpers.

DolphinScheduler renamed several REST path segments in 3.3.0:

    process-definition  ->  workflow-definition
    process-instances   ->  workflow-instances

The tool's call sites are written against the legacy ("process") spelling.
This module rewrites those path segments to the ``workflow`` spelling when
the target deployment is DolphinScheduler >= 3.3.0, so a single code base
drives both the 3.2.x and the 3.3.x/3.4.x API families.

Everything here is pure and side-effect free; live version detection lives
in :mod:`dolphin_mcp_pilot.client`, which owns the HTTP/auth layer.
"""

from __future__ import annotations

# Legacy (<= 3.2.x) path segment  ->  3.3.0+ path segment.
# Keyed on the *legacy* spelling because that is what the call sites emit.
SEGMENT_MAP = {
    "process-definition": "workflow-definition",
    "process-instances": "workflow-instances",
}

# The DolphinScheduler release that renamed the segments above.
WORKFLOW_STYLE_SINCE = (3, 3, 0)

VALID_STYLES = ("auto", "process", "workflow")


def normalize_style(value: str | None) -> str:
    """Normalise a configured style string to one of :data:`VALID_STYLES`.

    Unknown / empty values fall back to ``"auto"`` so a typo never hard-fails
    a deployment; it just means "detect it".
    """
    style = (value or "").strip().lower()
    return style if style in VALID_STYLES else "auto"


def apply_style(path: str, style: str) -> str:
    """Rewrite legacy path segments to the ``workflow`` spelling when needed.

    Only whole path segments are rewritten, and only the path portion before
    any ``?`` query string is touched, so substrings such as
    ``executors/start-process-instance`` (singular, a different endpoint that
    was *not* renamed) are left intact.

    The rewrite is a no-op for the ``process`` / ``auto`` styles and is
    idempotent for the ``workflow`` style.
    """
    if style != "workflow" or not path:
        return path

    if "?" in path:
        base, query = path.split("?", 1)
        suffix = "?" + query
    else:
        base, suffix = path, ""

    segments = [SEGMENT_MAP.get(segment, segment) for segment in base.split("/")]
    return "/".join(segments) + suffix


def style_for_version(version: tuple[int, ...] | None) -> str | None:
    """Map a parsed version tuple to a path style.

    Returns ``"workflow"`` for >= 3.3.0, ``"process"`` for older releases, and
    ``None`` when the version is unknown (so the caller can try another signal).
    """
    if not version:
        return None
    return "workflow" if tuple(version[:3]) >= WORKFLOW_STYLE_SINCE else "process"


def parse_version(text: str | None) -> tuple[int, ...] | None:
    """Extract a leading ``MAJOR.MINOR[.PATCH]`` version from free-form text.

    Tolerates suffixes like ``3.3.2-release`` or ``v3.4.1``. Returns ``None``
    when no dotted numeric version is present.
    """
    if not text:
        return None

    cleaned = str(text).strip().lstrip("vV")
    digits: list[int] = []
    for part in cleaned.split(".")[:3]:
        number = ""
        for char in part:
            if char.isdigit():
                number += char
            else:
                break
        if not number:
            break
        digits.append(int(number))

    if len(digits) < 2:
        return None
    return tuple(digits)
