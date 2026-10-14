"""Strict public arguments plus ownership; no input or existence in denials."""
from pydantic import ValidationError

from agent.tools.policy import ToolPolicyDenied, _INJECTED_ARGUMENTS
from service_desk.access import connection_for
from service_desk.contracts import ARGUMENT_MODELS


def validate_arguments(name, arguments, *, tool=None):
    if not isinstance(name, str) or name not in ARGUMENT_MODELS:
        raise ToolPolicyDenied('tool_not_allowed')
    if not isinstance(arguments, dict):
        raise ToolPolicyDenied('arguments_invalid')
    if 'user_id' in arguments or _INJECTED_ARGUMENTS.intersection(arguments):
        raise ToolPolicyDenied('injected_argument')
    model = ARGUMENT_MODELS[name]
    if tool is not None:
        schema = tool.tool_call_schema
        fields = set(schema.get('properties', {})) if isinstance(schema, dict) else set(schema.model_fields)
        if fields != set(model.model_fields):
            raise ToolPolicyDenied('schema_mismatch')
    try:
        return model.model_validate(arguments, strict=True).model_dump()
    except ValidationError:
        raise ToolPolicyDenied('arguments_invalid') from None


def check_ownership(connection, arguments, context):
    user = context.get('user_id')
    if not isinstance(user, str) or not user:
        raise ToolPolicyDenied('identity_missing')
    row = connection.execute('SELECT region FROM users WHERE user_id=?', (user,)).fetchone()
    if row is None:
        raise ToolPolicyDenied('identity_mismatch')

    def require(sql, values):
        if connection.execute(sql, values).fetchone() is None:
            raise ToolPolicyDenied('identity_mismatch')

    device = arguments.get('device_id')
    if device:
        require('SELECT 1 FROM devices WHERE device_id=? AND user_id=?', (device, user))
    for field in ('slot_id', 'new_slot_id'):
        slot = arguments.get(field)
        if slot:
            require('SELECT 1 FROM service_slots WHERE slot_id=? AND region=?', (slot, row['region']))
    sku = arguments.get('sku')
    if sku:
        # Visibility is compatibility with at least one device of this user.
        # Compatibility with the selected device is a proposal precondition.
        require('SELECT 1 FROM consumable_models c JOIN devices d USING(model_code) '
                'WHERE c.sku=? AND d.user_id=?', (sku, user))
    for field in ('id', 'target_id'):
        record = arguments.get(field)
        if record:
            table, key = {'O': ('orders', 'order_id'), 'T': ('tickets', 'ticket_id'),
                          'A': ('appointments', 'appointment_id')}[record[0]]
            require(f'SELECT 1 FROM {table} WHERE {key}=? AND user_id=?', (record, user))


def authorize_service_tool(name, arguments, context, *, tool=None, connection=None):
    validated = validate_arguments(name, arguments, tool=tool)
    user = context.get('user_id')
    if not isinstance(user, str) or not user:
        raise ToolPolicyDenied('identity_missing')
    if connection is None:
        with connection_for(context) as own_connection:
            check_ownership(own_connection, validated, context)
    else:
        check_ownership(connection, validated, context)
    return validated
