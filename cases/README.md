# Dolphin MCP Pilot — Community Case Studies

A gallery of **real-world usage stories**: people driving Apache DolphinScheduler through an
AI agent via dolphin-mcp-pilot, written up here and shared publicly (Xiaohongshu / RED, X,
掘金, CSDN, 知乎, Bilibili, YouTube, a personal blog, …).

Where [`examples/`](../examples/README.md) collects reusable *client configurations*, `cases/`
collects *what people actually did with them* — the scenario, the conversation, the before/after,
and a link to the public post that tells the story.

[中文说明见下方](#中文)

---

## What a good case shows

A case is not a feature list — it is a short, honest story of a task you got done. The strongest
cases share three things:

1. **A concrete task**, not a demo for its own sake. "Our nightly ETL failed at 3am and I had the
   agent find the failed instances and rerun-from-failure from my phone" beats "I listed projects".
2. **The agent actually operating DolphinScheduler** — a screenshot or short recording where you
   can see the natural-language request and the dolphin-mcp-pilot tool call / result. Read-only
   listing is fine as a supporting shot, but the interesting cases *change state*
   (create a workflow, fix a schedule, rerun a failed run).
3. **A public post** other people can read, with the link recorded in your case file.

## Creative directions

Pick one angle (or combine a few). These map to what dolphin-mcp-pilot is actually good at — see
the tool list in the [main README](../README.md):

- **自然语言运维 / NL ops** — operate DolphinScheduler in plain language from an MCP host
  (Claude Code, OpenClaw, Cursor, CodeBuddy, Claude Desktop). "Pause the sales-pipeline schedule,
  I'm doing maintenance."
- **Incident firefighting** — an instance failed; use the agent to read task logs, force a task
  success / skip a stuck task, or rerun-from-failure — end to end, without opening the DS console.
- **One-line workflow creation** — turn a sentence or a SQL snippet into a real SQL / DAG workflow,
  then bring it online.
- **Schedule management by chat** — create / online / offline / delete cron schedules
  conversationally, e.g. "move the daily report to 7am on weekdays only".
- **Monitoring & morning-brief** — have the agent summarize last night's runs, surface failures,
  and propose reruns.
- **Version safety** — roll back a workflow version or clone a workflow before a risky change.
- **Multi-tenant / team** — show per-request auth (`X-DS-Token` or `X-DS-User`/`X-DS-Password`)
  letting different teammates drive the same server with their own DolphinScheduler credentials.
- **Host integration write-up** — a focused "how I wired dolphin-mcp-pilot into <MCP host>" walkthrough,
  with the gotchas you hit.
- **Before / after** — the same task done by hand in the DS web console vs. driven by the agent;
  what got faster or safer.

Bonus points for cases that combine dolphin-mcp-pilot with other tools in a real pipeline, or that
teach a non-obvious trick (e.g. using the raw-API passthrough as a safety valve).

## Requirements

To keep the gallery trustworthy, every submission must meet **all** of these:

1. **Real usage.** You actually ran dolphin-mcp-pilot against a DolphinScheduler instance. The case
   includes at least one screenshot or short recording showing the agent's request and the
   dolphin-mcp-pilot tool call / result. Mock-ups, staged screenshots, or unverified text do not
   qualify.
2. **A public post.** The story is published on at least one public channel with an
   openly reachable URL (no login-walled or private links). Record every link in the frontmatter
   `channels:` list. The post should be substantive — a few sentences plus a visual, not a bare
   repost of this repo's README.
3. **Original content.** Your own writing and screenshots. No plagiarism, no AI-generated text
   passed off as a firsthand account. If you used AI to help draft the post, that's fine — just
   keep the *events* real.
4. **No secrets.** Redact tokens, passwords, `X-DS-*` header values, internal hostnames/IPs, and
   any private business data in every screenshot and config snippet. Use obvious placeholders.
5. **This case file links back.** The `README.md` you submit here must link to the public post(s),
   so a reader can go from the gallery to the full story.

## How to submit

1. Fork this repository.
2. Copy `cases/TEMPLATE/` to `cases/<your-case-id>/` (short, unique, kebab-case, e.g.
   `nightly-etl-rerun`).
3. Fill in `README.md` — complete the frontmatter and every section, and paste your public link(s).
   Add `preview.png` (or more images) showing the agent operating DolphinScheduler.
4. Open a Pull Request. Suggested title:

   ```txt
   [case] <case-id> — <one-line what you did>
   ```

Multiple cases? One directory per case, one PR is fine.

## Directory layout

```text
cases/
├── README.md                 # this file — directions and requirements
├── TEMPLATE/
│   └── README.md             # copy this to start a case
└── <your-case-id>/
    ├── README.md             # required — frontmatter + the story + public links
    ├── preview.png           # required — the agent operating DolphinScheduler
    └── *.png / *.gif         # optional — more screenshots
```

## Frontmatter

Each case `README.md` starts with YAML frontmatter:

```yaml
---
title: Rerunning a failed nightly ETL from my phone
author: your-github-handle
date: 2026-08-14                # YYYY-MM-DD, when you published
category: incident-firefighting # one of the creative directions above
host: claude-code               # the MCP host you used (claude-code / openclaw / cursor / codebuddy / claude-desktop / other)
testedWith: dolphin-mcp-pilot 0.2.0
channels:                       # one or more PUBLIC links to your published post(s)
  - https://www.xiaohongshu.com/...
  - https://x.com/...
---
```

---

<a name="中文"></a>

# Dolphin MCP Pilot — 社区使用案例

一个**真实使用故事**画廊：用户通过 dolphin-mcp-pilot、借助 AI 智能体来操作 Apache
DolphinScheduler，把过程写在这里，并发布到公开渠道（小红书、X、掘金、CSDN、知乎、B 站、
YouTube、个人博客……）。

[`examples/`](../examples/README.md) 收录的是可复用的**客户端配置**，`cases/` 收录的是
**大家真正用它做成了什么**——场景、对话、前后对比，以及一条能读到完整故事的公开链接。

## 一个好案例长什么样

案例不是功能罗列，而是一个诚实的小故事：你用它把某件事做成了。最打动人的案例有三个共性：

1. **一个具体任务**，而非为演示而演示。"凌晨 3 点 ETL 挂了，我在手机上让智能体找到失败实例并
   从失败处重跑"，比"我列了一下项目列表"有力得多。
2. **智能体真的在操作 DolphinScheduler**——截图或短录屏里能看到自然语言请求 +
   dolphin-mcp-pilot 的工具调用/结果。只读列举可以作为辅助画面，但真正有意思的案例会**改变状态**
   （新建工作流、修调度、重跑失败实例）。
3. **一条公开帖子**，别人能读到，链接记录在你的案例文件里。

## 创作方向

任选一个角度（也可组合）。这些正好对应 dolphin-mcp-pilot 擅长的能力（见
[主 README](../README.zh-CN.md) 的工具清单）：

- **自然语言运维**——在 MCP 宿主（Claude Code、OpenClaw、Cursor、CodeBuddy、Claude Desktop）里
  用大白话操作 DolphinScheduler。"把销售管道的调度下线，我要做维护。"
- **故障救火**——某个实例失败了：让智能体读任务日志、强制任务成功 / 跳过卡住的任务、或从失败处
  重跑，全程不打开 DS 控制台。
- **一句话建工作流**——把一句话或一段 SQL 变成真正的 SQL / DAG 工作流并上线。
- **对话式调度管理**——会话式地 创建 / 上线 / 下线 / 删除 cron 调度，例如"把日报挪到工作日早 7 点"。
- **监控与晨报**——让智能体总结昨晚的运行、暴露失败项、并建议重跑。
- **版本安全**——高风险改动前回滚工作流版本或克隆工作流。
- **多租户 / 团队**——展示逐请求鉴权（`X-DS-Token` 或 `X-DS-User`/`X-DS-Password`），让不同同事
  用各自的 DolphinScheduler 凭据驱动同一个 server。
- **宿主接入手记**——一篇聚焦的"我如何把 dolphin-mcp-pilot 接进 <某 MCP 宿主>"，含踩过的坑。
- **前后对比**——同一个任务，DS 网页控制台手工做 vs 智能体驱动，快在哪、稳在哪。

加分项：把 dolphin-mcp-pilot 和真实流水线里的其他工具组合起来，或讲清一个不显而易见的技巧
（比如用 raw-API passthrough 当安全阀）。

## 要求

为了让画廊可信，每份提交必须**同时**满足：

1. **真实使用**。你确实对一个 DolphinScheduler 实例跑过 dolphin-mcp-pilot；案例含至少一张截图或
   一段短录屏，能看到智能体请求 + dolphin-mcp-pilot 工具调用/结果。臆造、摆拍、未经验证的文字不算。
2. **公开帖子**。故事发布在至少一个公开渠道、链接可直达（不能是需登录/私密链接）；每条链接写进
   frontmatter 的 `channels:`。帖子要有实质内容——几句话加一张图，而不是照抄本仓 README。
3. **原创**。自己的文字和截图，不抄袭，不拿 AI 生成的文字冒充第一手经历。用 AI 帮你润色文案没问题，
   但**发生的事情**要真实。
4. **不泄密**。每张截图和配置片段都要打码 token、密码、`X-DS-*` 头的值、内网域名/IP、以及任何私有
   业务数据，用明显的占位符替换。
5. **案例文件要回链**。你在这里提交的 `README.md` 必须链接到公开帖子，读者能从画廊跳到完整故事。

## 提交方式

1. Fork 本仓库。
2. 把 `cases/TEMPLATE/` 复制成 `cases/<你的案例 id>/`（简短、唯一、kebab-case，如
   `nightly-etl-rerun`）。
3. 填写 `README.md`——补全 frontmatter 和每个小节，贴上公开链接；加一张 `preview.png`（或更多图）
   展示智能体在操作 DolphinScheduler。
4. 发起 Pull Request。建议标题：

   ```txt
   [case] <案例 id> — <一句话你做了什么>
   ```

多个案例？一个案例一个目录，放在一个 PR 里也可以。

## 目录结构与 frontmatter

见上文英文部分的 *Directory layout* 与 *Frontmatter*。字段含义一致，`category` 取上面某个创作方向，
`channels` 至少一条公开链接。
