"""Determinism, independently checked facts and failure paths of the S0-A seed."""
from contextlib import closing
import csv
from datetime import date
import json
import sqlite3

import pytest

from scripts import manage
from service_desk.config import ROOT, load_config
from service_desk.db import content_sha256, init_db
from service_desk.seed import (
    assert_consistency, component_evidence, read_csv, warranty_examples, add_months,
    FIRST_TEN_INITIAL_STATE,
)


@pytest.fixture
def database(tmp_path):
    path = tmp_path / 'service.db'
    init_db(path)
    return path


def test_canonical_seed_hash_on_every_platform(tmp_path):
    first, second = tmp_path / 'a.db', tmp_path / 'b.db'
    init_db(first)
    init_db(second)
    assert content_sha256(first) == content_sha256(second) == load_config()['seed_content_sha256']


def test_no_overwrite_and_force_restores_seed(database, capsys):
    original = content_sha256(database)
    assert manage.main(['service-db', 'init', '--path', str(database)]) == 1
    assert '--force' in capsys.readouterr().err
    assert content_sha256(database) == original
    with closing(sqlite3.connect(database)) as connection:
        connection.execute("UPDATE users SET region='changed' WHERE user_id='1001'")
        connection.commit()
    assert content_sha256(database) != original
    assert manage.main(['service-db', 'init', '--path', str(database), '--force']) == 0
    assert content_sha256(database) == original
    assert manage.main(['service-db', 'hash', '--path', str(database)]) == 0
    assert capsys.readouterr().out.splitlines()[-1] == original


def test_hash_uses_pk_order_and_not_sqlite_bytes(database):
    original = content_sha256(database)
    with closing(sqlite3.connect(database)) as connection:
        # Rewrite a table in reverse insertion order and alter file layout.
        rows = connection.execute('SELECT * FROM telemetry_daily ORDER BY device_id DESC,date DESC').fetchall()
        connection.execute('DELETE FROM telemetry_daily')
        connection.executemany('INSERT INTO telemetry_daily VALUES (?,?,?,?,?)', rows)
        connection.commit()
        connection.execute('VACUUM')
    assert content_sha256(database) == original


def test_hash_missing_database_does_not_create_file(tmp_path):
    path = tmp_path / 'missing.db'
    with pytest.raises(sqlite3.Error):
        content_sha256(path)
    assert not path.exists()


def test_seed_scale_and_business_consistency(database):
    with closing(sqlite3.connect(database)) as connection:
        assert_consistency(connection, business_date='2026-01-12')
        assert connection.execute('SELECT count(*) FROM users').fetchone()[0] == 50
        assert connection.execute('SELECT count(*) FROM devices').fetchone()[0] == 58
        assert connection.execute('SELECT count(*) FROM models').fetchone()[0] == 4
        assert connection.execute('SELECT count(DISTINCT code) FROM error_codes').fetchone()[0] == 12
        assert len(connection.execute('SELECT user_id FROM devices GROUP BY user_id HAVING count(*)=2').fetchall()) == 8
        assert not connection.execute('PRAGMA foreign_key_check').fetchall()
        assert {row[1] for row in connection.execute('PRAGMA table_info(telemetry_daily)')} == {
            'device_id', 'date', 'area_m2', 'duration_min', 'error_events'}
        for table, expected in (('orders', {'completed', 'processing', 'cancelled'}),
                                ('tickets', {'completed', 'processing', 'scheduled', 'cancelled'}),
                                ('appointments', {'completed', 'scheduled', 'cancelled'})):
            assert {row[0] for row in connection.execute(f'SELECT DISTINCT status FROM {table}')} == expected
            assert connection.execute(f'SELECT count(*) FROM {table} WHERE source_action_id IS NOT NULL').fetchone()[0] == 0
        for region, in connection.execute('SELECT DISTINCT region FROM users'):
            assert connection.execute('SELECT count(DISTINCT substr(start_at,1,10)) FROM service_slots '
                                      'WHERE region=? AND start_at>?', (region, '2026-01-12T23:59:59')).fetchone()[0] == 14
            assert not connection.execute('SELECT a.appointment_id FROM appointments a JOIN tickets t USING(ticket_id) '
                                          'JOIN devices d ON t.device_id=d.device_id JOIN users u ON d.user_id=u.user_id '
                                          'JOIN service_slots s USING(slot_id) WHERE s.region!=u.region').fetchall()
        for slot, external, booked, capacity in connection.execute('SELECT slot_id,external_booked,booked,capacity FROM service_slots'):
            assert 0 <= external <= booked <= capacity
            assert booked == external + connection.execute("SELECT count(*) FROM appointments WHERE slot_id=? AND status='scheduled'",
                                                (slot,)).fetchone()[0]
        for model, in connection.execute('SELECT model_code FROM models'):
            assert connection.execute('SELECT count(*) FROM consumable_models WHERE model_code=?', (model,)).fetchone()[0] > 0
        states = warranty_examples(connection, '2026-01-12')
        by_device = {}
        for item in states:
            by_device.setdefault(item['device_id'], {})[item['component']] = item['in_warranty']
        assert by_device['D-1001-01'] == {'battery': False, 'whole_machine': False}
        assert by_device['D-1002-01'] == {'battery': False, 'whole_machine': True}
        assert by_device['D-1006-01'] == {'battery': True, 'whole_machine': True}
        assert by_device['D-1007-01'] == {'battery': False, 'whole_machine': False}
        assert {item['component']: item['expires_at'] for item in states
                if item['device_id'] == 'D-1006-01'} == {
            'battery': '2026-10-02', 'whole_machine': '2027-10-02'}
        assert connection.execute(
            'SELECT model_code,component,months FROM warranty_policies '
            "WHERE component!='consumables' ORDER BY model_code,component").fetchall() == [
                ('SV-100', 'battery', 6), ('SV-100', 'whole_machine', 12),
                ('SV-200', 'battery', 12), ('SV-200', 'whole_machine', 24),
                ('SV-300', 'battery', 12), ('SV-300', 'whole_machine', 18),
                ('SV-400', 'battery', 24), ('SV-400', 'whole_machine', 36)]
        assert connection.execute('SELECT count(*) FROM telemetry_daily WHERE device_id=?', ('D-1011-01',)).fetchone()[0] == 30


def test_purchase_dates_precede_csv_and_first_telemetry(database):
    with closing(sqlite3.connect(database)) as connection:
        dates = connection.execute(
            'SELECT d.device_id,d.purchase_date,min(t.date) FROM devices d '
            'JOIN telemetry_daily t USING(device_id) GROUP BY d.device_id,d.purchase_date').fetchall()
        assert len(dates) == 58
        assert all(purchase <= first for _, purchase, first in dates)
        assert connection.execute(
            "SELECT user_id,purchase_date FROM devices WHERE user_id IN ('1001','1007') ORDER BY user_id"
            ).fetchall() == [('1001', '2024-07-12'), ('1007', '2024-07-12')]
        assert not connection.execute(
            "SELECT device_id FROM devices WHERE user_id BETWEEN '1001' AND '1010' "
            "AND purchase_date>'2025-01-01'").fetchall()


@pytest.mark.parametrize('device,purchase', [
    ('D-1001-01', '2025-01-01'), ('D-1011-01', '2025-12-13'),
])
def test_purchase_on_first_usage_date_is_allowed(database, device, purchase):
    with closing(sqlite3.connect(database)) as connection:
        connection.execute('UPDATE devices SET purchase_date=? WHERE device_id=?', (purchase, device))
        assert_consistency(connection, business_date='2026-01-12')


@pytest.mark.parametrize('device,purchase,needle', [
    ('D-1001-01', '2025-03-01', 'purchase after CSV start'),
    ('D-1011-01', '2025-12-14', 'purchase after first telemetry date'),
    ('D-1015-02', '2025-12-14', 'purchase after first telemetry date'),
])
def test_purchase_after_first_usage_is_rejected(database, device, purchase, needle):
    with closing(sqlite3.connect(database)) as connection:
        connection.execute('UPDATE devices SET purchase_date=? WHERE device_id=?', (purchase, device))
        with pytest.raises(AssertionError, match=needle):
            assert_consistency(connection, business_date='2026-01-12')


def test_csv_literal_newlines_and_narrow_suggestion_exception():
    evidence = component_evidence(read_csv())
    assert {'filter', 'main_brush'} <= evidence['1001'].keys()
    mechanical = evidence['1006']['mechanical_arm']
    assert {item['month'] for item in mechanical} == {'2025-03', '2025-07', '2025-08'}
    assert 'multi_floor' in evidence['1006']
    rows = [{'用户ID': '1006', '时间': '2025-01', '清洁效率': '跨楼层失败', '耗材': '',
             '对比': '建议增加机械臂配件+提升跨楼层导航'}]
    assert component_evidence(rows)['1006'].keys() == {'multi_floor'}
    rows[0]['对比'] = '机械臂配件已加装'
    assert 'mechanical_arm' in component_evidence(rows)['1006']


@pytest.mark.parametrize('statement,needle', [
    ("DELETE FROM devices WHERE user_id='1001'", 'has no device'),
    ("UPDATE models SET components_json='[]' WHERE model_code='SV-100'", 'component mismatch'),
    ("UPDATE devices SET model_code='SV-400' WHERE user_id='1001'", 'assignment mismatch'),
    ("UPDATE telemetry_daily SET area_m2=1 WHERE device_id='D-1001-01'", 'daily area mismatch'),
    ("DELETE FROM telemetry_daily WHERE device_id='D-1001-01' AND date='2025-01-01'", 'month incomplete'),
    ("DELETE FROM telemetry_daily WHERE device_id='D-1003-01' AND date='2025-01-01'", 'year incomplete'),
    ("UPDATE warranty_policies SET months=60 WHERE component!='consumables'", 'warranty states'),
    ("UPDATE warranty_policies SET months=0", 'warranty states'),
    ("UPDATE warranty_policies SET months=24 WHERE component!='consumables'", 'warranty states missing: whole only'),
    ("DELETE FROM error_codes WHERE code='E07'", 'E07 missing'),
    ("UPDATE error_codes SET title='same' WHERE code='E07'", 'model-specific'),
    ("UPDATE consumables SET stock=1", 'out-of-stock'),
    ("UPDATE consumables SET max_per_order=NULL", 'purchase limit'),
    ("UPDATE service_slots SET booked=capacity WHERE region='north'", 'slot coverage'),
    ("UPDATE service_slots SET booked=0 WHERE region='north'", 'slot coverage'),
    ("DELETE FROM service_slots WHERE region='north' AND start_at LIKE '2026-01-26%'", 'slot coverage'),
    ("UPDATE orders SET user_id='nobody'", 'foreign key'),
])
def test_generation_assertions_reject_corrupt_business_facts(database, statement, needle):
    with closing(sqlite3.connect(database)) as connection:
        # Deliberately disable FK enforcement to exercise the diagnostic assertion.
        connection.execute(statement)
        with pytest.raises(AssertionError, match=needle):
            assert_consistency(connection, business_date='2026-01-12')


def test_invalid_csv_does_not_publish_partial_database(tmp_path):
    rows = read_csv()
    rows[0]['耗材'] += r'\n水箱已安装'
    source = tmp_path / 'records.csv'
    with source.open('w', encoding='utf-8', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    target = tmp_path / 'invalid.db'
    with pytest.raises(AssertionError, match='component mismatch'):
        init_db(target, csv_path=source)
    assert not target.exists()
    assert not list(tmp_path.glob('.service-*'))


@pytest.mark.parametrize('table', ['orders', 'tickets', 'appointments'])
def test_source_action_unique_allows_null_but_rejects_replay(database, table):
    with closing(sqlite3.connect(database)) as connection:
        connection.execute('PRAGMA foreign_keys=ON')
        connection.execute("INSERT INTO pending_actions VALUES ('test-action','session','1001','propose_order',"
                           "'{}',?,'测试','2026-01-12T09:00:00+08:00','2026-01-12T09:10:00+08:00','pending',NULL,NULL)", ('a' * 64,))
        keys = [row[0] for row in connection.execute(f'SELECT rowid FROM {table} ORDER BY rowid LIMIT 2')]
        connection.execute(f'UPDATE {table} SET source_action_id=? WHERE rowid=?', ('test-action', keys[0]))
        with pytest.raises(sqlite3.IntegrityError, match='UNIQUE'):
            connection.execute(f'UPDATE {table} SET source_action_id=? WHERE rowid=?', ('test-action', keys[1]))


def test_audit_is_empty_and_append_only(database):
    with closing(sqlite3.connect(database)) as connection:
        assert connection.execute('SELECT count(*) FROM audit_log').fetchone()[0] == 0
        connection.execute("INSERT INTO audit_log VALUES ('L-test','2026-01-12T09:00:00+08:00','session','1001',"
                           "NULL,'denied','propose_order',?,'测试拒绝事件')", ('a' * 64,))
        for statement in ("UPDATE audit_log SET detail='changed'", 'DELETE FROM audit_log'):
            with pytest.raises(sqlite3.IntegrityError, match='append-only'):
                connection.execute(statement)


@pytest.mark.parametrize('table', ['pending_actions', 'audit_log'])
def test_seed_assertions_reject_runtime_action_or_audit_rows(database, table):
    with closing(sqlite3.connect(database)) as connection:
        if table == 'pending_actions':
            connection.execute("INSERT INTO pending_actions VALUES ('test-action','session','1001','propose_order',"
                               "'{}',?,'测试','2026-01-12T09:00:00+08:00','2026-01-12T09:10:00+08:00','pending',NULL,NULL)", ('a' * 64,))
        else:
            connection.execute("INSERT INTO audit_log VALUES ('L-test','2026-01-12T09:00:00+08:00','session','1001',"
                               "NULL,'denied','propose_order',?,'测试拒绝事件')", ('a' * 64,))
        with pytest.raises(AssertionError, match=table + ' seed must be empty'):
            assert_consistency(connection, business_date='2026-01-12')


def test_calendar_month_end_and_anniversary_are_explicit():
    assert add_months(date(2024, 2, 29), 12) == date(2025, 2, 28)
    assert add_months(date(2025, 1, 31), 1) == date(2025, 2, 28)


def test_config_rejects_invalid_types_and_paths(tmp_path):
    import yaml
    original = load_config()
    for key, value in (('business_date', '2026-02-30'), ('pending_action_ttl_seconds', True),
                       ('db_path', '../outside.db'), ('kb_dir', 'C:/outside'),
                       ('seed_content_sha256', 'bad')):
        path = tmp_path / 'invalid.yml'
        path.write_text(yaml.safe_dump({**original, key: value}), encoding='utf-8')
        with pytest.raises(ValueError):
            load_config(path)


def test_curated_first_ten_history_and_global_scheduled_distribution(database):
    assert set(FIRST_TEN_INITIAL_STATE) == {str(user) for user in range(1001, 1011)}
    with closing(sqlite3.connect(database)) as connection:
        assert connection.execute("SELECT user_id FROM appointments WHERE user_id<='1010' AND status='scheduled' ORDER BY user_id").fetchall() == [('1004',), ('1005',), ('1008',)]
        assert connection.execute("SELECT user_id FROM orders WHERE user_id<='1010' AND status='processing' ORDER BY user_id").fetchall() == [('1007',), ('1009',), ('1010',)]
        assert connection.execute("SELECT count(*) FROM tickets WHERE user_id<='1010' AND status='processing'").fetchone()[0] == 0
        assert connection.execute("SELECT count(DISTINCT sku) FROM orders WHERE user_id<='1010'").fetchone()[0] == 4
        counts = connection.execute("SELECT d.device_id,count(a.appointment_id) FROM devices d LEFT JOIN tickets t USING(device_id) LEFT JOIN appointments a ON a.ticket_id=t.ticket_id AND a.status='scheduled' GROUP BY d.device_id").fetchall()
        assert sum(count for _, count in counts) == 5
        assert [count for _, count in counts].count(0) == 53
        assert [count for _, count in counts].count(1) == 5


@pytest.mark.parametrize('statement,needle', [
    ("UPDATE warranty_policies SET months=13 WHERE model_code='SV-100' AND component='battery'", 'battery warranty exceeds'),
    ("UPDATE warranty_policies SET months=12 WHERE model_code='SV-400' AND component='battery'", 'warranty states missing: both in'),
    ("UPDATE warranty_policies SET months=12 WHERE model_code IN ('SV-200','SV-300') AND component='whole_machine'", 'warranty states missing: whole only'),
    ("UPDATE warranty_policies SET months=36 WHERE component='whole_machine'", 'warranty states missing: both expired'),
    ("UPDATE service_slots SET booked=booked+1 WHERE slot_id='S-north-20260113-2'", 'slot booked accounting'),
    ("UPDATE service_slots SET external_booked=3,booked=3 WHERE slot_id='S-north-20260113-3'", 'slot capacity exceeded'),
    ("UPDATE service_slots SET external_booked=-1,booked=-1 WHERE slot_id='S-north-20260113-3'", 'negative external occupancy'),
    ("INSERT INTO appointments VALUES ('A-duplicate','T-1004-01','S-west-20260113-3','1004','scheduled',NULL); UPDATE service_slots SET booked=booked+1 WHERE slot_id='S-west-20260113-3'", 'multiple scheduled'),
    ("UPDATE tickets SET error_code='E06' WHERE ticket_id='T-1004-01'", 'appointment error does not require visit'),
    ("UPDATE tickets SET error_code='E06' WHERE ticket_id='T-1013-01'", 'appointment error does not require visit'),
    ("UPDATE tickets SET description='待查' WHERE ticket_id='T-1014-01'", 'explicit problem description'),
    ("UPDATE service_slots SET booked=booked-1 WHERE slot_id='S-west-20260113-2'; UPDATE appointments SET slot_id='S-east-20260113-2' WHERE appointment_id='A-1004-01'; UPDATE service_slots SET booked=booked+1 WHERE slot_id='S-east-20260113-2'", 'appointment region mismatch'),
    ("UPDATE tickets SET user_id='1001',device_id='D-1001-01',model_code='SV-100',error_code='E09' WHERE ticket_id='T-1005-01'; UPDATE appointments SET user_id='1001' WHERE appointment_id='A-1005-01'", 'protected E07 users'),
    ("UPDATE tickets SET user_id='1002',device_id='D-1002-01',model_code='SV-200' WHERE ticket_id='T-1014-01'", 'protected E07 users'),
    ("UPDATE orders SET amount_cents=1 WHERE order_id='O-1009-01'", 'order amount mismatch'),
    ("UPDATE orders SET sku='SKU-MAIN',amount_cents=6900 WHERE order_id='O-1009-01'", 'order SKU incompatible'),
])
def test_review_assertions_reject_counterexamples(database, statement, needle):
    with closing(sqlite3.connect(database)) as connection:
        # Bypass SQL constraints solely to exercise each generation diagnostic.
        connection.execute('PRAGMA ignore_check_constraints=ON')
        connection.executescript(statement)
        with pytest.raises(AssertionError, match=needle):
            assert_consistency(connection, business_date='2026-01-12')


@pytest.mark.parametrize('value', [-1, None])
def test_external_occupancy_column_rejects_negative_and_null(database, value):
    with closing(sqlite3.connect(database)) as connection:
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute('UPDATE service_slots SET external_booked=? WHERE slot_id=?',
                               (value, 'S-north-20260113-3'))


@pytest.mark.parametrize('statement,needle', [
    ("UPDATE tickets SET description='' WHERE ticket_id='T-1014-01'", 'explicit problem description'),
    ("UPDATE devices SET purchase_date='2025-03-01' WHERE device_id='D-1001-01'", 'purchase after CSV start'),
    ("UPDATE devices SET purchase_date='2025-12-14' WHERE device_id='D-1011-01'", 'purchase after first telemetry date'),
])
def test_review_assertions_are_active_under_python_optimization(database, statement, needle):
    import subprocess
    import sys
    code = ("import sqlite3; from service_desk.seed import assert_consistency; "
            "c=sqlite3.connect(__import__('sys').argv[1]); "
            f"c.execute({statement!r}); "
            "assert_consistency(c,business_date='2026-01-12')")
    result = subprocess.run([sys.executable, '-B', '-O', '-c', code, str(database)],
                            cwd=ROOT, capture_output=True, text=True, timeout=30)
    assert result.returncode != 0
    assert needle in result.stderr
