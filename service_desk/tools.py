"""Service reads. Identity, business clock and database path are server state."""
from datetime import date, timedelta
import json
from types import SimpleNamespace

from langchain.tools import ToolRuntime
from langchain_core.tools import StructuredTool

from service_desk.access import connection_for
from service_desk.contracts import READ_TOOLS, RESULT_MODELS
from service_desk.db import canonical_json
from service_desk.policy import authorize_service_tool, validate_arguments
from service_desk.seed import add_months
from service_desk.tool_schema import model_tool_schemas


def _device(connection, device_id):
    return connection.execute('SELECT * FROM devices WHERE device_id=?', (device_id,)).fetchone()


def _read(name, args, context, connection):
    user = context['user_id']
    today = date.fromisoformat(context['business_date'])
    if name == 'list_my_devices':
        rows = connection.execute(
            'SELECT d.*,m.display_name FROM devices d JOIN models m USING(model_code) '
            'WHERE user_id=? ORDER BY device_id', (user,))
        return {'devices': [
            {key: row[key] for key in ('device_id', 'model_code', 'display_name', 'purchase_date', 'firmware')}
            | {'serial_suffix': row['serial_no'][-4:]} for row in rows]}
    if name == 'lookup_error_code':
        device = args['device_id']
        if device is None:
            devices = connection.execute('SELECT device_id FROM devices WHERE user_id=? ORDER BY device_id',
                                         (user,)).fetchall()
            if len(devices) != 1:
                return {'status': 'clarify', 'definitions': [], 'message': '请先选择要查询的设备。'}
            device = devices[0]['device_id']
        model = _device(connection, device)['model_code']
        rows = connection.execute('SELECT * FROM error_codes WHERE model_code=? AND code=?',
                                  (model, args['code'])).fetchall()
        definitions = [dict(row) | {'self_fixable': bool(row['self_fixable']),
                                    'requires_visit': bool(row['requires_visit'])} for row in rows]
        return {'status': 'ok', 'definitions': definitions} if rows else {
            'status': 'not_found', 'definitions': [], 'message': '该型号没有相应错误码定义。'}
    if name == 'check_warranty':
        device = _device(connection, args['device_id'])
        rows = connection.execute(
            'SELECT * FROM warranty_policies WHERE model_code=? '
            'AND (? IS NULL OR component=?) ORDER BY component',
            (device['model_code'], args['component'], args['component']))
        purchase = date.fromisoformat(device['purchase_date'])
        coverage = []
        for row in rows:
            expires = add_months(purchase, row['months'])
            covered = row['months'] > 0 and purchase <= today <= expires
            reason = None if covered else ('耗材正常磨损不在保。' if row['months'] == 0 else
                                          '尚未到购买日期。' if today < purchase else '保修期限已届满。')
            coverage.append({'component': row['component'], 'in_warranty': covered,
                             'expires_date': expires.isoformat(),
                             'basis': f"{device['model_code']}：购买日起{row['months']}个月，到期日计入；{row['excludes']}",
                             'reason': reason})
        return {'device_id': args['device_id'], 'business_date': today.isoformat(), 'coverage': coverage}
    if name == 'rag_summarize':
        from agent.tools.agent_tools import rag_summerize
        # S1-A reuses legacy retrieval. Device ownership is checked, but model
        # filtering and the separate service collection are deferred to S1-B.
        answer = rag_summerize.func(args['query'], SimpleNamespace(context=context))
        return {'answer': answer, 'references': []}
    if name == 'fetch_external_data':
        from utils.records import load_records
        context.update(report=False, report_data=None, lookup_result=None)
        record = load_records().get((user, args['month']))
        if record is None:
            return {'status': 'not_found', 'user_id': user, 'month': args['month'],
                    'message': '该用户在指定月份没有使用记录，不能生成该月使用情况结论。'}
        return {'status': 'ok', 'user_id': user, 'month': args['month'], 'data': record}
    if name == 'get_daily_usage':
        # The column is an enum validated before this SQL; all values are bound.
        metric = args['metric']
        row = connection.execute(
            f'SELECT count(*) AS days_observed,coalesce(sum({metric}),0) AS total,'
            f'coalesce(avg({metric}),0) AS daily_average,coalesce(max({metric}),0) AS maximum '
            'FROM telemetry_daily WHERE device_id=? AND date BETWEEN ? AND ?',
            (args['device_id'], args['start'], args['end'])).fetchone()
        return args | dict(row)
    if name == 'find_service_slots':
        start = date.fromisoformat(args['from_date']) if args['from_date'] else today + timedelta(days=1)
        end = start + timedelta(days=args['days'])
        rows = connection.execute(
            'SELECT s.slot_id,s.region,s.start_at,s.end_at,s.capacity-s.booked AS available '
            'FROM service_slots s JOIN users u ON u.region=s.region '
            'WHERE u.user_id=? AND s.booked<s.capacity AND substr(s.start_at,1,10)>=? '
            'AND substr(s.start_at,1,10)<? AND substr(s.start_at,1,10)>? ORDER BY s.start_at,s.slot_id',
            (user, start.isoformat(), end.isoformat(), today.isoformat()))
        return {'device_id': args['device_id'], 'slots': [dict(row) for row in rows]}
    if name == 'find_consumables':
        model = _device(connection, args['device_id'])['model_code']
        rows = connection.execute(
            'SELECT c.* FROM consumables c JOIN consumable_models m USING(sku) '
            'WHERE m.model_code=? AND (? IS NULL OR c.kind=?) ORDER BY c.sku',
            (model, args['kind'], args['kind']))
        return {'device_id': args['device_id'], 'consumables': [dict(row) for row in rows]}
    if name == 'get_my_orders_and_tickets':
        kinds = [args['kind']] if args['kind'] else ['order', 'ticket', 'appointment']
        records = []
        for kind in kinds:
            table, key, fields = {
                'order': ('orders', 'order_id', 'device_id,sku,qty,amount_cents,status'),
                'ticket': ('tickets', 'ticket_id', 'device_id,error_code,description,notes,status'),
                'appointment': ('appointments', 'appointment_id', 'ticket_id,slot_id,status'),
            }[kind]
            rows = connection.execute(
                f'SELECT {key} AS id,{fields} FROM {table} WHERE user_id=? '
                f'AND (? IS NULL OR {key}=?) ORDER BY {key}', (user, args['id'], args['id']))
            records.extend(dict(row) | {'kind': kind} for row in rows)
        return {'records': records}
    raise ValueError('unsupported read tool')


def execute_service_tool(name, arguments, context):
    """Defensive checks also apply when a trusted caller bypasses LangGraph."""
    validate_arguments(name, arguments)
    if name not in READ_TOOLS:
        raise ValueError('proposal tools are not implemented in this stage')
    with connection_for(context) as connection:
        args = authorize_service_tool(name, arguments, context, connection=connection)
        result = RESULT_MODELS[name].model_validate(_read(name, args, context, connection), strict=True)
        payload = result.model_dump(by_alias=True, exclude_none=True)
        if name == 'fetch_external_data':
            context['lookup_result'] = payload
            context.setdefault('lookup_results', []).append(payload)
            context['report_data'] = payload if payload['status'] == 'ok' else None
            context['report'] = payload['status'] == 'ok'
        return canonical_json(payload)


def _tool_for(schema):
    function = schema['function']

    def invoke(runtime: ToolRuntime[dict], **arguments) -> str:
        return execute_service_tool(function['name'], arguments, runtime.context)

    return StructuredTool(name=function['name'], description=function['description'],
                          args_schema=function['parameters'], func=invoke)


def build_service_tools():
    """Lean dictionaries bind to the model; strict checks run in policy."""
    return [_tool_for(schema) for schema in model_tool_schemas()]
