"""Pytest fixtures for the dolphin-mcp-pilot e2e test suite.

The fixtures provide:
- readiness polling before tests run
- shared MCP client with admin credentials
- unique project names for test isolation
- best-effort cleanup tracking

Configuration via environment variables:
    E2E_DS_PORT        DS API port on localhost       (default 12345)
    E2E_PILOT_PORT     pilot port on localhost        (default 18001)
    E2E_DS_USER        DS admin username              (default "admin")
    E2E_DS_PASSWORD    DS admin password              (default "dolphinscheduler123")
    E2E_DS_TOKEN       if set, used instead of user/password
    E2E_PILOT_URL      explicit pilot URL (skips port construction)
    E2E_DS_URL         explicit DS URL (skips port construction)
"""

import os
import time
import urllib.request

import pytest

from .mcp_client import MCPClient

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DS_PORT = int(os.getenv("E2E_DS_PORT", "12345"))
PILOT_PORT = int(os.getenv("E2E_PILOT_PORT", "18001"))
DS_USER = os.getenv("E2E_DS_USER", "admin")
DS_PASSWORD = os.getenv("E2E_DS_PASSWORD", "dolphinscheduler123")
DS_TOKEN = os.getenv("E2E_DS_TOKEN", "")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def wait_for_url(url, timeout=120, interval=2):
    """Poll a URL until it responds (any status) or the timeout elapses."""
    deadline = time.time() + timeout
    last_exc = None
    while time.time() < deadline:
        try:
            # Use a simple socket check - any response means server is up
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=5):
                return True
        except urllib.error.HTTPError as exc:
            # Any HTTP response (even 406) means server is running
            if exc.code < 500:
                return True
            last_exc = exc
        except Exception as exc:  # noqa: BLE001 - we want to keep trying
            last_exc = exc
        time.sleep(interval)
    raise TimeoutError(
        f"Service at {url} did not become ready within {timeout}s: {last_exc}"
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def ds_url():
    """Base URL for the DS REST API."""
    explicit = os.getenv("E2E_DS_URL")
    if explicit:
        return explicit
    return f"http://127.0.0.1:{DS_PORT}/dolphinscheduler"


@pytest.fixture(scope="session")
def pilot_url():
    """Base URL for the pilot MCP server."""
    explicit = os.getenv("E2E_PILOT_URL")
    if explicit:
        return explicit
    return f"http://127.0.0.1:{PILOT_PORT}"


@pytest.fixture(scope="session", autouse=True)
def wait_for_services(pilot_url, ds_url):
    """Block the session until both services respond to HTTP."""
    wait_for_url(pilot_url + "/mcp/", timeout=60)
    wait_for_url(ds_url + "/dolphinscheduler/ui/login", timeout=180)
    yield


@pytest.fixture(scope="session")
def admin_credentials():
    """Admin credentials used by most tests."""
    return {"user": DS_USER, "password": DS_PASSWORD, "token": DS_TOKEN}


@pytest.fixture(scope="session")
def mcp_client(pilot_url, admin_credentials):
    """An initialized MCPClient with admin credentials.

    The client is shared across the session; do not mutate its session_id
    from individual tests (create a fresh MCPClient if you need isolation).
    """
    client = MCPClient(
        pilot_url,
        user=admin_credentials["user"],
        password=admin_credentials["password"],
        token=admin_credentials["token"],
    )
    client.initialize()
    return client


@pytest.fixture
def unique_project_name():
    """Return a unique project name for a single test.

    Cleanup is the test's responsibility; the name is chosen to be
    lexically identifiable so stale projects are easy to spot.
    """
    return f"e2e_{os.getpid()}_{int(time.time() * 1000)}"


@pytest.fixture(scope="session")
def cleanup_tracker():
    """A dict of resource cleanup callbacks for a test session.

    Each test can register (resource_type, cleanup_fn) entries; the
    session-scoped finalizer walks them in reverse on teardown.
    """
    entries = []

    def register(kind, fn):
        entries.append((kind, fn))

    yield register

    for kind, fn in reversed(entries):
        try:
            fn()
        except Exception as exc:  # noqa: BLE001
            print(f"[cleanup] {kind} cleanup failed: {exc}")
