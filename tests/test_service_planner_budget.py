"""Examples can be discarded without discarding user evidence or repair rules."""
import json
from pathlib import Path

import pytest

from agent.context_budget import ContextBudgetExceeded
from service_desk import plan_core, planner


def test_planner_removes_only_marked_example_when_request_is_tight(monkeypatch, tmp_path):
    folder = tmp_path / 'prompts'
    folder.mkdir()
    (folder / 'service_planner.txt').write_text(
        '保留安全规则\n[示例开始]长示例[示例结束]\n保留修复规则', encoding='utf-8')
    monkeypatch.setattr(planner, 'ROOT', tmp_path)
    seen = []
    def admit(messages, **kwargs):
        seen.append(messages)
        if '长示例' in messages[0].content:
            raise ContextBudgetExceeded(100, 90)
    monkeypatch.setattr(planner, 'enforce_request', admit)
    feedback = {'validation_errors': [{'code': 'P3', 'detail': '保留出处检查'}]}
    messages = planner.planner_messages('保留完整用户原话', [], [], {'business_date': '2026-01-12'},
        feedback, model=None, policy=None, run=None, schema={})
    assert len(seen) == 2
    assert messages[0].content == '保留安全规则\n\n保留修复规则'
    data = json.loads(messages[1].content)
    assert data['query'] == '保留完整用户原话'
    assert data['feedback'] == feedback


def test_planner_still_rejects_over_budget_rules_or_user_query(monkeypatch, tmp_path):
    folder = tmp_path / 'prompts'
    folder.mkdir()
    (folder / 'service_planner.txt').write_text('不可再裁剪的规则', encoding='utf-8')
    monkeypatch.setattr(planner, 'ROOT', tmp_path)
    def reject(*args, **kwargs):
        raise ContextBudgetExceeded(100, 90)
    monkeypatch.setattr(planner, 'enforce_request', reject)
    with pytest.raises(ContextBudgetExceeded):
        planner.planner_messages('用户原话', [], [], {'business_date': '2026-01-12'}, {},
                                model=None, policy=None, run=None, schema={})


def test_planner_complete_example_satisfies_unmodified_core():
    prompt = (Path(__file__).resolve().parents[1] / 'prompts/service_planner.txt').read_text(encoding='utf-8')
    example = prompt.split('[示例开始]', 1)[1].split('[示例结束]', 1)[0]
    plan = json.loads(example[example.index('{'):].strip())
    checked = plan_core.validate_plan(plan, {
        'user_text': '吸口报E03，已自查仍异常。查错误原因，准备1月20日16点的上门卡片',
        'history_user_texts': [], 'business_date': '2026-01-12', 'pending_cards': [],
        'remaining_model_calls': 7, 'remaining_tool_calls': 12,
    })
    assert checked['ok'], checked['errors']
