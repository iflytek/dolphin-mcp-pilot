# E2E Integration Tests

End-to-end tests that boot a full DolphinScheduler + dolphin-mcp-pilot stack
using docker-compose and exercise the MCP server through its public HTTP/SSE
transport.

## Overview

The suite validates the *entire* user journey: a real DolphinScheduler
standalone server (all-in-one with embedded database) and a real
dolphin-mcp-pilot container — all running via docker-compose. pytest drives
the MCP client through the same HTTP endpoints that production AI agents
will hit, so a green e2e run is strong evidence that the system works
end-to-end.

```
┌────────────────────┐        ┌──────────────────────────────────────┐
│  pytest (host)     │        │  docker-compose                      │
│                    │        │  ┌────────────────────────────────┐  │
│  E2E_DS_PORT ──────┼───────▶│  │ dolphinscheduler-standalone    │  │
│                    │ 12345  │  │ (API + Master + Worker + DB)   │  │
│  E2E_PILOT_PORT ───┼───────▶│  │                    :12345      │  │
│                    │ 18001  │  └────────────────────────────────┘  │
│                    │        │  ┌────────────────────────────────┐  │
│                    │        │  │ dolphin-mcp-pilot      :8001   │  │
│                    │        │  └────────────────────────────────┘  │
└────────────────────┘        └──────────────────────────────────────┘
```

## Prerequisites

| Requirement      | Minimum version | Notes                                          |
|------------------|-----------------|------------------------------------------------|
| Docker           | 20.10           | Required for running containers.               |
| docker-compose   | 2.0             | Standalone or Docker Compose plugin.           |
| Python           | 3.10            | `pytest`, `pytest-timeout`.                    |
| RAM              | 3 GB free       | DS standalone uses ~1.5 GB with optimized JVM. |
| Disk             | 5 GB free       | Docker images.                                 |

## Quick Start

### One-command full pipeline

```bash
bash scripts/e2e/run-e2e.sh
```

This will:

1. Stop any existing e2e services
2. Start DolphinScheduler standalone server
3. Wait for DolphinScheduler to become healthy (~2-3 minutes)
4. Verify DS login with admin credentials
5. Start dolphin-mcp-pilot
6. Run the pytest suite
7. Tear down all services

### Keep the services alive for debugging

```bash
bash scripts/e2e/run-e2e.sh --skip-teardown
```

After the run you can inspect the services:

```bash
docker compose -f tests/e2e/deploy/docker-compose.yml ps
docker compose -f tests/e2e/deploy/docker-compose.yml logs dolphinscheduler
docker compose -f tests/e2e/deploy/docker-compose.yml logs dolphin-mcp-pilot
```

When done, tear them down manually:

```bash
docker compose -f tests/e2e/deploy/docker-compose.yml down -v
```

## Manual Steps

If you prefer to walk through the pipeline step-by-step:

```bash
# 1. Stop any existing services.
docker compose -f tests/e2e/deploy/docker-compose.yml down -v

# 2. Start DolphinScheduler standalone.
docker compose -f tests/e2e/deploy/docker-compose.yml up -d dolphinscheduler

# 3. Wait for DS to become healthy (typically 2-3 minutes).
# The healthcheck will report healthy when the API is ready.
docker compose -f tests/e2e/deploy/docker-compose.yml ps

# 4. Verify DS login.
curl -sf -X POST "http://localhost:12345/dolphinscheduler/login" \
  -d "userName=admin&userPassword=dolphinscheduler123"

# 5. Start dolphin-mcp-pilot.
docker compose -f tests/e2e/deploy/docker-compose.yml up -d dolphin-mcp-pilot

# 6. Wait for pilot to become healthy.
docker compose -f tests/e2e/deploy/docker-compose.yml ps

# 7. Run the tests.
E2E_DS_PORT=12345 E2E_PILOT_PORT=18001 \
  python -m pytest tests/e2e/ -v --tb=short --timeout=300

# 8. Tear down.
docker compose -f tests/e2e/deploy/docker-compose.yml down -v
```

## Test Scenarios

The pytest suite under `tests/e2e/` is organised into four categories:

| # | Category         | What it covers                                                |
|---|------------------|---------------------------------------------------------------|
| 1 | **Smoke**        | Tool catalog listing, `ds_help`, MCP protocol handshake       |
| 2 | **Auth**         | Username/password login, multi-tenant isolation               |
| 3 | **Project CRUD** | Create project → list → delete                                |
| 6 | **Negative**     | Bad credentials, unknown tool, malformed JSON, server health  |

Each category lives in its own file (`test_01_smoke.py`, `test_02_auth.py`, etc.)
so failures can be triaged by category.

**Note**: Test files 04 and 05 (Schedule and Instance tests) are not yet
implemented because the standalone DS server returns HTTP 405 for workflow
endpoints. These tests will be added when a full DS cluster setup is available.

## Environment Variables

All variables have sensible defaults; you only need to set them when running
a non-standard configuration (e.g. different ports).

| Variable          | Default                | Description                            |
|-------------------|------------------------|----------------------------------------|
| `E2E_DS_PORT`     | `12345`                | Host port mapped to DS API.            |
| `E2E_PILOT_PORT`  | `18001`                | Host port mapped to pilot.             |
| `E2E_DS_USER`     | `admin`                | DS login username.                     |
| `E2E_DS_PASSWORD` | `dolphinscheduler123`  | DS login password (default admin).     |
| `E2E_DS_URL`      | (constructed)          | Explicit DS URL (skips port construct).|
| `E2E_PILOT_URL`   | (constructed)          | Explicit pilot URL (skips port).       |
| `DS_VERSION`      | `3.4.2`                | DolphinScheduler Docker image version. |
| `LOG_DIR`         | `/tmp`                 | Where `e2e-*.log` artifacts land.      |

## Known Limitations

- **Token auth** — `X-DS-Token` header authentication is accepted by the
  middleware but not consumed by `client.py`; only session-based login is
  fully exercised.
- **Workflow/Instance tests** — The standalone DS server does not expose
  workflow CRUD or process instance endpoints (returns HTTP 405). These
  tests require a full DS cluster setup.
- **Memory usage** — The DS standalone server uses significant memory. The
  docker-compose configuration sets `JAVA_OPTS` to `-Xms512m -Xmx2g`
  (default 4g causes OOM on memory-constrained systems).
- **macOS Docker Desktop** users may need to increase the file-handle limit:
  `ulimit -n 10240` before running the suite.
- **Startup time** — DolphinScheduler standalone typically takes 2-3 minutes
  to become healthy on first start.

## CI Integration

The pipeline runs automatically on every push and pull request to `main` or
`dev` via `.github/workflows/e2e.yml`. Highlights:

- **Concurrency** — one run per branch; older runs are cancelled on new push.
- **Caching** — pip dependencies are cached between runs to keep the workflow
  fast.
- **Timeout** — 15 minute timeout to prevent hung runs.
- **Artifacts** — on failure, all `/tmp/e2e-*.log` files are uploaded for
  7 days for offline diagnosis.
- **Cleanup** — docker-compose services are always torn down in the final
  step, even on cancellation, to free runner resources.

To re-run a failed job without pushing a new commit, use the
*Re-run failed jobs* button in the GitHub Actions UI, or trigger a manual
run via `workflow_dispatch`.
