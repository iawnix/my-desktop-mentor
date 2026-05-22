from __future__ import annotations

import os
import tempfile
import unittest

from desktop_mentor_app.state.conversations import (
    append_chat_turn,
    create_conversation_session,
    delete_conversation_session,
    list_conversation_sessions,
    session_messages_path,
)


class ConversationSessionTests(unittest.TestCase):
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

    def test_delete_conversation_session_removes_file_and_index_entry(self) -> None:
        older = create_conversation_session("旧会话")
        append_chat_turn("你好", "在。", older.session_id)
        current = create_conversation_session("当前会话")
        append_chat_turn("要删除", "好的。", current.session_id)
        current_path = session_messages_path(current.session_id)

        next_session = delete_conversation_session(current.session_id)

        self.assertEqual(next_session.session_id, older.session_id)
        self.assertFalse(current_path.exists())
        session_ids = [session.session_id for session in list_conversation_sessions()]
        self.assertIn(older.session_id, session_ids)
        self.assertNotIn(current.session_id, session_ids)

    def test_delete_only_conversation_creates_fresh_active_session(self) -> None:
        current = create_conversation_session("唯一会话")
        append_chat_turn("你好", "在。", current.session_id)
        current_path = session_messages_path(current.session_id)

        next_session = delete_conversation_session(current.session_id)

        self.assertFalse(current_path.exists())
        self.assertNotEqual(next_session.session_id, current.session_id)
        self.assertEqual(list_conversation_sessions()[0].session_id, next_session.session_id)


if __name__ == "__main__":
    unittest.main()
