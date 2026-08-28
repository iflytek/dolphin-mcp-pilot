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

"""dolphin-mcp-pilot - An MCP server for Apache DolphinScheduler.

64+ tools covering projects, workflows (SQL & DAG), schedules,
instances, resources (full CRUD + recursive delete), monitoring
and raw API passthrough. Includes ds_help tool for navigation.

Usage:
    # Run as MCP server
    python -m dolphin_mcp_pilot

    # Or import programmatically
    from dolphin_mcp_pilot import mcp, ds_list_projects
"""

__version__ = "0.3.1"
__author__ = "dolphin-mcp-pilot contributors"
__license__ = "Apache-2.0"

from .config import get_ds_url, get_ds_credentials, get_tenant_code
from .auth import set_current_credentials, get_credentials, login, clear_cache
from .client import ds_get, ds_post, ds_put, ds_delete
from .utils import require_ok, resolve_project_code
from .server import mcp

__all__ = [
    "__version__",
    "__author__",
    "__license__",
    # config
    "get_ds_url",
    "get_ds_credentials",
    "get_tenant_code",
    # auth
    "set_current_credentials",
    "get_credentials",
    "login",
    "clear_cache",
    # client
    "ds_get",
    "ds_post",
    "ds_put",
    "ds_delete",
    # utils
    "require_ok",
    "resolve_project_code",
    # MCP app
    "mcp",
]
