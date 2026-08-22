#!/usr/bin/env python3
"""Render the sanitized case evidence as a self-contained HTML proof sheet."""

from __future__ import annotations

import argparse
from hashlib import sha256
from html import escape
import json
from pathlib import Path
from typing import Any


EVIDENCE_FILES = (
    "finops-agent.json",
    "marketing-agent.json",
    "cross-team-negative-agent.json",
    "concurrency.json",
)


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def tool_events(evidence: dict[str, Any]) -> list[dict[str, Any]]:
    return [event for event in evidence["events"] if event["type"] == "mcp_tool_call"]


def one_project_name(event: dict[str, Any]) -> str:
    results = event["result"]
    if not results or not isinstance(results[0], dict):
        raise ValueError("expected a project object in tool evidence")
    return str(results[0]["name"])


def validate(
    finops: dict[str, Any],
    marketing: dict[str, Any],
    negative: dict[str, Any],
    concurrency: dict[str, Any],
) -> None:
    for role, evidence in (("finops", finops), ("marketing", marketing)):
        calls = tool_events(evidence)
        names = [call["tool"] for call in calls]
        if names != ["ds_list_projects", "ds_rename_project", "ds_list_projects"]:
            raise ValueError(f"unexpected {role} tool sequence: {names}")
        if any(call["is_error"] for call in calls):
            raise ValueError(f"positive {role} path contains a tool error")
        if one_project_name(calls[-1]) != calls[1]["arguments"]["new_name"]:
            raise ValueError(f"{role} after-state does not match the requested name")

    negative_calls = tool_events(negative)
    if [call["tool"] for call in negative_calls] != [
        "ds_list_projects",
        "ds_rename_project",
    ]:
        raise ValueError("unexpected negative-path tool sequence")
    if not negative_calls[1]["is_error"]:
        raise ValueError("cross-team rename unexpectedly succeeded")
    if "not found" not in str(negative_calls[1]["result"]).casefold():
        raise ValueError(
            "negative evidence does not contain the expected not-found boundary"
        )

    if concurrency["status"] != "PASS":
        raise ValueError("concurrency evidence did not pass")
    if concurrency["credential_bleed_count"] != 0:
        raise ValueError("concurrency evidence reports credential bleed")


def short_hash(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()[:12]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root = Path(__file__).resolve().parent
    evidence_dir = root / "evidence"
    paths = {name: evidence_dir / name for name in EVIDENCE_FILES}
    evidence = {name: load_json(path) for name, path in paths.items()}

    finops = evidence["finops-agent.json"]
    marketing = evidence["marketing-agent.json"]
    negative = evidence["cross-team-negative-agent.json"]
    concurrency = evidence["concurrency.json"]
    validate(finops, marketing, negative, concurrency)

    finops_calls = tool_events(finops)
    marketing_calls = tool_events(marketing)
    negative_calls = tool_events(negative)
    finops_before = one_project_name(finops_calls[0])
    finops_after = one_project_name(finops_calls[-1])
    marketing_before = one_project_name(marketing_calls[0])
    marketing_after = one_project_name(marketing_calls[-1])
    negative_error = str(negative_calls[-1]["result"][0])
    hashes = " · ".join(
        f"{escape(name)} {short_hash(path)}" for name, path in paths.items()
    )

    def h(value: Any) -> str:
        return escape(str(value))

    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Request-scoped team isolation evidence</title>
  <style>
    :root {{ color-scheme: dark; --bg:#07111f; --panel:#0d1b2f; --line:#243b59;
      --text:#edf5ff; --muted:#9fb2c9; --blue:#57a6ff; --green:#5ce1a6;
      --amber:#ffc96b; --red:#ff8797; }}
    * {{ box-sizing: border-box; }}
    body {{ margin:0; background:radial-gradient(circle at 15% 0,#15325a 0,transparent 33%),
      linear-gradient(180deg,#07111f,#091626); color:var(--text); font-family:Inter,ui-sans-serif,
      system-ui,-apple-system,"Segoe UI",sans-serif; }}
    main {{ width:1480px; margin:0 auto; padding:58px 64px 54px; }}
    header {{ border:1px solid #31517a; border-radius:28px; padding:40px 44px;
      background:linear-gradient(135deg,rgba(37,81,139,.62),rgba(10,25,45,.92));
      box-shadow:0 24px 70px rgba(0,0,0,.28); }}
    .eyebrow {{ color:#91c8ff; font-size:18px; letter-spacing:.14em; text-transform:uppercase;
      font-weight:750; }}
    h1 {{ font-size:52px; line-height:1.07; margin:13px 0 14px; letter-spacing:-.035em; }}
    .subtitle {{ color:#bed0e5; font-size:23px; line-height:1.45; max-width:1100px; margin:0; }}
    .chips {{ display:flex; gap:12px; flex-wrap:wrap; margin-top:27px; }}
    .chip {{ border:1px solid #3a5c83; background:#102641; border-radius:999px;
      padding:10px 15px; color:#d6e8fb; font-size:16px; }}
    .stats {{ display:grid; grid-template-columns:repeat(4,1fr); gap:18px; margin:24px 0; }}
    .stat,.card {{ border:1px solid var(--line); background:rgba(13,27,47,.94);
      border-radius:22px; box-shadow:0 18px 50px rgba(0,0,0,.18); }}
    .stat {{ padding:22px 24px; }} .stat strong {{ display:block; font-size:35px; color:var(--green); }}
    .stat span {{ color:var(--muted); font-size:16px; }}
    .grid {{ display:grid; grid-template-columns:1fr 1fr; gap:22px; }}
    .card {{ padding:27px 29px; }}
    h2 {{ margin:0 0 7px; font-size:27px; }}
    .role {{ color:var(--muted); font-size:16px; margin-bottom:20px; }}
    .prompt {{ border-left:4px solid var(--blue); background:#0a1728; padding:15px 17px;
      border-radius:0 12px 12px 0; color:#d9e9fa; line-height:1.48; font-size:16px; min-height:92px; }}
    .flow {{ display:grid; gap:10px; margin-top:18px; }}
    .call {{ display:grid; grid-template-columns:58px 205px 1fr 84px; align-items:center;
      gap:12px; background:#0a1728; border:1px solid #1e3551; border-radius:13px; padding:12px 14px; }}
    .step {{ color:#87a4c3; font-weight:700; }} .tool {{ color:#9cccff; font-family:ui-monospace,monospace;
      font-size:14px; }} .result {{ color:#dce9f7; font-family:ui-monospace,monospace; font-size:13px;
      overflow-wrap:anywhere; }} .ok {{ color:var(--green); font-weight:800; text-align:right; }}
    .boundary {{ margin-top:22px; border-color:#68404c; background:linear-gradient(140deg,#251826,#111c2e); }}
    .boundary-grid {{ display:grid; grid-template-columns:1.1fr .9fr; gap:22px; align-items:start; }}
    .deny {{ color:var(--red); font-weight:800; }}
    pre {{ white-space:pre-wrap; overflow-wrap:anywhere; background:#091422; border:1px solid #3f2c3a;
      padding:17px; border-radius:13px; color:#ffd2d8; font:14px/1.48 ui-monospace,monospace; margin:14px 0 0; }}
    .claim {{ margin-top:22px; display:grid; grid-template-columns:1fr 1fr; gap:22px; }}
    ul {{ margin:13px 0 0; padding-left:22px; color:#c8d8e9; line-height:1.6; }}
    footer {{ margin-top:22px; border-top:1px solid #233951; padding-top:20px; color:#849bb5;
      font:13px/1.55 ui-monospace,monospace; overflow-wrap:anywhere; }}
  </style>
</head>
<body>
<main data-testid="evidence-sheet">
  <header>
    <div class="eyebrow">HER Hack-Astron #3 · sanitized execution evidence</div>
    <h1>One stateless MCP server.<br>Two identities. Zero credential bleed.</h1>
    <p class="subtitle">Two ordinary DolphinScheduler users issued state-changing requests through the
      same dolphin-mcp-pilot process. Per-request credentials stayed local; DolphinScheduler applied
      project visibility; a cross-team mutation was rejected before state changed.</p>
    <div class="chips"><span class="chip">DolphinScheduler 3.4.2</span>
      <span class="chip">dolphin-mcp-pilot d7681d3</span><span class="chip">official MCP SDK</span>
      <span class="chip">typed tools only · no raw API</span></div>
  </header>

  <section class="stats" aria-label="verification summary">
    <div class="stat"><strong>2</strong><span>independent user identities</span></div>
    <div class="stat"><strong>6</strong><span>successful state-path tool calls</span></div>
    <div class="stat"><strong>{h(concurrency["total_calls"])}/{h(concurrency["total_calls"])}</strong><span>concurrent visibility checks passed</span></div>
    <div class="stat"><strong>{h(concurrency["credential_bleed_count"])}</strong><span>credential bleed observations</span></div>
  </section>

  <section class="grid">
    <article class="card" data-testid="finops-run">
      <h2>Finance on-call</h2><div class="role">Independent request credentials · state change verified</div>
      <div class="prompt">“{h(finops["prompt"])}”</div>
      <div class="flow">
        <div class="call"><span class="step">01</span><span class="tool">ds_list_projects</span><span class="result">{h(finops_before)}</span><span class="ok">OK</span></div>
        <div class="call"><span class="step">02</span><span class="tool">ds_rename_project</span><span class="result">status = renamed</span><span class="ok">OK</span></div>
        <div class="call"><span class="step">03</span><span class="tool">ds_list_projects</span><span class="result">{h(finops_after)}</span><span class="ok">VERIFIED</span></div>
      </div>
    </article>
    <article class="card" data-testid="marketing-run">
      <h2>Marketing on-call</h2><div class="role">Independent request credentials · state change verified</div>
      <div class="prompt">“{h(marketing["prompt"])}”</div>
      <div class="flow">
        <div class="call"><span class="step">01</span><span class="tool">ds_list_projects</span><span class="result">{h(marketing_before)}</span><span class="ok">OK</span></div>
        <div class="call"><span class="step">02</span><span class="tool">ds_rename_project</span><span class="result">status = renamed</span><span class="ok">OK</span></div>
        <div class="call"><span class="step">03</span><span class="tool">ds_list_projects</span><span class="result">{h(marketing_after)}</span><span class="ok">VERIFIED</span></div>
      </div>
    </article>
  </section>

  <article class="card boundary" data-testid="negative-boundary">
    <div class="boundary-grid"><div><h2>Negative boundary: cross-team rename</h2>
      <div class="role">Finance credentials requested Marketing's exact project name</div>
      <div class="prompt">“{h(negative["prompt"])}”</div></div>
      <div><div class="deny">EXPECTED DENIAL · NO MUTATION</div>
        <pre>{h(negative_error)}</pre></div></div>
  </article>

  <section class="claim">
    <article class="card"><h2>What this run proves</h2><ul>
      <li>Each request reached the same MCP process with a different identity.</li>
      <li>Each role repeatedly saw its own project and never the other role's project.</li>
      <li>Both positive mutations were followed by a read-after-write check.</li>
      <li>The typed resolver rejected the cross-team name before mutation.</li></ul></article>
    <article class="card"><h2>Claim boundary</h2><ul>
      <li>DolphinScheduler remains the authority for project visibility.</li>
      <li>This is a controlled local reproduction, not a proof for every deployment.</li>
      <li>Only list and rename tools were exposed to the agent.</li>
      <li>Credentials and request-header values are omitted by construction.</li></ul></article>
  </section>

  <footer data-testid="evidence-hashes">Rendered from committed sanitized JSON. SHA-256 prefixes:
    {hashes}<br>No passwords, tokens, X-DS-* values, private hostnames, or production data are present.</footer>
</main>
</body>
</html>"""
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(html, encoding="utf-8")
    print(json.dumps({"output": str(args.output), "status": "PASS"}))


if __name__ == "__main__":
    main()
