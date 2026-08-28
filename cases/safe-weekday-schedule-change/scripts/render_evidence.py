#!/usr/bin/env python3
"""Render a sanitized evidence bundle from two Claude Code stream-json logs."""

from __future__ import annotations

import argparse
import hashlib
import html
import ipaddress
import json
import re
from pathlib import Path


SENSITIVE_KEY_PART = re.compile(
    r"(?:pass(?:word|wd)?|token|authorization|api[_-]?key|cookie|secret|"
    r"credential|x-ds-|private[_-]?key|access[_-]?key)",
    re.I,
)
ACCOUNT_KEY = re.compile(
    r"(?:user(?:id|name|_name)?|owner(?:id|name|_name)?)",
    re.I,
)
RUNTIME_LOCATION_KEYS = {"host", "hostname", "executePath", "execute_path"}
RUNTIME_LOCATION_KEYS_LOWER = {key.lower() for key in RUNTIME_LOCATION_KEYS}
PRIVATE_IP = re.compile(
    r"\b(?:127(?:\.\d{1,3}){3}|10(?:\.\d{1,3}){3}|"
    r"192\.168(?:\.\d{1,3}){2}|172\.(?:1[6-9]|2\d|3[01])(?:\.\d{1,3}){2})"
    r"(?::\d+)?\b"
)
IPV6_CANDIDATE = re.compile(
    r"\[([0-9A-Fa-f:.]+)\](?::\d+)?|"
    r"(?<![0-9A-Fa-f:])([0-9A-Fa-f:]{2,})(?![0-9A-Fa-f:])"
)
RUNTIME_PATH = re.compile(r"/tmp/dolphinscheduler/exec/[^\"\s]+")
INTERNAL_HOST = re.compile(
    r"\b(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+"
    r"(?:internal|local|lan|svc|cluster\.local)\b",
    re.I,
)
EMAIL = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)
SENSITIVE_TEXT_PAIR = re.compile(
    r"(?P<prefix>[\"']?(?P<key>pass(?:word|wd)?|token|authorization|"
    r"api[_-]?key|cookie|secret|credential|x-ds-[\w-]*|private[_-]?key|"
    r"access[_-]?key|user(?:id|name|_name)?|owner(?:id|name|_name)?|"
    r"host(?:name)?|executePath|execute_path)"
    r"[\"']?\s*[:=]\s*)"
    r"(?P<value>\"(?:\\.|[^\"])*\"|'(?:\\.|[^'])*'|[^,;\s}\]]+)",
    re.I,
)
AUTH_HEADER = re.compile(
    r"(?P<prefix>\bauthorization\b\s*[:=]\s*)"
    r"(?P<value>\"[^\"]*\"|'[^']*'|[^\r\n,;]+)",
    re.I,
)


def redact_ipv6(match: re.Match[str]) -> str:
    """Redact a valid IPv6 candidate without mistaking timestamps for addresses."""
    candidate = match.group(1) or match.group(2)
    if ":" not in candidate:
        return match.group(0)
    try:
        parsed = ipaddress.ip_address(candidate)
    except ValueError:
        return match.group(0)
    return "<redacted-address>" if parsed.version == 6 else match.group(0)


def redact_text_pair(match: re.Match[str]) -> str:
    """Preserve the key and quoting while replacing a sensitive text value."""
    key = match.group("key").lower()
    value = match.group("value")
    marker = (
        "<redacted-runtime-location>"
        if key in RUNTIME_LOCATION_KEYS_LOWER
        else "<redacted>"
    )
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        marker = f"{value[0]}{marker}{value[-1]}"
    return f"{match.group('prefix')}{marker}"


def sanitize(value: object) -> object:
    """Redact private addresses, runtime paths, and auth-like values recursively."""
    if isinstance(value, dict):
        cleaned: dict[str, object] = {}
        for key, item in value.items():
            if item is None:
                cleaned[key] = None
            elif SENSITIVE_KEY_PART.search(key) or ACCOUNT_KEY.fullmatch(key):
                cleaned[key] = "<redacted>"
            elif key.lower() in RUNTIME_LOCATION_KEYS_LOWER:
                cleaned[key] = "<redacted-runtime-location>"
            else:
                cleaned[key] = sanitize(item)
        return cleaned
    if isinstance(value, list):
        return [sanitize(item) for item in value]
    if isinstance(value, str):
        value = AUTH_HEADER.sub(
            lambda match: f"{match.group('prefix')}<redacted>", value
        )
        value = SENSITIVE_TEXT_PAIR.sub(redact_text_pair, value)
        value = PRIVATE_IP.sub("<redacted-private-address>", value)
        value = IPV6_CANDIDATE.sub(redact_ipv6, value)
        value = RUNTIME_PATH.sub("<redacted-runtime-path>", value)
        value = INTERNAL_HOST.sub("<redacted-internal-host>", value)
        return EMAIL.sub("<redacted-email>", value)
    return value


def tool_result_text(content: object) -> str:
    if not isinstance(content, list):
        return ""
    return "\n".join(
        item.get("text", "")
        for item in content
        if isinstance(item, dict) and item.get("type") == "text"
    )


def parse_result(text: str) -> tuple[object, str]:
    if not text.strip():
        return None, "empty"
    try:
        return json.loads(text), "json"
    except json.JSONDecodeError:
        pass

    # Some MCP list responses are emitted as consecutive JSON objects.
    decoder = json.JSONDecoder()
    values: list[object] = []
    index = 0
    try:
        while index < len(text):
            while index < len(text) and text[index].isspace():
                index += 1
            if index == len(text):
                break
            value, index = decoder.raw_decode(text, index)
            values.append(value)
    except json.JSONDecodeError:
        return text, "text"
    return (values, "json-sequence") if len(values) > 1 else (text, "text")


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
                    "result_format": "missing",
                    "result_received": False,
                    "is_error": None,
                }
                pending[item["id"]] = record
                ordered.append(record)
        elif event.get("type") == "user":
            for item in event.get("message", {}).get("content", []):
                if item.get("type") != "tool_result":
                    continue
                record = pending.get(item.get("tool_use_id"))
                if record is not None:
                    result, result_format = parse_result(
                        tool_result_text(item.get("content"))
                    )
                    record["result"] = sanitize(result)
                    record["result_format"] = result_format
                    record["result_received"] = True
                    record["is_error"] = bool(item.get("is_error", False))
    return ordered, digest


def compact_result(record: dict[str, object]) -> object:
    result = record["result"]
    tool = record["tool"]
    if not isinstance(result, dict):
        return result
    keys_by_tool = {
        "ds_set_schedule": ("schedule_id", "cron", "releaseState"),
        "ds_online_schedule": ("schedule_id", "status"),
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
    if isinstance(result, list):
        return [
            {"name": item["name"], "state": item["state"]}
            for item in result
            if isinstance(item, dict)
            and isinstance(item.get("name"), str)
            and isinstance(item.get("state"), str)
        ]
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


def records_by_tool(records: object) -> dict[str, list[dict[str, object]]]:
    """Index one validated phase's records by tool name."""
    if not isinstance(records, list):
        raise ValueError("phase records must be a list")
    indexed: dict[str, list[dict[str, object]]] = {}
    for record in records:
        if not isinstance(record, dict):
            raise ValueError("each record must be an object")
        indexed.setdefault(str(record.get("tool")), []).append(record)
    return indexed


def require(condition: bool, message: str) -> None:
    """Reject evidence that cannot support a green claim in the rendered image."""
    if not condition:
        raise ValueError(message)


def result_dict(record: dict[str, object], label: str) -> dict[str, object]:
    """Return a record result only when it is a JSON object."""
    result = record.get("result")
    if not isinstance(result, dict):
        raise ValueError(f"{label} must have an object result")
    return result


def result_has_state(result: object, state: str) -> bool:
    """Check a parsed object, JSON sequence, or fallback text for a state."""
    if isinstance(result, dict):
        return result.get("state") == state
    if isinstance(result, list):
        return any(
            isinstance(item, dict) and item.get("state") == state for item in result
        )
    return isinstance(result, str) and state in result


def validate_bundle(bundle: dict[str, object]) -> None:
    """Validate every state claim that the HTML renders as successful."""
    baseline = bundle.get("baseline")
    change = bundle.get("change")
    if not isinstance(baseline, dict) or not isinstance(change, dict):
        raise ValueError("bundle must contain baseline and change phases")

    baseline_records = baseline.get("records")
    change_records = change.get("records")
    expected_baseline_tools = [
        "ds_set_schedule",
        "ds_online_schedule",
        "ds_list_schedules",
        "ds_run_workflow",
        "ds_list_process_instances",
        "ds_list_task_instances",
        "ds_list_process_instances",
    ]
    expected_change_tools = [
        "ds_get_workflow",
        "ds_list_schedules",
        "ds_clone_workflow",
        "ds_list_workflows",
        "ds_update_schedule_cron",
        "ds_run_workflow",
        "ds_list_process_instances",
        "ds_list_task_instances",
        "ds_list_process_instances",
    ]
    require(
        isinstance(baseline_records, list)
        and [record.get("tool") for record in baseline_records]
        == expected_baseline_tools,
        "unexpected baseline tool sequence",
    )
    require(
        isinstance(change_records, list)
        and [record.get("tool") for record in change_records] == expected_change_tools,
        "unexpected change tool sequence",
    )

    all_records = baseline_records + change_records
    require(
        all(record.get("result_received") is True for record in all_records),
        "every tool call must have a matching result event",
    )
    require(
        all(record.get("is_error") is False for record in all_records),
        "tool error present in evidence",
    )
    ids = [record.get("id") for record in all_records]
    require(
        all(isinstance(record_id, str) and record_id for record_id in ids),
        "tool-use IDs must be non-empty strings",
    )
    require(len(ids) == len(set(ids)), "tool-use IDs must be unique")
    for phase_name, records in (
        ("baseline", baseline_records),
        ("change", change_records),
    ):
        timestamps = [record.get("timestamp") for record in records]
        require(
            all(isinstance(timestamp, str) for timestamp in timestamps)
            and timestamps == sorted(timestamps),
            f"{phase_name} timestamps must be present and ordered",
        )

    baseline_tools = records_by_tool(baseline_records)
    change_tools = records_by_tool(change_records)
    for label, record in (
        ("baseline schedule query", baseline_tools["ds_list_schedules"][-1]),
        ("change schedule query", change_tools["ds_list_schedules"][-1]),
    ):
        require(
            record.get("result_format") == "empty" and record.get("result") is None,
            f"{label} must have an empty text result",
        )

    schedule_set = result_dict(baseline_tools["ds_set_schedule"][-1], "baseline set")
    schedule_online = result_dict(
        baseline_tools["ds_online_schedule"][-1], "baseline online"
    )
    require(
        schedule_set.get("cron") == "0 0 6 * * ? *"
        and schedule_set.get("releaseState") == "OFFLINE",
        "baseline cron or initial state mismatch",
    )
    require(
        schedule_set.get("schedule_id") == schedule_online.get("schedule_id") == 1,
        "baseline schedule IDs do not match",
    )
    require(schedule_online.get("status") == "ONLINE", "baseline is not online")
    baseline_tasks = task_summary(
        baseline_tools["ds_list_task_instances"][-1].get("result")
    )
    require(
        len(baseline_tasks) == 3
        and {item["name"]: item["state"] for item in baseline_tasks}
        == {
            "extract_orders": "SUCCESS",
            "build_report": "SUCCESS",
            "quality_gate": "SUCCESS",
        },
        "baseline tasks did not all reach SUCCESS",
    )
    baseline_terminal = result_dict(
        baseline_tools["ds_list_process_instances"][-1], "baseline terminal process"
    )
    require(
        baseline_terminal.get("state") == "SUCCESS",
        "baseline process did not reach SUCCESS",
    )

    clone = result_dict(change_tools["ds_clone_workflow"][-1], "workflow clone")
    require(
        clone.get("success") is True
        and isinstance(clone.get("workflow_code"), int)
        and clone.get("release") == "OFFLINE"
        and clone.get("task_count") == 3,
        "workflow-definition copy is not an offline three-task copy",
    )
    listed_clone = result_dict(
        change_tools["ds_list_workflows"][-1], "listed workflow clone"
    )
    require(
        listed_clone.get("code") == clone.get("workflow_code")
        and listed_clone.get("name") == clone.get("name")
        and listed_clone.get("releaseState") == "OFFLINE",
        "workflow-definition copy was not independently listed as offline",
    )
    changed_schedule = result_dict(
        change_tools["ds_update_schedule_cron"][-1], "updated schedule"
    )
    require(
        changed_schedule.get("schedule_id") == schedule_set.get("schedule_id")
        and changed_schedule.get("new_cron") == "0 0 7 ? * MON-FRI *"
        and changed_schedule.get("release_state") == "ONLINE",
        "schedule did not reach weekday 07:00 and ONLINE",
    )
    require(
        changed_schedule.get("status") == "updated",
        "schedule update was not acknowledged",
    )
    submitted = result_dict(change_tools["ds_run_workflow"][-1], "workflow trigger")
    require(submitted.get("status") == "submitted", "workflow was not submitted")
    running_result = change_tools["ds_list_process_instances"][0].get("result")
    require(
        result_has_state(running_result, "RUNNING_EXECUTION"),
        "running state was not observed",
    )
    change_tasks = task_summary(
        change_tools["ds_list_task_instances"][-1].get("result")
    )
    require(
        len(change_tasks) == 3
        and {item["name"]: item["state"] for item in change_tasks}
        == {
            "extract_orders": "SUCCESS",
            "build_report": "SUCCESS",
            "quality_gate": "SUCCESS",
        },
        "change tasks did not all reach SUCCESS",
    )
    change_terminal = result_dict(
        change_tools["ds_list_process_instances"][-1], "change terminal process"
    )
    require(
        change_terminal.get("state") == "SUCCESS",
        "change process did not reach SUCCESS",
    )
    require(
        not any(
            str(record.get("tool")).startswith("ds_raw_")
            or str(record.get("tool")).startswith("ds_delete_")
            for record in change_records
        ),
        "core change used a raw or delete tool",
    )


def render_html(bundle: dict[str, object], output: Path) -> None:
    validate_bundle(bundle)
    baseline = bundle["baseline"]
    change = bundle["change"]
    records = change["records"]
    by_tool: dict[str, list[dict[str, object]]] = {}
    for record in records:
        by_tool.setdefault(str(record["tool"]), []).append(record)

    baseline_by_tool: dict[str, list[dict[str, object]]] = {}
    for record in baseline["records"]:
        baseline_by_tool.setdefault(str(record["tool"]), []).append(record)

    baseline_set = baseline_by_tool["ds_set_schedule"][-1]
    baseline_online = baseline_by_tool["ds_online_schedule"][-1]
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
.meta{{color:#8da2bb;font-size:15px;margin-bottom:18px}} .prompt{{background:#10243d;border-left:5px solid #45a3ff;padding:18px 22px;border-radius:10px;margin-bottom:18px}}
.baseline{{background:#132136;border:1px solid #36516f;border-radius:12px;padding:16px 20px;margin-bottom:18px}}
.baseline-grid{{display:grid;grid-template-columns:1fr 1fr;gap:18px}} .note{{color:#8da2bb;font-size:14px;margin-top:10px}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:18px}} .card{{background:#0d1b2d;border:1px solid #263d58;border-radius:12px;padding:18px 20px;min-height:235px}}
.tool{{color:#63b3ff;font-weight:700;margin-bottom:10px}} pre{{white-space:pre-wrap;word-break:break-word;margin:8px 0 0;color:#c9d7e8;font-size:15px}}
.ok{{color:#59d98e;font-weight:700}} .warn{{color:#ffc96b}} .badges{{display:flex;gap:10px;flex-wrap:wrap;margin-top:12px}}
.badge{{background:#123628;color:#8df0b1;border:1px solid #286849;padding:7px 10px;border-radius:999px;font-size:14px}}
.footer{{margin-top:20px;color:#8da2bb;font-size:14px}}
</style></head><body><main class="wrap">
<h1>Claude Code × dolphin-mcp-pilot：真实 MCP 事件证据</h1>
<div class="meta">由两段 stream-json 原始日志自动生成并脱敏<br>基线 SHA-256 {baseline["source_sha256"]} · 变更 SHA-256 {change["source_sha256"]}</div>
<div class="baseline"><div class="tool">变更前独立基线</div><div class="baseline-grid">
<div><div class="ok">① ds_set_schedule：每天 06:00</div><pre>{code(compact_result(baseline_set))}</pre></div>
<div><div class="ok">② ds_online_schedule：上线 schedule 1</div><pre>{code(compact_result(baseline_online))}</pre></div>
</div><div class="note">同轮 ds_list_schedules 的 tool_result 无文本内容，因此前态只取自上述两个真实工具返回，不把空结果包装成证据。</div></div>
<div class="prompt"><b>正式变更请求</b><br>{html.escape(str(change["prompt"]))}</div>
<section class="grid">
<article class="card"><div class="tool">③ ds_clone_workflow</div><div class="ok">备份工作流定义（不含 schedule）</div><pre>{code(compact_result(clone))}</pre></article>
<article class="card"><div class="tool">④ ds_update_schedule_cron</div><div class="ok">变更后自动恢复 ONLINE</div><pre>{code(compact_result(schedule))}</pre></article>
<article class="card"><div class="tool">⑤ ds_run_workflow</div><div class="warn">submitted 只代表已提交，继续轮询</div><pre>{code(compact_result(submitted))}</pre></article>
<article class="card"><div class="tool">⑥ ds_list_task_instances → ds_list_process_instances</div><div class="ok">任务与流程均到达真实终态</div><div class="badges">{task_badges}</div><pre>{code(compact_result(terminal))}</pre></article>
</section>
<div class="footer">证据摘要图（非 Claude TUI 截图）· 未展示认证头；私有地址、运行目录已替换。完整脱敏工具记录见 evidence.json。</div>
</main></body></html>"""
    output.write_text(page + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("baseline_log", type=Path)
    parser.add_argument("baseline_prompt", type=Path)
    parser.add_argument("change_log", type=Path)
    parser.add_argument("change_prompt", type=Path)
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()

    baseline_records, baseline_digest = load_records(args.baseline_log)
    change_records, change_digest = load_records(args.change_log)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    bundle = {
        "schema_version": 2,
        "source": "Claude Code stream-json event logs",
        "baseline": {
            "source_sha256": baseline_digest,
            "prompt": args.baseline_prompt.read_text(encoding="utf-8").strip(),
            "records": baseline_records,
        },
        "change": {
            "source_sha256": change_digest,
            "prompt": args.change_prompt.read_text(encoding="utf-8").strip(),
            "records": change_records,
        },
    }
    validate_bundle(bundle)
    (args.output_dir / "evidence.json").write_text(
        json.dumps(bundle, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    render_html(bundle, args.output_dir / "transcript.html")


if __name__ == "__main__":
    main()
