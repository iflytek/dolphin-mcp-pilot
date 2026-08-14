---
title: One-line summary of what you got done
author: your-github-handle
date: 2026-08-14                 # YYYY-MM-DD — when you published the post
category: nl-ops                 # one creative direction: nl-ops / incident-firefighting /
                                 #   workflow-creation / schedule-management / monitoring /
                                 #   version-safety / multi-tenant / host-integration / before-after / other
host: claude-code                # MCP host used: claude-code / openclaw / cursor / codebuddy / claude-desktop / other
testedWith: dolphin-mcp-pilot 0.2.0
channels:                        # one or more PUBLIC, non-login-walled links to your post(s)
  - https://www.xiaohongshu.com/REPLACE_ME
---

# <Title of your case>

> Replace this file with your story. Keep the frontmatter above and fill every field.
> Redact all tokens, passwords, `X-DS-*` values, internal hostnames/IPs, and private data
> in every screenshot before committing.

## The task

What were you actually trying to get done? One or two sentences. Make it concrete
("rerun a failed nightly ETL", not "explore the tools").

## Setup (brief)

- **MCP host**: e.g. Claude Code 1.x
- **dolphin-mcp-pilot**: version/commit (matches `testedWith`)
- **DolphinScheduler**: version, and whether it was local / staging / prod-like

## What happened

Tell the story. What did you ask the agent, and what did dolphin-mcp-pilot do? Show the
natural-language request and the tool call / result. Paste your screenshots or link a short
recording. If your case changes state (creates a workflow, fixes a schedule, reruns an
instance), show the before and after.

![the agent operating DolphinScheduler](preview.png)

## Why it mattered

What was faster, safer, or newly possible compared to doing it by hand in the DS console?

## Published post

Link to the public write-up(s) — these must match the `channels:` frontmatter:

- <https://www.xiaohongshu.com/REPLACE_ME>

## Notes / gotchas (optional)

Anything that tripped you up, or a tip for the next person.
