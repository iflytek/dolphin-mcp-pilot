#!/usr/bin/env python3
# Copyright 2026 iFLYTEK CO., LTD.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Main entry point.

Run modes:
    stdio: python -m dolphin_mcp_pilot
    http:  DS_MCP_TRANSPORT=http python -m dolphin_mcp_pilot

Env vars:
    DS_URL             DolphinScheduler API base URL (required)
    DS_USER            Default username (stdio mode; fallback in http mode)
    DS_PASSWORD        Default password
    DS_TOKEN           API token (preferred over user/password)
    DS_TENANT_CODE     Tenant code used when creating workflows (default: "default")
    DS_MCP_TRANSPORT   "stdio" (default) or "http"
    MCP_HOST           HTTP host to bind (default: 0.0.0.0)
    MCP_PORT           HTTP port to bind (default: 8001)

HTTP mode per-request auth headers:
    X-DS-Token:     API token (preferred)
    X-DS-User:      username
    X-DS-Password:  password
"""

import sys

import uvicorn
from starlette.applications import Starlette

from .config import DS_MCP_TRANSPORT, MCP_HOST, MCP_PORT
from .middleware import AuthMiddleware
from .server import mcp


def build_http_app() -> Starlette:
    """Build the stateless MCP 2.0 HTTP app with per-request DS auth."""
    app = mcp.streamable_http_app(
        streamable_http_path="/mcp/",
        stateless_http=True,
        host=MCP_HOST,
    )
    app.add_middleware(AuthMiddleware)
    return app


def main() -> None:
    if DS_MCP_TRANSPORT == "http":
        config = uvicorn.Config(
            build_http_app(),
            host=MCP_HOST,
            port=MCP_PORT,
            log_level="info",
        )
        print(f"dolphin-mcp-pilot listening on http://{MCP_HOST}:{MCP_PORT}/mcp/")
        print("Pass X-DS-Token or X-DS-User/X-DS-Password headers per request.")
        uvicorn.Server(config).run()
    else:
        print("dolphin-mcp-pilot starting in stdio mode", file=sys.stderr)
        mcp.run()


if __name__ == "__main__":
    main()
