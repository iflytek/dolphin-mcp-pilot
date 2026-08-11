# E2E Integration Tests

End-to-end tests that boot a full DolphinScheduler + dolphin-mcp-pilot stack
inside a local [kind](https://kind.sigs.k8s.io/) cluster and exercise the MCP
server through its public HTTP/SSE transport.

## Overview

The suite validates the *entire* user journey: a real DolphinScheduler API
server, a real PostgreSQL database, a real ZooKeeper ensemble, and a real
dolphin-mcp-pilot pod — all running in Kubernetes. pytest drives the MCP
client through the same HTTP endpoints that production AI agents will hit,
so a green e2e run is strong evidence that the system works end-to-end.

```
┌────────────────────┐        ┌──────────────────────────────────────┐
│  pytest (host)     │──pf──▶ │  kind cluster "dolphin-mcp-e2e"      │
│                    │ 12345  │  ┌──────────────────────────────┐    │
│  E2E_DS_PORT ──────┼───────▶│  │ dolphinscheduler-api :12345 │    │
│  E2E_PILOT_PORT ───┼──pf───▶│  └──────────────────────────────┘    │
│                    │ 18001  │  ┌──────────────────────────────┐    │
│                    │        │  │ dolphin-mcp-pilot    :8001  │    │
│                    │        │  └──────────────────────────────┘    │
│                    │        │  postgres · zookeeper · master ·     │
│                    │        │  worker · alert                      │
└────────────────────┘        └──────────────────────────────────────┘
```

## Prerequisites

| Requirement | Minimum version | Notes |
|-------------|-----------------|-------|
| Docker      | 20.10           | kind runs containers as nodes. |
| Python      | 3.10            | `pytest`, `pytest-timeout`. |
| RAM         | 4 GB free       | The full DS stack uses ~1.5 GB. |
| Disk        | 10 GB free      | Docker images + kind node image. |

The scripts install `kind`, `kubectl`, and `helm` automatically into
`.bin/` at the repo root — you do not need to install them manually.

## Quick Start

### One-command full pipeline

```bash
bash scripts/e2e/run-e2e.sh
```

This will:

1. Provision a fresh kind cluster
2. Build the pilot image and load it into kind
3. Install DolphinScheduler via Helm (chart v1.4.3)
4. Deploy dolphin-mcp-pilot
5. Run the pytest suite
6. Tear down the cluster

### Keep the cluster alive for debugging

```bash
bash scripts/e2e/run-e2e.sh --skip-teardown
```

After the run you can inspect the cluster:

```bash
export PATH="$PWD/.bin:$PATH"
kubectl -n dolphinscheduler get pods
kubectl -n dolphinscheduler logs -l app=dolphin-mcp-pilot
```

When done, tear it down manually:

```bash
kind delete cluster --name dolphin-mcp-e2e
```

## Manual Steps

If you prefer to walk through the pipeline step-by-step:

```bash
# 1. Provision the cluster (installs kind/kubectl/helm on first run).
bash scripts/e2e/setup-kind.sh

# 2. Build and load the pilot image.
docker build -t dolphin-mcp-pilot:e2e -f Dockerfile .
kind load docker-image dolphin-mcp-pilot:e2e --name dolphin-mcp-e2e

# 3. Install DolphinScheduler.
export PATH="$PWD/.bin:$PATH"
kubectl create namespace dolphinscheduler --dry-run=client -o yaml | kubectl apply -f -
helm repo add dolphinscheduler https://apache.jfrog.io/artifactory/dolphinscheduler
helm repo update dolphinscheduler
helm upgrade --install dolphinscheduler dolphinscheduler/dolphinscheduler \
  -n dolphinscheduler \
  --version 1.4.3 \
  -f tests/e2e/deploy/dolphinscheduler-values.yaml \
  --wait --timeout 600s

# 4. Wait for DS pods (typically 3–8 minutes on kind).
kubectl wait --for=condition=ready pod \
  -l app=dolphinscheduler -n dolphinscheduler --timeout=600s

# 5. Port-forward the DS API.
kubectl port-forward -n dolphinscheduler svc/dolphinscheduler-api 12345:12345 &

# 6. Deploy the pilot.
kubectl apply -n dolphinscheduler -f tests/e2e/deploy/dolphin-mcp-pilot.yaml
kubectl wait --for=condition=ready pod \
  -l app=dolphin-mcp-pilot -n dolphinscheduler --timeout=120s

# 7. Port-forward the pilot.
kubectl port-forward -n dolphinscheduler svc/dolphin-mcp-pilot 18001:8001 &

# 8. Run the tests.
E2E_DS_PORT=12345 E2E_PILOT_PORT=18001 \
  python -m pytest tests/e2e/ -v --tb=short --timeout=300
```

## Test Scenarios

The pytest suite under `tests/e2e/` is organised into six categories:

| # | Category         | What it covers |
|---|------------------|----------------|
| 1 | **Smoke**        | Tool catalog listing, `ds_help`, MCP protocol handshake |
| 2 | **Auth**         | Username/password login, multi-tenant isolation |
| 3 | **Workflow CRUD**| Create project → create workflow → list → delete |
| 4 | **Schedule**     | Create schedule → online → offline → delete |
| 5 | **Instance**     | Trigger run → pause → resume → rerun |
| 6 | **Negative**     | Bad credentials, unknown tool, malformed JSON |

Each category lives in its own file (`test_smoke.py`, `test_auth.py`, etc.)
so failures can be triaged by category.

## Environment Variables

All variables have sensible defaults; you only need to set them when running
a non-standard configuration (e.g. an existing cluster on a different port).

| Variable          | Default                | Description |
|-------------------|------------------------|-------------|
| `E2E_DS_PORT`     | `12345`                | Host port forwarded to DS API. |
| `E2E_PILOT_PORT`  | `18001`                | Host port forwarded to pilot. |
| `E2E_DS_USER`     | `admin`                | DS login username. |
| `E2E_DS_PASSWORD` | `dolphinscheduler123`  | DS login password (default admin). |
| `CLUSTER_NAME`    | `dolphin-mcp-e2e`      | kind cluster name. |
| `NAMESPACE`       | `dolphinscheduler`     | Kubernetes namespace. |
| `DS_CHART_VERSION`| `1.4.3`                | DolphinScheduler Helm chart version. |
| `LOG_DIR`         | `/tmp`                 | Where `e2e-*.log` artifacts land. |

## Known Limitations

- **Token auth** — `X-DS-Token` header authentication is not yet implemented
  in the MCP client; only session-based login is exercised.
- **Instance control tests** require the DS worker to be fully ready; on slow
  CI machines the first worker registration can take 60–90 s after the pod
  reports `Ready`.
- **DS Helm chart startup** typically takes 5–10 minutes on kind even with
  the reduced resource limits in `tests/e2e/deploy/dolphinscheduler-values.yaml`.
- **macOS Docker Desktop** users may need to increase the file-handle limit:
  `ulimit -n 10240` before running the suite.

## CI Integration

The pipeline runs automatically on every push and pull request to `main` or
`dev` via `.github/workflows/e2e.yml`. Highlights:

- **Concurrency** — one run per branch; older runs are cancelled on new push.
- **Caching** — pip dependencies and the `.bin/` toolchain directory are
  cached between runs to keep the workflow under 15 minutes.
- **Artifacts** — on failure, all `/tmp/e2e-*.log` and `/tmp/e2e-*.txt`
  files are uploaded for 7 days for offline diagnosis.
- **Cleanup** — the kind cluster is always deleted in the final step, even
  on cancellation, to free runner disk space.

To re-run a failed job without pushing a new commit, use the
*Re-run failed jobs* button in the GitHub Actions UI, or trigger a manual
run via `workflow_dispatch`.
