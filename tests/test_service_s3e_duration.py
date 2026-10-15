from copy import deepcopy

import pytest

from service_desk import plan_core, planner
from service_desk.render import guard_text
from test_service_reads import seed_path, read
from test_service_agent import db, graph
from test_service_plan_agent import visit_plan, planned


@pytest.mark.parametrize('unit', ['秒', '小时', '周', '工作日', '个工作日'])
def test_guard_duration_drop_and_preserve(unit):
    text = f'将在30 {unit}内完成。'
    kept, removed = guard_text(text, [])
    assert not kept and removed == [text]
    kept, removed = guard_text(text, [text])
    assert kept == text and not removed


