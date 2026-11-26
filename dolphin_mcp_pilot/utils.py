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

"""工具函数模块"""

from .client import ds_get


def require_ok(result: dict, action: str) -> None:
    """检查 API 返回结果是否成功

    Args:
        result: API 返回的 JSON 数据
        action: 操作描述（用于错误消息）

    Raises:
        RuntimeError: 如果 API 返回失败
    """
    if result.get("code") != 0:
        raise RuntimeError(f"{action} 失败: {result.get('msg', result)}")


def resolve_project_code(project_name: str, timeout: float | None = None) -> int:
    """根据项目名称查找 project code，可选限定查询等待时间（秒）

    Args:
        project_name: 项目名称
        timeout: 本次项目查询的最大等待秒数

    Returns:
        项目 code

    Raises:
        ValueError: 如果项目不存在
    """
    result = ds_get("/projects/list", timeout=timeout)
    require_ok(result, "获取项目列表")
    for p in result.get("data", []):
        if p["name"] == project_name:
            return p["code"]
    raise ValueError(f"项目 '{project_name}' 不存在")
