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

"""Resource file and folder management tools (DS 3.x API, resource_id based).

All mutating operations use resource_id: rename, update-content, delete, download, view.
Create operations use currentDir + pid.
fullName -> id resolution uses /resources/list (recursive tree search),
because /resources/query-by-name has a bug in some DS versions.
"""

import base64
import os
import re
import urllib.parse

from mcp.server.mcpserver import MCPServer

from ..client import (
    ds_get,
    ds_post,
    ds_put,
    ds_delete,
    ds_post_multipart,
    ds_download_bytes,
    guess_content_type,
)
from ..utils import require_ok


def _find_resource_in_tree(items: list, target_full_name: str) -> dict | None:
    """Recursively find a resource by fullName in the resource tree.

    DS fullName format:
      - Root-level: 'public' or '/public'
      - Nested: 'public/script.py' or '/public/script.py'
    Comparison is done with leading slashes stripped.
    """
    target = target_full_name.strip("/")
    for item in items or []:
        fn = (item.get("fullName") or "").strip("/")
        if fn == target:
            return item
        kids = item.get("children") or []
        if kids:
            found = _find_resource_in_tree(kids, target_full_name)
            if found:
                return found
    return None


def _list_all_resources(resource_type: str = "FILE") -> list:
    """Call /resources/list, supporting ALL (merged FILE + UDF)."""
    if resource_type and resource_type.upper() == "ALL":
        items = []
        for t in ("FILE", "UDF"):
            try:
                r = ds_get(f"/resources/list?type={t}")
                if r.get("code") == 0:
                    for it in r.get("data") or []:
                        it["_source_type"] = t
                        items.append(it)
            except Exception:
                continue
        return items
    result = ds_get(f"/resources/list?type={resource_type}")
    if result.get("code") != 0:
        raise RuntimeError(f"Failed to list resources: {result.get('msg', result)}")
    return result.get("data") or []


def _get_resource_by_name(full_name: str, resource_type: str = "FILE") -> dict:
    """Find a resource by full path (via /resources/list recursive search).

    Uses /resources/list instead of /resources/query-by-name due to a bug
    in some DS versions where query-by-name returns 'resource not exist'.

    resource_type supports "FILE" / "UDF" / "ALL" (searches both types).
    """
    if resource_type and resource_type.upper() == "ALL":
        for t in ("FILE", "UDF"):
            try:
                result = ds_get(f"/resources/list?type={t}")
                if result.get("code") == 0:
                    found = _find_resource_in_tree(result.get("data") or [], full_name)
                    if found:
                        found["_source_type"] = t
                        return found
            except Exception:
                continue
        raise ValueError(
            f"Resource '{full_name}' not found (searched both FILE and UDF types)"
        )

    result = ds_get(f"/resources/list?type={resource_type}")
    if result.get("code") != 0:
        raise RuntimeError(f"Failed to list resources: {result.get('msg', result)}")
    found = _find_resource_in_tree(result.get("data") or [], full_name)
    if not found:
        raise ValueError(
            f"Resource '{full_name}' not found (resource_type={resource_type})"
        )
    return found


def _resolve_resource_id(full_name: str, resource_type: str = "FILE") -> int:
    """Resolve fullName to resource_id."""
    res = _get_resource_by_name(full_name, resource_type)
    return res.get("id")


def _resolve_pid_from_current_dir(current_dir: str, resource_type: str = "FILE") -> int:
    """Resolve parent directory path to pid. Returns -1 for root."""
    cd = (current_dir or "").strip("/")
    if not cd:
        return -1
    try:
        parent = _get_resource_by_name(cd, resource_type)
        return parent.get("id", -1)
    except Exception:
        return -1


def normalize_resource_list(resource_list: list) -> list:
    """Normalize resource list to DS expected format: [{"id": int, "name": ""}].

    DS only uses id to locate resources; name field can be empty string.

    Accepts three input formats:
      - int: resource_id (used directly, name left empty)
      - str: full path (e.g. "/scripts/x.py") — looks up id
      - dict: {"id": int, ...} — extracts id, name left empty

    Raises ValueError if a path/filename cannot be found (no silent skipping).
    """
    if not resource_list:
        return []

    normalized = []
    for item in resource_list:
        if isinstance(item, int):
            normalized.append({"id": item, "name": ""})

        elif isinstance(item, str):
            try:
                r = _get_resource_by_name(item, resource_type="ALL")
                normalized.append({"id": r["id"], "name": ""})
            except Exception as e:
                raise ValueError(
                    f"Resource '{item}' not found. "
                    f"Provide a full path (e.g. '/scripts/xxx.py') or resource_id (int). "
                    f"Error: {e}"
                )

        elif isinstance(item, dict):
            rid = item.get("id")
            if rid:
                normalized.append({"id": rid, "name": ""})
            else:
                raise ValueError(f"resourceList item missing 'id' field: {item}")

    return normalized


def register_resource_tools(mcp: MCPServer):
    """Register resource file management MCP tools."""

    # ================================================================
    # Read operations
    # ================================================================

    @mcp.tool()
    def ds_list_resources(resource_type: str = "ALL", full_name: str = "") -> list:
        """List resources (files and folders) at a given path.

        Args:
            resource_type: Resource type — FILE / UDF / ALL (default, lists both)
            full_name: Path prefix filter; empty = list everything from root
        """
        rt = (resource_type or "ALL").upper()
        if rt == "ALL":
            items = []
            for t in ("FILE", "UDF"):
                params = f"type={t}"
                if full_name:
                    params += f"&fullName={urllib.parse.quote(full_name)}"
                result = ds_get(f"/resources/list?{params}")
                if result.get("code") == 0:
                    for it in result.get("data") or []:
                        it["_source_type"] = t
                        items.append(it)
            return items

        params = f"type={rt}"
        if full_name:
            params += f"&fullName={urllib.parse.quote(full_name)}"
        result = ds_get(f"/resources/list?{params}")
        require_ok(result, "list resources")
        return result.get("data", []) or []

    @mcp.tool()
    def ds_view_resource(
        resource_id: int, skip_line_num: int = 0, limit: int = 1000
    ) -> dict:
        """View resource file content (paginated, text files only).

        Args:
            resource_id: Resource ID (from ds_list_resources or ds_get_resource_by_name)
            skip_line_num: Number of lines to skip
            limit: Max lines to read
        """
        result = ds_get(
            f"/resources/{resource_id}/view?skipLineNum={skip_line_num}&limit={limit}"
        )
        require_ok(result, "view resource content")
        return result.get("data", {})

    @mcp.tool()
    def ds_get_resource_by_name(full_name: str, resource_type: str = "FILE") -> dict:
        """Find a resource (file or folder) by full path, returning id and metadata.

        Implementation: uses /resources/list recursive search
        (avoids /resources/query-by-name due to known DS bug).

        Args:
            full_name: Full resource path, e.g. "public/test.py" or "scripts"
            resource_type: Resource type, default FILE
        """
        return _get_resource_by_name(full_name, resource_type)

    @mcp.tool()
    def ds_download_resource(resource_id: int, save_to: str = "") -> dict:
        """Download a resource file (supports binary, e.g. jar, zip).

        Args:
            resource_id: Resource ID
            save_to: Optional local save path (accessible to MCP server process).
                     If empty, returns base64-encoded content.

        Returns:
            If save_to provided: {"resource_id", "saved_to", "size"}
            Otherwise: {"resource_id", "size", "content_base64"}
        """
        content = ds_download_bytes(f"/resources/{resource_id}/download")
        size = len(content)

        if save_to:
            parent = os.path.dirname(os.path.abspath(save_to))
            if parent:
                os.makedirs(parent, exist_ok=True)
            with open(save_to, "wb") as f:
                f.write(content)
            return {
                "resource_id": resource_id,
                "saved_to": os.path.abspath(save_to),
                "size": size,
            }

        return {
            "resource_id": resource_id,
            "size": size,
            "content_base64": base64.b64encode(content).decode("ascii"),
        }

    # ================================================================
    # Write operations
    # ================================================================

    @mcp.tool()
    def ds_create_folder(
        name: str,
        current_dir: str = "/",
        resource_type: str = "FILE",
    ) -> dict:
        """Create a folder in the resource area.

        Args:
            name: Folder name (no path prefix, e.g. "scripts")
            current_dir: Parent directory path, default root "/"
            resource_type: FILE or UDF
        """
        if not current_dir.endswith("/"):
            current_dir += "/"

        pid = _resolve_pid_from_current_dir(current_dir, resource_type)

        result = ds_post(
            "/resources/directory",
            data={
                "type": resource_type,
                "name": name,
                "pid": pid,
                "currentDir": current_dir,
            },
        )
        require_ok(result, "create resource folder")

        data = result.get("data", {}) or {}
        raw_full_name = data.get("fullName") or f"{current_dir}{name}"
        clean_full_name = re.sub(r"/+", "/", raw_full_name).lstrip("/")
        return {
            "name": name,
            "current_dir": current_dir,
            "full_name": clean_full_name,
            "id": data.get("id"),
            "pid": pid,
            "status": "created",
        }

    @mcp.tool()
    def ds_online_create_file(
        file_name: str,
        suffix: str,
        content: str,
        current_dir: str = "/",
        description: str = "",
        resource_type: str = "FILE",
    ) -> dict:
        """Create a text file inline (no upload required).

        Args:
            file_name: Filename without extension (e.g. "my_script")
            suffix: File extension without dot (e.g. "py" / "sh" / "sql")
            content: Text content to write
            current_dir: Parent directory path, default root "/"
            description: File description
            resource_type: FILE or UDF
        """
        if not current_dir.endswith("/"):
            current_dir += "/"

        pid = _resolve_pid_from_current_dir(current_dir, resource_type)

        result = ds_post(
            "/resources/online-create",
            data={
                "type": resource_type,
                "fileName": file_name,
                "suffix": suffix,
                "content": content,
                "currentDir": current_dir,
                "pid": pid,
                "description": description or "",
            },
        )
        require_ok(result, "create file online")

        data = result.get("data", {}) or {}
        raw_full_name = data.get("fullName") or f"{current_dir}{file_name}.{suffix}"
        # Normalize double slashes
        clean_full_name = re.sub(r"/+", "/", raw_full_name).lstrip("/")
        return {
            "file_name": f"{file_name}.{suffix}",
            "current_dir": current_dir,
            "full_name": clean_full_name,
            "id": data.get("id"),
            "pid": pid,
            "status": "created",
        }

    @mcp.tool()
    def ds_upload_file(
        local_path: str = "",
        file_name: str = "",
        file_content_base64: str = "",
        current_dir: str = "/",
        resource_type: str = "FILE",
    ) -> dict:
        """Upload a file to the resource area (supports binary, e.g. jar / zip).

        Two ways to provide file content:
            Method 1: local_path — path to a file accessible by the MCP server process
            Method 2: file_name + file_content_base64 — base64-encoded content

        Args:
            local_path: Local file path (Method 1)
            file_name: Filename with extension (Method 2)
            file_content_base64: Base64-encoded file content (Method 2)
            current_dir: Parent directory path, default root "/"
            resource_type: FILE or UDF
        """
        if not current_dir.endswith("/"):
            current_dir += "/"

        if local_path:
            if not os.path.isfile(local_path):
                raise ValueError(f"Local file not found: {local_path}")
            with open(local_path, "rb") as f:
                content_bytes = f.read()
            fname = file_name or os.path.basename(local_path)
        elif file_name and file_content_base64:
            content_bytes = base64.b64decode(file_content_base64)
            fname = file_name
        else:
            raise ValueError(
                "Must provide local_path or both file_name + file_content_base64"
            )

        pid = _resolve_pid_from_current_dir(current_dir, resource_type)

        ctype = guess_content_type(fname)
        result = ds_post_multipart(
            "/resources",
            fields={
                "type": resource_type,
                "name": fname,
                "pid": pid,
                "currentDir": current_dir,
            },
            files={"file": (fname, content_bytes, ctype)},
        )
        require_ok(result, "upload file")

        data = result.get("data", {}) or {}
        raw_full_name = data.get("fullName") or f"{current_dir}{fname}"
        clean_full_name = re.sub(r"/+", "/", raw_full_name).lstrip("/")
        return {
            "file_name": fname,
            "current_dir": current_dir,
            "full_name": clean_full_name,
            "id": data.get("id"),
            "pid": pid,
            "size": len(content_bytes),
            "status": "uploaded",
        }

    @mcp.tool()
    def ds_update_resource_content(
        resource_id: int,
        content: str,
        description: str = "",
    ) -> dict:
        """Update resource file content (text files only).

        ⚠️ Changes take effect immediately. Workflows referencing this script
        will use the new version on their next execution.

        Args:
            resource_id: Resource ID
            content: New file content
            description: Update note (optional)
        """
        result = ds_put(
            f"/resources/{resource_id}/update-content",
            data={"content": content, "description": description or ""},
        )
        require_ok(result, "update resource content")
        return {
            "resource_id": resource_id,
            "status": "updated",
        }

    @mcp.tool()
    def ds_rename_resource(
        resource_id: int,
        new_name: str,
        description: str = "",
        resource_type: str = "FILE",
    ) -> dict:
        """Rename a resource file or folder.

        ⚠️ Warning: DS may implement rename as delete + recreate, which
        changes the resource_id. If this resource is referenced by workflow tasks,
        the reference will become invalid after renaming.
        Check references with ds_list_workflows before proceeding.

        Args:
            resource_id: Resource ID
            new_name: New name (filename or folder name only, no path prefix)
            description: Description
            resource_type: FILE or UDF
        """
        result = ds_put(
            f"/resources/{resource_id}",
            data={
                "name": new_name,
                "description": description or "",
                "type": resource_type,
            },
        )
        require_ok(result, "rename resource")
        return {
            "resource_id": resource_id,
            "new_name": new_name,
            "status": "renamed",
            "warning": (
                "DS rename may change resource_id (delete + recreate). "
                "Check workflow task references if this resource is in use."
            ),
        }

    @mcp.tool()
    def ds_delete_resource(resource_id: int, recursive: bool = False) -> dict:
        """Delete a resource (file or folder).

        ⚠️ Warning: Deletion is irreversible. Resources referenced by workflow
        tasks will cause those tasks to fail on next execution.

        DS behavior: Deleting a non-empty folder returns error 20018.
        Use recursive=True to delete children first, then the folder.

        Args:
            resource_id: Resource ID
            recursive: Delete children recursively (for folders, default False)

        Returns:
            {"resource_id", "status", "deleted_children"}
        """
        deleted_children = []

        if recursive:
            try:

                def _find_by_id(items, target_id):
                    for item in items or []:
                        if item.get("id") == target_id:
                            return item
                        found = _find_by_id(item.get("children") or [], target_id)
                        if found:
                            return found
                    return None

                node = None
                for t in ("FILE", "UDF"):
                    list_result = ds_get(f"/resources/list?type={t}")
                    if list_result.get("code") == 0:
                        node = _find_by_id(list_result.get("data") or [], resource_id)
                        if node:
                            break

                if node:
                    is_dir = bool(node.get("directory")) or bool(node.get("dirctory"))
                    if is_dir:

                        def _collect_children(n):
                            ids = []
                            for c in n.get("children") or []:
                                ids.extend(_collect_children(c))
                                ids.append(c.get("id"))
                            return ids

                        child_ids = _collect_children(node)
                        for cid in child_ids:
                            if cid:
                                try:
                                    ds_delete(f"/resources/{cid}")
                                    deleted_children.append(cid)
                                except Exception:
                                    pass
            except Exception:
                pass

        result = ds_delete(f"/resources/{resource_id}")
        require_ok(result, "delete resource")

        return {
            "resource_id": resource_id,
            "status": "deleted",
            "deleted_children": deleted_children,
        }
