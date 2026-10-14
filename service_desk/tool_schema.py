"""Lean model-facing descriptions; strict argument validation remains in contracts.

This module generates metadata only, without registering or implementing tools.
Optional arguments are omitted when unused; null is not advertised to the model.
"""
from service_desk.contracts import ARGUMENT_MODELS

TOOL_DESCRIPTIONS = {
    'list_my_devices': '需要辨认设备或选择服务对象时，查询当前用户的设备清单。',
    'lookup_error_code': '设备报错时，按设备型号查询错误含义及是否需要上门。',
    'check_warranty': '需要判断服务保障时，查询设备整机或指定部件的保修状态。',
    'rag_summarize': '需要操作、维护或服务政策说明时，检索适用资料并总结。',
    'fetch_external_data': '需要月度报告或耗材剩余寿命时，查询指定月份的使用记录。',
    'get_daily_usage': '需要比较清扫用量时，聚合指定设备至多三十一天的日记录。',
    'find_service_slots': '准备预约或改约时，查询设备所在区域未来可预约的时段。',
    'find_consumables': '准备购买或核对耗材时，查询设备兼容品及价格、库存和限购。',
    'get_my_orders_and_tickets': '需要查进度或变更记录时，查询当前用户的订单、工单和预约。',
    'propose_service_visit': '选好设备和时段后，只生成待确认的上门预约，用户确认后提交。',
    'propose_order': '选好兼容耗材和数量后，只生成待确认的订单，用户确认后才会下单。',
    'propose_change': '需要改约或取消预约、订单时，只生成待确认的变更，用户确认后提交。',
}

FIELD_DESCRIPTIONS = {
    'device_id': '设备编号', 'code': '错误码', 'component': '保修部件',
    'query': '资料问题', 'month': '月份 YYYY-MM',
    'start': '开始日期 YYYY-MM-DD', 'end': '结束日期 YYYY-MM-DD',
    'metric': '聚合指标', 'from_date': '起始日期 YYYY-MM-DD', 'days': '查询天数，1至14',
    'kind': '查询类别', 'id': '记录编号', 'error_code': '错误码',
    'description': '实际问题描述', 'slot_id': '所选时段编号',
    'sku': '耗材编号', 'qty': '数量，正整数', 'target_id': '待变更记录编号',
    'change': '变更类型', 'new_slot_id': '改约时必填的新时段编号',
}


def model_tool_schemas():
    """Return fresh OpenAI tool objects derived from the frozen argument models."""
    schemas = []
    for name, model in ARGUMENT_MODELS.items():
        strict = model.model_json_schema()
        properties = {}
        for field, definition in strict.get('properties', {}).items():
            if 'anyOf' in definition:
                alternatives = [item for item in definition['anyOf'] if item.get('type') != 'null']
                if len(alternatives) != 1:
                    raise ValueError(f'unsupported union: {name}.{field}')
                definition = alternatives[0]
            if definition.get('type') not in ('string', 'integer', 'number', 'boolean'):
                raise ValueError(f'unsupported field type: {name}.{field}')
            properties[field] = {'type': definition['type'], 'description': FIELD_DESCRIPTIONS[field]}
            if 'enum' in definition:
                properties[field]['enum'] = list(definition['enum'])
        schemas.append({
            'type': 'function',
            'function': {
                'name': name,
                'description': TOOL_DESCRIPTIONS[name],
                'parameters': {
                    'type': 'object', 'properties': properties,
                    'required': [field for field, info in model.model_fields.items() if info.is_required()],
                },
            },
        })
    return schemas
