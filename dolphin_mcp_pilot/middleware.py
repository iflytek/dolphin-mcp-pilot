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

"""HTTP auth middleware.

Extracts per-request credentials from HTTP headers and stores them in
contextvars, so concurrent requests from different users don't mix.

Supported headers:
  - X-DS-Token:     DolphinScheduler API token (preferred)
  - X-DS-User:      username (used with X-DS-Password)
  - X-DS-Password:  password
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from .auth import request_credentials


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        token = request.headers.get("X-DS-Token", "")
        user = request.headers.get("X-DS-User", "")
        password = request.headers.get("X-DS-Password", "")

        with request_credentials(user=user, password=password, token=token):
            return await call_next(request)
