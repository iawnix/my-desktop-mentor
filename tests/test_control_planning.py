from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from desktop_mentor_app.control import PermissionLevel
from desktop_mentor_app.tools.registry import build_control_plan, build_control_plan_from_agent_reply


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

    def test_agent_reply_control_request_promotes_read_to_approval(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            target = Path(tmpdir) / "readme.txt"
            target.write_text("ok", encoding="utf-8")
            plan, cleaned = build_control_plan_from_agent_reply(
                f"先看这个。\nCONTROL_REQUEST: /read {target}",
                tmpdir,
            )
        self.assertIsNotNone(plan)
        assert plan is not None
        self.assertEqual(plan.action, "read_file")
        self.assertEqual(plan.permission, PermissionLevel.USER_APPROVAL)
        self.assertEqual(cleaned, "先看这个。")


if __name__ == "__main__":
    unittest.main()
