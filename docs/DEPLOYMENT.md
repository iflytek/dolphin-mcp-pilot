# 🚀 Deployment Guide

Production and development deployment guide for **dolphin-mcp-pilot**.

## 📋 Prerequisites

- **Docker** 20.10+ and **Docker Compose** v2 (the `docker compose` command)
- Access to a running **DolphinScheduler** instance (3.x recommended)
- DolphinScheduler API token or username/password

## ⚡ Quick Start (3 steps)

### 1. Clone the repository

```bash
git clone https://github.com/iflytek/dolphin-mcp-pilot.git
cd dolphin-mcp-pilot
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env — at minimum set DS_URL and DS_TOKEN (or DS_USER/DS_PASSWORD)
```

See [Configuration](CONFIGURATION.md) for the full environment variable reference.

### 3. Start the service

**Development mode** (recommended — builds locally):
```bash
docker compose --profile dev up -d dolphin-mcp-pilot-dev
```

**Production mode** (pulls from ghcr.io — requires a release tag to be available):
```bash
docker compose up -d
```

✅ Service will be available at `http://localhost:8001/mcp/` (note the trailing slash)

The endpoint serves MCP 2.0's stateless `2026-07-28` protocol and remains
compatible with MCP 1.x clients. Because the HTTP transport keeps no
`Mcp-Session-Id` state, requests can be distributed across replicas without
session affinity.

## 🐳 Docker Compose Reference

The [`docker-compose.yml`](../docker-compose.yml) provides two services that share configuration via YAML anchors (`x-common`):

### Development mode (`--profile dev`)

Builds from the local Dockerfile and mounts `./dolphin_mcp_pilot` as read-only. Source changes require a container restart (uvicorn is not started with `--reload`).

```bash
docker compose --profile dev up -d dolphin-mcp-pilot-dev
docker compose --profile dev ps        # STATUS should show (healthy) after ~10s
docker compose --profile dev logs -f   # watch startup logs
```

### Production mode (default)

Pulls the published multi-arch image from `ghcr.io/iflytek/dolphin-mcp-pilot:${IMAGE_TAG:-latest}`.

> **Note**: The `latest` tag is only created when a stable release tag (e.g. `v0.2.0`) is pushed. Until the first release is tagged, use dev mode.

```bash
# Optional: pin to a specific version
echo "IMAGE_TAG=0.2.0" >> .env

docker compose up -d
docker compose ps        # STATUS should show (healthy)
```

### Port convention

The container always listens on **8001** internally (matching the Dockerfile `HEALTHCHECK`). The `MCP_PORT` variable in `.env` controls only the **host-side** port mapping:

```bash
# .env
MCP_PORT=9000    # host:9000 → container:8001
```

The compose file's `environment:` block explicitly sets `MCP_PORT: "8001"` inside the container to prevent the host-side value from leaking in.

### Built-in configuration

The default `docker-compose.yml` already includes:

- **Healthcheck**: stdlib socket probe on `127.0.0.1:8001` (30s interval, 5s timeout, 10s start period, 3 retries)
- **Log rotation**: `json-file` driver, `max-size: 10m`, `max-file: 3`
- **Resource limits**: `cpus: 1.0 / memory: 512M` limits, `0.25 / 128M` reservations
- **Non-root runtime**: `uid=1001 gid=1001`

All values are tunable via `.env` variables (`LOG_MAX_SIZE`, `CPU_LIMIT`, `MEMORY_LIMIT`, etc.). See [Configuration](CONFIGURATION.md) for the full list.

## 🔍 Verify Deployment

### Test legacy MCP compatibility

```bash
curl -X POST http://localhost:8001/mcp/ \
  -H "X-DS-Token: your_token" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"curl","version":"1"}}}'
```

Expected: an SSE `data:` line containing `"serverInfo":{"name":"DolphinScheduler",...}`

MCP 2.0 clients use `server/discover` instead of this legacy initialize
handshake; both paths are exercised in CI.

> **Note**: URL must end with `/`. Without it, Starlette returns HTTP 307 redirect, which some MCP clients fail to follow.

### View logs

```bash
docker compose logs -f
```

### Check container status

```bash
docker compose ps
```

## 🔧 Configuration Details

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DS_URL` | ✅ Yes | - | DolphinScheduler API base URL |
| `DS_TOKEN` | ⚠️ Recommended | - | API token (DolphinScheduler 3.x+) |
| `DS_USER` | ⚠️ If no token | - | Username (fallback auth) |
| `DS_PASSWORD` | ⚠️ If no token | - | Password (fallback auth) |
| `DS_TENANT_CODE` | ❌ No | `default` | Tenant code for workflow creation |
| `DS_MCP_TRANSPORT` | ❌ No | `http` | Transport mode: `stdio` or `http` |
| `MCP_HOST` | ❌ No | `0.0.0.0` | HTTP server bind address |
| `MCP_PORT` | ❌ No | `8001` | Host-side port (container always uses 8001) |

### Getting DolphinScheduler API Token

1. Log in to DolphinScheduler Web UI
2. Navigate to **User Center** → **Token Management**
3. Click **Create Token**
4. Set expiration date and generate
5. Copy the token to your `.env` file

## 🔌 Client Configuration

See [Client Configuration](CLIENT_CONFIG.md) for MCP client setup (CodeBuddy, Claude Desktop, etc.) and multi-tenant per-request auth.

## 🐛 Troubleshooting

### Container won't start

**Check logs:**
```bash
docker compose logs
```

**Common issues:**
- Missing `.env` file → Copy from `.env.example`
- Invalid `DS_URL` → Verify DolphinScheduler is accessible
- Port 8001 already in use → Change `MCP_PORT` in `.env`

### Connection refused

**Verify DolphinScheduler is reachable:**
```bash
curl http://your-ds-host:12345/dolphinscheduler/ui
```

**Check network:**
- If DolphinScheduler is on `localhost`, use `host.docker.internal` in Docker
- Ensure firewall allows connections

### Authentication failed

**Token mode:**
- Verify token is valid and not expired
- Check token has correct permissions

**Username/password mode:**
- Verify credentials are correct
- Check user account is not locked

### Tools not working

**Check DolphinScheduler version:**
- This MCP server is tested with DolphinScheduler 3.x
- Some APIs may differ in 2.x versions

**Verify permissions:**
- User/token must have appropriate project permissions
- Some operations require admin privileges

### Healthcheck failing

- Container port is always 8001 internally — verify nothing else overrides `MCP_PORT` inside the container
- Check `docker compose ps` for health status details
- If the app hasn't started yet, wait for the `start_period` (10s)

## 🔄 Updates

### Pull latest changes

```bash
git pull origin main
docker compose down
docker compose --profile dev up -d --build   # dev mode
# or
docker compose pull && docker compose up -d  # prod mode
```

### View changelog

```bash
git log --oneline
```

## 🛑 Stop Service

```bash
docker compose down
docker compose --profile dev down   # also stop dev service
```

To remove volumes as well:
```bash
docker compose down -v
```

## 📦 Production Deployment

### Use published Docker image

```yaml
services:
  dolphin-mcp-pilot:
    image: ghcr.io/iflytek/dolphin-mcp-pilot:latest
    # See docker-compose.yml for full production config
```

### Enable HTTPS

Use a reverse proxy (nginx, Caddy, Traefik) in front of the service:

```nginx
server {
    listen 443 ssl;
    server_name mcp.yourdomain.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    location /mcp {
        proxy_pass http://localhost:8001;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
    }
}
```

## 📞 Support

- **Issues**: https://github.com/iflytek/dolphin-mcp-pilot/issues
- **Discussions**: https://github.com/iflytek/dolphin-mcp-pilot/discussions
- **DolphinScheduler Docs**: https://dolphinscheduler.apache.org/

## 📄 License

Apache-2.0

---

← Back to [README](../README.md) | [Installation](INSTALLATION.md) | [Configuration](CONFIGURATION.md)
