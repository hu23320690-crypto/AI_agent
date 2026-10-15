"""render.py 的单元测试。"""

from __future__ import annotations

import json

import pytest

from service_desk.render import (
    compose_answer,
    guard_text,
    render_ask,
    render_facts,
    render_outcomes,
)

BUSINESS_DATE = "2026-01-12"


def test_rag_fact_preserves_fullwidth_and_all_original_text():
    original = "编号ＡＢＣ，数量３个。\n\t请保留原文。"
    assert render_facts([{'tool': 'rag_summarize', 'args': {}, 'payload': {'answer': original}}]) == ["资料说明：" + original]


def test_recovered_read_renders_success_once():
    entries = [result('list_my_devices', {'status': 'blocked', 'message': '暂时失败'}),
               result('list_my_devices', DEVICES_PAYLOAD)]
    facts = render_facts(entries)
    assert len(facts) == 1 and 'D-1002-01' in facts[0] and '暂时失败' not in facts[0]


@pytest.mark.parametrize('mode', ['react', 'plan'])
def test_card_is_last_even_when_a_read_follows(mode):
    results = [result('propose_order', PROPOSAL_PAYLOAD), result('list_my_devices', DEVICES_PAYLOAD)]
    text = compose_answer(mode=mode, results=results)
    assert text.index('你的设备：') < text.index('待确认：')
    assert text.endswith('请在确认卡片上确认，确认前不会提交。')


def keep(text: str, sources) -> str:
    """只取 guard_text 保留的部分，方便断言。"""
    return guard_text(text, sources)[0]


def result(tool: str, payload: dict, args: dict | None = None) -> dict:
    """构造一条工具结果。"""
    return {"tool": tool, "args": args or {}, "payload": payload}


DEVICES_PAYLOAD = {
    "devices": [
        {
            "device_id": "D-1002-01",
            "model_code": "SV-200",
            "display_name": "扫拖一体型",
            "serial_suffix": "0000",
            "purchase_date": "2024-07-12",
            "firmware": "1.0.0",
        }
    ]
}

TWO_DEVICES_PAYLOAD = {
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
}

ERROR_OK_PAYLOAD = {
    "status": "ok",
    "definitions": [
        {
            "model_code": "SV-200",
            "code": "E07",
            "title": "水箱供水检测异常",
            "severity": 2,
            "self_fixable": False,
            "requires_visit": True,
            "doc_ref": "errors.txt#SV-200-E07",
        }
    ],
}

WARRANTY_PAYLOAD = {
    "device_id": "D-1002-01",
    "business_date": BUSINESS_DATE,
    "coverage": [
        {
            "component": "battery",
            "in_warranty": False,
            "expires_date": "2025-07-12",
            "basis": "随机保修条款",
            "reason": "保修期限已届满。",
        },
        {
            "component": "consumables",
            "in_warranty": False,
            "expires_date": "2024-07-12",
            "basis": "随机保修条款",
            "reason": "耗材正常磨损不在保。",
        },
        {
            "component": "whole_machine",
            "in_warranty": True,
            "expires_date": "2026-07-12",
            "basis": "随机保修条款",
        },
    ],
}

USAGE_PAYLOAD = {
    "device_id": "D-1001-01",
    "start": "2025-06-01",
    "end": "2025-06-07",
    "metric": "area_m2",
    "days_observed": 7,
    "total": 350.0,
    "daily_average": 50.0,
    "maximum": 52.0,
}

SLOTS_PAYLOAD = {
    "device_id": "D-1002-01",
    "slots": [
        {
            "slot_id": "S-east-20260113-2",
            "region": "east",
            "start_at": "2026-01-13T13:00:00+08:00",
            "end_at": "2026-01-13T15:00:00+08:00",
            "available": 2,
        }
    ],
}

CONSUMABLES_PAYLOAD = {
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
}

RECORDS_PAYLOAD = {
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
            "kind": "ticket",
            "id": "T-1008-01",
            "device_id": "D-1008-01",
            "error_code": "E07",
            "description": "拖地时显示 E07",
            "notes": "",
            "status": "scheduled",
        },
        {
            "kind": "appointment",
            "id": "A-1008-01",
            "ticket_id": "T-1008-01",
            "slot_id": "S-west-20260115-2",
            "status": "scheduled",
        },
    ]
}

PROPOSAL_PAYLOAD = {
    "action_id": "6f1c0d1e-0000-4000-8000-000000000000",
    "status": "pending",
    "tool": "propose_order",
    "args": {"device_id": "D-1007-01", "sku": "SKU-SIDE", "qty": 2},
    "args_sha256": "0" * 64,
    "summary": "下单：设备D-1007-01，通用边刷（SKU-SIDE）×2；单价19.00元，金额38.00元；等待卡片确认。",
    "created_at": "2026-01-12T07:00:00+00:00",
    "expires_at": "2026-01-12T07:10:00+00:00",
    "amount_cents": 3800,
}

FAILURE_PAYLOAD = {
    "status": "blocked",
    "reason_code": "out_of_stock",
    "message": "库存不足，未生成订单提议。",
}


# ---------------------------------------------------------------------------
# render_facts：每种工具
# ---------------------------------------------------------------------------

def test_facts_list_my_devices_one_device():
    facts = render_facts([result("list_my_devices", DEVICES_PAYLOAD)])
    assert facts == ["你的设备：D-1002-01（SV-200 扫拖一体型，购买日期 2024-07-12）。"]


def test_facts_list_my_devices_multiple_devices():
    facts = render_facts([result("list_my_devices", TWO_DEVICES_PAYLOAD)])
    assert facts == [
        "你的设备：D-1020-01（SV-400 自集尘旗舰型，购买日期 2024-03-01）；"
        "D-1020-02（SV-100 基础扫地型，购买日期 2024-05-01）。"
    ]


def test_facts_lookup_error_code_ok_needs_visit():
    facts = render_facts([result("lookup_error_code", ERROR_OK_PAYLOAD, {"code": "E07"})])
    assert facts == [
        "错误码 E07（SV-200）：水箱供水检测异常。严重程度 2；不建议自行处理，需要服务人员上门检查。"
    ]


def test_facts_lookup_error_code_ok_self_fixable():
    payload = {
        "status": "ok",
        "definitions": [
            {
                "model_code": "SV-100",
                "code": "E01",
                "title": "主刷缠绕",
                "severity": 1,
                "self_fixable": True,
                "requires_visit": False,
            }
        ],
    }
    facts = render_facts([result("lookup_error_code", payload, {"code": "E01"})])
    assert facts == ["错误码 E01（SV-100）：主刷缠绕。严重程度 1；可以先按手册自查，自查后仍异常再申请上门。"]


def test_facts_lookup_error_code_not_found_uses_args():
    payload = {"status": "not_found", "definitions": [], "message": "该型号没有相应错误码定义。"}
    facts = render_facts(
        [result("lookup_error_code", payload, {"code": "E42", "model_code": "SV-300"})]
    )
    assert facts == ["型号 SV-300 没有错误码 E42 的定义，请核对屏幕上的编号。"]


def test_facts_lookup_error_code_not_found_without_model():
    payload = {"status": "not_found", "definitions": [], "message": "该型号没有相应错误码定义。"}
    facts = render_facts([result("lookup_error_code", payload, {"code": "E42"})])
    assert facts == ["型号 该设备 没有错误码 E42 的定义，请核对屏幕上的编号。"]


def test_facts_lookup_error_code_clarify_outputs_message():
    payload = {"status": "clarify", "definitions": [], "message": "请先选择要查询的设备。"}
    facts = render_facts([result("lookup_error_code", payload, {"code": "E07"})])
    assert facts == ["请先选择要查询的设备。"]


def test_facts_check_warranty_with_in_warranty_component():
    facts = render_facts([result("check_warranty", WARRANTY_PAYLOAD)])
    assert facts == [
        "保修（D-1002-01，以 2026-01-12 为准）：整机在保，到期日 2026-07-12；"
        "电池已过保，到期日 2025-07-12；耗材正常磨损不在保。"
        "在保不代表一定免费，故障原因需服务人员检查。"
    ]


def test_facts_check_warranty_without_in_warranty_component():
    payload = {
        "device_id": "D-1002-01",
        "business_date": BUSINESS_DATE,
        "coverage": [
            {"component": "whole_machine", "in_warranty": False, "expires_date": "2026-01-01"},
            {"component": "battery", "in_warranty": False, "expires_date": "2025-07-12"},
            {
                "component": "consumables",
                "in_warranty": False,
                "expires_date": "2024-07-12",
                "reason": "耗材正常磨损不在保。",
            },
        ],
    }
    facts = render_facts([result("check_warranty", payload)])
    assert facts == [
        "保修（D-1002-01，以 2026-01-12 为准）：整机已过保，到期日 2026-01-01；"
        "电池已过保，到期日 2025-07-12；耗材正常磨损不在保。"
    ]


def test_facts_rag_summarize_keeps_newlines():
    payload = {
        "answer": "第一行说明\n第二行说明",
        "references": [{"doc_ref": "service_kb/sv-200_manual.txt#abc", "models": ["SV-200"]}],
    }
    facts = render_facts([result("rag_summarize", payload, {"query": "水箱"})])
    assert facts == ["资料说明：第一行说明\n第二行说明"]


@pytest.mark.parametrize(
    "metric,expected",
    [
        ("area_m2", "清扫面积合计 350 ㎡，日均 50.00 ㎡，最大 52 ㎡。"),
        ("duration_min", "清扫时长合计 350 分钟，日均 50.00 分钟，最大 52 分钟。"),
        ("error_events", "错误事件合计 350 次，日均 50.00 次，最大 52 次。"),
    ],
)
def test_facts_get_daily_usage_metrics(metric, expected):
    payload = dict(USAGE_PAYLOAD, metric=metric)
    facts = render_facts([result("get_daily_usage", payload)])
    assert facts == [
        "D-1001-01 在 2025-06-01 至 2025-06-07（有记录 7 天）：" + expected
    ]


def test_facts_find_service_slots():
    facts = render_facts([result("find_service_slots", SLOTS_PAYLOAD)])
    assert facts == ["可约时段：1）2026-01-13 13:00–15:00（剩余 2）。"]


def test_facts_find_service_slots_empty():
    facts = render_facts([result("find_service_slots", {"device_id": "D-1002-01", "slots": []})])
    assert facts == ["未查到可约时段。"]


def test_facts_find_consumables_stock_and_limit():
    facts = render_facts([result("find_consumables", CONSUMABLES_PAYLOAD)])
    assert facts == [
        "兼容耗材：SKU-FILTER 通用滤网，39.00 元，库存 80，单次限购 2；"
        "SKU-MOP 清洁拖布，29.00 元，缺货。"
    ]


def test_facts_find_consumables_without_max_per_order():
    payload = {
        "device_id": "D-1006-01",
        "consumables": [
            {"sku": "SKU-FILTER", "name": "通用滤网", "kind": "filter", "price_cents": 3900, "stock": 80}
        ],
    }
    facts = render_facts([result("find_consumables", payload)])
    assert facts == ["兼容耗材：SKU-FILTER 通用滤网，39.00 元，库存 80。"]


def test_facts_get_my_orders_and_tickets():
    facts = render_facts([result("get_my_orders_and_tickets", RECORDS_PAYLOAD)])
    assert facts == [
        "订单 O-1007-01：SKU-MAIN × 1，69.00 元，处理中。"
        "工单 T-1008-01：E07，已预约。"
        "预约 A-1008-01：时段 S-west-20260115-2，已预约。"
    ]


def test_facts_get_my_orders_and_tickets_empty():
    facts = render_facts([result("get_my_orders_and_tickets", {"records": []})])
    assert facts == ["没有查到相关记录。"]


def test_facts_proposal_expires_at_timezone():
    facts = render_facts([result("propose_order", PROPOSAL_PAYLOAD)])
    assert facts == [
        "待确认：下单：设备D-1007-01，通用边刷（SKU-SIDE）×2；"
        "单价19.00元，金额38.00元；等待卡片确认。（有效期至 2026-01-12 15:10）。"
    ]


def test_facts_failure_outputs_message():
    facts = render_facts([result("propose_order", FAILURE_PAYLOAD)])
    assert facts == ["库存不足，未生成订单提议。"]
    denied = {"status": "denied", "reason_code": "identity_mismatch", "message": "对象不属于当前用户或不可见。"}
    assert render_facts([result("check_warranty", denied)]) == ["对象不属于当前用户或不可见。"]


def test_facts_deduplicates_same_tool_and_args():
    results = [
        result("list_my_devices", DEVICES_PAYLOAD),
        result("list_my_devices", DEVICES_PAYLOAD),
        result("list_my_devices", TWO_DEVICES_PAYLOAD, {"x": 1}),
    ]
    facts = render_facts(results)
    assert len(facts) == 2
    assert facts[0].startswith("你的设备：D-1002-01")


def test_facts_deduplicates_normalized_args():
    results = [
        result("find_consumables", CONSUMABLES_PAYLOAD, {"device_id": "D-1006-01", "kind": "filter"}),
        result("find_consumables", CONSUMABLES_PAYLOAD, {"kind": "filter", "device_id": "D-1006-01"}),
    ]
    assert len(render_facts(results)) == 1


def test_facts_skips_fetch_external_data():
    results = [
        result("fetch_external_data", {"status": "ok", "month": "2025-12", "data": {}}),
        result("list_my_devices", DEVICES_PAYLOAD),
    ]
    facts = render_facts(results)
    assert len(facts) == 1
    assert facts[0].startswith("你的设备：")


def test_facts_without_ok_marker_still_renders():
    payload = {"device_id": "D-1001-01", "start": "2025-06-01", "end": "2025-06-07",
               "metric": "area_m2", "days_observed": 7, "total": 350.0,
               "daily_average": 50.0, "maximum": 52.0}
    assert render_facts([result("get_daily_usage", payload)])[0].startswith("D-1001-01 在 ")


# ---------------------------------------------------------------------------
# guard_text
# ---------------------------------------------------------------------------

def test_guard_keeps_sentence_supported_by_source():
    kept, dropped = guard_text("设备 D-1002-01 已查到。", ["D-1002-01"])
    assert kept == "设备 D-1002-01 已查到。"
    assert dropped == []


def test_guard_drops_sentence_with_unknown_id():
    kept, dropped = guard_text("设备 D-9999-01 已查到。", ["D-1002-01"])
    assert kept == ""
    assert dropped == ["设备 D-9999-01 已查到。"]


@pytest.mark.parametrize(
    "sentence,source",
    [
        ("工单 T-1008-01 已经登记。", "T-1008-01"),
        ("预约 A-1008-01 已排期。", "A-1008-01"),
        ("订单 O-1007-01 正在处理。", "O-1007-01"),
        ("时段 S-west-20260115-2 可约。", "S-west-20260115-2"),
        ("耗材 SKU-FILTER 有货。", "SKU-FILTER"),
        ("错误码 E07 需要上门。", "E07"),
        ("金额是 39.00 元。", "39.00 元"),
        ("占比 85%。", "85%"),
        ("剩余 30天。", "30天"),
        ("一共 3个。", "3个"),
        ("连续 2次。", "2次"),
        ("每天 50㎡。", "50㎡"),
        ("耗时 45分钟。", "45分钟"),
    ],
)
def test_guard_keeps_each_marker_type_when_supported(sentence, source):
    kept, dropped = guard_text(sentence, [source])
    assert kept == sentence
    assert dropped == []

@pytest.mark.parametrize(
    "sentence",
    [
        "设备 D-9999-01 已查到。",
        "工单 T-9999-01 已经登记。",
        "预约 A-9999-01 已排期。",
        "订单 O-9999-01 正在处理。",
        "时段 S-north-20990101-1 可约。",
        "耗材 SKU-BAD 有货。",
        "错误码 E99 需要上门。",
        "金额是 99.00 元。",
        "占比 99%。",
        "剩余 99天。",
        "一共 99个。",
        "连续 99次。",
        "每天 99㎡。",
        "耗时 99分钟。",
        "时间是 09:30。",
        "日期是 2026-05-05。",
    ],
)
def test_guard_drops_each_marker_type_when_unsupported(sentence):
    kept, dropped = guard_text(sentence, ["与本句无关的来源"])
    assert kept == ""
    assert dropped == [sentence]


def test_guard_keeps_time_when_supported():
    kept, dropped = guard_text("上门时间是 13:00。", ["2026-01-13 13:00"])
    assert kept == "上门时间是 13:00。"
    assert dropped == []


def test_guard_treats_two_date_writings_as_equal():
    kept, dropped = guard_text("到期日是 2026年7月12日。", ["expires_date: 2026-07-12"])
    assert kept == "到期日是 2026年7月12日。"
    assert dropped == []

    kept2, _ = guard_text("到期日是 2026-07-12。", ["到期日 2026年7月12日"])
    assert kept2 == "到期日是 2026-07-12。"


def test_guard_treats_date_without_leading_zero_as_equal():
    kept, _ = guard_text("上门日期 2026-1-13。", ["start_at 2026-01-13T13:00:00+08:00"])
    assert kept == "上门日期 2026-1-13。"


def test_guard_drops_date_that_is_not_in_sources():
    kept, dropped = guard_text("到期日是 2025-07-12。", ["expires_date: 2026-07-12"])
    assert kept == ""
    assert dropped == ["到期日是 2025-07-12。"]


def test_guard_handles_fullwidth_digits():
    kept, _ = guard_text("设备 Ｄ 不对，金额是 ３９元。", ["金额 39元"])
    assert kept == "设备 D 不对，金额是 39元。"

    kept2, dropped2 = guard_text("错误码 Ｅ９９ 需要上门。", ["E07"])
    assert kept2 == ""
    assert dropped2 == ["错误码 E99 需要上门。"]


def test_guard_matches_number_with_unit_separated_by_space():
    kept, dropped = guard_text("合计 350 ㎡。", ['"total": 350.0, "unit": "㎡"'])
    assert kept == "合计 350 ㎡。"
    assert dropped == []


def test_guard_drops_claim_of_finished_write():
    kept, dropped = guard_text("已为你预约上门服务。", ["预约"])
    assert kept == ""
    assert dropped == ["已为你预约上门服务。"]


def test_guard_removes_whole_sentence_with_claim():
    kept, dropped = guard_text(
        "设备 D-1002-01 报 E07，已为你预约上门。建议先检查水箱。",
        ["D-1002-01", "E07"],
    )
    assert kept == "建议先检查水箱。"
    assert dropped == ["设备 D-1002-01 报 E07，已为你预约上门。"]


def test_guard_removes_sentence_with_claim_and_extra_facts():
    kept, dropped = guard_text("已为你预约上门，时间是明天。", ["2026-01-13"])
    assert kept == ""
    assert dropped == ["已为你预约上门，时间是明天。"]


def test_guard_keeps_negated_claim():
    sentence = "尚未为你预约上门服务。"
    kept, dropped = guard_text(sentence, ["预约"])
    assert kept == sentence
    assert dropped == []


@pytest.mark.parametrize("word", ["未", "尚未", "没有", "不会"])
def test_guard_keeps_each_negation_word(word):
    sentence = f"{word}为你预约上门服务。"
    kept, _ = guard_text(sentence, ["预约"])
    assert kept == sentence


def test_guard_splits_sentences_and_keeps_punctuation():
    text = "已为你下单。设备 D-1002-01 正常；他没有提出问题？好的\n结束"
    kept, dropped = guard_text(text, ["D-1002-01", "下单"])
    assert dropped == ["已为你下单。"]
    assert kept == "设备 D-1002-01 正常；他没有提出问题？好的\n结束"


def test_guard_returns_empty_when_everything_dropped():
    kept, dropped = guard_text("已为你预约。订单 O-1 已创建。", [])
    assert kept == ""
    assert len(dropped) == 2


@pytest.mark.parametrize(
    "sentence",
    ["通用滤网单价 39 元。", "通用滤网单价 39.0 元。", "通用滤网单价 39.00元。"],
)
def test_guard_treats_amounts_by_value(sentence):
    results = [result("find_consumables", CONSUMABLES_PAYLOAD)]
    kept, dropped = guard_text(sentence, [json.dumps(results[0]["payload"], ensure_ascii=False)])
    assert kept == sentence
    assert dropped == []


def test_compose_react_keeps_consumable_price_from_facts():
    results = [result("find_consumables", CONSUMABLES_PAYLOAD)]
    answer = compose_answer(
        mode="react",
        results=results,
        model_text="通用滤网单价 39 元。",
    )
    assert answer.startswith("通用滤网单价 39 元。")


def test_compose_react_uses_facts_text_as_source():
    results = [result("find_consumables", CONSUMABLES_PAYLOAD)]
    # payload 里只有 3900 分，模型写的 39.00 元要靠事实块文本才算有依据
    answer = compose_answer(mode="react", results=results, model_text="通用滤网单价 39.00 元。")
    assert answer.startswith("通用滤网单价 39.00 元。")


def test_compose_react_uses_report_text_as_source():
    results = [result("list_my_devices", DEVICES_PAYLOAD)]
    answer = compose_answer(
        mode="react",
        results=results,
        model_text="本月日均 50.00 ㎡。",
        report_text="2025-12 月报：日均 50.00 ㎡。",
    )
    assert answer.startswith("本月日均 50.00 ㎡。")


def test_ticket_without_error_code_uses_description():
    payload = {
        "records": [
            {
                "kind": "ticket",
                "id": "T-1004-01",
                "device_id": "D-1004-01",
                "error_code": None,
                "description": "主刷不转，机器停在客厅中间",
                "status": "scheduled",
            }
        ]
    }
    facts = render_facts([result("get_my_orders_and_tickets", payload)])
    assert facts == ["工单 T-1004-01：主刷不转，机器停在客厅中间，已预约。"]


def test_ticket_without_error_code_truncates_long_description():
    payload = {
        "records": [
            {
                "kind": "ticket",
                "id": "T-1005-01",
                "error_code": None,
                "description": "拖地时反复显示错误并自动停机" * 4,
                "status": "scheduled",
            }
        ]
    }
    facts = render_facts([result("get_my_orders_and_tickets", payload)])
    assert facts == [
        "工单 T-1005-01：" + ("拖地时反复显示错误并自动停机" * 4)[:30] + "…，已预约。"
    ]


def test_ticket_without_error_code_and_description():
    payload = {
        "records": [
            {"kind": "ticket", "id": "T-1006-01", "error_code": None, "status": "scheduled"}
        ]
    }
    facts = render_facts([result("get_my_orders_and_tickets", payload)])
    assert facts == ["工单 T-1006-01：无错误码，已预约。"]


# ---------------------------------------------------------------------------
# render_outcomes
# ---------------------------------------------------------------------------

def test_outcomes_proposed():
    assert render_outcomes([{"goal_type": "book", "goal_text": "预约上门", "status": "proposed",
                             "action": "visit", "condition": None, "reason": None}]) == [
        "已为你准备预约的确认卡片。"
    ]


def test_outcomes_condition_false_with_warranty():
    outcome = {
        "goal_type": "book",
        "goal_text": "在保才约",
        "status": "condition_false",
        "action": "visit",
        "condition": {"type": "warranty_in_force", "component": "battery"},
        "reason": None,
    }
    assert render_outcomes([outcome]) == [
        "按你的要求（电池在保），条件不成立，未生成预约卡片。"
    ]


def test_outcomes_condition_false_with_threshold():
    outcome = {
        "goal_type": "order",
        "goal_text": "滤网不够就买",
        "status": "condition_false",
        "action": "order",
        "condition": {
            "type": "record_threshold",
            "month": "2025-12",
            "field_hint": "HEPA",
            "op": "<=",
            "value": 15,
            "unit": "%",
        },
        "reason": None,
    }
    assert render_outcomes([outcome]) == [
        "按你的要求（2025-12 HEPA 不高于 15%），条件不成立，未生成订单卡片。"
    ]


@pytest.mark.parametrize(
    "op,text",
    [("<=", "不高于"), ("<", "低于"), (">=", "不低于"), (">", "高于")],
)
def test_outcomes_threshold_operators(op, text):
    outcome = {
        "goal_type": "order",
        "goal_text": "t",
        "status": "condition_unknown",
        "action": "order",
        "condition": {"type": "record_threshold", "month": "2025-12", "field_hint": "主刷",
                      "op": op, "value": 30, "unit": "天"},
        "reason": None,
    }
    assert render_outcomes([outcome]) == [
        f"无法判断你的条件（2025-12 主刷 {text} 30天）是否成立，未生成订单卡片。"
    ]


def test_outcomes_condition_unknown_warranty():
    outcome = {
        "goal_type": "book",
        "goal_text": "在保才约",
        "status": "condition_unknown",
        "action": "visit",
        "condition": {"type": "warranty_in_force", "component": "whole_machine"},
        "reason": None,
    }
    assert render_outcomes([outcome]) == [
        "无法判断你的条件（整机在保）是否成立，未生成预约卡片。"
    ]


def test_outcomes_precheck_failed():
    outcome = {
        "goal_type": "order",
        "goal_text": "买滤网",
        "status": "precheck_failed",
        "action": "order",
        "condition": None,
        "reason": "库存不足",
    }
    assert render_outcomes([outcome]) == ["库存不足，未生成订单卡片。"]


def test_outcomes_slot_unavailable():
    outcome = {
        "goal_type": "book",
        "goal_text": "约明天下午一点",
        "status": "slot_unavailable",
        "action": "visit",
        "condition": None,
        "reason": "slot_unavailable",
    }
    assert render_outcomes([outcome]) == ["你指定的时段没有可约名额，未生成预约卡片。"]


def test_outcomes_missing():
    outcome = {
        "goal_type": "diagnose",
        "goal_text": "查一下 E07",
        "status": "missing",
        "action": None,
        "condition": None,
        "reason": None,
    }
    assert render_outcomes([outcome]) == ["未能完成：查一下 E07。"]


def test_outcomes_done_is_silent():
    outcome = {
        "goal_type": "diagnose",
        "goal_text": "查一下 E07",
        "status": "done",
        "action": None,
        "condition": None,
        "reason": None,
    }
    assert render_outcomes([outcome]) == []


def test_outcomes_change_action_wording():
    outcome = {
        "goal_type": "change",
        "goal_text": "改约",
        "status": "proposed",
        "action": "change",
        "condition": None,
        "reason": None,
    }
    assert render_outcomes([outcome]) == ["已为你准备变更的确认卡片。"]


# ---------------------------------------------------------------------------
# render_ask
# ---------------------------------------------------------------------------

def test_ask_which_device():
    results = [result("list_my_devices", TWO_DEVICES_PAYLOAD)]
    assert render_ask({"type": "which_device", "text": "ignored"}, results) == (
        "你有多台设备：D-1020-01（SV-400）；D-1020-02（SV-100）。请问是哪一台？"
    )


def test_ask_which_slot():
    assert render_ask({"type": "which_slot", "text": ""}, []) == "请从下面的可约时段里选一个。"


def test_ask_quantity():
    assert render_ask({"type": "quantity", "text": ""}, []) == "请告诉我需要的数量。"


def test_ask_other_keeps_supported_text():
    text = "请问你指的是哪一台 D-1002-01？"
    results = [result("list_my_devices", DEVICES_PAYLOAD)]
    assert render_ask({"type": "other", "text": text}, results) == text


def test_ask_other_falls_back_when_filtered():
    assert render_ask({"type": "other", "text": "已为你预约。"}, []) == "请补充更多信息。"


# ---------------------------------------------------------------------------
# compose_answer
# ---------------------------------------------------------------------------

def test_compose_react_order_and_guard():
    results = [
        result("lookup_error_code", ERROR_OK_PAYLOAD, {"code": "E07"}),
        result("list_my_devices", DEVICES_PAYLOAD),
    ]
    sources = [json.dumps(item["payload"], ensure_ascii=False) for item in results]
    answer = compose_answer(
        mode="react",
        results=results,
        model_text="设备 D-1002-01 报 E07，已为你预约上门。建议先检查水箱。",
        report_text="2025-12 月报：日均 50 ㎡。",
        sources=sources,
    )
    assert answer == (
        "建议先检查水箱。\n\n"
        "2025-12 月报：日均 50 ㎡。\n\n"
        "错误码 E07（SV-200）：水箱供水检测异常。严重程度 2；不建议自行处理，需要服务人员上门检查。\n"
        "你的设备：D-1002-01（SV-200 扫拖一体型，购买日期 2024-07-12）。"
    )


def test_compose_react_without_model_text_only_facts():
    results = [result("list_my_devices", DEVICES_PAYLOAD)]
    answer = compose_answer(mode="react", results=results, model_text="已为你预约。")
    assert answer == "你的设备：D-1002-01（SV-200 扫拖一体型，购买日期 2024-07-12）。"


def test_compose_react_skips_empty_report_text():
    results = [result("list_my_devices", DEVICES_PAYLOAD)]
    answer = compose_answer(mode="react", results=results, model_text=None, report_text="")
    assert "\n\n\n" not in answer
    assert answer.endswith("。")


def test_compose_plan_order():
    results = [
        result("find_service_slots", SLOTS_PAYLOAD),
        result("propose_service_visit", PROPOSAL_PAYLOAD),
    ]
    answer = compose_answer(
        mode="plan",
        results=results,
        outcomes=[
            {"goal_type": "book", "goal_text": "约明天", "status": "proposed",
             "action": "visit", "condition": None, "reason": None},
            {"goal_type": "diagnose", "goal_text": "查 E07", "status": "done",
             "action": None, "condition": None, "reason": None},
        ],
        report_text="月报正文。",
    )
    assert answer == (
        "已为你准备预约的确认卡片。\n\n"
        "月报正文。\n\n"
        "可约时段：1）2026-01-13 13:00–15:00（剩余 2）。\n"
        "待确认：下单：设备D-1007-01，通用边刷（SKU-SIDE）×2；"
        "单价19.00元，金额38.00元；等待卡片确认。（有效期至 2026-01-12 15:10）。\n"
        "请在确认卡片上确认，确认前不会提交。"
    )


def test_compose_plan_ask_before_outcomes():
    results = [result("list_my_devices", TWO_DEVICES_PAYLOAD)]
    answer = compose_answer(
        mode="plan",
        results=results,
        ask={"type": "which_device", "text": ""},
        outcomes=[{"goal_type": "book", "goal_text": "约上门", "status": "missing",
                   "action": "visit", "condition": None, "reason": None}],
    )
    assert answer == (
        "你有多台设备：D-1020-01（SV-400）；D-1020-02（SV-100）。请问是哪一台？\n"
        "未能完成：约上门。\n\n"
        "你的设备：D-1020-01（SV-400 自集尘旗舰型，购买日期 2024-03-01）；"
        "D-1020-02（SV-100 基础扫地型，购买日期 2024-05-01）。"
    )


def test_compose_appends_proposal_tail_when_card_created():
    results = [
        result("list_my_devices", DEVICES_PAYLOAD),
        result("propose_order", PROPOSAL_PAYLOAD),
    ]
    answer = compose_answer(mode="plan", results=results)
    assert answer.endswith("\n请在确认卡片上确认，确认前不会提交。")
    assert answer.count("请在确认卡片上确认，确认前不会提交。") == 1


def test_compose_does_not_append_tail_without_successful_proposal():
    results = [result("list_my_devices", DEVICES_PAYLOAD), result("propose_order", FAILURE_PAYLOAD)]
    answer = compose_answer(mode="plan", results=results)
    assert "请在确认卡片上确认" not in answer
    assert answer.endswith("库存不足，未生成订单提议。")


def test_compose_plan_without_ask_or_outcomes_is_facts_only():
    results = [result("list_my_devices", DEVICES_PAYLOAD)]
    answer = compose_answer(mode="plan", results=results, outcomes=[])
    assert answer == "你的设备：D-1002-01（SV-200 扫拖一体型，购买日期 2024-07-12）。"


def test_compose_react_uses_payload_as_guard_source():
    results = [result("get_daily_usage", USAGE_PAYLOAD)]
    answer = compose_answer(
        mode="react",
        results=results,
        model_text="上周清扫面积合计 350 ㎡。",
    )
    assert answer.startswith("上周清扫面积合计 350 ㎡。")


def test_compose_react_drops_value_absent_from_payload():
    results = [result("get_daily_usage", USAGE_PAYLOAD)]
    answer = compose_answer(
        mode="react",
        results=results,
        model_text="上周清扫面积合计 999 ㎡。",
    )
    assert answer.startswith("D-1001-01 在 2025-06-01")


def test_compose_no_trailing_blank_lines():
    results = [result("list_my_devices", DEVICES_PAYLOAD)]
    answer = compose_answer(mode="react", results=results, model_text=None, report_text=None)
    assert not answer.endswith("\n")
