import unittest
from pathlib import Path
from unittest.mock import patch
from streamlit.testing.v1 import AppTest
from agent.react_agent import ReactAgent
from agent.runtime import DeadlineExceeded

APP = str(Path(__file__).resolve().parents[1] / "app.py")

class PageFlowTests(unittest.TestCase):
    def test_chat_identity_switch_and_clear(self):
        page = AppTest.from_file(APP, default_timeout=20).run()
        self.assertEqual(len(page.exception), 0)
        self.assertEqual(page.session_state["agent"].user_id, "1001")
        with patch.object(ReactAgent, "execute_stream", return_value=iter(["测试回答"])):
            page.chat_input[0].set_value("你好").run()
        self.assertEqual(len(page.exception), 0)
        self.assertEqual(len(page.session_state["message"]), 2)
        page.text_input[0].set_value("1002").run()
        self.assertEqual(page.session_state["agent"].user_id, "1002")
        self.assertEqual(page.session_state["message"], [])
        with patch.object(ReactAgent, "execute_stream", return_value=iter(["另一个回答"])):
            page.chat_input[0].set_value("你好").run()
        page.button[0].click().run()
        self.assertEqual(page.session_state["message"], [])
        self.assertEqual(page.session_state["agent"].messages, [])

    def test_failed_turn_does_not_destroy_successful_chat(self):
        page = AppTest.from_file(APP, default_timeout=20).run()
        with patch.object(ReactAgent, "execute_stream", return_value=iter(["第一次成功"])):
            page.chat_input[0].set_value("第一问").run()
        with patch.object(ReactAgent, "execute_stream", side_effect=ConnectionError("offline")):
            page.chat_input[0].set_value("第二问").run()
        self.assertEqual(len(page.exception), 0)
        self.assertEqual(len(page.error), 1)
        self.assertEqual(len(page.session_state["message"]), 2)
        self.assertEqual(page.session_state["message"][0]["content"], "第一问")

    def test_runtime_timeout_is_readable_and_not_committed(self):
        page = AppTest.from_file(APP, default_timeout=20).run()
        with patch.object(ReactAgent, 'execute_stream', side_effect=DeadlineExceeded('本轮已超过总时间预算')):
            page.chat_input[0].set_value('慢请求').run()
        self.assertEqual(len(page.exception), 0)
        self.assertIn('总时间预算', page.error[0].value)
        self.assertEqual(page.session_state['message'], [])

if __name__ == "__main__":
    unittest.main()

