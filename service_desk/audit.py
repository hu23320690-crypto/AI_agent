"""Append service audit events inside the caller's transaction."""
from uuid import uuid4


def append_event(connection, context, action, event, timestamp, detail):
    # Unknown/foreign actions use NULL because action_id is a foreign key.
    # Their audit envelope must not depend on whether the requested ID exists.
    connection.execute(
        'INSERT INTO audit_log (id,ts,session_id,user_id,action_id,event,tool,args_sha256,detail) '
        'VALUES (?,?,?,?,?,?,?,?,?)',
        ('L-' + uuid4().hex, timestamp, context['session_id'], context['user_id'],
         action['action_id'] if action is not None else None, event,
         action['tool'] if action is not None else 'service_action',
         action['args_sha256'] if action is not None else '0' * 64, detail))
