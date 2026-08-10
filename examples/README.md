# Dolphin MCP Pilot Examples

A community-contributed gallery of reusable **dolphin-mcp-pilot client configurations**. Each
community example is documented, validated, and ready to adapt for a supported MCP client or
deployment mode.

> **Built-in configurations vs. community examples** — the JSON files at the root of this
> directory are maintained by the project. New community contributions use one self-contained
> directory per example so their requirements, testing notes, and authorship stay with the config.

[中文贡献指南见下方](#中文)

## Included configurations

- [`codebuddy-config.json`](codebuddy-config.json) — CodeBuddy over HTTP with token authentication.
- [`claude-desktop-config.json`](claude-desktop-config.json) — Claude Desktop over stdio with Docker.
- [`http-auth-token.json`](http-auth-token.json) — HTTP transport with a DolphinScheduler API token.
- [`http-auth-password.json`](http-auth-password.json) — HTTP transport with username/password authentication.

Replace every `your_*` or `YOUR_*` placeholder before using a configuration. For HTTP examples,
also update the server URL and keep the trailing `/` in `/mcp/`. See the
[deployment guide](../docs/DEPLOYMENT.md) for server setup and HTTPS guidance.

## What a community example contains

Use a short, unique kebab-case id for the directory:

```text
examples/
├── README.md                  # this file — format and contribution guide
├── TEMPLATE/                  # copy this to start a contribution
│   ├── README.md              # metadata plus setup and testing notes
│   └── config.json            # sanitized MCP client configuration
├── scripts/
│   └── lint.py                # dependency-free validation
└── <example-id>/
    ├── README.md              # required — metadata and instructions
    ├── config.json            # required — valid, sanitized JSON
    └── preview.png            # optional — screenshot of the working client
```

- **`config.json`** must be a complete MCP client configuration with a non-empty `mcpServers`
  object. Replace credentials, private hosts, and personal paths with obvious placeholders.
- **`README.md`** contains YAML frontmatter for automated validation followed by setup, test, and
  compatibility notes.
- **`preview.png`** is optional, but useful when the client has a visual MCP configuration screen.

## Metadata (README frontmatter)

```yaml
---
id: my-client-example                 # unique, kebab-case, matches the directory name
title: My MCP Client Example          # display name
description: One-sentence summary of the configuration.
client: claude-desktop                # client name; use other for an unlisted client
transport: http                       # http | stdio
authentication: token                 # token | password | none | other
author: your-github-handle            # contributor's GitHub username
testedWith: dolphin-mcp-pilot 0.2.0   # version or commit used for validation
sourceUrl: ''                         # optional blog post, video, or discussion
---
```

The body should explain prerequisites, where to place the configuration, which placeholders to
replace, how the example was tested, and any known limitations.

## How to contribute

1. **Copy the template:** `cp -r examples/TEMPLATE examples/<your-example-id>`
2. **Add your configuration:** replace `config.json` with the tested client configuration.
3. **Fill the metadata and instructions:** update `README.md`, including the exact version tested.
4. **Scrub secrets:** remove tokens, passwords, private hosts, internal IPs, and personal paths.
5. **Run the validator:** `python examples/scripts/lint.py`
6. **Open a pull request against `main`:**

   ```bash
   git checkout -b examples/<your-example-id>
   git add examples/<your-example-id>
   git commit -s -m 'examples: add <your-example-id>'
   git push origin examples/<your-example-id>
   ```

The `-s` flag adds the DCO sign-off required for contributions.

### Quality bar

An example is ready to merge when it:

- Uses a unique kebab-case `id` that matches its directory name.
- Contains valid JSON with a non-empty `mcpServers` object.
- Has been tested with the stated dolphin-mcp-pilot version or commit.
- Contains no live credentials, private/internal endpoints, or user-specific filesystem paths.
- Clearly explains setup, placeholders, verification steps, and external requirements.
- Passes `python examples/scripts/lint.py` and the repository CI checks.

---

<a id='中文'></a>

## 中文

这里是社区共建的 **dolphin-mcp-pilot 客户端配置示例库**。目录根部的 JSON 文件由项目维护；
新的社区示例采用“一示例一目录”，以便同时保存配置、说明、测试版本和作者信息。

### 目录规范

复制 `examples/TEMPLATE` 为 `examples/<示例-id>`。示例 id 使用小写短横线格式，并包含：

- **`config.json`（必需）**：完整、可解析且已清理敏感信息的 MCP 客户端配置。
- **`README.md`（必需）**：保留模板中的 YAML frontmatter，并写明安装、占位符和验证步骤。
- **`preview.png`（可选）**：客户端配置界面或运行结果截图。

### 如何贡献

1. 复制模板：`cp -r examples/TEMPLATE examples/<示例-id>`
2. 替换并验证 `config.json`
3. 填写 `README.md` 元数据、安装方法和实际测试版本
4. **清理密钥和隐私信息**：token、密码、内部 IP、私有域名及个人路径必须改为占位符
5. 运行：`python examples/scripts/lint.py`
6. 向 `main` 提交 PR，commit 使用 `-s` 添加 DCO 签名

### 合并门槛

- id 唯一、使用小写短横线格式，并与目录名一致
- JSON 有效且包含非空的 `mcpServers`
- 已在注明的 dolphin-mcp-pilot 版本或 commit 上测试
- 不含真实凭据、内部地址或个人文件路径
- 说明清晰，并通过 examples lint 与仓库 CI
