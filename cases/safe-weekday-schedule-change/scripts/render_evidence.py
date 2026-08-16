#!/usr/bin/env python3
"""Render a sanitized evidence bundle from a Claude Code stream-json log."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
from pathlib import Path


PRIVATE_IP = re.compile(
    r"\b(?:127(?:\.\d{1,3}){3}|10(?:\.\d{1,3}){3}|"
    r"192\.168(?:\.\d{1,3}){2}|172\.(?:1[6-9]|2\d|3[01])(?:\.\d{1,3}){2})"
    r"(?::\d+)?\b"
)
RUNTIME_PATH = re.compile(r"/tmp/dolphinscheduler/exec/[^\"\s]+")


def sanitize(value: object) -> object:
    """Redact private addresses, runtime paths, and auth-like values recursively."""
    if isinstance(value, dict):
        cleaned: dict[str, object] = {}
        for key, item in value.items():
            if re.search(r"(?:password|token|authorization|x-ds-)", key, re.I):
                cleaned[key] = "<redacted>"
            elif key in {"host", "executePath"}:
                cleaned[key] = "<redacted-runtime-location>"
            else:
                cleaned[key] = sanitize(item)
        return cleaned
    if isinstance(value, list):
        return [sanitize(item) for item in value]
    if isinstance(value, str):
        value = PRIVATE_IP.sub("<redacted-private-address>", value)
        return RUNTIME_PATH.sub("<redacted-runtime-path>", value)
    return value


def tool_result_text(content: object) -> str:
    if not isinstance(content, list):
        return ""
    return "\n".join(
        item.get("text", "")
        for item in content
        if isinstance(item, dict) and item.get("type") == "text"
    )


def parse_result(text: str) -> object:
    if not text.strip():
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Some MCP list responses are emitted as consecutive JSON objects.
        return text


def load_records(log_path: Path) -> tuple[list[dict[str, object]], str]:
    raw = log_path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    pending: dict[str, dict[str, object]] = {}
    ordered: list[dict[str, object]] = []

    for line in raw.decode("utf-8").splitlines():
        event = json.loads(line)
        if event.get("type") == "assistant":
            timestamp = event.get("timestamp")
            for item in event.get("message", {}).get("content", []):
                if item.get("type") != "tool_use":
                    continue
                record = {
                    "id": item["id"],
                    "timestamp": timestamp,
                    "tool": item["name"].removeprefix("mcp__dolphin-scheduler__"),
                    "input": sanitize(item.get("input", {})),
                    "result": None,
                }
                pending[item["id"]] = record
                ordered.append(record)
        elif event.get("type") == "user":
            for item in event.get("message", {}).get("content", []):
                if item.get("type") != "tool_result":
                    continue
                record = pending.get(item.get("tool_use_id"))
                if record is not None:
                    record["result"] = sanitize(
                        parse_result(tool_result_text(item.get("content")))
                    )
    return ordered, digest


def compact_result(record: dict[str, object]) -> object:
    result = record["result"]
    tool = record["tool"]
    if not isinstance(result, dict):
        return result
    keys_by_tool = {
        "ds_clone_workflow": (
            "success",
            "workflow_code",
            "name",
            "task_count",
            "release",
        ),
        "ds_list_workflows": ("code", "name", "releaseState"),
        "ds_update_schedule_cron": (
            "schedule_id",
            "new_cron",
            "release_state",
            "status",
            "online_retry_detail",
        ),
        "ds_run_workflow": ("status", "workflow_code"),
        "ds_list_process_instances": (
            "id",
            "name",
            "state",
            "startTime",
            "endTime",
        ),
    }
    keys = keys_by_tool.get(str(tool))
    if not keys:
        return result
    return {key: result.get(key) for key in keys if key in result}


def task_summary(result: object) -> list[dict[str, str]]:
    if not isinstance(result, str):
        return []
    return [
        {"name": name, "state": state}
        for name, state in re.findall(
            r'"name"\s*:\s*"([^"]+)".*?"state"\s*:\s*"([^"]+)"',
            result,
            re.S,
        )
    ]


def render_html(bundle: dict[str, object], output: Path) -> None:
    records = bundle["records"]
    by_tool: dict[str, list[dict[str, object]]] = {}
    for record in records:
        by_tool.setdefault(str(record["tool"]), []).append(record)

    clone = by_tool["ds_clone_workflow"][-1]
    schedule = by_tool["ds_update_schedule_cron"][-1]
    submitted = by_tool["ds_run_workflow"][-1]
    tasks = task_summary(by_tool["ds_list_task_instances"][-1]["result"])
    terminal = by_tool["ds_list_process_instances"][-1]

    def code(value: object) -> str:
        return html.escape(json.dumps(value, ensure_ascii=False, indent=2))

    task_badges = "".join(
        f'<span class="badge"><b>{html.escape(item["name"])}</b> '
        f"{html.escape(item['state'])}</span>"
        for item in tasks
    )
    page = f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><title>MCP evidence</title>
<style>
*{{box-sizing:border-box}} body{{margin:0;background:#07111f;color:#e6edf7;font:18px/1.5 ui-monospace,SFMono-Regular,Menlo,monospace}}
.wrap{{width:1680px;margin:0 auto;padding:42px}} h1{{font:700 34px/1.2 system-ui;margin:0 0 8px;color:#fff}}
.meta{{color:#8da2bb;font-size:15px;margin-bottom:24px}} .prompt{{background:#10243d;border-left:5px solid #45a3ff;padding:18px 22px;border-radius:10px;margin-bottom:22px}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:18px}} .card{{background:#0d1b2d;border:1px solid #263d58;border-radius:12px;padding:18px 20px;min-height:235px}}
.tool{{color:#63b3ff;font-weight:700;margin-bottom:10px}} pre{{white-space:pre-wrap;word-break:break-word;margin:8px 0 0;color:#c9d7e8;font-size:15px}}
.ok{{color:#59d98e;font-weight:700}} .warn{{color:#ffc96b}} .badges{{display:flex;gap:10px;flex-wrap:wrap;margin-top:12px}}
.badge{{background:#123628;color:#8df0b1;border:1px solid #286849;padding:7px 10px;border-radius:999px;font-size:14px}}
.footer{{margin-top:20px;color:#8da2bb;font-size:14px}}
</style></head><body><main class="wrap">
<h1>Claude Code × dolphin-mcp-pilot：真实 MCP 事件摘录</h1>
<div class="meta">由 stream-json 原始日志自动生成并脱敏 · SHA-256 {bundle["source_sha256"]}</div>
<div class="prompt"><b>自然语言请求</b><br>{html.escape(str(bundle["prompt"]))}</div>
<section class="grid">
<article class="card"><div class="tool">① ds_clone_workflow</div><div class="ok">先建立 OFFLINE 恢复点</div><pre>{code(compact_result(clone))}</pre></article>
<article class="card"><div class="tool">② ds_update_schedule_cron</div><div class="ok">变更后自动恢复 ONLINE</div><pre>{code(compact_result(schedule))}</pre></article>
<article class="card"><div class="tool">③ ds_run_workflow</div><div class="warn">submitted 只代表已提交，继续轮询</div><pre>{code(compact_result(submitted))}</pre></article>
<article class="card"><div class="tool">④ ds_list_task_instances → ds_list_process_instances</div><div class="ok">任务与流程均到达真实终态</div><div class="badges">{task_badges}</div><pre>{code(compact_result(terminal))}</pre></article>
</section>
<div class="footer">未展示认证头；私有地址、运行目录已替换。完整脱敏事件见 evidence.json。</div>
</main></body></html>"""
    output.write_text(page, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("log", type=Path)
    parser.add_argument("prompt", type=Path)
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()

    records, digest = load_records(args.log)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    bundle = {
        "schema_version": 1,
        "source": "Claude Code stream-json event log",
        "source_sha256": digest,
        "prompt": args.prompt.read_text(encoding="utf-8").strip(),
        "records": records,
    }
    (args.output_dir / "evidence.json").write_text(
        json.dumps(bundle, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    render_html(bundle, args.output_dir / "transcript.html")


if __name__ == "__main__":
    main()
