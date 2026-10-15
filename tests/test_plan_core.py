"""plan_core.py 的单元测试（业务日期统一用 2026-01-12）。"""

from __future__ import annotations

import copy
import json

import pytest

from service_desk import plan_core as pc
from service_desk.plan_core import (
    evaluate_condition,
    parse_date,
    parse_month,
    parse_number,
    parse_time,
    plan_json_schema,
    precheck,
    resolve_args,
    validate_plan,
)

BUSINESS_DATE = "2026-01-12"


def test_tools_match_public_service_schemas():
    from service_desk.tool_schema import model_tool_schemas
    public = {s['function']['name']: s['function']['parameters'] for s in model_tool_schemas()}
    assert set(pc.TOOLS) == set(public)
    for name, definition in pc.TOOLS.items():
        schema = public[name]
        assert set(definition['params']) == set(schema['properties'])
        assert definition['required'] == schema['required']
        for param, value in definition['params'].items():
            assert value['type'] == schema['properties'][param]['type']
            assert value.get('enum') == schema['properties'][param].get('enum')


def ctx(**overrides) -> dict:
    """构造一个校验上下文。"""
    base = {
        "user_text": "",
        "history_user_texts": [],
        "business_date": BUSINESS_DATE,
        "pending_cards": [],
        "remaining_model_calls": 8,
        "remaining_tool_calls": 12,
    }
    base.update(overrides)
    return base


def value(arg, evidence) -> dict:
    """原话取值来源。"""
    return {"value": arg, "evidence": evidence}


def slot(date_value, date_evidence, start_value, start_evidence) -> dict:
    """时段挑选里 date 和 start 都是原话取值。"""
    return {
        "date": value(date_value, date_evidence),
        "start": value(start_value, start_evidence),
    }


def enum(arg) -> dict:
    """枚举来源。"""
    return {"enum": arg}


def step(step_id, tool, args=None, depends_on=None, covers=None, condition=None) -> dict:
    """构造一个步骤。"""
    return {
        "id": step_id,
        "tool": tool,
        "args": args or {},
        "depends_on": depends_on or [],
        "covers": covers or [],
        "condition": condition,
    }


def codes(report: dict) -> list[str]:
    """取校验报告里的错误码列表。"""
    return [item["code"] for item in report["errors"]]


# 用户原话和计划：设备 D-1002-01 报 E07，在保才约明天下午一点
VISIT_USER_TEXT = "我的设备 D-1002-01 报 E07，如果还在保就帮我约明天下午一点上门"
VISIT_GOAL = {"id": "g1", "type": "book", "text": "预约上门检查 E07"}
VISIT_PLAN = {
    "goals": [VISIT_GOAL],
    "steps": [
        step("s1", "list_my_devices", covers=["g1"]),
        step(
            "s2",
            "lookup_error_code",
            args={"code": value("E07", "E07"), "device_id": {"from_step": "s1", "pick": "only_device"}},
            depends_on=["s1"],
            covers=["g1"],
        ),
        step(
            "s3",
            "check_warranty",
            args={
                "device_id": {"from_step": "s1", "pick": "only_device"},
                "component": enum("whole_machine"),
            },
            depends_on=["s1", "s2"],
            covers=["g1"],
        ),
        step(
            "s4",
            "find_service_slots",
            args={
                "device_id": {"from_step": "s1", "pick": "only_device"},
                "from_date": value("2026-01-13", "明天"),
            },
            depends_on=["s1"],
            covers=["g1"],
        ),
        step(
            "s5",
            "propose_service_visit",
            args={
                "device_id": {"from_step": "s1", "pick": "only_device"},
                "error_code": value("E07", "E07"),
                "description": {"text": "报 E07"},
                "slot_id": {
                    "from_step": "s4",
                    "pick": "slot_at",
                    **slot("2026-01-13", "明天", "13:00", "下午一点"),
                },
            },
            depends_on=["s1", "s2", "s3", "s4"],
            covers=["g1"],
            condition={
                "type": "warranty_in_force",
                "from_step": "s3",
                "component": "whole_machine",
            },
        ),
    ],
    "ask_user": None,
}

ORDER_USER_TEXT = "上个月 HEPA 滤网剩余不高于 15% 就帮我买两个滤网，设备 D-1006-01"
ORDER_PLAN = {
    "goals": [{"id": "g1", "type": "order", "text": "购买滤网"}],
    "steps": [
        step("s1", "list_my_devices", covers=["g1"]),
        step(
            "s2",
            "fetch_external_data",
            args={"month": value("2025-12", "上个月")},
            depends_on=[],
            covers=["g1"],
        ),
        step(
            "s3",
            "find_consumables",
            args={
                "device_id": {"from_step": "s1", "pick": "only_device"},
                "kind": enum("filter"),
            },
            depends_on=["s1"],
            covers=["g1"],
        ),
        step(
            "s4",
            "propose_order",
            args={
                "device_id": {"from_step": "s1", "pick": "only_device"},
                "sku": {"from_step": "s3", "pick": "consumable_kind", "kind": "filter"},
                "qty": value(2, "两个"),
            },
            depends_on=["s1", "s2", "s3"],
            covers=["g1"],
            condition={
                "type": "record_threshold",
                "from_step": "s2",
                "field_hint": "HEPA",
                "op": "<=",
                "value": 15,
                "unit": "%",
                "evidence": "不高于15%",
            },
        ),
    ],
    "ask_user": None,
}


def valid_visit() -> dict:
    """合法计划的深拷贝。"""
    return copy.deepcopy(VISIT_PLAN)


def valid_order() -> dict:
    """合法下单计划的深拷贝。"""
    return copy.deepcopy(ORDER_PLAN)


# ---------------------------------------------------------------------------
# 规范化
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "evidence,expected",
    [
        ("今天", "2026-01-12"),
        ("明天", "2026-01-13"),
        ("后天", "2026-01-14"),
        ("大后天", "2026-01-15"),
        ("1月15日", "2026-01-15"),
        ("1月15号", "2026-01-15"),
        ("2027年3月2日", "2027-03-02"),
        ("2026-01-13", "2026-01-13"),
        ("２０２６年３月２日", "2026-03-02"),
    ],
)
def test_parse_date(evidence, expected):
    assert parse_date(evidence, BUSINESS_DATE) == expected


def test_parse_date_rejects_garbage():
    assert parse_date("随便什么时候", BUSINESS_DATE) is None
    assert parse_date("", BUSINESS_DATE) is None


@pytest.mark.parametrize(
    "evidence,expected",
    [
        ("上个月", "2025-12"),
        ("这个月", "2026-01"),
        ("本月", "2026-01"),
        ("下个月", "2026-02"),
        ("2025年12月", "2025-12"),
        ("2025-11", "2025-11"),
        ("12月", "2025-12"),
        ("1月", "2026-01"),
    ],
)
def test_parse_month(evidence, expected):
    assert parse_month(evidence, BUSINESS_DATE) == expected


@pytest.mark.parametrize(
    "evidence,expected",
    [
        ("下午一点", "13:00"),
        ("上午九点", "09:00"),
        ("晚上八点", "20:00"),
        ("16点到18点", "16:00"),
        ("13:00–15:00", "13:00"),
        ("13:00-15:00", "13:00"),
        ("下午3:30", "15:30"),
        ("９点", "09:00"),
    ],
)
def test_parse_time(evidence, expected):
    assert parse_time(evidence) == expected


def test_parse_time_rejects_garbage():
    assert parse_time("尽快") is None


@pytest.mark.parametrize(
    "evidence,expected",
    [("两个", 2), ("3件", 3), ("一个", 1), ("十二个", 12), ("２个", 2)],
)
def test_parse_number(evidence, expected):
    assert parse_number(evidence) == expected


def test_normalize_text_converts_fullwidth():
    assert pc.normalize_text("下午１点") == "下午1点"


def test_plan_json_schema_is_dict():
    schema = plan_json_schema()
    assert isinstance(schema, dict)
    assert "properties" in schema


# ---------------------------------------------------------------------------
# 合法计划
# ---------------------------------------------------------------------------

def test_valid_visit_plan_passes():
    report = validate_plan(valid_visit(), ctx(user_text=VISIT_USER_TEXT))
    assert report["ok"] is True, report["errors"]
    assert report["plan"] is not None


def test_valid_order_plan_passes():
    report = validate_plan(valid_order(), ctx(user_text=ORDER_USER_TEXT))
    assert report["ok"] is True, report["errors"]


# ---------------------------------------------------------------------------
# P1
# ---------------------------------------------------------------------------

def test_p1_rejects_extra_key():
    plan = valid_visit()
    plan["extra"] = 1
    report = validate_plan(plan, ctx(user_text=VISIT_USER_TEXT))
    assert report["ok"] is False
    assert codes(report) == ["P1"]
    assert report["plan"] is None


def test_p1_rejects_extra_key_in_step():
    plan = valid_visit()
    plan["steps"][0]["note"] = "x"
    report = validate_plan(plan, ctx(user_text=VISIT_USER_TEXT))
    assert codes(report) == ["P1"]


def test_p1_rejects_duplicate_step_id():
    plan = valid_visit()
    plan["steps"][1]["id"] = "s1"
    report = validate_plan(plan, ctx(user_text=VISIT_USER_TEXT))
    assert codes(report) == ["P1"]


def test_p1_rejects_duplicate_goal_id():
    plan = valid_visit()
    plan["goals"].append({"id": "g1", "type": "diagnose", "text": "重复"})
    report = validate_plan(plan, ctx(user_text=VISIT_USER_TEXT))
    assert codes(report) == ["P1"]


def test_p1_rejects_goal_id_and_step_id_overlap():
    plan = valid_visit()
    plan["steps"][0]["id"] = "g1"
    report = validate_plan(plan, ctx(user_text=VISIT_USER_TEXT))
    assert codes(report) == ["P1"]


def test_p1_rejects_too_many_goals():
    plan = valid_visit()
    plan["goals"] = [{"id": f"g{i}", "type": "diagnose", "text": "x"} for i in range(1, 6)]
    report = validate_plan(plan, ctx(user_text=VISIT_USER_TEXT))
    assert codes(report) == ["P1"]


def test_p1_rejects_too_many_steps():
    plan = valid_visit()
    plan["steps"] = plan["steps"] + [step("s9", "list_my_devices"), step("s10", "list_my_devices")]
    report = validate_plan(plan, ctx(user_text=VISIT_USER_TEXT))
    assert codes(report) == ["P1"]


def test_p1_rejects_bad_goal_type_and_bad_id():
    plan = valid_visit()
    plan["goals"][0]["type"] = "unknown_type"
    assert codes(validate_plan(plan, ctx(user_text=VISIT_USER_TEXT))) == ["P1"]
    plan = valid_visit()
    plan["goals"][0]["id"] = "goal1"
    assert codes(validate_plan(plan, ctx(user_text=VISIT_USER_TEXT))) == ["P1"]
    plan = valid_visit()
    plan["steps"][0]["id"] = "step1"
    assert codes(validate_plan(plan, ctx(user_text=VISIT_USER_TEXT))) == ["P1"]


def test_p1_rejects_bad_ask_user():
    plan = valid_visit()
    plan["ask_user"] = {"type": "unknown", "text": "?"}
    assert codes(validate_plan(plan, ctx(user_text=VISIT_USER_TEXT))) == ["P1"]


# ---------------------------------------------------------------------------
# P2
# ---------------------------------------------------------------------------

def test_p2_rejects_unknown_tool():
    plan = valid_visit()
    plan["steps"][0]["tool"] = "no_such_tool"
    assert codes(validate_plan(plan, ctx(user_text=VISIT_USER_TEXT))) == ["P1"]


def test_p2_rejects_unknown_param():
    plan = valid_visit()
    plan["steps"][0]["args"] = {"model": value("SV-200", "SV-200")}
    report = validate_plan(plan, ctx(user_text=VISIT_USER_TEXT + " SV-200"))
    assert "P2" in codes(report)


def test_p2_rejects_missing_required_param():
    plan = valid_visit()
    del plan["steps"][1]["args"]["code"]
    report = validate_plan(plan, ctx(user_text=VISIT_USER_TEXT))
    assert "P2" in codes(report)


def test_p2_rejects_user_id():
    plan = valid_visit()
    plan["steps"][1]["args"]["user_id"] = value("U-1", "U-1")
    report = validate_plan(plan, ctx(user_text=VISIT_USER_TEXT + " U-1"))
    assert "P2" in codes(report)


# ---------------------------------------------------------------------------
# P3
# ---------------------------------------------------------------------------

def test_p3_rejects_evidence_not_in_user_text():
    plan = valid_visit()
    plan["steps"][1]["args"]["code"] = value("E09", "E09")
    report = validate_plan(plan, ctx(user_text=VISIT_USER_TEXT))
    assert "P3" in codes(report)


def test_p3_accepts_evidence_from_history():
    plan = valid_visit()
    plan["steps"][1]["args"]["code"] = value("E09", "E09")
    report = validate_plan(
        plan, ctx(user_text=VISIT_USER_TEXT, history_user_texts=["上次报的是 E09"])
    )
    assert report["ok"] is True, report["errors"]


def test_p3_rejects_date_recompute_mismatch():
    plan = valid_visit()
    plan["steps"][3]["args"]["from_date"] = value("2026-01-20", "明天")
    report = validate_plan(plan, ctx(user_text=VISIT_USER_TEXT))
    assert "P3" in codes(report)


def test_p3_accepts_date_recompute_match():
    plan = valid_visit()
    plan["steps"][3]["args"]["from_date"] = value("2026-01-13", "明天")
    report = validate_plan(plan, ctx(user_text=VISIT_USER_TEXT))
    assert report["ok"] is True, report["errors"]


def test_p3_rejects_qty_mismatch():
    plan = valid_order()
    plan["steps"][3]["args"]["qty"] = value(3, "两个")
    report = validate_plan(plan, ctx(user_text=ORDER_USER_TEXT))
    assert "P3" in codes(report)


def test_p3_rejects_month_mismatch():
    plan = valid_order()
    plan["steps"][1]["args"]["month"] = value("2025-11", "上个月")
    report = validate_plan(plan, ctx(user_text=ORDER_USER_TEXT))
    assert "P3" in codes(report)


def test_p3_rejects_code_not_from_evidence():
    plan = valid_visit()
    plan["steps"][1]["args"]["code"] = value("E07", "水箱")
    report = validate_plan(plan, ctx(user_text=VISIT_USER_TEXT))
    assert "P3" in codes(report)


def test_p3_rejects_wrong_tool_for_pick():
    plan = valid_visit()
    plan["steps"][2]["args"]["device_id"] = {
        "from_step": "s1",
        "pick": "slot_at",
        **slot("2026-01-13", "明天", "13:00", "下午一点"),
    }
    report = validate_plan(plan, ctx(user_text=VISIT_USER_TEXT))
    assert "P3" in codes(report)


def test_p3_rejects_from_step_tool_mismatch():
    plan = valid_visit()
    plan["steps"][2]["args"]["device_id"] = {"from_step": "s2", "pick": "only_device"}
    report = validate_plan(plan, ctx(user_text=VISIT_USER_TEXT))
    assert "P3" in codes(report)


def test_p3_rejects_param_source_kind_mismatch():
    plan = valid_order()
    plan["steps"][3]["args"]["sku"] = value("SKU-FILTER", "滤网")
    report = validate_plan(plan, ctx(user_text=ORDER_USER_TEXT))
    assert "P3" in codes(report)


def test_p3_rejects_free_text_on_description():
    plan = valid_visit()
    plan["steps"][4]["args"]["description"] = {"free_text": "拖地时显示 E07"}
    report = validate_plan(plan, ctx(user_text=VISIT_USER_TEXT))
    assert "P3" in codes(report)


def test_p3_accepts_free_text_on_query():
    plan = {
        "goals": [{"id": "g1", "type": "knowledge", "text": "水箱怎么保养"}],
        "steps": [
            step("s1", "rag_summarize", args={"query": {"free_text": "水箱保养"}}, covers=["g1"])
        ],
        "ask_user": None,
    }
    report = validate_plan(plan, ctx(user_text="水箱怎么保养"))
    assert report["ok"] is True, report["errors"]


def test_p3_rejects_text_not_in_user_text():
    plan = valid_visit()
    plan["steps"][4]["args"]["description"] = {"text": "别的话"}
    report = validate_plan(plan, ctx(user_text=VISIT_USER_TEXT))
    assert "P3" in codes(report)


def test_p3_rejects_bad_enum():
    plan = valid_visit()
    plan["steps"][2]["args"]["component"] = enum("screen")
    report = validate_plan(plan, ctx(user_text=VISIT_USER_TEXT))
    assert "P3" in codes(report)


def test_p3_rejects_from_pending_without_card():
    plan = valid_order()
    plan["steps"][3]["args"]["sku"] = {"from_pending": "sku", "tool": "propose_order"}
    report = validate_plan(plan, ctx(user_text=ORDER_USER_TEXT))
    assert "P3" in codes(report)


def test_p3_rejects_from_pending_when_two_cards():
    plan = valid_order()
    plan["steps"][3]["args"]["sku"] = {"from_pending": "sku", "tool": "propose_order"}
    cards = [
        {"action_id": "a1", "tool": "propose_order", "args": {"sku": "SKU-FILTER"}},
        {"action_id": "a2", "tool": "propose_order", "args": {"sku": "SKU-MOP"}},
    ]
    report = validate_plan(plan, ctx(user_text=ORDER_USER_TEXT, pending_cards=cards))
    assert "P3" in codes(report)


def test_from_pending_with_single_card_passes_p3_but_p7_still_needs_consumables():
    plan = {
        "goals": [{"id": "g1", "type": "order", "text": "换成两个滤网"}],
        "steps": [
            step(
                "s1",
                "propose_order",
                args={
                    "device_id": {"from_pending": "device_id", "tool": "propose_order"},
                    "sku": {"from_pending": "sku", "tool": "propose_order"},
                    "qty": value(2, "两个"),
                },
                covers=["g1"],
            )
        ],
        "ask_user": None,
    }
    cards = [{"action_id": "a1", "tool": "propose_order", "args": {"device_id": "D-1", "sku": "SKU-FILTER"}}]
    report = validate_plan(plan, ctx(user_text="换成两个滤网", pending_cards=cards))
    # from_pending 只免除设备类的读步骤，耗材清单仍然是必须的
    assert [item["code"] for item in report["errors"]] == ["P7"]
    assert "find_consumables" in report["errors"][0]["detail"]


def test_from_pending_accepted_without_write_flow():
    plan = {
        "goals": [{"id": "g1", "type": "status", "text": "沿用上次的订单"}],
        "steps": [
            step(
                "s1",
                "get_my_orders_and_tickets",
                args={"id": {"from_pending": "sku", "tool": "propose_order"}},
                covers=["g1"],
            )
        ],
        "ask_user": None,
    }
    cards = [{"action_id": "a1", "tool": "propose_order", "args": {"device_id": "D-1", "sku": "SKU-FILTER"}}]
    report = validate_plan(plan, ctx(user_text="查一下订单", pending_cards=cards))
    assert report["ok"] is True, report["errors"]


def test_p3_rejects_condition_evidence_missing():
    plan = valid_order()
    plan["steps"][3]["condition"]["evidence"] = "不高于20%"
    report = validate_plan(plan, ctx(user_text=ORDER_USER_TEXT))
    assert "P3" in codes(report)


def test_p3_rejects_condition_value_mismatch():
    plan = valid_order()
    plan["steps"][3]["condition"]["value"] = 20
    report = validate_plan(plan, ctx(user_text=ORDER_USER_TEXT))
    assert "P3" in codes(report)


def test_p3_rejects_condition_from_step_tool_mismatch():
    plan = valid_order()
    plan["steps"][3]["condition"]["from_step"] = "s3"
    report = validate_plan(plan, ctx(user_text=ORDER_USER_TEXT))
    assert "P3" in codes(report)


def test_invalid_pick_value_is_p1():
    plan = valid_visit()
    plan["steps"][1]["args"]["device_id"] = {"from_step": "s1", "pick": "device_name"}
    report = validate_plan(plan, ctx(user_text=VISIT_USER_TEXT))
    assert codes(report) == ["P1"]
    assert "pick" in report["errors"][0]["detail"]


# ---------------------------------------------------------------------------
# P4
# ---------------------------------------------------------------------------

def test_p4_rejects_reference_to_missing_step():
    plan = valid_visit()
    plan["steps"][2]["args"]["device_id"] = {"from_step": "s8", "pick": "only_device"}
    plan["steps"][2]["depends_on"] = ["s1", "s2", "s8"]
    report = validate_plan(plan, ctx(user_text=VISIT_USER_TEXT))
    assert "P4" in codes(report)


def test_p4_rejects_missing_depends_on():
    plan = valid_visit()
    plan["steps"][4]["depends_on"] = ["s1"]
    report = validate_plan(plan, ctx(user_text=VISIT_USER_TEXT))
    assert "P4" in codes(report)


def test_p4_rejects_cycle():
    plan = valid_visit()
    plan["steps"][0]["depends_on"] = ["s2"]
    report = validate_plan(plan, ctx(user_text=VISIT_USER_TEXT))
    assert "P4" in codes(report)


# ---------------------------------------------------------------------------
# P5
# ---------------------------------------------------------------------------

def test_p5_rejects_uncovered_goal():
    plan = valid_visit()
    plan["goals"].append({"id": "g2", "type": "usage", "text": "看看这个月的用量"})
    report = validate_plan(plan, ctx(user_text=VISIT_USER_TEXT))
    assert "P5" in codes(report)
    assert any("g2" in item["detail"] for item in report["errors"])


def test_p5_allows_uncovered_goal_with_ask_user():
    plan = {
        "goals": [{"id": "g1", "type": "book", "text": "预约上门"}],
        "steps": [],
        "ask_user": {"type": "which_device", "text": "哪一台？"},
    }
    report = validate_plan(plan, ctx(user_text="帮我约上门"))
    assert report["ok"] is True, report["errors"]


def test_p5_rejects_book_goal_without_propose():
    plan = valid_visit()
    plan["steps"][4]["tool"] = "check_warranty"
    plan["steps"][4]["args"] = {"device_id": {"from_step": "s1", "pick": "only_device"}}
    plan["steps"][4]["condition"] = None
    report = validate_plan(plan, ctx(user_text=VISIT_USER_TEXT))
    assert "P5" in codes(report)


def test_p5_rejects_covers_unknown_goal():
    plan = valid_visit()
    plan["steps"][0]["covers"] = ["g9"]
    report = validate_plan(plan, ctx(user_text=VISIT_USER_TEXT))
    assert "P5" in codes(report)


# ---------------------------------------------------------------------------
# P6
# ---------------------------------------------------------------------------

def test_p6_rejects_write_step_depended_on():
    plan = valid_visit()
    plan["steps"].append(
        step("s6", "rag_summarize", args={"query": {"free_text": "保修"}}, depends_on=["s5"], covers=["g1"])
    )
    report = validate_plan(plan, ctx(user_text=VISIT_USER_TEXT))
    assert "P6" in codes(report)


def test_p6_rejects_three_write_steps():
    plan = {
        "goals": [{"id": "g1", "type": "order", "text": "下单并改约"}],
        "steps": [
            step(
                "s1",
                "propose_order",
                args={
                    "device_id": {"from_pending": "device_id", "tool": "propose_order"},
                    "sku": {"from_pending": "sku", "tool": "propose_order"},
                    "qty": value(2, "两个"),
                },
                covers=["g1"],
            ),
            step(
                "s2",
                "propose_order",
                args={
                    "device_id": {"from_pending": "device_id", "tool": "propose_order"},
                    "sku": {"from_pending": "sku", "tool": "propose_order"},
                    "qty": value(2, "两个"),
                },
                covers=["g1"],
            ),
            step(
                "s3",
                "propose_change",
                args={
                    "target_id": {"from_step": "s4", "pick": "record", "kind": "order"},
                    "change": enum("cancel_order"),
                },
                depends_on=["s4"],
                covers=["g1"],
            ),
            step(
                "s4",
                "get_my_orders_and_tickets",
                args={"kind": enum("order")},
                covers=["g1"],
            ),
        ],
        "ask_user": None,
    }
    cards = [{"action_id": "a1", "tool": "propose_order", "args": {"device_id": "D-1", "sku": "SKU-FILTER"}}]
    report = validate_plan(plan, ctx(user_text="换成两个滤网", pending_cards=cards))
    assert "P6" in codes(report)


def test_p6_rejects_condition_on_read_step():
    plan = valid_visit()
    plan["steps"][3]["condition"] = {
        "type": "warranty_in_force",
        "from_step": "s3",
        "component": "battery",
    }
    report = validate_plan(plan, ctx(user_text=VISIT_USER_TEXT))
    assert "P6" in codes(report)


# ---------------------------------------------------------------------------
# P7
# ---------------------------------------------------------------------------

def test_p7_rejects_missing_slots_for_visit():
    plan = valid_visit()
    plan["steps"] = [item for item in plan["steps"] if item["tool"] != "find_service_slots"]
    plan["steps"][3]["args"]["slot_id"] = value("S-east-20260113-2", "明天下午一点")
    plan["steps"][3]["depends_on"] = ["s1", "s2", "s3"]
    report = validate_plan(plan, ctx(user_text=VISIT_USER_TEXT))
    assert "P7" in codes(report)


def test_p7_rejects_missing_warranty_for_visit():
    plan = valid_visit()
    plan["steps"] = [item for item in plan["steps"] if item["tool"] != "check_warranty"]
    plan["steps"][3]["condition"] = None
    plan["steps"][3]["depends_on"] = ["s1", "s2", "s4"]
    report = validate_plan(plan, ctx(user_text=VISIT_USER_TEXT))
    assert "P7" in codes(report)


def test_p7_rejects_missing_consumables_for_order():
    plan = valid_order()
    plan["steps"] = [item for item in plan["steps"] if item["tool"] != "find_consumables"]
    plan["steps"][2]["args"]["sku"] = value("SKU-FILTER", "滤网")
    plan["steps"][2]["depends_on"] = ["s1", "s2"]
    report = validate_plan(plan, ctx(user_text=ORDER_USER_TEXT))
    assert "P7" in codes(report)


def test_p7_rejects_missing_fetch_for_threshold():
    plan = valid_order()
    plan["steps"] = [item for item in plan["steps"] if item["tool"] != "fetch_external_data"]
    report = validate_plan(plan, ctx(user_text=ORDER_USER_TEXT))
    assert "P7" in codes(report)


def test_p7_rejects_missing_records_for_change():
    plan = {
        "goals": [{"id": "g1", "type": "change", "text": "取消订单"}],
        "steps": [
            step(
                "s1",
                "propose_change",
                args={"target_id": value("O-1007-01", "O-1007-01"), "change": enum("cancel_order")},
                covers=["g1"],
            )
        ],
        "ask_user": None,
    }
    report = validate_plan(plan, ctx(user_text="取消订单 O-1007-01"))
    assert "P7" in codes(report)


def test_p7_rejects_missing_slots_for_reschedule():
    plan = {
        "goals": [{"id": "g1", "type": "change", "text": "改约上门时间"}],
        "steps": [
            step(
                "s1",
                "get_my_orders_and_tickets",
                args={"kind": enum("appointment")},
                covers=["g1"],
            ),
            step(
                "s2",
                "propose_change",
                args={
                    "target_id": {"from_step": "s1", "pick": "record", "kind": "appointment"},
                    "change": enum("reschedule"),
                    "new_slot_id": value("S-west-20260115-2", "后天下午"),
                },
                depends_on=["s1"],
                covers=["g1"],
            ),
        ],
        "ask_user": None,
    }
    report = validate_plan(plan, ctx(user_text="帮我把预约改到后天下午"))
    assert "P7" in codes(report)


def test_p7_rejects_knowledge_goal_without_rag():
    plan = {
        "goals": [{"id": "g1", "type": "knowledge", "text": "水箱怎么保养"}],
        "steps": [step("s1", "list_my_devices", covers=["g1"])],
        "ask_user": None,
    }
    report = validate_plan(plan, ctx(user_text="水箱怎么保养"))
    assert "P7" in codes(report)


# ---------------------------------------------------------------------------
# P8
# ---------------------------------------------------------------------------

def test_p8_rejects_model_budget():
    plan = valid_visit()
    report = validate_plan(plan, ctx(user_text=VISIT_USER_TEXT, remaining_model_calls=-1))
    assert "P8" in codes(report)


def test_p8_rejects_tool_budget():
    plan = valid_visit()
    report = validate_plan(plan, ctx(user_text=VISIT_USER_TEXT, remaining_tool_calls=2))
    assert "P8" in codes(report)


# ---------------------------------------------------------------------------
# resolve_args
# ---------------------------------------------------------------------------

DEVICES_RESULT = {
    "s1": {
        "tool": "list_my_devices",
        "args": {},
        "payload": {
            "devices": [
                {
                    "device_id": "D-1020-01",
                    "model_code": "SV-400",
                    "display_name": "自集尘旗舰型",
                    "purchase_date": "2024-03-01",
                },
                {
                    "device_id": "D-1020-02",
                    "model_code": "SV-100",
                    "display_name": "基础扫地型",
                    "purchase_date": "2024-05-01",
                },
            ]
        },
    }
}

ONE_DEVICE_RESULT = {
    "s1": {
        "tool": "list_my_devices",
        "args": {},
        "payload": {
            "devices": [
                {
                    "device_id": "D-1002-01",
                    "model_code": "SV-200",
                    "display_name": "扫拖一体型",
                    "purchase_date": "2024-07-12",
                }
            ]
        },
    }
}

SLOTS_RESULT = {
    "s2": {
        "tool": "find_service_slots",
        "args": {},
        "payload": {
            "device_id": "D-1002-01",
            "slots": [
                {
                    "slot_id": "S-east-20260113-2",
                    "start_at": "2026-01-13T13:00:00+08:00",
                    "end_at": "2026-01-13T15:00:00+08:00",
                    "available": 2,
                }
            ],
        },
    }
}

CONSUMABLES_RESULT = {
    "s3": {
        "tool": "find_consumables",
        "args": {},
        "payload": {
            "device_id": "D-1006-01",
            "consumables": [
                {
                    "sku": "SKU-FILTER",
                    "name": "通用滤网",
                    "kind": "filter",
                    "price_cents": 3900,
                    "stock": 80,
                    "max_per_order": 2,
                },
                {"sku": "SKU-MOP", "name": "清洁拖布", "kind": "mop_pad", "price_cents": 2900, "stock": 0},
            ],
        },
    }
}

RECORDS_RESULT = {
    "s4": {
        "tool": "get_my_orders_and_tickets",
        "args": {},
        "payload": {
            "records": [
                {
                    "kind": "order",
                    "id": "O-1007-01",
                    "device_id": "D-1007-01",
                    "sku": "SKU-MAIN",
                    "qty": 1,
                    "amount_cents": 6900,
                    "status": "processing",
                },
                {
                    "kind": "order",
                    "id": "O-1008-01",
                    "device_id": "D-1008-01",
                    "sku": "SKU-SIDE",
                    "qty": 2,
                    "amount_cents": 3800,
                    "status": "completed",
                },
                {
                    "kind": "ticket",
                    "id": "T-1004-01",
                    "device_id": "D-1004-01",
                    "error_code": "E09",
                    "description": "主刷不转",
                    "status": "scheduled",
                },
                {
                    "kind": "appointment",
                    "id": "A-1004-01",
                    "ticket_id": "T-1004-01",
                    "slot_id": "S-west-20260113-2",
                    "status": "scheduled",
                },
            ]
        },
    }
}


def test_resolve_only_device_ok():
    resolved = resolve_args({"args": {"device_id": {"from_step": "s1", "pick": "only_device"}}},
                            ONE_DEVICE_RESULT, ctx())
    assert resolved == {"status": "ok", "args": {"device_id": "D-1002-01"}}


def test_resolve_only_device_ambiguous():
    resolved = resolve_args({"args": {"device_id": {"from_step": "s1", "pick": "only_device"}}},
                            DEVICES_RESULT, ctx())
    assert resolved["status"] == "ambiguous"
    assert resolved["param"] == "device_id"
    assert resolved["candidates"] == ["D-1020-01", "D-1020-02"]


def test_resolve_only_device_unresolved():
    results = {"s1": {"tool": "list_my_devices", "args": {}, "payload": {"devices": []}}}
    resolved = resolve_args({"args": {"device_id": {"from_step": "s1", "pick": "only_device"}}},
                            results, ctx())
    assert resolved["status"] == "unresolved"


def test_resolve_device_matching_hits_flagship():
    resolved = resolve_args(
        {"args": {"device_id": {"from_step": "s1", "pick": "device_matching", "hint": "旗舰"}}},
        DEVICES_RESULT,
        ctx(),
    )
    assert resolved == {"status": "ok", "args": {"device_id": "D-1020-01"}}


def test_resolve_device_matching_ambiguous():
    resolved = resolve_args(
        {"args": {"device_id": {"from_step": "s1", "pick": "device_matching", "hint": "型"}}},
        DEVICES_RESULT,
        ctx(),
    )
    assert resolved["status"] == "ambiguous"


def test_resolve_slot_at_ok():
    resolved = resolve_args(
        {
            "args": {
                "slot_id": {
                    "from_step": "s2",
                    "pick": "slot_at",
                    **slot("2026-01-13", "明天", "13:00", "下午一点"),
                }
            }
        },
        SLOTS_RESULT,
        ctx(),
    )
    assert resolved == {"status": "ok", "args": {"slot_id": "S-east-20260113-2"}}


def test_resolve_slot_at_unresolved():
    resolved = resolve_args(
        {
            "args": {
                "slot_id": {
                    "from_step": "s2",
                    "pick": "slot_at",
                    **slot("2026-01-20", "1月20日", "13:00", "13:00"),
                }
            }
        },
        SLOTS_RESULT,
        ctx(),
    )
    assert resolved["status"] == "unresolved"
    assert resolved["detail"] == "slot_unavailable"


def test_resolve_consumable_kind_ok():
    resolved = resolve_args(
        {"args": {"sku": {"from_step": "s3", "pick": "consumable_kind", "kind": "filter"}}},
        CONSUMABLES_RESULT,
        ctx(),
    )
    assert resolved == {"status": "ok", "args": {"sku": "SKU-FILTER"}}


def test_resolve_consumable_kind_unresolved():
    resolved = resolve_args(
        {"args": {"sku": {"from_step": "s3", "pick": "consumable_kind", "kind": "dust_bag"}}},
        CONSUMABLES_RESULT,
        ctx(),
    )
    assert resolved["status"] == "unresolved"


def test_resolve_record_by_id():
    resolved = resolve_args(
        {
            "args": {
                "target_id": {
                    "from_step": "s4",
                    "pick": "record",
                    "kind": "order",
                    "id": value("O-1007-01", "订单O-1007-01"),
                }
            }
        },
        RECORDS_RESULT,
        ctx(),
    )
    assert resolved == {"status": "ok", "args": {"target_id": "O-1007-01"}}


def test_resolve_record_by_status_unique():
    resolved = resolve_args(
        {
            "args": {
                "target_id": {
                    "from_step": "s4",
                    "pick": "record",
                    "kind": "order",
                    "status": "processing",
                }
            }
        },
        RECORDS_RESULT,
        ctx(),
    )
    assert resolved == {"status": "ok", "args": {"target_id": "O-1007-01"}}


def test_resolve_record_by_hint_matches_order_sku():
    resolved = resolve_args(
        {
            "args": {
                "target_id": {"from_step": "s4", "pick": "record", "kind": "order", "hint": "MAIN"}
            }
        },
        RECORDS_RESULT,
        ctx(),
    )
    assert resolved == {"status": "ok", "args": {"target_id": "O-1007-01"}}


def test_resolve_record_by_hint_matches_appointment_ticket_description():
    resolved = resolve_args(
        {
            "args": {
                "target_id": {
                    "from_step": "s4",
                    "pick": "record",
                    "kind": "appointment",
                    "hint": "主刷",
                }
            }
        },
        RECORDS_RESULT,
        ctx(),
    )
    assert resolved == {"status": "ok", "args": {"target_id": "A-1004-01"}}


def test_resolve_record_ambiguous():
    resolved = resolve_args(
        {"args": {"target_id": {"from_step": "s4", "pick": "record", "kind": "order"}}},
        RECORDS_RESULT,
        ctx(),
    )
    assert resolved["status"] == "ambiguous"
    assert set(resolved["candidates"]) == {"O-1007-01", "O-1008-01"}


def test_resolve_value_normalized():
    resolved = resolve_args(
        {"args": {"start": value("x", "明天"), "metric": enum("area_m2")}},
        {},
        ctx(),
    )
    assert resolved == {"status": "ok", "args": {"start": "2026-01-13", "metric": "area_m2"}}


def test_resolve_qty_from_evidence():
    resolved = resolve_args({"args": {"qty": value(2, "两个")}}, {}, ctx())
    assert resolved == {"status": "ok", "args": {"qty": 2}}


def test_resolve_from_pending():
    cards = [{"action_id": "a1", "tool": "propose_order", "args": {"device_id": "D-1007-01", "sku": "SKU-FILTER"}}]
    resolved = resolve_args(
        {"args": {"device_id": {"from_pending": "device_id", "tool": "propose_order"}}},
        {},
        ctx(pending_cards=cards),
    )
    assert resolved == {"status": "ok", "args": {"device_id": "D-1007-01"}}


def test_resolve_from_pending_without_card():
    resolved = resolve_args(
        {"args": {"device_id": {"from_pending": "device_id", "tool": "propose_order"}}},
        {},
        ctx(),
    )
    assert resolved["status"] == "unresolved"


def test_resolve_missing_step_result():
    resolved = resolve_args({"args": {"device_id": {"from_step": "s9", "pick": "only_device"}}}, {}, ctx())
    assert resolved["status"] == "unresolved"


# ---------------------------------------------------------------------------
# evaluate_condition
# ---------------------------------------------------------------------------

WARRANTY_FALSE = {
    "s3": {
        "tool": "check_warranty",
        "args": {},
        "payload": {
            "device_id": "D-1002-01",
            "business_date": BUSINESS_DATE,
            "coverage": [
                {"component": "whole_machine", "in_warranty": True, "expires_date": "2026-07-12"},
                {"component": "battery", "in_warranty": False, "expires_date": "2025-07-12"},
            ],
        },
    }
}

MONTH_REPORT = {
    "s2": {
        "tool": "fetch_external_data",
        "args": {"month": "2025-12"},
        "payload": {
            "status": "ok",
            "month": "2025-12",
            "data": {
                "特征": "65㎡公寓 | 单身 | 木地板",
                "效率": "覆盖率:90%\\n日均清扫:50㎡",
                "耗材": "主刷寿命:剩余30天\\nHEPA滤网:剩余10%",
                "对比": "优于85%同面积用户",
            },
        },
    }
}

MONTH_REPORT_REAL_NEWLINE = {
    "s2": {
        "tool": "fetch_external_data",
        "args": {"month": "2025-12"},
        "payload": {
            "status": "ok",
            "month": "2025-12",
            "data": {"耗材": "主刷寿命:剩余30天\nHEPA滤网:剩余10%"},
        },
    }
}


def test_condition_warranty_false_for_battery():
    status, detail = evaluate_condition(
        {"type": "warranty_in_force", "from_step": "s3", "component": "battery"}, WARRANTY_FALSE
    )
    assert status == "false"
    assert detail


def test_condition_warranty_true_for_whole_machine():
    status, _ = evaluate_condition(
        {"type": "warranty_in_force", "from_step": "s3", "component": "whole_machine"},
        WARRANTY_FALSE,
    )
    assert status == "true"


def test_condition_warranty_unknown_for_missing_component():
    status, _ = evaluate_condition(
        {"type": "warranty_in_force", "from_step": "s3", "component": "battery"},
        {"s3": {"tool": "check_warranty", "args": {}, "payload": {"coverage": []}}},
    )
    assert status == "unknown"


def test_condition_warranty_unknown_without_result():
    status, _ = evaluate_condition(
        {"type": "warranty_in_force", "from_step": "s9", "component": "battery"}, {}
    )
    assert status == "unknown"


def test_condition_threshold_true_with_literal_newline():
    status, _ = evaluate_condition(
        {
            "type": "record_threshold",
            "from_step": "s2",
            "field_hint": "HEPA",
            "op": "<=",
            "value": 15,
            "unit": "%",
            "evidence": "不高于15%",
        },
        MONTH_REPORT,
    )
    assert status == "true"


def test_condition_threshold_true_with_real_newline():
    status, _ = evaluate_condition(
        {
            "type": "record_threshold",
            "from_step": "s2",
            "field_hint": "HEPA",
            "op": "<=",
            "value": 15,
            "unit": "%",
            "evidence": "不高于15%",
        },
        MONTH_REPORT_REAL_NEWLINE,
    )
    assert status == "true"


def test_condition_threshold_false():
    status, _ = evaluate_condition(
        {
            "type": "record_threshold",
            "from_step": "s2",
            "field_hint": "HEPA",
            "op": ">=",
            "value": 15,
            "unit": "%",
            "evidence": "不低于15%",
        },
        MONTH_REPORT,
    )
    assert status == "false"


def test_condition_threshold_unknown_unit():
    status, _ = evaluate_condition(
        {
            "type": "record_threshold",
            "from_step": "s2",
            "field_hint": "HEPA",
            "op": "<=",
            "value": 15,
            "unit": "天",
            "evidence": "不高于15天",
        },
        MONTH_REPORT,
    )
    assert status == "unknown"


def test_condition_threshold_unknown_field():
    status, _ = evaluate_condition(
        {
            "type": "record_threshold",
            "from_step": "s2",
            "field_hint": "尘盒",
            "op": "<=",
            "value": 15,
            "unit": "%",
            "evidence": "不高于15%",
        },
        MONTH_REPORT,
    )
    assert status == "unknown"


def test_condition_threshold_unknown_when_status_not_ok():
    results = copy.deepcopy(MONTH_REPORT)
    results["s2"]["payload"]["status"] = "blocked"
    status, _ = evaluate_condition(
        {
            "type": "record_threshold",
            "from_step": "s2",
            "field_hint": "HEPA",
            "op": "<=",
            "value": 15,
            "unit": "%",
            "evidence": "不高于15%",
        },
        results,
    )
    assert status == "unknown"


def test_condition_unknown_type():
    status, _ = evaluate_condition({"type": "something_else"}, {})
    assert status == "unknown"


# ---------------------------------------------------------------------------
# precheck
# ---------------------------------------------------------------------------

ORDER_RESULTS = dict(CONSUMABLES_RESULT)
VISIT_RESULTS = dict(SLOTS_RESULT)
CHANGE_RESULTS = dict(RECORDS_RESULT)


def test_precheck_order_ok():
    assert precheck("propose_order", {"device_id": "D-1006-01", "sku": "SKU-FILTER", "qty": 2}, ORDER_RESULTS) is None


def test_precheck_order_no_catalog():
    result = precheck("propose_order", {"device_id": "D-9999-01", "sku": "SKU-FILTER", "qty": 1}, ORDER_RESULTS)
    assert result["reason_code"] == "no_catalog_evidence"


def test_precheck_order_incompatible():
    result = precheck("propose_order", {"device_id": "D-1006-01", "sku": "SKU-BAD", "qty": 1}, ORDER_RESULTS)
    assert result["reason_code"] == "incompatible_consumable"
    assert result["message"] == "耗材与所选设备型号不兼容"


def test_precheck_order_out_of_stock():
    result = precheck("propose_order", {"device_id": "D-1006-01", "sku": "SKU-MOP", "qty": 1}, ORDER_RESULTS)
    assert result["reason_code"] == "out_of_stock"
    assert result["message"] == "库存不足"


def test_precheck_order_purchase_limit():
    result = precheck("propose_order", {"device_id": "D-1006-01", "sku": "SKU-FILTER", "qty": 3}, ORDER_RESULTS)
    assert result["reason_code"] == "purchase_limit"
    assert result["message"] == "数量超过单次限购"


def test_precheck_visit_ok():
    assert precheck("propose_service_visit", {"slot_id": "S-east-20260113-2"}, VISIT_RESULTS) is None


def test_precheck_visit_slot_unavailable():
    result = precheck("propose_service_visit", {"slot_id": "S-north-20260113-1"}, VISIT_RESULTS)
    assert result["reason_code"] == "slot_unavailable"
    assert result["message"] == "所选时段没有可约名额"


def test_precheck_change_missing_record():
    result = precheck("propose_change", {"target_id": "A-9999-01", "change": "cancel_appointment"}, CHANGE_RESULTS)
    assert result["reason_code"] == "no_record_evidence"


def test_precheck_change_cancel_order_ok():
    assert precheck("propose_change", {"target_id": "O-1007-01", "change": "cancel_order"}, CHANGE_RESULTS) is None


def test_precheck_change_order_not_processing():
    result = precheck("propose_change", {"target_id": "O-1008-01", "change": "cancel_order"}, CHANGE_RESULTS)
    assert result["reason_code"] == "order_not_processing"
    assert result["message"] == "该订单当前不能取消"


def test_precheck_change_reschedule_ok():
    results = dict(CHANGE_RESULTS)
    results["s5"] = {
        "tool": "find_service_slots",
        "args": {},
        "payload": {
            "device_id": "D-1004-01",
            "slots": [
                {"slot_id": "S-west-20260115-2", "start_at": "2026-01-15T13:00:00+08:00", "available": 2}
            ],
        },
    }
    assert precheck(
        "propose_change",
        {"target_id": "A-1004-01", "change": "reschedule", "new_slot_id": "S-west-20260115-2"},
        results,
    ) is None


def test_precheck_change_reschedule_slot_unavailable():
    result = precheck(
        "propose_change",
        {"target_id": "A-1004-01", "change": "reschedule", "new_slot_id": "S-west-20260115-2"},
        CHANGE_RESULTS,
    )
    assert result["reason_code"] == "slot_unavailable"


def test_precheck_change_appointment_not_scheduled():
    results = copy.deepcopy(CHANGE_RESULTS)
    for record in results["s4"]["payload"]["records"]:
        if record["id"] == "A-1004-01":
            record["status"] = "cancelled"
    result = precheck("propose_change", {"target_id": "A-1004-01", "change": "cancel_appointment"}, results)
    assert result["reason_code"] == "appointment_not_scheduled"


CARD_VISIT = {
    "action_id": "a1",
    "tool": "propose_service_visit",
    "args": {
        "device_id": "D-1002-01",
        "error_code": "E07",
        "description": "报 E07",
        "slot_id": "S-east-20260113-2",
    },
}

# 取消订单的计划：target_id 用原话取值
CHANGE_PLAN_ORDER_ID = {
    "goals": [{"id": "g1", "type": "change", "text": "取消订单"}],
    "steps": [
        step("s1", "get_my_orders_and_tickets", args={"kind": enum("order")}, covers=["g1"]),
        step(
            "s2",
            "propose_change",
            args={
                "target_id": {
                    "from_step": "s1",
                    "pick": "record",
                    "kind": "order",
                    "id": value("O-1007-01", "订单O-1007-01"),
                },
                "change": enum("cancel_order"),
            },
            depends_on=["s1"],
            covers=["g1"],
        ),
    ],
    "ask_user": None,
}


def test_precheck_unknown_tool_returns_none():
    assert precheck("list_my_devices", {}, {}) is None


# ---------------------------------------------------------------------------
# slot_at / record 的原话取值
# ---------------------------------------------------------------------------

def test_slot_at_rejects_date_evidence_not_in_user_text():
    plan = valid_visit()
    plan["steps"][4]["args"]["slot_id"]["date"] = value("2026-01-13", "下周三")
    report = validate_plan(plan, ctx(user_text=VISIT_USER_TEXT))
    assert "P3" in codes(report)
    assert any("evidence" in item["detail"] for item in report["errors"])


def test_slot_at_rejects_date_recompute_mismatch():
    plan = valid_visit()
    plan["steps"][4]["args"]["slot_id"]["date"] = value("2026-01-14", "明天")
    report = validate_plan(plan, ctx(user_text=VISIT_USER_TEXT))
    assert "P3" in codes(report)
    assert any("date" in item["detail"] for item in report["errors"])


def test_slot_at_rejects_start_recompute_mismatch():
    plan = valid_visit()
    plan["steps"][4]["args"]["slot_id"]["start"] = value("15:00", "下午一点")
    report = validate_plan(plan, ctx(user_text=VISIT_USER_TEXT))
    assert "P3" in codes(report)
    assert any("start" in item["detail"] for item in report["errors"])


def test_slot_at_rejects_empty_evidence():
    plan = valid_visit()
    plan["steps"][4]["args"]["slot_id"]["date"] = value("2026-01-13", "")
    report = validate_plan(plan, ctx(user_text=VISIT_USER_TEXT))
    assert "P3" in codes(report)
    assert any("不能为空" in item["detail"] for item in report["errors"])


def test_value_rejects_empty_evidence():
    plan = valid_visit()
    plan["steps"][1]["args"]["code"] = value("E07", "")
    report = validate_plan(plan, ctx(user_text=VISIT_USER_TEXT))
    assert "P3" in codes(report)
    assert any("不能为空" in item["detail"] for item in report["errors"])


def test_record_id_accepts_value_inside_evidence():
    plan = CHANGE_PLAN_ORDER_ID
    report = validate_plan(plan, ctx(user_text="把订单O-1007-01取消掉", history_user_texts=[]))
    assert report["ok"] is True, report["errors"]


def test_record_id_rejects_value_absent_from_evidence():
    plan = CHANGE_PLAN_ORDER_ID
    report = validate_plan(plan, ctx(user_text="把订单O-1008-01取消掉", history_user_texts=[]))
    assert "P3" in codes(report)
    assert any(".id" in item["detail"] for item in report["errors"])


def test_code_rejects_value_mismatch_with_evidence():
    plan = valid_visit()
    plan["steps"][1]["args"]["code"] = value("E09", "E07")
    report = validate_plan(plan, ctx(user_text=VISIT_USER_TEXT))
    assert "P3" in codes(report)


def test_code_rejects_evidence_without_code_pattern():
    plan = valid_visit()
    plan["steps"][1]["args"]["code"] = value("E07", "水箱供水异常")
    report = validate_plan(plan, ctx(user_text=VISIT_USER_TEXT + "，水箱供水异常"))
    assert "P3" in codes(report)
    assert any("没有错误码" in item["detail"] for item in report["errors"])


def test_code_rejects_evidence_not_in_user_text():
    plan = valid_visit()
    plan["steps"][1]["args"]["code"] = value("E07", "水箱")
    report = validate_plan(plan, ctx(user_text=VISIT_USER_TEXT))
    assert "P3" in codes(report)
    assert any("evidence" in item["detail"] for item in report["errors"])


def test_from_pending_counts_only_same_tool_cards():
    plan = {
        "goals": [{"id": "g1", "type": "book", "text": "沿用上次的时段"}],
        "steps": [
            step(
                "s1",
                "propose_service_visit",
                args={
                    "device_id": {"from_pending": "device_id", "tool": "propose_service_visit"},
                    "description": {"from_pending": "description", "tool": "propose_service_visit"},
                    "slot_id": {"from_pending": "slot_id", "tool": "propose_service_visit"},
                },
                covers=["g1"],
            )
        ],
        "ask_user": None,
    }
    report = validate_plan(
        plan,
        ctx(
            user_text="还是上次那个时间吧",
            pending_cards=[
                CARD_VISIT,
                {"action_id": "a2", "tool": "propose_order", "args": {"device_id": "D-1", "sku": "SKU-FILTER"}},
            ],
        ),
    )
    p3 = [item for item in report["errors"] if item["code"] == "P3"]
    assert p3 == [], report["errors"]


def test_from_pending_rejects_two_cards_of_same_tool():
    plan = {
        "goals": [{"id": "g1", "type": "book", "text": "沿用上次的时段"}],
        "steps": [
            step(
                "s1",
                "propose_service_visit",
                args={
                    "device_id": {"from_pending": "device_id", "tool": "propose_service_visit"},
                    "description": {"from_pending": "description", "tool": "propose_service_visit"},
                    "slot_id": {"from_pending": "slot_id", "tool": "propose_service_visit"},
                },
                covers=["g1"],
            )
        ],
        "ask_user": None,
    }
    report = validate_plan(
        plan,
        ctx(user_text="还是上次那个时间吧", pending_cards=[CARD_VISIT, dict(CARD_VISIT, action_id="a3")]),
    )
    assert "P3" in codes(report)


def test_resolve_from_pending_uses_visit_card_among_two_cards():
    resolved = resolve_args(
        {"args": {"slot_id": {"from_pending": "slot_id", "tool": "propose_service_visit"}}},
        {},
        ctx(
            pending_cards=[
                CARD_VISIT,
                {"action_id": "a2", "tool": "propose_order", "args": {"device_id": "D-1", "sku": "SKU-FILTER"}},
            ]
        ),
    )
    assert resolved == {"status": "ok", "args": {"slot_id": "S-east-20260113-2"}}


def test_resolve_from_pending_ignores_other_tool_cards_entirely():
    resolved = resolve_args(
        {"args": {"sku": {"from_pending": "sku", "tool": "propose_order"}}},
        {},
        ctx(
            pending_cards=[
                CARD_VISIT,
                {"action_id": "a2", "tool": "propose_order", "args": {"sku": "SKU-FILTER"}},
                {"action_id": "a3", "tool": "propose_change", "args": {"target_id": "O-1007-01"}},
            ]
        ),
    )
    assert resolved == {"status": "ok", "args": {"sku": "SKU-FILTER"}}


def test_resolve_slot_at_prefers_recomputed_value():
    resolved = resolve_args(
        {
            "args": {
                "slot_id": {
                    "from_step": "s2",
                    "pick": "slot_at",
                    **slot("2026-01-13", "明天", "13:00", "下午一点"),
                }
            }
        },
        SLOTS_RESULT,
        ctx(),
    )
    assert resolved["args"]["slot_id"] == "S-east-20260113-2"


def test_resolve_record_id_uses_value():
    resolved = resolve_args(
        {
            "args": {
                "target_id": {
                    "from_step": "s4",
                    "pick": "record",
                    "kind": "order",
                    "id": value("O-1007-01", "订单O-1007-01"),
                }
            }
        },
        RECORDS_RESULT,
        ctx(),
    )
    assert resolved == {"status": "ok", "args": {"target_id": "O-1007-01"}}


def test_schema_contains_enums_and_patterns():
    schema = plan_json_schema()
    defs = schema["$defs"]
    goal_type = defs["Goal"]["properties"]["type"]
    assert goal_type["enum"] == list(pc.GOAL_TYPES)
    assert set(defs["Step"]["properties"]["tool"]["enum"]) == set(pc.TOOLS)
    assert defs["AskUser"]["properties"]["type"]["enum"] == [
        "which_device", "which_slot", "quantity", "other",
    ]
    assert defs["Goal"]["properties"]["id"]["pattern"] == "^g[0-9]+$"
    assert defs["Step"]["properties"]["id"]["pattern"] == "^s[0-9]+$"
    serialized = json.dumps(schema, ensure_ascii=False)
    assert "find_service_slots" in serialized
    assert "list_my_devices" in serialized
