#!/usr/bin/env python3
"""Unit tests for DolphinScheduler API path-compatibility handling.

Covers the pure segment-rewrite logic (api_compat) and the client-side
version detection / caching, none of which need a live DS instance.
"""

import os
import sys
import unittest
import urllib.error
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dolphin_mcp_pilot import api_compat, client, config


class TestApplyStyle(unittest.TestCase):
    """Path-segment rewriting."""

    def test_workflow_style_rewrites_definition_segment(self):
        self.assertEqual(
            api_compat.apply_style("/projects/abc/process-definition/42", "workflow"),
            "/projects/abc/workflow-definition/42",
        )

    def test_workflow_style_rewrites_instances_segment(self):
        self.assertEqual(
            api_compat.apply_style(
                "/projects/abc/process-instances/7/tasks", "workflow"
            ),
            "/projects/abc/workflow-instances/7/tasks",
        )

    def test_workflow_style_preserves_query_string(self):
        self.assertEqual(
            api_compat.apply_style(
                "/projects/abc/process-definition?pageNo=1&pageSize=10", "workflow"
            ),
            "/projects/abc/workflow-definition?pageNo=1&pageSize=10",
        )

    def test_process_style_is_noop(self):
        path = "/projects/abc/process-definition/42"
        self.assertEqual(api_compat.apply_style(path, "process"), path)

    def test_auto_style_is_noop(self):
        # apply_style only rewrites for the resolved "workflow" style.
        path = "/projects/abc/process-instances"
        self.assertEqual(api_compat.apply_style(path, "auto"), path)

    def test_does_not_touch_singular_start_process_instance(self):
        # executors/start-process-instance is a different endpoint that was
        # NOT renamed; the whole-segment match must leave it intact.
        path = "/projects/abc/executors/start-process-instance"
        self.assertEqual(api_compat.apply_style(path, "workflow"), path)

    def test_does_not_touch_unrelated_segments(self):
        path = "/projects/abc/schedules/5/online"
        self.assertEqual(api_compat.apply_style(path, "workflow"), path)

    def test_idempotent_on_already_workflow_path(self):
        path = "/projects/abc/workflow-definition/42"
        self.assertEqual(api_compat.apply_style(path, "workflow"), path)

    def test_empty_path(self):
        self.assertEqual(api_compat.apply_style("", "workflow"), "")


class TestNormalizeStyle(unittest.TestCase):
    """Configured-style normalisation."""

    def test_normalize_style(self):
        self.assertEqual(api_compat.normalize_style("WORKFLOW"), "workflow")
        self.assertEqual(api_compat.normalize_style(" process "), "process")
        self.assertEqual(api_compat.normalize_style("bogus"), "auto")
        self.assertEqual(api_compat.normalize_style(None), "auto")


class TestClientStyleResolution(unittest.TestCase):
    """Client-side detection, caching, and path resolution."""

    def setUp(self):
        client._resolved_api_style = None

    def tearDown(self):
        client._resolved_api_style = None

    def test_explicit_workflow_skips_detection(self):
        with patch.object(config, "DS_API_STYLE", "workflow"):
            with patch.object(client, "_detect_api_style") as detect:
                self.assertEqual(
                    client._resolve_path("/projects/x/process-definition"),
                    "/projects/x/workflow-definition",
                )
                detect.assert_not_called()

    def test_explicit_process_skips_detection(self):
        with patch.object(config, "DS_API_STYLE", "process"):
            with patch.object(client, "_detect_api_style") as detect:
                self.assertEqual(
                    client._resolve_path("/projects/x/process-definition"),
                    "/projects/x/process-definition",
                )
                detect.assert_not_called()

    def test_auto_detects_once_and_caches(self):
        with patch.object(config, "DS_API_STYLE", "auto"):
            with patch.object(
                client, "_detect_api_style", return_value="workflow"
            ) as detect:
                first = client._resolve_path("/projects/x/process-instances")
                second = client._resolve_path("/projects/x/process-definition")
                self.assertEqual(first, "/projects/x/workflow-instances")
                self.assertEqual(second, "/projects/x/workflow-definition")
                detect.assert_called_once()

    def test_detect_returns_workflow_when_route_exists(self):
        with patch.object(client, "ds_api_request", return_value={"code": 0}) as req:
            self.assertEqual(client._detect_api_style(), "workflow")
            # Probe must bypass resolution to avoid recursion.
            _, kwargs = req.call_args
            self.assertFalse(kwargs.get("_resolve", True))

    def test_detect_returns_process_on_404(self):
        err = urllib.error.HTTPError("u", 404, "not found", None, None)
        with patch.object(client, "ds_api_request", side_effect=err):
            self.assertEqual(client._detect_api_style(), "process")

    def test_detect_returns_workflow_on_403(self):
        # 403 means the route resolved but denied us -> the controller exists.
        err = urllib.error.HTTPError("u", 403, "forbidden", None, None)
        with patch.object(client, "ds_api_request", side_effect=err):
            self.assertEqual(client._detect_api_style(), "workflow")

    def test_detect_returns_none_when_inconclusive(self):
        # 401 / 5xx / network errors are inconclusive: no confident verdict.
        for err in (
            urllib.error.HTTPError("u", 401, "unauthorized", None, None),
            urllib.error.HTTPError("u", 502, "bad gateway", None, None),
            OSError("timeout"),
        ):
            with patch.object(client, "ds_api_request", side_effect=err):
                self.assertIsNone(client._detect_api_style())

    def test_inconclusive_probe_is_not_cached(self):
        # A transient failure must not stick the tool on the legacy paths for
        # the whole process lifetime; the next call re-probes and self-heals.
        with patch.object(config, "DS_API_STYLE", "auto"):
            with patch.object(
                client, "_detect_api_style", side_effect=[None, "workflow"]
            ) as detect:
                self.assertEqual(
                    client._resolve_path("/projects/x/process-definition"),
                    "/projects/x/process-definition",
                )
                self.assertIsNone(client._resolved_api_style)
                self.assertEqual(
                    client._resolve_path("/projects/x/process-definition"),
                    "/projects/x/workflow-definition",
                )
                self.assertEqual(detect.call_count, 2)


if __name__ == "__main__":
    unittest.main()
