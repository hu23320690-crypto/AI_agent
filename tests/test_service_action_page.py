"""Streamlit AppTest card flows; real SQLite/agents with scripted models."""
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
import shutil
import sqlite3
from unittest.mock import patch

from langchain_core.messages import HumanMessage
import pytest
from streamlit.testing.v1 import AppTest

from agent.context_budget import ContextPolicy
from agent.react_agent import ReactAgent
from service_desk.db import init_db
from test_core_flows import ScriptedModel, answer, call

APP = str(Path(__file__).resolve().parents[1] / 'app.py')


@pytest.fixture(scope='module')
def template(tmp_path_factory):
    return init_db(tmp_path_factory.mktemp('service-action-page') / 'seed.db')


@pytest.fixture
def db(template, tmp_path):
    path = tmp_path / 'service.db'
    shutil.copyfile(template, path)
    return path


@contextmanager
def page_factory(monkeypatch, db, responses=(), *, toolset='service'):
    monkeypatch.setenv('AGENT_TOOLSET', toolset)

    def factory(**kwargs):
        return ReactAgent(**kwargs, service_db_path=db, model=ScriptedModel(responses=list(responses)),
                          context_policy=ContextPolicy(window_tokens=32768, reserve_output_tokens=1024,
                                                       reasoning_enabled=False))

    with patch('agent.react_agent.ReactAgent', side_effect=factory):
        yield


def buttons(page):
    return [button.label for button in page.button]


def click_button(page, label):
    return next(button for button in page.button if button.label == label).click().run()


def order_responses():
    return [call('propose_order', device_id='D-1002-01', sku='SKU-FILTER', qty=1), answer('请使用下方卡片确认')]


def order_page():
    page = AppTest.from_file(APP, default_timeout=20).run()
    page.text_input[0].set_value('1002').run()
    page.chat_input[0].set_value('购买一个滤网').run()
    assert not page.exception
    assert buttons(page) == ['确认', '拒绝', '清空对话']
    assert any('有效期至：' in caption.value for caption in page.caption)
    assert any('SKU-FILTER' in item.value for item in page.markdown)
    return page


@pytest.mark.parametrize('operation,status', [('确认', 'executed'), ('拒绝', 'rejected')])
def test_card_appears_decision_renders_result_and_removes_buttons(monkeypatch, db, operation, status):
    with page_factory(monkeypatch, db, order_responses()):
        page = order_page()
        agent = page.session_state['agent']
        original_model_calls = len(agent.summary_model.seen)
        click_button(page, operation)
        assert not page.exception and not page.error
        assert buttons(page) == ['清空对话']
        with sqlite3.connect(db) as connection:
            assert connection.execute('SELECT status FROM pending_actions').fetchone()[0] == status
            added = connection.execute('SELECT count(*) FROM orders WHERE source_action_id IS NOT NULL').fetchone()[0]
        assert added == (1 if status == 'executed' else 0)
        history = agent.messages
        assert isinstance(history[-2], HumanMessage) and history[-2].name == 'action_event'
        assert history[-2].content.startswith('[卡片操作] ' + operation)
        result_text = history[-1].content
        assert result_text in [m.value for m in page.markdown]
        assert len(agent.summary_model.seen) == original_model_calls
        assert page.session_state['message'][-1] == {'role': 'assistant', 'content': result_text}
        previous = list(history)
        page.run()
        assert agent.messages == previous and buttons(page) == ['清空对话']


@pytest.mark.parametrize('terminal', ['expired', 'failed', 'superseded'])
def test_nonpending_card_states_have_no_buttons(monkeypatch, db, terminal):
    with page_factory(monkeypatch, db, order_responses()):
        page = order_page()
        if terminal == 'failed':
            with sqlite3.connect(db) as connection:
                connection.execute("UPDATE consumables SET stock=0 WHERE sku='SKU-FILTER'")
            click_button(page, '确认')
        else:
            with sqlite3.connect(db) as connection:
                if terminal == 'expired':
                    connection.execute('UPDATE pending_actions SET expires_at=?',
                                       ((datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat(),))
                else:
                    connection.execute("UPDATE pending_actions SET status='superseded'")
            page.run()
        assert not page.exception and buttons(page) == ['清空对话']
        with sqlite3.connect(db) as connection:
            assert connection.execute('SELECT status FROM pending_actions').fetchone()[0] == terminal
        assert any('状态：' in item.value for item in page.caption)
        assert not any('有效期至：' in item.value for item in page.caption)


def test_switch_user_and_clear_generate_new_service_session_ids(monkeypatch, db):
    with page_factory(monkeypatch, db, order_responses()):
        page = order_page()
        first = page.session_state['session_id']
        assert page.session_state['agent'].session_id == first
        page.text_input[0].set_value('1003').run()
        second = page.session_state['session_id']
        assert second != first and page.session_state['message'] == []
        assert buttons(page) == ['清空对话']
        page.button[0].click().run()
        third = page.session_state['session_id']
        assert third not in (first, second) and page.session_state['agent'].session_id == third
        assert page.session_state['agent'].messages == []
        with sqlite3.connect(db) as connection:
            assert connection.execute('SELECT session_id,status FROM pending_actions').fetchone() == (first, 'pending')


def test_missing_database_prompts_init_and_never_creates_file(monkeypatch, tmp_path):
    db = tmp_path / 'missing.db'
    with page_factory(monkeypatch, db, [answer('不应调用模型')]):
        page = AppTest.from_file(APP, default_timeout=20).run()
        assert not page.exception and page.warning[0].value == '请先运行 scripts/manage.py service-db init'
        page.chat_input[0].set_value('购买滤网').run()
        assert not db.exists() and page.session_state['message'] == []
        assert page.session_state['agent'].summary_model.seen == []
        assert buttons(page) == ['清空对话']


def test_legacy_page_shape_identity_clear_and_no_cards_are_unchanged(monkeypatch, db):
    with page_factory(monkeypatch, db, [answer('legacy 回答')], toolset='legacy'):
        page = AppTest.from_file(APP, default_timeout=20).run()
        assert not page.exception and not page.warning
        assert buttons(page) == ['清空对话']
        assert [item.label for item in page.text_input] == ['演示用户 ID', '所在城市（可选）']
        assert [item.value for item in page.caption] == [
            '内置使用记录覆盖 2025 年。可试：生成我 2025 年 8 月的使用报告。',
            '用户 ID 用于选择演示数据；天气服务尚未接入。']
        page.chat_input[0].set_value('你好').run()
        assert page.session_state['message'] == [
            {'role': 'user', 'content': '你好'}, {'role': 'assistant', 'content': 'legacy 回答'}]
        assert buttons(page) == ['清空对话']
        page.text_input[0].set_value('1002').run()
        assert page.session_state['message'] == [] and page.session_state['agent'].user_id == '1002'
        page.button[0].click().run()
        assert page.session_state['agent'].messages == []
