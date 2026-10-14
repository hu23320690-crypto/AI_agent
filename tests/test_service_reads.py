"""Service read tests use the published seed/data documentation, no task sets."""
from datetime import date
import json
import sqlite3
from unittest.mock import patch

import pytest

from agent.tools.policy import ToolPolicyDenied, authorize_tool
from service_desk.access import connection_for, session_context
from service_desk.contracts import ARGUMENT_MODELS, READ_TOOLS, RESULT_MODELS
from service_desk.db import init_db
from service_desk.seed import add_months
from service_desk.tools import build_service_tools, execute_service_tool
from service_desk.tool_schema import model_tool_schemas
from langchain_core.utils.function_calling import convert_to_openai_tool


@pytest.fixture(scope='module')
def seed_path(tmp_path_factory):
    path = tmp_path_factory.mktemp('service-read') / 'service.db'
    init_db(path)
    return path


def context(path, user='1002'):
    return session_context(user, 'test-session', path)


def read(path, name, user='1002', **args):
    value = execute_service_tool(name, args, context(path, user))
    RESULT_MODELS[name].model_validate_json(value)
    return json.loads(value)


def test_actual_model_schema_and_public_fields():
    assert [convert_to_openai_tool(tool) for tool in build_service_tools()] == model_tool_schemas()
    for tool in build_service_tools():
        fields = set(tool.tool_call_schema['properties'])
        assert fields == set(ARGUMENT_MODELS[tool.name].model_fields)
        assert 'user_id' not in fields


@pytest.mark.parametrize('name,args', [
    ('list_my_devices', {}), ('lookup_error_code', {'code': 'E07'}),
    ('check_warranty', {'device_id': 'D-1002-01'}),
    ('rag_summarize', {'query': '水箱清理'}),
    ('fetch_external_data', {'month': '2025-12'}),
    ('get_daily_usage', {'device_id': 'D-1002-01', 'start': '2025-12-01',
                         'end': '2025-12-31', 'metric': 'area_m2'}),
    ('find_service_slots', {'device_id': 'D-1002-01'}),
    ('find_consumables', {'device_id': 'D-1002-01'}),
    ('get_my_orders_and_tickets', {}),
])
def test_all_read_results_validate(seed_path, name, args):
    with patch('agent.tools.agent_tools.get_rag_service') as rag:
        rag.return_value.rag_summarize.return_value = '先暂停，再检查水箱。'
        read(seed_path, name, **args)


def test_documented_devices_errors_and_stock(seed_path):
    devices = read(seed_path, 'list_my_devices')['devices']
    assert devices == [{'device_id': 'D-1002-01', 'model_code': 'SV-200', 'display_name': '扫拖一体型',
                        'purchase_date': '2024-07-12', 'firmware': '1.0.0', 'serial_suffix': '0000'}]
    error = read(seed_path, 'lookup_error_code', code='E07')['definitions'][0]
    assert (error['title'], error['self_fixable'], error['requires_visit']) == ('水箱供水检测异常', False, True)
    stock = {item['sku']: item for item in read(seed_path, 'find_consumables', device_id='D-1002-01')['consumables']}
    assert (stock['SKU-FILTER']['price_cents'], stock['SKU-FILTER']['stock'],
            stock['SKU-FILTER']['max_per_order']) == (3900, 80, 2)
    assert stock['SKU-MOP']['stock'] == 0
    assert 'SKU-RUBBER' not in stock


@pytest.mark.parametrize('user,expires,covered', [
    ('1001', '2025-07-12', False), ('1002', '2026-07-12', True), ('1003', '2026-02-20', True),
    ('1004', '2024-10-05', False), ('1005', '2025-11-08', False), ('1006', '2027-10-02', True),
    ('1007', '2025-07-12', False), ('1008', '2026-07-12', True), ('1009', '2025-03-01', False),
    ('1010', '2024-12-03', False),
])
def test_documented_whole_warranties(seed_path, user, expires, covered):
    result = read(seed_path, 'check_warranty', user=user, device_id=f'D-{user}-01', component='whole_machine')
    assert result['business_date'] == '2026-01-12'
    assert (result['coverage'][0]['expires_date'], result['coverage'][0]['in_warranty']) == (expires, covered)


@pytest.mark.parametrize('user,expected', [('1002', False), ('1006', True), ('1004', False)])
def test_documented_battery_warranties(seed_path, user, expected):
    assert read(seed_path, 'check_warranty', user=user, device_id=f'D-{user}-01',
                component='battery')['coverage'][0]['in_warranty'] is expected


@pytest.mark.parametrize('today,expected', [('2026-07-11', True), ('2026-07-12', True),
                                           ('2026-07-13', False), ('2024-07-11', False)])
def test_expiry_day_is_inclusive(seed_path, today, expected):
    state = context(seed_path)
    state['business_date'] = today
    result = json.loads(execute_service_tool('check_warranty',
                        {'device_id': 'D-1002-01', 'component': 'whole_machine'}, state))
    assert result['coverage'][0]['in_warranty'] is expected


@pytest.mark.parametrize('purchase,months,expected', [
    ('2024-01-31', 1, '2024-02-29'), ('2025-01-31', 1, '2025-02-28'),
    ('2024-02-29', 12, '2025-02-28'), ('2025-12-31', 2, '2026-02-28'),
])
def test_month_end_clamping(purchase, months, expected):
    assert add_months(date.fromisoformat(purchase), months).isoformat() == expected


def test_records_and_slots_are_scoped(seed_path):
    records = read(seed_path, 'get_my_orders_and_tickets', user='1004')['records']
    assert {r['id'] for r in records} == {'T-1004-01', 'A-1004-01'}
    for slot in read(seed_path, 'find_service_slots', user='1004', device_id='D-1004-01')['slots']:
        assert slot['region'] == 'west'
        assert '2026-01-13' <= slot['start_at'][:10] < '2026-01-20'
        assert slot['available'] > 0
    order = read(seed_path, 'get_my_orders_and_tickets', user='1007', id='O-1007-01')['records'][0]
    assert (order['status'], order['qty'], order['amount_cents'], order['sku']) == ('processing', 1, 6900, 'SKU-MAIN')


def test_daily_aggregation_and_missing_interval(seed_path):
    from utils.records import load_records
    from utils.report_render import record_fields
    from re import search
    daily = read(seed_path, 'get_daily_usage', user='1001', device_id='D-1001-01', start='2025-12-01',
                 end='2025-12-31', metric='area_m2')
    fields = record_fields(load_records()[('1001', '2025-12')])
    expected = float(search(r'\d+', fields['日均清扫'])[0])
    assert daily['days_observed'] == 31
    assert daily['daily_average'] == expected
    assert daily['total'] == expected * 31
    empty = read(seed_path, 'get_daily_usage', device_id='D-1002-01', start='2026-01-01',
                 end='2026-01-02', metric='error_events')
    assert (empty['days_observed'], empty['total'], empty['daily_average'], empty['maximum']) == (0, 0, 0, 0)


def test_record_context_matches_legacy_shape(seed_path):
    state = context(seed_path)
    value = json.loads(execute_service_tool('fetch_external_data', {'month': '2025-12'}, state))
    assert state['report'] is True
    assert state['lookup_result'] == state['report_data'] == value
    assert state['lookup_results'] == [value]
    missing = json.loads(execute_service_tool('fetch_external_data', {'month': '2026-01'}, state))
    assert missing['status'] == 'not_found' and not state['report']
    assert state['report_data'] is None and state['lookup_result'] == missing


@pytest.mark.parametrize('name,base,field,foreign,absent', [
    ('check_warranty', {}, 'device_id', 'D-1001-01', 'D-9999-01'),
    ('get_my_orders_and_tickets', {}, 'id', 'O-1007-01', 'O-9999-01'),
    ('get_my_orders_and_tickets', {}, 'id', 'A-1004-01', 'A-9999-01'),
    ('get_my_orders_and_tickets', {}, 'id', 'T-1004-01', 'T-9999-01'),
    ('propose_order', {'device_id': 'D-1002-01', 'qty': 1}, 'sku', 'SKU-RUBBER', 'SKU-UNKNOWN'),
    ('propose_service_visit', {'device_id': 'D-1002-01', 'description': '异常'},
     'slot_id', 'S-north-20260113-2', 'S-east-20990101-2'),
])
def test_unknown_and_foreign_ids_have_identical_denials(seed_path, name, base, field, foreign, absent):
    denials = []
    for value in (foreign, absent):
        with pytest.raises(ToolPolicyDenied) as error:
            authorize_tool(name, base | {field: value}, context(seed_path))
        denials.append((error.value.code, str(error.value)))
        assert value not in str(error.value)
    assert denials == [('identity_mismatch', 'Tool permission denied')] * 2


@pytest.mark.parametrize('name', sorted(READ_TOOLS))
def test_no_service_tool_accepts_identity(seed_path, name):
    with pytest.raises(ToolPolicyDenied) as error:
        authorize_tool(name, {'user_id': '1001'}, context(seed_path))
    assert error.value.code == 'injected_argument'


@pytest.mark.parametrize('args', [
    {'device_id': 'D-1002-01', 'start': '2025-12-01', 'end': '2026-01-01', 'metric': 'area_m2'},
    {'device_id': 'D-1002-01', 'start': '2025-12-02', 'end': '2025-12-01', 'metric': 'area_m2'},
    {'device_id': 'D-1002-01', 'start': '2025-02-30', 'end': '2025-02-30', 'metric': 'area_m2'},
    {'device_id': 'D-1002-01', 'start': '2025-12-01', 'end': '2025-12-01', 'metric': 'stock'},
])
def test_usage_strict_constraints(seed_path, args):
    with pytest.raises(ToolPolicyDenied) as error:
        authorize_tool('get_daily_usage', args, context(seed_path))
    assert error.value.code == 'arguments_invalid'


def test_optional_device_requires_clarification(seed_path):
    assert read(seed_path, 'lookup_error_code', user='1015', code='E07')['status'] == 'clarify'
    assert read(seed_path, 'lookup_error_code', code='E99')['status'] == 'not_found'


def test_readonly_connection_cannot_write(seed_path):
    with connection_for(context(seed_path)) as connection:
        with pytest.raises(sqlite3.OperationalError, match='readonly'):
            connection.execute("UPDATE consumables SET stock=0")
    missing = seed_path.parent / 'absent.db'
    with pytest.raises(sqlite3.OperationalError):
        with connection_for(context(missing)):
            pass
    assert not missing.exists()


def test_default_database_path_comes_from_service_config():
    from service_desk.config import ROOT, load_config
    assert session_context('1002', 's')['service_db_path'] == ROOT / load_config()['db_path']


def test_warranty_result_clamps_purchase_leap_day(seed_path, tmp_path):
    import shutil
    path = tmp_path / 'leap-purchase.db'
    shutil.copyfile(seed_path, path)
    with sqlite3.connect(path) as connection:
        connection.execute("UPDATE devices SET purchase_date='2024-02-29' WHERE device_id='D-1002-01'")
    state = context(path)
    state['business_date'] = '2026-02-28'
    coverage = json.loads(execute_service_tool('check_warranty',
                         {'device_id': 'D-1002-01', 'component': 'whole_machine'}, state))['coverage'][0]
    assert coverage['expires_date'] == '2026-02-28' and coverage['in_warranty']
    state['business_date'] = '2026-03-01'
    coverage = json.loads(execute_service_tool('check_warranty',
                         {'device_id': 'D-1002-01', 'component': 'whole_machine'}, state))['coverage'][0]
    assert not coverage['in_warranty']
