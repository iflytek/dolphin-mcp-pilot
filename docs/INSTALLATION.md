# 📦 Installation Guide

## Option A: Docker Compose (Recommended)

### A1. Development mode (recommended for now)

Builds from the local Dockerfile and mounts `./dolphin_mcp_pilot` into the container as read-only. Source changes require a container restart (uvicorn is not started with `--reload`):

```bash
# 1. Prepare environment
cp .env.example .env
# edit .env — at minimum set DS_URL and DS_TOKEN (see Configuration below)

# 2. Start (dev profile builds locally)
docker compose --profile dev up -d dolphin-mcp-pilot-dev

# 3. Verify
docker compose --profile dev ps        # STATUS should show (healthy) after ~10s
docker compose --profile dev logs -f   # watch startup logs
```

The service will be available at `http://localhost:8001/mcp/` (note the trailing slash).

### A2. Production mode (published image)

> **Note**: The `ghcr.io/iflytek/dolphin-mcp-pilot:latest` image is published automatically when a stable release tag (e.g. `v0.2.0`) is pushed. Until the first release is tagged, use **A1** or **Option B/C** below.

Once a release is available, the prod service pulls from ghcr.io:

```bash
# Optional: pin to a specific version
echo "IMAGE_TAG=0.2.0" >> .env

docker compose up -d
docker compose ps        # STATUS should show (healthy)
```

See [`docker-compose.yml`](../docker-compose.yml) for the full reference (resource limits, log rotation, healthcheck, etc.).

## Option B: From source

```bash
git clone https://github.com/iflytek/dolphin-mcp-pilot.git
cd dolphin-mcp-pilot
pip install -r requirements.txt
python -m dolphin_mcp_pilot
```

## Option C: Install as package

```bash
pip install .
dolphin-mcp-pilot
```

## 🏃 Run Modes

### stdio mode (for local AI tools)

```bash
python -m dolphin_mcp_pilot
```

### HTTP mode (for remote AI agents)

```bash
DS_MCP_TRANSPORT=http python -m dolphin_mcp_pilot
```

Or with Docker:

```bash
docker compose up -d
```

## 📦 Packaging & Distribution

Build wheel:

```bash
pip install build
python -m build
```

Install locally:

```bash
pip install .
```

Then run:

```bash
dolphin-mcp-pilot
```

---

← Back to [README](../README.md) | [Features](FEATURES.md) | [Configuration](CONFIGURATION.md) | [Deployment](DEPLOYMENT.md)
