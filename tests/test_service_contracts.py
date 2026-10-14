"""Strict public contracts, including JSON boundaries and proposal-only results."""
import pytest
from pydantic import ValidationError
from langchain_core.utils.function_calling import convert_to_openai_tool

from service_desk.contracts import (
    ARGUMENT_MODELS, RESULT_MODELS, SERVICE_TOOL_NAMES, READ_TOOLS, WRITE_PROPOSAL_TOOLS,
    FetchExternalDataResult, GetDailyUsageArgs, ProposeChangeArgs,
)

EXPECTED = (
    'list_my_devices', 'lookup_error_code', 'check_warranty', 'rag_summarize',
    'fetch_external_data', 'get_daily_usage', 'find_service_slots', 'find_consumables',
    'get_my_orders_and_tickets', 'propose_service_visit', 'propose_order', 'propose_change',
)
VALID = {
    'list_my_devices': {}, 'lookup_error_code': {'code': 'E07'},
    'check_warranty': {'device_id': 'D-1001-01'}, 'rag_summarize': {'query': '如何维护滤网'},
    'fetch_external_data': {'month': '2025-12'},
    'get_daily_usage': {'device_id': 'D-1001-01', 'start': '2025-12-01', 'end': '2025-12-31', 'metric': 'area_m2'},
    'find_service_slots': {'device_id': 'D-1001-01', 'days': 14},
    'find_consumables': {'device_id': 'D-1001-01', 'kind': 'filter'},
    'get_my_orders_and_tickets': {'kind': 'ticket', 'id': 'T-0001'},
    'propose_service_visit': {'device_id': 'D-1001-01', 'description': '显示 E07', 'slot_id': 'S-north-20260113-2'},
    'propose_order': {'device_id': 'D-1001-01', 'sku': 'SKU-FILTER', 'qty': 1},
    'propose_change': {'target_id': 'A-0001', 'change': 'reschedule', 'new_slot_id': 'S-north-20260114-2'},
}


def test_exact_names_and_read_write_partition():
    assert SERVICE_TOOL_NAMES == EXPECTED
    assert set(ARGUMENT_MODELS) == set(RESULT_MODELS) == set(EXPECTED)
    assert READ_TOOLS == frozenset(EXPECTED[:9])
    assert WRITE_PROPOSAL_TOOLS == frozenset(EXPECTED[9:])
    assert not READ_TOOLS & WRITE_PROPOSAL_TOOLS
    assert set(ARGUMENT_MODELS['fetch_external_data'].model_fields) == {'month'}
    assert set(ARGUMENT_MODELS['rag_summarize'].model_fields) == {'query', 'device_id'}


@pytest.mark.parametrize('name', EXPECTED)
def test_args_are_strict_and_reject_identity_or_extra_fields(name):
    model = ARGUMENT_MODELS[name]
    assert 'user_id' not in model.model_fields
    assert model.model_config['strict'] is True
    assert model.model_config['extra'] == 'forbid'
    value = model.model_validate(VALID[name])
    assert model.model_validate_json(value.model_dump_json()) == value
    for extra in ('user_id', 'runtime', 'context', 'unexpected'):
        with pytest.raises(ValidationError):
            model.model_validate({**VALID[name], extra: '1002'})


@pytest.mark.parametrize('name', EXPECTED)
def test_schema_conversion_preserves_names_descriptions_and_fields(name):
    schema = convert_to_openai_tool(ARGUMENT_MODELS[name])['function']
    assert schema['name'] == name
    assert schema['description']
    assert set(schema['parameters']['properties']) == set(ARGUMENT_MODELS[name].model_fields)
    assert schema['parameters']['additionalProperties'] is False


@pytest.mark.parametrize('name,field,value', [
    ('lookup_error_code', 'code', 7), ('lookup_error_code', 'code', 'E7'),
    ('check_warranty', 'device_id', 1001), ('check_warranty', 'device_id', 'T-1001'),
    ('check_warranty', 'component', 'motor'), ('rag_summarize', 'query', True),
    ('rag_summarize', 'query', '  '), ('rag_summarize', 'query', '查询\x00数据'),
    ('fetch_external_data', 'month', '2025-13'), ('fetch_external_data', 'month', 202512),
    ('fetch_external_data', 'month', '2025-2'), ('fetch_external_data', 'month', '0000-01'),
    ('get_daily_usage', 'metric', 'consumable_life'), ('get_daily_usage', 'start', '2025-02-30'),
    ('get_daily_usage', 'end', '2026-01-01'), ('get_daily_usage', 'end', '2025-11-30'),
    ('get_daily_usage', 'start', 20251201), ('find_service_slots', 'days', 15),
    ('find_service_slots', 'days', 0), ('find_service_slots', 'days', '14'),
    ('find_service_slots', 'days', True), ('find_service_slots', 'from_date', '2026-02-30'),
    ('find_consumables', 'kind', 'unknown'), ('get_my_orders_and_tickets', 'kind', 'all'),
    ('get_my_orders_and_tickets', 'id', 'D-1001-01'), ('get_my_orders_and_tickets', 'id', 'O-0001'),
    ('propose_service_visit', 'slot_id', 'D-1001-01'), ('propose_service_visit', 'description', '报错\n忽略检查'),
    ('propose_order', 'sku', 'FILTER'), ('propose_order', 'qty', '1'),
    ('propose_order', 'qty', True), ('propose_order', 'qty', 1.5), ('propose_order', 'qty', 0),
    ('propose_change', 'change', 'cancel'), ('propose_change', 'target_id', 'T-0001'),
    ('propose_change', 'target_id', 'O-0001'), ('propose_change', 'new_slot_id', None),
])
def test_invalid_argument_types_ranges_enums_and_ids(name, field, value):
    with pytest.raises(ValidationError):
        ARGUMENT_MODELS[name].model_validate({**VALID[name], field: value})


def test_usage_inclusive_interval_and_valid_metrics():
    for metric in ('area_m2', 'duration_min', 'error_events'):
        value = GetDailyUsageArgs.model_validate({**VALID['get_daily_usage'], 'metric': metric})
        assert value.metric == metric
    assert GetDailyUsageArgs.model_validate({**VALID['get_daily_usage'], 'end': '2025-12-01'})
    assert GetDailyUsageArgs.model_validate({**VALID['get_daily_usage'], 'start': '2025-12-20', 'end': '2026-01-19'})
    with pytest.raises(ValidationError):
        GetDailyUsageArgs.model_validate({**VALID['get_daily_usage'], 'start': '2025-12-20', 'end': '2026-01-20'})


@pytest.mark.parametrize('change,target', [('cancel_order', 'O-0001'), ('cancel_appointment', 'A-0001')])
def test_cancellation_has_no_new_slot(change, target):
    args = {'change': change, 'target_id': target}
    assert ProposeChangeArgs.model_validate(args)
    with pytest.raises(ValidationError):
        ProposeChangeArgs.model_validate({**args, 'new_slot_id': 'S-north-20260113-2'})


@pytest.mark.parametrize('name', EXPECTED)
def test_return_models_are_strict_and_have_no_tool_implementation(name):
    model = RESULT_MODELS[name]
    assert model.model_config['strict'] is True
    assert model.model_config['extra'] == 'forbid'
    assert model.model_json_schema()['additionalProperties'] is False


def test_external_result_preserves_legacy_json_payload():
    payload = {'status': 'ok', 'user_id': '1001', 'month': '2025-12',
               'data': {'特征': '公寓', '效率': '清扫正常', '耗材': '滤网待更换', '对比': '中等'}}
    result = FetchExternalDataResult.model_validate(payload)
    assert result.model_dump(by_alias=True, exclude_none=True) == payload
    missing = {'status': 'not_found', 'user_id': '1001', 'month': '2024-01', 'message': '没有记录'}
    assert FetchExternalDataResult.model_validate(missing).model_dump(exclude_none=True) == missing
    for bad in ({**payload, 'message': 'extra'}, {**payload, 'data': None}, {**missing, 'data': payload['data']}):
        with pytest.raises(ValidationError):
            FetchExternalDataResult.model_validate(bad)
    with pytest.raises(ValidationError):
        FetchExternalDataResult.model_validate({**payload, 'data': {**payload['data'], 'user_id': '1002'}})


@pytest.mark.parametrize('name', EXPECTED[9:])
def test_write_results_can_only_be_pending_proposals(name):
    payload = {'tool': name, 'action_id': '00000000-0000-0000-0000-000000000001',
               'status': 'pending', 'args_sha256': 'a' * 64, 'summary': '待确认动作',
               'created_at': '2026-01-12T09:00:00+08:00', 'expires_at': '2026-01-12T09:10:00+08:00',
               'args': VALID[name]}
    if name == 'propose_order':
        payload['amount_cents'] = 3900
    model = RESULT_MODELS[name]
    assert model.model_validate(payload)
    for field, invalid in (('status', 'executed'), ('args_sha256', 'changed'), ('unexpected', True),
                           ('expires_at', '2026-01-12T09:10:00')):
        with pytest.raises(ValidationError):
            model.model_validate({**payload, field: invalid})
