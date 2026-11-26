#!/usr/bin/env python3
"""P0 任务内容编辑行为测试：mock DS 传输，不访问生产环境。"""

import copy
import json
import unittest
from unittest.mock import patch

from dolphin_mcp_pilot.tools import workflow_advanced as wa


PROJECT = "sandbox"
WORKFLOW_CODE = 1001
TASK_NAME = "sql_node"
OLD_SQL = "SELECT a, b FROM source WHERE dt = '20261125'"
NEW_SQL = "SELECT a, b FROM source WHERE dt = '20261125' AND a > 0"


class DummyMCP:
    def __init__(self):
        self.tools = {}

    def tool(self):
        def decorator(func):
            self.tools[func.__name__] = func
            return func

        return decorator


def workflow(version=3, sql=OLD_SQL, release="ONLINE"):
    return {
        "code": 0,
        "data": {
            "processDefinition": {
                "name": "edit-sandbox",
                "description": "",
                "version": version,
                "releaseState": release,
                "globalParamStr": "[]",
                "locations": "[]",
                "tenantCode": "default",
                "executionType": "PARALLEL",
                "timeout": 0,
            },
            "taskDefinitionList": [
                {
                    "code": 501,
                    "name": TASK_NAME,
                    "taskType": "SQL",
                    "taskParams": {"sql": sql, "datasource": 1, "type": "HIVE"},
                    "failRetryTimes": 4,
                    "failRetryInterval": 4,
                }
            ],
            "processTaskRelationList": [],
        },
    }


class FakeDS:
    """只实现本测试读取/修改工作流所需的最小 DS 行为。"""

    def __init__(self):
        self.state = workflow()
        self.put_count = 0
        self.get_paths = []
        self.post_paths = []
        self.timeout_on_put = False
        self.timeout_on_online = False
        self.timeout_on_verify = False
        self.timeout_on_final_verify = False
        self.read_count_after_put = 0

    def get(self, path, timeout=None):
        self.get_paths.append(path)
        assert timeout is None or timeout > 0
        if path.startswith("/projects/1/schedules"):
            return {
                "code": 0,
                "data": {
                    "totalList": [
                        {
                            "id": 8,
                            "processDefinitionCode": WORKFLOW_CODE,
                            "releaseState": "OFFLINE",
                        }
                    ]
                },
            }
        if path == f"/projects/1/process-definition/{WORKFLOW_CODE}":
            if self.put_count:
                self.read_count_after_put += 1
                if self.timeout_on_verify and self.read_count_after_put == 1:
                    raise TimeoutError("verify timed out")
                if self.timeout_on_final_verify and self.read_count_after_put == 2:
                    raise TimeoutError("final verify timed out")
            return copy.deepcopy(self.state)
        raise AssertionError(f"unexpected GET {path}")

    def put(self, path, data=None, json_body=None, timeout=None):
        assert timeout is None or timeout > 0
        if self.timeout_on_put:
            raise TimeoutError("write timed out")
        assert path == f"/projects/1/process-definition/{WORKFLOW_CODE}"
        payload = data
        self.put_count += 1
        tasks = json.loads(payload["taskDefinitionJson"])
        self.state["data"]["taskDefinitionList"] = tasks
        self.state["data"]["processDefinition"]["version"] += 1
        self.state["data"]["processDefinition"]["releaseState"] = "OFFLINE"
        return {"code": 0}

    def post(self, path, data=None, json_body=None, timeout=None):
        assert timeout is None or timeout > 0
        self.post_paths.append(path)
        if path.endswith("/release") and data.get("releaseState") == "ONLINE":
            if self.timeout_on_online:
                raise TimeoutError("online timed out")
            self.state["data"]["processDefinition"]["releaseState"] = "ONLINE"
            return {"code": 0}
        if path.endswith("/release") and data.get("releaseState") == "OFFLINE":
            self.state["data"]["processDefinition"]["releaseState"] = "OFFLINE"
            return {"code": 0}
        if path == "/projects/1/schedules/8/online":
            return {"code": 0}
        raise AssertionError(f"unexpected POST {path}")


class TaskContentEditingTests(unittest.TestCase):
    def setUp(self):
        self.mcp = DummyMCP()
        wa.register_workflow_advanced_tools(self.mcp)
        self.tools = self.mcp.tools
        self.fake = FakeDS()
        self.patches = [
            patch.object(wa, "resolve_project_code", return_value=1),
            patch.object(wa, "client_get", side_effect=self.fake.get),
            patch.object(wa, "client_put", side_effect=self.fake.put),
            patch.object(wa, "client_post", side_effect=self.fake.post),
        ]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in reversed(self.patches):
            p.stop()

    def preview(self, **kwargs):
        args = dict(
            project_name=PROJECT,
            workflow_code=WORKFLOW_CODE,
            task_name=TASK_NAME,
            old_str=" WHERE dt = '20261125'",
            new_str=" WHERE dt = '20261125' AND a > 0",
            dry_run=True,
        )
        args.update(kwargs)
        return self.tools["ds_patch_task_content"](**args)

    def apply_patch(self, **kwargs):
        args = dict(
            project_name=PROJECT,
            workflow_code=WORKFLOW_CODE,
            task_name=TASK_NAME,
            old_str=" WHERE dt = '20261125'",
            new_str=" WHERE dt = '20261125' AND a > 0",
            dry_run=False,
            expected_version=3,
        )
        args.update(kwargs)
        return self.tools["ds_patch_task_content"](**args)

    def test_preview_is_read_only_and_returns_diff(self):
        result = self.preview()
        self.assertEqual(result["status"], "preview")
        self.assertEqual(result["current_version"], 3)
        self.assertIn("+SELECT a, b FROM source", result["diff"])
        self.assertFalse(result["persisted"])
        self.assertEqual(self.fake.put_count, 0)
        self.assertEqual(self.fake.post_paths, [])

    def test_non_unique_match_never_writes(self):
        for old, expected in (("missing", 0), (" ", 8)):
            with self.subTest(old=old):
                with self.assertRaisesRegex(ValueError, str(expected)):
                    self.preview(old_str=old, new_str="x")
                self.assertEqual(self.fake.put_count, 0)

    def test_apply_persists_and_reads_back_exact_sql(self):
        result = self.apply_patch()
        self.assertEqual(result["status"], "updated")
        self.assertEqual(result["previous_version"], 3)
        self.assertEqual(result["version"], 4)
        self.assertTrue(result["persisted"])
        self.assertTrue(result["content_verified"])
        self.assertEqual(self.fake.put_count, 1)
        actual = self.fake.state["data"]["taskDefinitionList"][0]["taskParams"]["sql"]
        self.assertEqual(actual, NEW_SQL)
        self.assertIn("/projects/1/schedules/8/online", self.fake.post_paths)

    def test_version_conflict_rejects_write(self):
        with self.assertRaisesRegex(ValueError, "版本已变化"):
            self.apply_patch(expected_version=2)
        self.assertEqual(self.fake.put_count, 0)

    def test_apply_requires_preview_version(self):
        with self.assertRaisesRegex(ValueError, "expected_version"):
            self.apply_patch(expected_version=0)
        self.assertEqual(self.fake.put_count, 0)

    def test_shell_script_patch_persists(self):
        self.fake.state["data"]["taskDefinitionList"][0]["taskType"] = "SHELL"
        self.fake.state["data"]["taskDefinitionList"][0]["taskParams"] = {
            "rawScript": "echo one\necho two"
        }
        result = self.apply_patch(
            field="script", old_str="echo one", new_str="echo ready"
        )
        self.assertEqual(result["status"], "updated")
        self.assertTrue(result["content_verified"])
        script = self.fake.state["data"]["taskDefinitionList"][0]["taskParams"][
            "rawScript"
        ]
        self.assertEqual(script, "echo ready\necho two")

    def test_final_content_read_failure_is_partial(self):
        self.fake.timeout_on_final_verify = True
        result = self.apply_patch()
        self.assertEqual(result["status"], "partially_applied")
        self.assertEqual(result["phase"], "verify_task_content")
        self.assertTrue(result["persisted"])
        self.assertFalse(result["content_verified"])

    def test_write_timeout_is_unknown_and_not_retried(self):
        self.fake.timeout_on_put = True
        result = self.tools["ds_update_task_param"](
            project_name=PROJECT,
            workflow_code=WORKFLOW_CODE,
            task_name=TASK_NAME,
            updates={"sql": NEW_SQL},
        )
        self.assertEqual(result["status"], "unknown")
        self.assertEqual(result["phase"], "write")
        self.assertFalse(result["retry_safe"])
        self.assertEqual(self.fake.put_count, 0)
        self.assertEqual(self.fake.state["data"]["processDefinition"]["version"], 3)

    def test_verify_timeout_after_write_is_partial(self):
        self.fake.timeout_on_verify = True
        result = self.tools["ds_update_task_param"](
            project_name=PROJECT,
            workflow_code=WORKFLOW_CODE,
            task_name=TASK_NAME,
            updates={"sql": NEW_SQL},
        )
        self.assertEqual(result["status"], "partially_applied")
        self.assertEqual(result["phase"], "verify")
        self.assertTrue(result["persisted"])
        self.assertEqual(self.fake.put_count, 1)

    def test_online_timeout_after_write_is_partial(self):
        self.fake.timeout_on_online = True
        result = self.tools["ds_update_task_param"](
            project_name=PROJECT,
            workflow_code=WORKFLOW_CODE,
            task_name=TASK_NAME,
            updates={"sql": NEW_SQL},
        )
        self.assertEqual(result["status"], "partially_applied")
        self.assertEqual(result["phase"], "online")
        self.assertTrue(result["persisted"])
        self.assertEqual(self.fake.put_count, 1)


if __name__ == "__main__":
    unittest.main()
