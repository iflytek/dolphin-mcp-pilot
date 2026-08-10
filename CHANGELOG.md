# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Added

- **Release workflow** (`.github/workflows/release.yml`): publishes multi-arch (`linux/amd64` + `linux/arm64`) images to `ghcr.io/iflytek/dolphin-mcp-pilot`
  - `push` tag `v*.*.*` → semver tags (`<version>`, `<major>.<minor>`, `<major>`) + `latest` on stable releases
  - `push` to `main` → `:<git-sha-long>` traceable pre-release builds
  - `pull_request` → build-only (catches Dockerfile breakage without publishing)
  - `workflow_dispatch` → manual runs with optional tag override
- **Docker HEALTHCHECK**: stdlib-socket probe against `127.0.0.1:8001` (30s interval, 5s timeout, 10s start period, 3 retries) — zero extra dependencies
- **OCI metadata labels**: `org.opencontainers.image.{title,description,licenses}` set in the image for catalog indexing

### Changed

- **Multi-stage Docker build**: dependencies installed into a venv in the `builder` stage and copied into the slim runtime stage — image content size drops to ~60MB
- **Non-root runtime**: container now runs as `dolphin_mcp` (UID/GID `1001:1001`) with source files `COPY --chown`-ed at build time
- **Leaner build context**: `.dockerignore` now excludes `tests/`, `docs/`, `examples/`, `scripts/`, `.github/`, `.claude/`, `.ruff_cache/`, and cache directories
- **CI bumps**: `actions/checkout` v4 → v7, `actions/setup-python` v5 → v7 (Dependabot)

### Fixed

- **Package metadata**: replaced stale `your-org` placeholder with `iflytek` in `pyproject.toml` and `README*.md` URLs
- **Setuptools deprecations**: migrated `project.license` from deprecated TOML table `{ text = "Apache-2.0" }` to SPDX string `"Apache-2.0"`; removed `License :: OSI Approved :: Apache Software License` classifier; bumped `setuptools>=68` → `setuptools>=77`

### Docker Compose upgrade (issue #11)

- **`docker-compose.yml`** rewritten as a production-ready reference:
  - Default `dolphin-mcp-pilot` service pulls from `ghcr.io/iflytek/dolphin-mcp-pilot:${IMAGE_TAG:-latest}`
  - `dolphin-mcp-pilot-dev` service under `profiles: ["dev"]` builds from local Dockerfile and mounts `./dolphin_mcp_pilot` read-only
  - Explicit `healthcheck`, `logging` (json-file, `max-size`/`max-file`), and `deploy.resources` (CPU/memory limits + reservations)
  - Shared config factored via YAML anchors (`x-common`) to keep prod and dev in sync
  - Container port fixed at 8001 (matches Dockerfile HEALTHCHECK); `MCP_PORT` only controls host-side port mapping
- **`.env.example`** extended with Compose-tunable variables: `IMAGE_TAG`, `LOG_MAX_SIZE`, `LOG_MAX_FILE`, `CPU_LIMIT`, `MEMORY_LIMIT`, `CPU_RESERVATION`, `MEMORY_RESERVATION`
- **`README.md` / `README.zh-CN.md`** Option A rewritten as a Docker Compose quickstart (prepare `.env` → `docker compose up` → verify `healthy`); dev mode documented alongside

---

## [0.2.0] - 2026-07-29

### Added

- **Guided troubleshooting**: `ds_list_process_instances` now attaches a `next_action` hint to RUNNING/FAILURE instances, pointing agents to `ds_list_task_instances` for detailed node inspection (v2.0.19)
- **58 tools** covering all DolphinScheduler operations (up from 53 in v0.1.0)
- **Navigational help**: `ds_help()` tool for category-based tool discovery
- **Raw API passthrough**: 4 tools (GET/POST/PUT/DELETE) for uncovered scenarios

### Changed

- **Reliable serial backfill**: `ds_complement_data` with `RUN_MODE_SERIAL` now uses `complementStartDate`/`complementEndDate` range format to ensure day-by-day execution order (v2.0.18)
- **Flexible task updates**: `ds_update_task_param` accepts both `snake_case` and `camelCase` field names (e.g., `pre_statements` or `preStatements`) (v2.0.17)
- **Enhanced timeout control**: Added missing timeout fields (`timeout`, `timeoutFlag`, `timeoutNotifyStrategy`) to `ds_update_task_param` (v2.0.17)

### Fixed

- **Backfill ordering bug**: Serial complement data no longer generates instances in random order (v2.0.18)
- **Field compatibility**: Resolved issues with `preStatements` field name variations (v2.0.17)

### Documentation

- Migrated to standard open source project structure
- Added `CONTRIBUTING.md` with contribution guidelines
- Added `OWNERS` file for project governance
- Reorganized docs into `docs/` directory
- Enhanced README with Landscape ecosystem attribution

---

## [0.1.0] - 2025-12-xx

### Added

- Initial release with 53+ tools
- Support for stdio / SSE / HTTP transports
- Dual authentication modes (header token / username+password)
- Docker and docker-compose deployment
- Examples for Claude Desktop and CodeBuddy integration

---

## Version Numbering

- **Major version (X.0.0)**: Breaking API changes
- **Minor version (0.X.0)**: New features, backward compatible (quarterly)
- **Patch version (0.0.X)**: Bug fixes, backward compatible (monthly)
