# 🔐 Client Configuration

## CodeBuddy / Claude Desktop (HTTP mode)

Add to your MCP client config:

```json
{
  "mcpServers": {
    "dolphinscheduler": {
      "type": "sse",
      "url": "http://localhost:8001/mcp/",
      "headers": {
        "X-DS-Token": "your_api_token"
      }
    }
  }
}
```

> ⚠️ The URL **must end with `/`**. Without the trailing slash, Starlette returns a 307 redirect, which some MCP clients fail to follow.

## Example Configurations

More examples in the [`examples/`](../examples/) directory:

- `codebuddy-config.json` — CodeBuddy configuration
- `claude-desktop-config.json` — Claude Desktop stdio mode
- `http-auth-token.json` — HTTP with token auth
- `http-auth-password.json` — HTTP with username/password

## Multi-Tenant Per-Request Auth

In HTTP mode, each caller can pass their own credentials:

**Token mode (preferred):**
```
X-DS-Token: your_api_token
```

**Username/password mode:**
```
X-DS-User: alice
X-DS-Password: alice_password
```

This enables multi-tenant scenarios where different AI agents or users operate with different DolphinScheduler credentials through the same MCP server instance.

---

← Back to [README](../README.md) | [Configuration](CONFIGURATION.md) | [Deployment](DEPLOYMENT.md) | [API Reference](API.md)
