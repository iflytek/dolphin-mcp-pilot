#!/usr/bin/env bash
# =============================================================================
# run-e2e.sh — End-to-end pipeline for dolphin-mcp-pilot (docker-compose)
# =============================================================================
# Brings up DolphinScheduler standalone + dolphin-mcp-pilot via docker-compose
# and runs the pytest suite under tests/e2e/.
#
# Usage:
#   bash scripts/e2e/run-e2e.sh                 # full run, tears down
#   bash scripts/e2e/run-e2e.sh --skip-teardown # keep containers for debug
#
# Prerequisites: docker, docker-compose (or docker compose plugin)
# =============================================================================
set -euo pipefail

# --- Argument parsing --------------------------------------------------------
SKIP_TEARDOWN=0
for arg in "$@"; do
  case "$arg" in
    --skip-teardown) SKIP_TEARDOWN=1 ;;
    -h|--help)
      sed -n '2,18p' "$0"
      exit 0
      ;;
    *)
      echo "Unknown argument: $arg" >&2
      exit 1
      ;;
  esac
done

# --- Path & environment ------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"
cd "${ROOT_DIR}"

COMPOSE_FILE="${ROOT_DIR}/tests/e2e/deploy/docker-compose.yml"
export DS_VERSION="${DS_VERSION:-3.4.2}"
export E2E_DS_PORT="${E2E_DS_PORT:-12345}"
export E2E_PILOT_PORT="${E2E_PILOT_PORT:-18001}"
export E2E_DS_USER="${E2E_DS_USER:-admin}"
export E2E_DS_PASSWORD="${E2E_DS_PASSWORD:-dolphinscheduler123}"

LOG_DIR="${LOG_DIR:-/tmp}"
LOG_PREFIX="${LOG_DIR}/e2e-$(date +%s)"

# Detect docker compose command (plugin vs standalone)
if docker compose version >/dev/null 2>&1; then
  COMPOSE="docker compose"
elif command -v docker-compose >/dev/null 2>&1; then
  COMPOSE="docker-compose"
else
  echo "ERROR: docker compose or docker-compose is required" >&2
  exit 1
fi

log() { printf '\n=== %s ===\n' "$*"; }

# --- Cleanup -----------------------------------------------------------------
cleanup() {
  local rc=$?
  log "Cleanup (exit=${rc}, skip_teardown=${SKIP_TEARDOWN})"

  if [[ "${SKIP_TEARDOWN}" -eq 0 ]]; then
    log "Stopping docker-compose services"
    ${COMPOSE} -f "${COMPOSE_FILE}" down -v --remove-orphans 2>&1 || true
  else
    log "Skipping teardown (--skip-teardown)"
    log "  Services still running: ${COMPOSE} -f ${COMPOSE_FILE} ps"
  fi

  exit "${rc}"
}
trap cleanup EXIT INT TERM

# --- Step 1: Stop any existing services --------------------------------------
log "[1/6] Stopping any existing e2e services"
${COMPOSE} -f "${COMPOSE_FILE}" down -v --remove-orphans 2>&1 || true

# --- Step 2: Start DolphinScheduler standalone -------------------------------
log "[2/6] Starting DolphinScheduler standalone server"
${COMPOSE} -f "${COMPOSE_FILE}" up -d dolphinscheduler 2>&1 | tee "${LOG_PREFIX}-ds-up.log"

# --- Step 3: Wait for DolphinScheduler healthy -------------------------------
log "[3/6] Waiting for DolphinScheduler to become healthy"
DS_URL="http://localhost:${E2E_DS_PORT}/dolphinscheduler/ui/"
deadline=$((SECONDS + 300))
until curl -sf -o /dev/null "${DS_URL}"; do
  if [[ "${SECONDS}" -ge "${deadline}" ]]; then
    echo "ERROR: DolphinScheduler did not become ready within 300s" >&2
    ${COMPOSE} -f "${COMPOSE_FILE}" logs dolphinscheduler
    exit 1
  fi
  sleep 5
done
log "  DolphinScheduler is healthy"

# --- Step 4: Verify DS login -------------------------------------------------
log "[4/6] Verifying DolphinScheduler login"
LOGIN_RESP=$(curl -sf -X POST \
  "http://localhost:${E2E_DS_PORT}/dolphinscheduler/login" \
  -d "userName=${E2E_DS_USER}&userPassword=${E2E_DS_PASSWORD}" || true)

if [[ -z "${LOGIN_RESP}" ]]; then
  echo "ERROR: DS login returned empty response" >&2
  exit 1
fi
if ! echo "${LOGIN_RESP}" | grep -q '"code"[[:space:]]*:[[:space:]]*0'; then
  echo "ERROR: DS login failed: ${LOGIN_RESP}" >&2
  exit 1
fi
log "  login OK"

# --- Step 5: Start dolphin-mcp-pilot -----------------------------------------
log "[5/6] Starting dolphin-mcp-pilot"
${COMPOSE} -f "${COMPOSE_FILE}" up -d dolphin-mcp-pilot 2>&1 | tee "${LOG_PREFIX}-pilot-up.log"

# Wait for the pilot TCP listener. A GET to the MCP endpoint can remain open as
# a streaming response, so it is not a safe readiness probe.
deadline=$((SECONDS + 60))
until python -c 'import socket, sys; socket.create_connection(("127.0.0.1", int(sys.argv[1])), timeout=2).close()' "${E2E_PILOT_PORT}"; do
  if [[ "${SECONDS}" -ge "${deadline}" ]]; then
    echo "ERROR: dolphin-mcp-pilot did not become ready within 60s" >&2
    ${COMPOSE} -f "${COMPOSE_FILE}" logs dolphin-mcp-pilot
    exit 1
  fi
  sleep 3
done
log "  dolphin-mcp-pilot is healthy"

# --- Step 6: Run pytest ------------------------------------------------------
log "[6/6] Running pytest suite"
export E2E_DS_PORT E2E_PILOT_PORT E2E_DS_USER E2E_DS_PASSWORD
export E2E_DS_URL="http://localhost:${E2E_DS_PORT}/dolphinscheduler"
export E2E_PILOT_URL="http://localhost:${E2E_PILOT_PORT}"

set +e
python -m pytest "${ROOT_DIR}/tests/e2e/" \
  -v --tb=short --timeout=300 \
  2>&1 | tee "${LOG_PREFIX}-pytest.log"
PYTEST_RC=${PIPESTATUS[0]}
set -e

# --- Collect logs ------------------------------------------------------------
log "Collecting service logs"
${COMPOSE} -f "${COMPOSE_FILE}" logs --no-color dolphinscheduler > "${LOG_PREFIX}-ds.log" 2>&1 || true
${COMPOSE} -f "${COMPOSE_FILE}" logs --no-color dolphin-mcp-pilot > "${LOG_PREFIX}-pilot.log" 2>&1 || true

# --- Report ------------------------------------------------------------------
log "Done (exit=${PYTEST_RC})"
if [[ "${PYTEST_RC}" -eq 0 ]]; then
  log "All e2e tests passed"
else
  log "e2e tests FAILED — logs saved to ${LOG_PREFIX}-*.log"
fi

exit "${PYTEST_RC}"
