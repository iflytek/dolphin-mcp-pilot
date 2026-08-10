# ⚙️ Configuration

Create a `.env` file from [`.env.example`](../.env.example).

## Required

```bash
DS_URL=http://your-dolphinscheduler-host:12345/dolphinscheduler
```

## Authentication Options

### Option A: API Token (recommended)

```bash
DS_TOKEN=your_api_token
```

Get token from DolphinScheduler: **User Center → Token Management**

### Option B: Default username/password

```bash
DS_USER=your_username
DS_PASSWORD=your_password
```

## Optional

```bash
DS_TENANT_CODE=default          # Tenant code for workflow creation
DS_MCP_TRANSPORT=http           # "stdio" or "http"
MCP_HOST=0.0.0.0                # HTTP bind host
MCP_PORT=8001                   # HTTP bind port (host-side only in Docker Compose)
```

## Docker Compose Variables

When using Docker Compose, these additional variables are available in `.env`:

```bash
IMAGE_TAG=latest                # Published image tag (prod mode)
LOG_MAX_SIZE=10m                # Per-container log rotation max size
LOG_MAX_FILE=3                  # Per-container log rotation max files
CPU_LIMIT=1.0                   # CPU limit
MEMORY_LIMIT=512M               # Memory limit
CPU_RESERVATION=0.25            # CPU reservation
MEMORY_RESERVATION=128M         # Memory reservation
```

See [`docker-compose.yml`](../docker-compose.yml) for the full reference.

---

← Back to [README](../README.md) | [Features](FEATURES.md) | [Installation](INSTALLATION.md) | [Deployment](DEPLOYMENT.md)
