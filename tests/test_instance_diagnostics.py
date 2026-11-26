#!/usr/bin/env python3
"""日志诊断与补数防呆行为测试；不访问真实 DS。"""

import unittest
from unittest.mock import patch

from dolphin_mcp_pilot.tools import instance as inst


class DummyMCP:
    def __init__(self):
        self.tools = {}

    def tool(self):
        def decorator(func):
            self.tools[func.__name__] = func
            return func

        return decorator


class InstanceDiagnosticsTests(unittest.TestCase):
    def setUp(self):
        self.mcp = DummyMCP()
        inst.register_instance_tools(self.mcp)
        self.tools = self.mcp.tools

    def test_default_log_is_single_page_and_unfiltered(self):
        with patch.object(
            inst, "ds_get", return_value={"code": 0, "data": "SQL\nINFO"}
        ) as get:
            result = self.tools["ds_get_task_log"](task_instance_id=7)
        self.assertEqual(result["log"], "SQL\nINFO")
        self.assertFalse(result["filtered"])
        self.assertEqual(get.call_count, 1)

    def test_error_only_scans_bounded_pages_with_context(self):
        pages = {
            0: "SELECT a\nSELECT b",
            2: "SELECT c\nException: bad column",
            4: "Traceback detail",
        }

        def get_log(path, timeout=None):
            skip = int(path.split("skipLineNum=")[1].split("&")[0])
            return {"code": 0, "data": pages.get(skip, "")}

        with patch.object(inst, "ds_get", side_effect=get_log):
            result = self.tools["ds_get_task_log"](
                task_instance_id=7,
                limit=2,
                error_only=True,
                context_lines=1,
                max_scan_lines=5,
            )
        self.assertEqual(result["match_count"], 2)
        self.assertEqual(result["scanned_lines"], 5)
        self.assertEqual(result["next_skip_line_num"], 5)
        self.assertIn("SELECT c", result["log"])
        self.assertIn("Exception: bad column", result["log"])
        self.assertNotIn("SELECT a", result["log"])

    def test_latest_failure_sorts_by_end_time_and_filters_sql(self):
        def get(path, timeout=None):
            if path.startswith("/projects/1/process-instances?"):
                return {
                    "code": 0,
                    "data": {
                        "totalList": [
                            {
                                "id": 10,
                                "processDefinitionCode": 100,
                                "state": "FAILURE",
                                "endTime": "2026-09-01 08:00:00",
                            },
                            {
                                "id": 20,
                                "processDefinitionCode": 100,
                                "state": "FAILURE",
                                "endTime": "2026-11-25 08:00:00",
                            },
                            {
                                "id": 15,
                                "processDefinitionCode": 100,
                                "state": "FAILURE",
                                "endTime": "2026-10-01 08:00:00",
                            },
                        ]
                    },
                }
            if path == "/projects/1/process-instances/20/tasks":
                return {
                    "code": 0,
                    "data": {
                        "taskList": [
                            {
                                "taskInstanceId": 900,
                                "taskName": "failed_sql",
                                "taskType": "SQL",
                                "state": "FAILURE",
                            }
                        ]
                    },
                }
            if path.startswith("/log/detail"):
                prefix = "\n".join(f"INFO sql-line-{i}" for i in range(30))
                return {
                    "code": 0,
                    "data": {
                        "message": "INSERT OVERWRITE x SELECT 1\n"
                        + prefix
                        + "\nException: column mismatch\nCaused by: schema drift"
                    },
                }
            raise AssertionError(path)

        with patch.object(inst, "resolve_project_code", return_value=1), patch.object(
            inst, "ds_get", side_effect=get
        ):
            result = self.tools["ds_get_latest_failure_log"](
                project_name="sandbox", workflow_code=100
            )
        self.assertEqual(result["instance_id"], 20)
        log = result["failed_tasks"][0]["log_tail"]
        self.assertIn("column mismatch", log)
        self.assertNotIn("INSERT OVERWRITE", log)

    def test_complement_parallel_payload_and_planned_dates(self):
        with patch.object(inst, "resolve_project_code", return_value=1), patch.object(
            inst, "ds_post", return_value={"code": 0}
        ) as post:
            result = self.tools["ds_complement_data"](
                project_name="sandbox",
                workflow_code=100,
                start_date="2026-09-01",
                end_date="2026-11-01",
                run_mode="RUN_MODE_PARALLEL",
                parallelism=2,
            )
        self.assertEqual(result["planned_instance_count"], 62)
        self.assertEqual(result["planned_biz_dates"][0], "20260831")
        self.assertEqual(result["planned_biz_dates"][-1], "20261031")
        self.assertEqual(result["actual_parallelism"], "not_observed")
        payload = post.call_args.kwargs["data"]
        self.assertEqual(payload["expectedParallelismNumber"], 2)

    def test_complement_dry_run_never_submits(self):
        with patch.object(inst, "resolve_project_code", return_value=1), patch.object(
            inst, "ds_post"
        ) as post:
            result = self.tools["ds_complement_data"](
                project_name="sandbox",
                workflow_code=100,
                partition_date="2026-11-25",
                start_date="2026-01-01",
                dry_run=True,
            )
        self.assertEqual(result["status"], "preview")
        self.assertEqual(result["planned_biz_dates"], ["20261125"])
        self.assertEqual(result["ignored_inputs"], ["start_date", "end_date"])
        post.assert_not_called()

    def test_complement_rejects_invalid_inputs_without_submit(self):
        cases = [
            {"start_date": "2026-11-02", "end_date": "2026-11-01"},
            {"partition_date": "2026-11-25", "parallelism": 2},
            {"partition_date": "2026-11-25", "run_mode": "UNKNOWN"},
            {"partition_date": "2026-11-25", "parallelism": -1},
        ]
        for args in cases:
            with self.subTest(args=args), patch.object(
                inst, "resolve_project_code", return_value=1
            ), patch.object(inst, "ds_post") as post:
                with self.assertRaises(ValueError):
                    self.tools["ds_complement_data"](
                        project_name="sandbox", workflow_code=100, **args
                    )
                post.assert_not_called()


if __name__ == "__main__":
    unittest.main()
