"""Private deterministic effects; invoked only by the trusted confirmation path.

The caller owns the IMMEDIATE transaction, strict validation, ownership and
preconditions. This module neither commits nor registers model tools.
"""
from uuid import UUID

from service_desk.proposals import _money


def _business_id(prefix, action_id):
    return prefix + '-SVC-' + UUID(action_id).hex


def _execute(connection, context, action, args, extra):
    action_id, user = action['action_id'], context['user_id']
    result = {'action_id': action_id, 'status': 'executed', 'tool': action['tool']}
    if action['tool'] == 'propose_service_visit':
        ticket_id = _business_id('T', action_id)
        appointment_id = _business_id('A', action_id)
        device = connection.execute('SELECT * FROM devices WHERE device_id=?', (args['device_id'],)).fetchone()
        slot = connection.execute('SELECT * FROM service_slots WHERE slot_id=?', (args['slot_id'],)).fetchone()
        connection.execute(
            'INSERT INTO tickets '
            '(ticket_id,user_id,device_id,model_code,error_code,description,notes,status,source_action_id) '
            "VALUES (?,?,?,?,?,?,?,'scheduled',?)",
            (ticket_id, user, args['device_id'], device['model_code'], args['error_code'],
             args['description'], '', action_id))
        connection.execute(
            'INSERT INTO appointments (appointment_id,ticket_id,slot_id,user_id,status,source_action_id) '
            "VALUES (?,?,?,?,'scheduled',?)",
            (appointment_id, ticket_id, args['slot_id'], user, action_id))
        connection.execute('UPDATE service_slots SET booked=booked+1 WHERE slot_id=?', (args['slot_id'],))
        return result | {'ticket_id': ticket_id, 'appointment_id': appointment_id, 'slot_id': args['slot_id'],
                         'start_at': slot['start_at'], 'end_at': slot['end_at'],
                         'message': f"已创建工单 {ticket_id}，预约 {appointment_id}（{slot['start_at']}至{slot['end_at']}）。"}
    if action['tool'] == 'propose_order':
        order_id = _business_id('O', action_id)
        device = connection.execute('SELECT * FROM devices WHERE device_id=?', (args['device_id'],)).fetchone()
        amount = extra['amount_cents']
        connection.execute(
            'INSERT INTO orders '
            '(order_id,user_id,device_id,model_code,sku,qty,amount_cents,status,source_action_id) '
            "VALUES (?,?,?,?,?,?,?,'processing',?)",
            (order_id, user, args['device_id'], device['model_code'], args['sku'], args['qty'], amount, action_id))
        connection.execute('UPDATE consumables SET stock=stock-? WHERE sku=?', (args['qty'], args['sku']))
        return result | {'order_id': order_id, 'sku': args['sku'], 'qty': args['qty'], 'amount_cents': amount,
                         'message': f"已创建订单 {order_id}，{args['sku']} × {args['qty']}，金额 {_money(amount)}，处理中。"}
    if action['tool'] != 'propose_change':
        raise ValueError('unsupported action tool')
    target, change = args['target_id'], args['change']
    if change == 'cancel_order':
        order = connection.execute('SELECT * FROM orders WHERE order_id=?', (target,)).fetchone()
        connection.execute("UPDATE orders SET status='cancelled' WHERE order_id=?", (target,))
        connection.execute('UPDATE consumables SET stock=stock+? WHERE sku=?', (order['qty'], order['sku']))
        return result | {'order_id': target, 'change': change,
                         'message': f'已取消订单 {target}，未发货的耗材数量已退回库存。'}
    appointment = connection.execute('SELECT * FROM appointments WHERE appointment_id=?', (target,)).fetchone()
    ticket_id, old_slot = appointment['ticket_id'], appointment['slot_id']
    connection.execute('UPDATE service_slots SET booked=booked-1 WHERE slot_id=?', (old_slot,))
    if change == 'reschedule':
        slot = connection.execute('SELECT * FROM service_slots WHERE slot_id=?', (args['new_slot_id'],)).fetchone()
        connection.execute('UPDATE appointments SET slot_id=? WHERE appointment_id=?', (args['new_slot_id'], target))
        connection.execute("UPDATE tickets SET status='scheduled' WHERE ticket_id=?", (ticket_id,))
        connection.execute('UPDATE service_slots SET booked=booked+1 WHERE slot_id=?', (args['new_slot_id'],))
        return result | {'appointment_id': target, 'ticket_id': ticket_id, 'change': change,
                         'old_slot_id': old_slot, 'slot_id': args['new_slot_id'],
                         'start_at': slot['start_at'], 'end_at': slot['end_at'],
                         'message': f"预约 {target} 已改至 {slot['start_at']}至{slot['end_at']}，工单 {ticket_id} 待上门。"}
    connection.execute("UPDATE appointments SET status='cancelled' WHERE appointment_id=?", (target,))
    connection.execute("UPDATE tickets SET status='cancelled' WHERE ticket_id=?", (ticket_id,))
    return result | {'appointment_id': target, 'ticket_id': ticket_id, 'slot_id': old_slot, 'change': change,
                     'message': f'已取消预约 {target} 和工单 {ticket_id}。'}
