from __future__ import annotations

import json
import os
import tempfile
import unittest

from desktop_mentor_app.config.store import user_memory_path
from desktop_mentor_app.state.user_memory import (
    add_user_memory,
    build_user_memory_context,
    delete_user_memory,
    load_user_memories,
    record_user_memory_turn,
    set_user_memory_enabled,
    update_user_memory,
)


class UserMemoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.old_config = os.environ.get("DESKTOP_MENTOR_CONFIG")
        os.environ["DESKTOP_MENTOR_CONFIG"] = os.path.join(self.tmpdir.name, "config.json")

    def tearDown(self) -> None:
        if self.old_config is None:
            os.environ.pop("DESKTOP_MENTOR_CONFIG", None)
        else:
            os.environ["DESKTOP_MENTOR_CONFIG"] = self.old_config
        self.tmpdir.cleanup()

    def test_add_update_disable_delete_memory(self) -> None:
        memory = add_user_memory("默认先给结论，再给细节。", source="manual")

        self.assertIsNotNone(memory)
        assert memory is not None
        self.assertTrue(user_memory_path().exists())
        self.assertIn("默认先给结论", build_user_memory_context("今天怎么推进", 4))

        updated = update_user_memory(memory.memory_id, text="默认用中文，先给结论。")
        self.assertIsNotNone(updated)
        self.assertIn("默认用中文", build_user_memory_context("今天怎么推进", 4))

        set_user_memory_enabled(memory.memory_id, False)
        self.assertNotIn("默认用中文", build_user_memory_context("今天怎么推进", 4))

        self.assertTrue(delete_user_memory(memory.memory_id))
        self.assertEqual(load_user_memories(), [])

    def test_record_turn_extracts_only_memory_like_user_text(self) -> None:
        recorded = record_user_memory_turn("以后默认先给我结论。这个项目不要自动删除文件。", "ok", session_id="s1")

        self.assertEqual(len(recorded), 2)
        self.assertIn("以后默认先给我结论", build_user_memory_context("", 4))
        self.assertIn("这个项目不要自动删除文件", build_user_memory_context("", 4))
        self.assertEqual(record_user_memory_turn("普通聊天内容", "ok", session_id="s1"), [])

    def test_load_memory_accepts_string_enabled_flags(self) -> None:
        path = user_memory_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "version": 1,
                    "memories": [
                        {"id": "disabled", "text": "默认使用中文。", "enabled": "false"},
                        {"id": "enabled", "text": "默认先给结论。", "enabled": "true"},
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        memories = load_user_memories()

        self.assertEqual([memory.memory_id for memory in memories], ["disabled", "enabled"])
        self.assertFalse(memories[0].enabled)
        self.assertTrue(memories[1].enabled)
        context = build_user_memory_context("", 4)
        self.assertNotIn("默认使用中文", context)
        self.assertIn("默认先给结论", context)


if __name__ == "__main__":
    unittest.main()
