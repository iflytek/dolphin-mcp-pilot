#!/usr/bin/env python3
"""v2.0.20 Docker MCP 协议冒烟：版本、工具 schema、ds_help 与编辑参数。"""

import http.client
import json
import os
import sys

PORT = int(os.environ.get("SMOKE_PORT", "8020"))
SID = None


def mcp(method, params=None):
    global SID
    conn = http.client.HTTPConnection("localhost", PORT, timeout=30)
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    if SID:
        headers["mcp-session-id"] = SID
    body = {"jsonrpc": "2.0", "method": method, "params": params or {}}
    if method != "notifications/initialized":
        body["id"] = 1
    conn.request("POST", "/mcp/", json.dumps(body), headers)
    response = conn.getresponse()
    response_headers = dict(response.getheaders())
    if not SID and response_headers.get("mcp-session-id"):
        SID = response_headers["mcp-session-id"]
    raw = response.read().decode().replace("\r", "")
    conn.close()
    for line in raw.split("\n"):
        if line.startswith("data: "):
            try:
                return json.loads(line[6:])
            except json.JSONDecodeError:
                pass
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"_raw": raw[:300]}


def call(name, args):
    response = mcp("tools/call", {"name": name, "arguments": args})
    if "error" in response:
        return {"_error": response["error"]}
    content = response.get("result", {}).get("content", [])
    if content and content[0].get("type") == "text":
        try:
            return json.loads(content[0]["text"])
        except json.JSONDecodeError:
            return {"_text": content[0]["text"]}
    return response.get("result", {})


passed = 0
failed = 0


def check(name, condition, detail=""):
    global passed, failed
    if condition:
        passed += 1
        print(f"  PASS {name} {detail}")
    else:
        failed += 1
        print(f"  FAIL {name} {detail}")


print("=" * 64)
print("DolphinScheduler MCP v2.0.20 Docker smoke")
print("=" * 64)

response = mcp(
    "initialize",
    {
        "protocolVersion": "2024-11-05",
        "capabilities": {},
        "clientInfo": {"name": "smoke-v2.0.20", "version": "1.0"},
    },
)
check("MCP initialize", "result" in response and "error" not in response)
check("version v2.0.20", "v2.0.20" in json.dumps(response))
mcp("notifications/initialized", {})

response = mcp("tools/list", {})
tools = response.get("result", {}).get("tools", [])
check("59 tools", len(tools) == 59, f"actual={len(tools)}")
by_name = {t.get("name"): t for t in tools}
patch = by_name.get("ds_patch_task_content", {})
check("patch tool registered", bool(patch))
schema = patch.get("inputSchema", {})
properties = schema.get("properties", {})
for arg in (
    "old_str",
    "new_str",
    "field",
    "expected_version",
    "dry_run",
    "timeout_seconds",
):
    check(f"patch schema {arg}", arg in properties)
check("dry_run defaults true", properties.get("dry_run", {}).get("default") is True)
for tool_name in ("ds_modify_workflow_dag", "ds_update_task_param"):
    props = by_name.get(tool_name, {}).get("inputSchema", {}).get("properties", {})
    check(f"{tool_name} expected_version", "expected_version" in props)
    check(f"{tool_name} timeout_seconds", "timeout_seconds" in props)

help_all = call("ds_help", {})
check("ds_help total_tools=59", help_all.get("total_tools") == 59)
help_workflow = call("ds_help", {"category": "workflow"})
help_text = json.dumps(help_workflow, ensure_ascii=False)
check("help includes patch tool", "ds_patch_task_content" in help_text)
check(
    "help includes preview/apply flow",
    "expected_version" in help_text and "dry_run" in help_text,
)
check(
    "help includes timeout recovery",
    "unknown" in help_text and "partially_applied" in help_text,
)
help_quickstart = json.dumps(
    call("ds_help", {"category": "quickstart"}), ensure_ascii=False
)
check(
    "quickstart includes content_verified", "content_verified=True" in help_quickstart
)

log_props = by_name["ds_get_task_log"]["inputSchema"]["properties"]
for arg in ("error_only", "grep", "context_lines", "max_scan_lines"):
    check(f"log schema {arg}", arg in log_props)
latest_props = by_name["ds_get_latest_failure_log"]["inputSchema"]["properties"]
check("latest failure error_only", "error_only" in latest_props)
complement_props = by_name["ds_complement_data"]["inputSchema"]["properties"]
check("complement dry_run", "dry_run" in complement_props)
help_instance = json.dumps(
    call("ds_help", {"category": "instance"}), ensure_ascii=False
)
check(
    "help includes bounded log scan",
    "error_only" in help_instance and "next_skip_line_num" in help_quickstart,
)
check(
    "help distinguishes planned parallelism",
    "parallelism" in help_instance and "planned" in help_instance,
)
check(
    "quickstart includes complement preview",
    "dry_run=True" in help_quickstart and "planned_biz_dates" in help_quickstart,
)

print("=" * 64)
print(f"OVERALL: {passed} PASS, {failed} FAIL")
print("=" * 64)
sys.exit(1 if failed else 0)
