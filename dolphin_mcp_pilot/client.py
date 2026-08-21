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

"""HTTP 客户端模块"""

from __future__ import annotations

import json
import mimetypes
import os
import urllib.error
import urllib.parse
import urllib.request
import uuid

from . import api_compat
from .config import get_ds_api_style, get_ds_url
from .auth import login

# Cached result of API-path-style auto-detection (see _effective_api_style).
_resolved_api_style: str | None = None


def _detect_api_style() -> str:
    """Probe the target DolphinScheduler for its REST path style.

    DS 3.3.0+ exposes the ``workflow-definition`` controller; 3.2.x does not.
    A bogus project code is enough — we only care whether the route exists.
    Detection falls back to the legacy ``"process"`` spelling whenever the
    probe is inconclusive, so an undetectable deployment never regresses.
    """
    try:
        ds_api_request(
            "GET",
            "/projects/0/workflow-definition/simple-list",
            _resolve=False,
        )
        return "workflow"
    except urllib.error.HTTPError as exc:
        # 404 => controller absent (legacy). 401/403/5xx => inconclusive;
        # keep the legacy default rather than guessing.
        return "process" if exc.code == 404 else "process"
    except Exception:
        return "process"


def _effective_api_style() -> str:
    """Return the path style to apply, detecting once when set to ``auto``."""
    global _resolved_api_style
    configured = get_ds_api_style()
    if configured != "auto":
        return configured
    if _resolved_api_style is None:
        _resolved_api_style = _detect_api_style()
    return _resolved_api_style


def _resolve_path(path: str) -> str:
    """Rewrite legacy DS path segments for the target version when needed."""
    return api_compat.apply_style(path, _effective_api_style())


def ds_api_request(
    method: str,
    path: str,
    data: dict | None = None,
    json_body: dict | None = None,
    timeout: int | None = None,
    _resolve: bool = True,
) -> dict:
    """发送 HTTP 请求到 DolphinScheduler API

    Args:
        method: HTTP 方法（GET/POST/PUT/DELETE）
        path: API 路径（如 /projects/list）
        data: 表单数据（application/x-www-form-urlencoded）
        json_body: JSON 数据（application/json）
        timeout: 超时时间（秒），默认从环境变量 DS_API_TIMEOUT 读取，未设置则为 120

    Returns:
        API 响应的 JSON 数据
    """
    if _resolve:
        path = _resolve_path(path)
    url = get_ds_url()
    sid = login()
    full_url = f"{url}{path}"
    headers = {"Cookie": f"sessionId={sid}"}

    body = None
    if json_body is not None:
        body = json.dumps(json_body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    elif data is not None:
        body = urllib.parse.urlencode(data).encode("utf-8")
        headers["Content-Type"] = "application/x-www-form-urlencoded"

    # 超时配置：优先使用传入参数，其次环境变量，最后默认 120
    if timeout is None:
        timeout = int(os.environ.get("DS_API_TIMEOUT", "120"))

    req = urllib.request.Request(full_url, data=body, headers=headers, method=method)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8")
        return json.loads(raw) if raw else {}


def ds_get(path: str) -> dict:
    """GET 请求"""
    return ds_api_request("GET", path)


def ds_post(path: str, data: dict | None = None, json_body: dict | None = None) -> dict:
    """POST 请求"""
    return ds_api_request("POST", path, data=data, json_body=json_body)


def ds_put(path: str, data: dict | None = None, json_body: dict | None = None) -> dict:
    """PUT 请求"""
    return ds_api_request("PUT", path, data=data, json_body=json_body)


def ds_delete(path: str) -> dict:
    """DELETE 请求"""
    return ds_api_request("DELETE", path)


def _encode_multipart(fields: dict, files: dict) -> tuple[bytes, str]:
    """将 form fields 和 files 编码为 multipart/form-data。

    Args:
        fields: 普通表单字段 {name: value}
        files: 文件字段 {name: (filename, content_bytes, content_type)}

    Returns:
        (body_bytes, content_type_header)
    """
    boundary = f"----DSMCPBoundary{uuid.uuid4().hex}"
    crlf = b"\r\n"
    parts: list[bytes] = []

    for name, value in fields.items():
        parts.append(f"--{boundary}".encode())
        parts.append(f'Content-Disposition: form-data; name="{name}"'.encode())
        parts.append(b"")
        parts.append(str(value).encode("utf-8"))

    for name, (filename, content, ctype) in files.items():
        parts.append(f"--{boundary}".encode())
        parts.append(
            (
                f'Content-Disposition: form-data; name="{name}"; '
                f'filename="{filename}"'
            ).encode()
        )
        parts.append(f"Content-Type: {ctype}".encode())
        parts.append(b"")
        parts.append(content)

    parts.append(f"--{boundary}--".encode())
    parts.append(b"")
    body = crlf.join(parts)
    return body, f"multipart/form-data; boundary={boundary}"


def ds_post_multipart(
    path: str,
    fields: dict | None = None,
    files: dict | None = None,
) -> dict:
    """发送 multipart/form-data POST 请求（用于文件上传）。

    Args:
        path: API 路径
        fields: 普通表单字段
        files: 文件字段 {name: (filename, content_bytes, content_type)}

    Returns:
        API 响应的 JSON 数据
    """
    return _multipart_request("POST", path, fields, files)


def ds_put_multipart(
    path: str,
    fields: dict | None = None,
    files: dict | None = None,
) -> dict:
    """发送 multipart/form-data PUT 请求（DS 3.x 的 PUT /resources 需要这个）。"""
    return _multipart_request("PUT", path, fields, files)


def _multipart_request(
    method: str,
    path: str,
    fields: dict | None = None,
    files: dict | None = None,
) -> dict:
    path = _resolve_path(path)
    url = get_ds_url()
    sid = login()
    full_url = f"{url}{path}"

    body, content_type = _encode_multipart(fields or {}, files or {})
    headers = {
        "Cookie": f"sessionId={sid}",
        "Content-Type": content_type,
        "Content-Length": str(len(body)),
    }

    req = urllib.request.Request(full_url, data=body, headers=headers, method=method)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(req, timeout=300) as resp:
        raw = resp.read().decode("utf-8")
        return json.loads(raw) if raw else {}


def ds_download_bytes(path: str) -> bytes:
    """下载二进制内容（用于 /resources/{id}/download 等）。

    Args:
        path: API 路径

    Returns:
        原始响应字节
    """
    path = _resolve_path(path)
    url = get_ds_url()
    sid = login()
    full_url = f"{url}{path}"
    headers = {"Cookie": f"sessionId={sid}"}

    req = urllib.request.Request(full_url, headers=headers, method="GET")
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(req, timeout=300) as resp:
        return resp.read()


def guess_content_type(filename: str) -> str:
    """根据文件名猜测 MIME 类型。"""
    ctype, _ = mimetypes.guess_type(filename)
    return ctype or "application/octet-stream"
