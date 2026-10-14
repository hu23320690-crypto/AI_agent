"""Offline B1 gold checks, not service tools, an Agent, or an execution runner.

Only this module's disposable seed copies are changed. No model is imported.
Run: python -B -m evaluation.service_suite_check [--write-reports].
"""
from collections import Counter
from contextlib import closing
import argparse
import csv
from datetime import date
import hashlib
import io
import json
from pathlib import Path
import re
import sqlite3
import tempfile
from typing import Literal
import uuid

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from service_desk.config import load_config
from service_desk.contracts import ARGUMENT_MODELS, WRITE_PROPOSAL_TOOLS
from service_desk.db import content_sha256, init_db
from service_desk.seed import add_months

ROOT = Path(__file__).resolve().parents[1]
DISTRIBUTION = {
    'dev': {'visit': 3, 'order': 2, 'change': 2, 'status': 1, 'read_multi': 2,
            'reject_or_revise': 2, 'precondition_fail': 2, 'clarify': 1},
    'test': {'visit': 5, 'order': 4, 'change': 4, 'status': 2, 'read_multi': 4,
             'reject_or_revise': 4, 'precondition_fail': 4, 'clarify': 2, 'boundary': 1},
    'injection': {'injection': 12},
}
CHECK_NAMES = ('structure', 'proposals', 'blocked_requests', 'evidence', 'final_state',
               'similarity', 'isolation', 'csv_overlay', 'sql_overlay')


class Strict(BaseModel):
    model_config = ConfigDict(strict=True, extra='forbid')


class Evidence(Strict):
    kind: Literal['db', 'kb', 'csv']
    table: str | None = None
    key: dict | None = None
    fields: dict | None = None
    file: str | None = None
    line_start: int | None = None
    line_end: int | None = None
    quote: str | None = None


class Proposal(Strict):
    tool: Literal['propose_service_visit', 'propose_order', 'propose_change']
    args: dict
    description_must_include: list[str] = Field(default_factory=list)
    slot_id_in: list[str] = Field(default_factory=list)


class Turn(Strict):
    type: Literal['user', 'confirm', 'reject']
    query: str | None = None
    expect: Literal['answer', 'clarify', 'refuse'] | None = None
    required_tools: list[str] | None = None
    allowed_tools: list[str] | None = None
    expected_proposals: list[Proposal] | None = None
    forbidden_proposals: list[str | dict] | None = None
    required_points: list[str] | None = None
    evidence: list[Evidence] | None = None
    proposal_ref: str | None = None


class FinalCheck(Strict):
    table: str
    where: dict
    expect_count: int = Field(ge=0)


class BlockedRequest(Strict):
    user_turn: int = Field(ge=1)
    tool: str
    args: dict
    reason: Literal['warranty_expired', 'out_of_stock', 'purchase_limit', 'no_slot',
                    'self_fixable', 'other_user', 'not_cancellable', 'incompatible']


class Injection(Strict):
    carrier_class: Literal['ticket_text', 'temporary_kb', 'catalog_text', 'monthly_or_warranty']
    kind: Literal['db', 'kb', 'csv']
    overlay: str
    table: str | None = None
    key: dict | None = None
    field: str | None = None
    user_id: str | None = None
    month: str | None = None
    payload: str
    intent: str
    hard_gates: list[Literal['H1', 'H2', 'H3', 'H4', 'H5', 'H6']]
    forbidden_read_user_ids: list[str]
    forbidden_claims: list[str]


class Task(Strict):
    id: str
    split: Literal['dev', 'test', 'injection']
    category: str
    user_id: str
    title: str
    turns: list[Turn]
    final_db_checks: list[FinalCheck]
    notes: str
    blocked_requests: list[BlockedRequest] = Field(default_factory=list)
    initial_db_checks: list[FinalCheck] = Field(default_factory=list)
    injection: Injection | None = None


def require(condition, message):
    if not condition:
        raise ValueError(message)


def load_jsonl(path):
    def unique_pairs(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, f'duplicate JSON key: {key}')
            result[key] = value
        return result
    return [json.loads(line, object_pairs_hook=unique_pairs) for line in
            Path(path).read_text(encoding='utf-8').splitlines() if line.strip()]


def safe_path(root, relative, prefix=None):
    require(isinstance(relative, str) and bool(relative), 'source path missing')
    path = (root / relative).resolve()
    require(path.is_relative_to(root.resolve()), f'path escapes repository: {relative}')
    if prefix:
        require(path.is_relative_to((root / prefix).resolve()), f'path outside {prefix}: {relative}')
    require(path.is_file(), f'missing source: {relative}')
    return path


def columns(connection, table):
    require(re.fullmatch(r'[a-z_]+', table) is not None, 'invalid table name')
    info = connection.execute(f'PRAGMA table_info("{table}")').fetchall()
    require(bool(info), f'unknown table: {table}')
    return {row[1] for row in info}, {row[1] for row in info if row[5]}


def where_clause(connection, table, where):
    available, _ = columns(connection, table)
    require(bool(where) and set(where) <= available, f'invalid predicates: {table}/{where}')
    require(all(isinstance(v, (str, int)) and not isinstance(v, bool) for v in where.values()),
            'predicates must be scalar text/integer equality')
    return ' AND '.join(f'"{key}"=?' for key in where), tuple(where.values())


def row_for(connection, table, key):
    _, primary = columns(connection, table)
    require(set(key) == primary, f'evidence/overlay key must be full PK: {table}')
    clause, values = where_clause(connection, table, key)
    rows = connection.execute(f'SELECT * FROM "{table}" WHERE {clause}', values).fetchall()
    require(len(rows) == 1, f'row missing: {table}/{key}')
    names = [c[1] for c in connection.execute(f'PRAGMA table_info("{table}")')]
    return dict(zip(names, rows[0]))


def raw_csv_cells(data, *, with_spans=False):
    """CSV lexer retaining every byte of each cell, including quote spelling."""
    rows, row, start, i, quoted = [], [], 0, 0, False
    span_rows, spans = [], []
    while i < len(data):
        char = data[i]
        if char == 34:
            if quoted and i + 1 < len(data) and data[i + 1] == 34:
                i += 2
                continue
            quoted = not quoted
        if not quoted and char in (44, 10, 13):
            row.append(data[start:i])
            spans.append((start, i))
            if char != 44:
                if char == 13 and i + 1 < len(data) and data[i + 1] == 10:
                    i += 1
                rows.append(row)
                span_rows.append(spans)
                row = []
                spans = []
            start = i + 1
        i += 1
    require(not quoted, 'unterminated CSV quote')
    if start < len(data) or row:
        row.append(data[start:])
        spans.append((start, len(data)))
        rows.append(row)
        span_rows.append(spans)
    return (rows, span_rows) if with_spans else rows


def snapshot(connection):
    return {table: set(connection.execute(f'SELECT * FROM "{table}"').fetchall())
            for table, in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")}


def apply_overlay(connection, task, root):
    injection = task.injection
    if injection is None:
        return None
    path = safe_path(root, injection.overlay, 'evaluation/service_injection_v1/overlays')
    if injection.kind == 'kb':
        require(injection.carrier_class == 'temporary_kb', 'wrong KB carrier class')
        require(injection.payload in path.read_text(encoding='utf-8'), 'KB payload absent')
        return 'kb'
    if injection.kind == 'csv':
        require(injection.carrier_class == 'monthly_or_warranty', 'wrong CSV carrier class')
        require(injection.field in ('对比', '耗材') and injection.user_id == task.user_id,
                'CSV target must be an allowed field of session user')
        original = (root / 'data/external/records.csv').read_bytes()
        replacement = path.read_bytes()
        before, spans = raw_csv_cells(original, with_spans=True)
        after = raw_csv_cells(replacement)
        require(len(before) == len(after), 'CSV row count changed')
        parsed = list(csv.DictReader(io.StringIO(original.decode('utf-8-sig'), newline='')))
        header = next(csv.reader(io.StringIO(original.decode('utf-8-sig'), newline='')))
        targets = [i + 1 for i, row in enumerate(parsed)
                   if (row['用户ID'], row['时间']) == (injection.user_id, injection.month)]
        require(len(targets) == 1, 'CSV overlay target not unique')
        expected = (targets[0], header.index(injection.field))
        differences = [(r, c) for r, row in enumerate(before) for c, cell in enumerate(row)
                       if r >= len(after) or len(row) != len(after[r]) or cell != after[r][c]]
        require(differences == [expected], 'CSV overlay changed undeclared cells')
        # Delimiters and line endings must also retain their exact byte spelling.
        after_cell = after[expected[0]][expected[1]]
        start, end = spans[expected[0]][expected[1]]
        require(original[:start] + after_cell + original[end:] == replacement,
                'CSV bytes outside target cell changed')
        require(injection.payload.encode('utf-8') in after_cell, 'CSV payload absent')
        return 'csv'
    require(injection.kind == 'db', 'unknown overlay kind')
    require(bool(injection.key), 'SQL overlay needs declared primary key')
    allowed = {'tickets': {'notes', 'description'}, 'consumables': {'name'},
               'error_codes': {'title'}, 'warranty_policies': {'excludes'}}
    require(injection.field in allowed.get(injection.table, set()), 'unsupported SQL text carrier')
    require(injection.carrier_class == {'tickets': 'ticket_text', 'consumables': 'catalog_text',
                                       'error_codes': 'catalog_text',
                                       'warranty_policies': 'monthly_or_warranty'}[injection.table],
            'SQL carrier class mismatch')
    target = row_for(connection, injection.table, injection.key)
    before, schema = snapshot(connection), connection.execute('SELECT sql FROM sqlite_master').fetchall()
    # Forbid DDL, reads, triggers, extra columns, writes to other tables and ATTACH.
    def authorize(action, first, second, database, trigger):
        if action == sqlite3.SQLITE_UPDATE:
            return sqlite3.SQLITE_OK if first == injection.table and second == injection.field else sqlite3.SQLITE_DENY
        if action == sqlite3.SQLITE_READ:
            return sqlite3.SQLITE_OK if first == injection.table and second in injection.key else sqlite3.SQLITE_DENY
        return sqlite3.SQLITE_DENY
    connection.set_authorizer(authorize)
    try:
        connection.executescript(path.read_text(encoding='utf-8'))
    finally:
        connection.set_authorizer(None)
    revised = row_for(connection, injection.table, injection.key)
    require(injection.payload in revised[injection.field], 'SQL payload absent')
    require(revised[injection.field] != target[injection.field], 'SQL overlay is a no-op')
    require(all(target[k] == revised[k] for k in target if k != injection.field), 'other SQL field changed')
    after = snapshot(connection)
    old_tuple, new_tuple = tuple(target.values()), tuple(revised.values())
    require(before[injection.table] - after[injection.table] == {old_tuple} and
            after[injection.table] - before[injection.table] == {new_tuple}, 'SQL changed undeclared rows')
    require(all(before[t] == after[t] for t in before if t != injection.table), 'SQL changed other tables')
    require(schema == connection.execute('SELECT sql FROM sqlite_master').fetchall(), 'SQL changed schema')
    require(not connection.execute('PRAGMA foreign_key_check').fetchall(), 'overlay FK failure')
    return 'sql'


def verify_evidence(connection, item, root):
    if item.kind == 'db':
        require(item.table is not None and item.key is not None and bool(item.fields), 'DB evidence incomplete')
        record = row_for(connection, item.table, item.key)
        require(set(item.fields) <= record.keys() and all(record[k] == v for k, v in item.fields.items()),
                f'DB evidence mismatch: {item.table}/{item.key}')
        require(item.file is None and item.quote is None, 'mixed evidence kinds')
    else:
        prefix = 'service_kb' if item.kind == 'kb' else 'data/external'
        path = safe_path(root, item.file, prefix)
        lines = path.read_text(encoding='utf-8-sig').splitlines()
        require(isinstance(item.line_start, int) and isinstance(item.line_end, int) and
                1 <= item.line_start <= item.line_end <= len(lines), 'source line range invalid')
        require(item.quote == '\n'.join(lines[item.line_start - 1:item.line_end]), 'source quote mismatch')
        require(item.table is None and item.key is None and item.fields is None, 'mixed evidence kinds')


def proposal_args(proposal):
    args = dict(proposal.args)
    if proposal.tool == 'propose_service_visit':
        require(bool(proposal.description_must_include) and all(proposal.description_must_include),
                'visit description needs nonempty review keywords')
        require('description' not in args, 'visit description must use keyword contract')
        args['description'] = '；'.join(proposal.description_must_include)
    else:
        require(not proposal.description_must_include, 'description keywords only apply to visit')
    if proposal.slot_id_in:
        slot_field = 'slot_id' if proposal.tool == 'propose_service_visit' else 'new_slot_id'
        require(slot_field not in args and len(set(proposal.slot_id_in)) == len(proposal.slot_id_in), 'ambiguous slot declaration')
        args[slot_field] = proposal.slot_id_in[0]
    return ARGUMENT_MODELS[proposal.tool].model_validate(args).model_dump(exclude_none=True)


def precondition(connection, user, tool, args, business_date):
    if tool not in WRITE_PROPOSAL_TOOLS:
        raise ValueError('blocked request must name a proposal tool')
    ARGUMENT_MODELS[tool].model_validate(args)
    if tool == 'propose_change':
        table, key = ('orders', 'order_id') if args['target_id'].startswith('O-') else ('appointments', 'appointment_id')
        record = row_for(connection, table, {key: args['target_id']})
        if record['user_id'] != user:
            return 'other_user'
        if record['status'] != ('processing' if table == 'orders' else 'scheduled'):
            return 'not_cancellable'
        if args['change'] != 'reschedule':
            return None
        slot_id = args['new_slot_id']
    else:
        device = row_for(connection, 'devices', {'device_id': args['device_id']})
        if device['user_id'] != user:
            return 'other_user'
        if tool == 'propose_order':
            sku = row_for(connection, 'consumables', {'sku': args['sku']})
            if not connection.execute('SELECT 1 FROM consumable_models WHERE sku=? AND model_code=?',
                                      (args['sku'], device['model_code'])).fetchone():
                return 'incompatible'
            if sku['stock'] < args['qty']:
                return 'out_of_stock'
            if sku['max_per_order'] is not None and args['qty'] > sku['max_per_order']:
                return 'purchase_limit'
            return None
        if args.get('error_code'):
            error = row_for(connection, 'error_codes', {'model_code': device['model_code'], 'code': args['error_code']})
            if not error['requires_visit']:
                return 'self_fixable'
        component = 'battery' if args.get('error_code') == 'E09' else 'whole_machine'
        months = row_for(connection, 'warranty_policies', {'model_code': device['model_code'], 'component': component})['months']
        expires = add_months(date.fromisoformat(device['purchase_date']), months)
        if not (date.fromisoformat(device['purchase_date']) <= date.fromisoformat(business_date) <= expires):
            return 'warranty_expired'
        require(not connection.execute("SELECT 1 FROM appointments a JOIN tickets t USING(ticket_id) WHERE t.device_id=? AND a.status='scheduled'",
                                       (device['device_id'],)).fetchone(), 'device already has scheduled appointment')
        slot_id = args['slot_id']
    slot = row_for(connection, 'service_slots', {'slot_id': slot_id})
    region = row_for(connection, 'users', {'user_id': user})['region']
    if slot['region'] != region:
        return 'other_user'
    if slot['booked'] >= slot['capacity'] or slot['start_at'][:10] <= business_date:
        return 'no_slot'
    return None


def matches_forbidden(proposal, item):
    if isinstance(item, str):
        require(item in WRITE_PROPOSAL_TOOLS, 'unknown forbidden proposal tool')
        return proposal.tool == item
    require(set(item) == {'tool', 'args'} and item['tool'] in WRITE_PROPOSAL_TOOLS and isinstance(item['args'], dict),
            'invalid forbidden proposal pattern')
    return proposal.tool == item['tool'] and all(proposal.args.get(k) == v for k, v in item['args'].items())


def verify_structure(task):
    require(re.fullmatch({'dev': r'SV-D\d{2}', 'test': r'SV-T\d{2}', 'injection': r'SI-I\d{2}'}[task.split], task.id), 'invalid task ID')
    require(task.category in DISTRIBUTION[task.split], 'invalid category/split')
    require(task.title.strip() and task.notes.strip() and task.final_db_checks, 'missing review metadata/final checks')
    user_count, refs, decided = 0, {}, set()
    for turn in task.turns:
        if turn.type == 'user':
            user_count += 1
            require(turn.query and turn.query.strip() and turn.expect and turn.proposal_ref is None, 'user turn incomplete')
            for key in ('required_tools', 'allowed_tools', 'expected_proposals', 'forbidden_proposals', 'required_points', 'evidence'):
                require(getattr(turn, key) is not None, f'missing user field: {key}')
            require(turn.required_points and turn.evidence, 'every user turn needs points/evidence')
            for names in (turn.required_tools, turn.allowed_tools):
                require(len(names) == len(set(names)) and set(names) <= ARGUMENT_MODELS.keys(), 'unknown/duplicate tools')
            require(set(turn.required_tools) <= set(turn.allowed_tools), 'required tools outside allowed')
            for item in turn.forbidden_proposals:
                if isinstance(item, str):
                    require(item in WRITE_PROPOSAL_TOOLS, 'unknown forbidden proposal tool')
                else:
                    require(set(item) == {'tool', 'args'} and item['tool'] in WRITE_PROPOSAL_TOOLS and isinstance(item['args'], dict),
                            'invalid forbidden proposal pattern')
            require(not any(name in turn.query for name in ARGUMENT_MODELS), 'tool name leaked into prompt')
            require(len(turn.expected_proposals) <= 2, 'more than two proposals per user turn')
            require(turn.expect == 'answer' or not turn.expected_proposals, 'clarify/refuse must not propose')
            require(set(turn.allowed_tools) & WRITE_PROPOSAL_TOOLS == {p.tool for p in turn.expected_proposals},
                    'allowed write tools must match this turn gold')
            for index, proposal in enumerate(turn.expected_proposals):
                require(proposal.tool in turn.required_tools, 'gold proposal must be required')
                require(not any(matches_forbidden(proposal, item) for item in turn.forbidden_proposals), 'gold contradicts forbidden')
                refs[f't{user_count}.p{index}'] = proposal
        else:
            require(turn.proposal_ref in refs and turn.proposal_ref not in decided, 'bad/duplicate proposal_ref')
            require(all(getattr(turn, key) is None for key in ('query', 'expect', 'required_tools', 'allowed_tools',
                        'expected_proposals', 'forbidden_proposals', 'required_points', 'evidence')), 'event has user fields')
            decided.add(turn.proposal_ref)
    require(1 <= user_count <= 3, 'user turn count outside 1..3')
    require((task.injection is not None) == (task.split == 'injection'), 'injection metadata/split mismatch')
    if task.injection:
        require(task.injection.payload.strip() and task.injection.intent.strip() and task.injection.hard_gates and
                task.injection.forbidden_read_user_ids and task.injection.forbidden_claims, 'injection review metadata incomplete')
    for blocker in task.blocked_requests:
        require(blocker.user_turn <= user_count, 'blocked request references missing user turn')
    require(task.category != 'precondition_fail' or task.blocked_requests, 'precondition task has no checkable blocker')


def final_results(connection, checks):
    results = []
    for item in checks:
        clause, values = where_clause(connection, item.table, item.where)
        actual = connection.execute(f'SELECT count(*) FROM "{item.table}" WHERE {clause}', values).fetchone()[0]
        results.append({'table': item.table, 'where': item.where, 'expected': item.expect_count, 'actual': actual,
                        'pass': actual == item.expect_count})
    return results


def gold_execute(connection, task, ref, proposal, args, action_id):
    """Reference-only fixture mutation on a throwaway DB, after gold confirm."""
    token = f'{task.id}-{ref.replace(".", "-")}'
    if proposal.tool == 'propose_order':
        device = row_for(connection, 'devices', {'device_id': args['device_id']})
        sku = row_for(connection, 'consumables', {'sku': args['sku']})
        connection.execute('INSERT INTO orders VALUES (?,?,?,?,?,?,?,?,?)',
                           (f'O-GOLD-{token}', task.user_id, args['device_id'], device['model_code'],
                            args['sku'], args['qty'], sku['price_cents'] * args['qty'], 'processing', action_id))
        connection.execute('UPDATE consumables SET stock=stock-? WHERE sku=?', (args['qty'], args['sku']))
    elif proposal.tool == 'propose_service_visit':
        device = row_for(connection, 'devices', {'device_id': args['device_id']})
        ticket = f'T-GOLD-{token}'
        connection.execute('INSERT INTO tickets VALUES (?,?,?,?,?,?,?,?,?)',
                           (ticket, task.user_id, args['device_id'], device['model_code'], args.get('error_code'),
                            args['description'], 'gold fixture only', 'scheduled', action_id))
        connection.execute('INSERT INTO appointments VALUES (?,?,?,?,?,?)',
                           (f'A-GOLD-{token}', ticket, args['slot_id'], task.user_id, 'scheduled', action_id))
        connection.execute('UPDATE service_slots SET booked=booked+1 WHERE slot_id=?', (args['slot_id'],))
    else:
        target = args['target_id']
        if args['change'] == 'cancel_order':
            connection.execute("UPDATE orders SET status='cancelled' WHERE order_id=?", (target,))
        else:
            old = row_for(connection, 'appointments', {'appointment_id': target})
            connection.execute('UPDATE service_slots SET booked=booked-1 WHERE slot_id=?', (old['slot_id'],))
            if args['change'] == 'reschedule':
                connection.execute('UPDATE appointments SET slot_id=? WHERE appointment_id=?', (args['new_slot_id'], target))
                connection.execute('UPDATE service_slots SET booked=booked+1 WHERE slot_id=?', (args['new_slot_id'],))
            else:
                connection.execute("UPDATE appointments SET status='cancelled' WHERE appointment_id=?", (target,))


def simulate(connection, task, business_date, root=ROOT):
    before = final_results(connection, task.final_db_checks)
    pending, user_turn, confirmed = {}, 0, 0
    details = {'proposals': 0, 'evidence': 0, 'blocked_requests': 0, 'confirm': 0, 'reject': 0}
    for turn in task.turns:
        if turn.type == 'user':
            user_turn += 1
            for evidence in turn.evidence:
                verify_evidence(connection, evidence, root)
                details['evidence'] += 1
            for blocked in task.blocked_requests:
                if blocked.user_turn == user_turn:
                    reason = precondition(connection, task.user_id, blocked.tool, blocked.args, business_date)
                    require(reason == blocked.reason, f'blocked condition mismatch: {reason}/{blocked.reason}')
                    details['blocked_requests'] += 1
            for index, proposal in enumerate(turn.expected_proposals):
                args = proposal_args(proposal)
                choices = proposal.slot_id_in or [None]
                for choice in choices:
                    candidate = dict(args)
                    if choice:
                        candidate['slot_id' if proposal.tool == 'propose_service_visit' else 'new_slot_id'] = choice
                    require(precondition(connection, task.user_id, proposal.tool, candidate, business_date) is None,
                            'gold proposal precondition fails')
                target = args.get('device_id', args.get('target_id'))
                for old_ref, (old, old_args, old_id, status) in list(pending.items()):
                    if status == 'pending' and old.tool == proposal.tool and old_args.get('device_id', old_args.get('target_id')) == target:
                        pending[old_ref] = (old, old_args, old_id, 'superseded')
                        connection.execute("UPDATE pending_actions SET status='superseded' WHERE action_id=?", (old_id,))
                ref = f't{user_turn}.p{index}'
                action_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f'B1-gold/{task.id}/{ref}'))
                encoded = json.dumps(args, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
                connection.execute('INSERT INTO pending_actions VALUES (?,?,?,?,?,?,?,?,?,?,NULL,NULL)',
                                   (action_id, f'gold-{task.id}', task.user_id, proposal.tool, encoded,
                                    hashlib.sha256(encoded.encode()).hexdigest(), task.title,
                                    f'{business_date}T09:00:00+08:00', f'{business_date}T09:10:00+08:00', 'pending'))
                pending[ref] = (proposal, args, action_id, 'pending')
                details['proposals'] += 1
        else:
            proposal, args, action_id, status = pending[turn.proposal_ref]
            require(status == 'pending', 'event references superseded/already decided proposal')
            status = 'rejected' if turn.type == 'reject' else 'executed'
            if turn.type == 'confirm':
                require(precondition(connection, task.user_id, proposal.tool, args, business_date) is None,
                        'gold confirm precondition fails')
                gold_execute(connection, task, turn.proposal_ref, proposal, args, action_id)
                confirmed += 1
            connection.execute('UPDATE pending_actions SET status=? WHERE action_id=?', (status, action_id))
            pending[turn.proposal_ref] = (proposal, args, action_id, status)
            details[turn.type] += 1
    after = final_results(connection, task.final_db_checks)
    require(all(item['pass'] for item in after), f'gold final state fails: {[x for x in after if not x["pass"]]}')
    if details['proposals']:
        require(not all(item['pass'] for item in before), 'vacuous final checks: doing nothing also passes')
    if confirmed:
        require(any(not item['pass'] and item['table'] in ('orders', 'tickets', 'appointments', 'service_slots', 'consumables')
                    for item in before), 'confirmed business write has no meaningful business final check')
    require(not connection.execute('PRAGMA foreign_key_check').fetchall(), 'gold simulation FK failure')
    require(not connection.execute("SELECT s.slot_id FROM service_slots s WHERE s.booked != s.external_booked + (SELECT count(*) FROM appointments a WHERE a.slot_id=s.slot_id AND a.status='scheduled')").fetchall(), 'gold occupancy mismatch')
    return {**details, 'final_checks': after, 'no_op_would_pass': all(item['pass'] for item in before)}


def prompt_bigrams(task):
    text = ''.join(turn.query for turn in task.turns if turn.type == 'user')
    text = ''.join(c.lower() for c in text if c.isalnum())
    return {text[i:i + 2] for i in range(len(text) - 1)}


def cross_similarity(tasks):
    pairs = []
    for index, left in enumerate(tasks):
        for right in tasks[index + 1:]:
            if left.split == right.split:
                continue
            a, b = prompt_bigrams(left), prompt_bigrams(right)
            score = len(a & b) / len(a | b) if a | b else 1.0
            if score >= .6:
                pairs.append({'left': left.id, 'right': right.id, 'jaccard': round(score, 6)})
    return pairs


def check_all(root=ROOT, *, write_reports=False):
    root = Path(root).resolve()
    sources = {'dev': root / 'evaluation/service_v1/dev.jsonl',
               'test': root / 'evaluation/service_v1/test.jsonl',
               'injection': root / 'evaluation/service_injection_v1/cases.jsonl'}
    tasks, failures = [], []
    for split, path in sources.items():
        for raw in load_jsonl(path):
            try:
                task = Task.model_validate(raw)
                require(task.split == split, 'file/split mismatch')
                verify_structure(task)
                tasks.append(task)
            except (ValueError, ValidationError) as error:
                failures.append({'id': raw.get('id', '<missing>'), 'check': 'structure', 'error': str(error)})
    ids = [task.id for task in tasks]
    require(len(ids) == len(set(ids)), 'duplicate task IDs')
    for split, expected in DISTRIBUTION.items():
        actual = dict(Counter(task.category for task in tasks if task.split == split))
        if actual != expected:
            failures.append({'id': split, 'check': 'structure', 'error': f'distribution: {actual} != {expected}'})
    injection_tasks = [t for t in tasks if t.injection]
    carriers = Counter(t.injection.carrier_class for t in injection_tasks)
    require(all(carriers[k] >= 2 for k in ('ticket_text', 'temporary_kb', 'catalog_text', 'monthly_or_warranty')),
            'injection carrier distribution incomplete')
    require(any(t.injection.kind == 'csv' for t in injection_tasks), 'monthly CSV carrier missing')
    seen_queries, duplicates = {}, []
    for task in tasks:
        for turn in task.turns:
            if turn.type != 'user':
                continue
            normalized = re.sub(r'\s+', '', turn.query)
            if normalized in seen_queries and seen_queries[normalized][1] != task.split:
                duplicates.append([seen_queries[normalized][0], task.id])
            seen_queries[normalized] = (task.id, task.split)
    if duplicates:
        failures.append({'id': 'all', 'check': 'isolation', 'error': f'duplicate cross-split prompts: {duplicates}'})
    per_task = []
    config = load_config()
    with tempfile.TemporaryDirectory(prefix='service-suite-') as folder:
        seed = Path(folder) / 'seed.db'
        init_db(seed)
        require(content_sha256(seed) == config['seed_content_sha256'], 'seed hash differs from config')
        # Independent copies include injection, gold writes and even rejected proposals.
        for task in tasks:
            with closing(sqlite3.connect(':memory:')) as connection, closing(sqlite3.connect(seed)) as source:
                source.backup(connection)
                connection.execute('PRAGMA foreign_keys=ON')
                try:
                    stage = 'final_state'
                    require(all(x['pass'] for x in final_results(connection, task.initial_db_checks)), 'initial facts do not hold')
                    stage = {'db': 'sql_overlay', 'csv': 'csv_overlay', 'kb': 'evidence'}.get(task.injection.kind if task.injection else '', 'evidence')
                    overlay = apply_overlay(connection, task, root)
                    stage = 'proposals'
                    details = simulate(connection, task, config['business_date'], root)
                    per_task.append({'id': task.id, 'split': task.split, 'pass': True, 'overlay': overlay, **details})
                except (ValueError, sqlite3.Error, ValidationError) as error:
                    failures.append({'id': task.id, 'check': stage, 'error': str(error)})
                    per_task.append({'id': task.id, 'split': task.split, 'pass': False, 'error': str(error)})
    pairs = cross_similarity(tasks)
    reports = {}
    for suite, splits in (('service_v1', {'dev', 'test'}), ('service_injection_v1', {'injection'})):
        selected = [t for t in tasks if t.split in splits]
        details = [t for t in per_task if t['split'] in splits]
        counts = {'structure': len(selected), 'proposals': sum(t.get('proposals', 0) for t in details),
                  'blocked_requests': sum(t.get('blocked_requests', 0) for t in details),
                  'evidence': sum(t.get('evidence', 0) for t in details),
                  'final_state': sum(len(t.get('final_checks', [])) for t in details),
                  'similarity': sum(1 for i, a in enumerate(tasks) for b in tasks[i + 1:]
                                    if a.split != b.split and (a.split in splits or b.split in splits)),
                  'isolation': sum(sum(turn.type == 'user' for turn in t.turns) for t in selected),
                  'csv_overlay': sum(t.get('overlay') == 'csv' for t in details),
                  'sql_overlay': sum(t.get('overlay') == 'sql' for t in details)}
        relevant_failures = [f for f in failures if f['id'] in {t.id for t in selected} or f['id'] in splits or f['id'] == 'all']
        reports[suite] = {'stage': 'B1-draft', 'ok': not relevant_failures, 'seed_content_sha256': config['seed_content_sha256'],
                          'checks': {name: {'passed': counts[name], 'failed': sum(f['check'] == name for f in relevant_failures)}
                                     for name in CHECK_NAMES},
                          'distribution': {split: dict(Counter(t.category for t in selected if t.split == split)) for split in sorted(splits)},
                          'user_counts': {split: dict(sorted(Counter(t.user_id for t in selected if t.split == split).items())) for split in sorted(splits)},
                          'similarity_pairs': [p for p in pairs if p['left'] in {t.id for t in selected} or p['right'] in {t.id for t in selected}],
                          'duplicate_prompts': duplicates, 'tasks': details, 'failures': relevant_failures}
        if write_reports:
            (root / 'evaluation' / suite / 'static_checks.json').write_text(
                json.dumps(reports[suite], ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
    return {'ok': not failures, 'reports': reports, 'failures': failures}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write-reports', action='store_true')
    args = parser.parse_args(argv)
    try:
        result = check_all(write_reports=args.write_reports)
    except (ValueError, OSError, sqlite3.Error) as error:
        print(json.dumps({'ok': False, 'error': str(error)}, ensure_ascii=False))
        return 1
    print(json.dumps({'ok': result['ok'], 'checks': {suite: report['checks'] for suite, report in result['reports'].items()},
                      'similarity_pairs': result['reports']['service_v1']['similarity_pairs'], 'failures': result['failures']}, ensure_ascii=False, indent=2))
    return 0 if result['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
