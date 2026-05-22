from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from desktop_mentor_app.model_client.base import ModelResponse, ToolCall
from desktop_mentor_app.tools.executor import execute_control_plan
from desktop_mentor_app.tools.registry import build_control_plan, build_control_plan_from_model_response
from desktop_mentor_app.tools.types import PermissionLevel


class ControlPlanningTests(unittest.TestCase):
    def test_write_command_builds_confirmation_plan(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            plan = build_control_plan("/write note.txt :: hello", tmpdir)
        self.assertIsNotNone(plan)
        assert plan is not None
        self.assertEqual(plan.action, "write_file")
        self.assertEqual(plan.args["content"], "hello")
        self.assertEqual(Path(str(plan.args["path"])).name, "note.txt")
        self.assertEqual(plan.permission, PermissionLevel.USER_APPROVAL)

    def test_shell_string_run_is_blocked(self) -> None:
        plan = build_control_plan("/run sh -c echo hi")
        self.assertIsNotNone(plan)
        assert plan is not None
        self.assertTrue(plan.is_blocked)
        self.assertEqual(plan.permission, PermissionLevel.BLOCKED)

    def test_model_response_tool_call_keeps_read_only_permission(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            target = Path(tmpdir) / "readme.txt"
            target.write_text("ok", encoding="utf-8")
            response = ModelResponse(
                "先看这个。",
                tool_calls=[ToolCall("tool-1", "read_file", {"path": str(target)}, f'{{"path":"{target}"}}')],
            )
            plan, cleaned = build_control_plan_from_model_response(response, tmpdir)
        self.assertIsNotNone(plan)
        assert plan is not None
        self.assertEqual(plan.action, "read_file")
        self.assertEqual(plan.permission, PermissionLevel.READ_ONLY)
        self.assertEqual(cleaned, "先看这个。")

    def test_path_info_is_a_read_only_base_tool(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            target = Path(tmpdir) / "calc"
            target.mkdir()
            response = ModelResponse(
                "",
                tool_calls=[ToolCall("tool-1", "path_info", {"path": str(target)}, f'{{"path":"{target}"}}')],
            )
            plan, _cleaned = build_control_plan_from_model_response(response, tmpdir)
        self.assertIsNotNone(plan)
        assert plan is not None
        self.assertEqual(plan.action, "path_info")
        self.assertEqual(plan.permission, PermissionLevel.READ_ONLY)

    def test_path_info_executor_reports_path_state(self) -> None:
        old_config = os.environ.get("DESKTOP_MENTOR_CONFIG")
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                os.environ["DESKTOP_MENTOR_CONFIG"] = str(Path(tmpdir) / "config.json")
                target = Path(tmpdir) / "run.sh"
                target.write_text("#!/bin/sh\n", encoding="utf-8")
                plan = build_control_plan(f"/stat {target}", tmpdir)
                assert plan is not None
                result = execute_control_plan(plan)
        finally:
            if old_config is None:
                os.environ.pop("DESKTOP_MENTOR_CONFIG", None)
            else:
                os.environ["DESKTOP_MENTOR_CONFIG"] = old_config
        self.assertTrue(result.ok)
        self.assertIn("exists: True", result.output)
        self.assertIn("type: file", result.output)

    def test_model_response_without_tool_calls_returns_text_only(self) -> None:
        plan, cleaned = build_control_plan_from_model_response(ModelResponse("只是说明，不调用工具。"), "/tmp")
        self.assertIsNone(plan)
        self.assertEqual(cleaned, "只是说明，不调用工具。")


if __name__ == "__main__":
    unittest.main()
