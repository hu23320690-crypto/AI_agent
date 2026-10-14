"""Deterministic synthetic seed using only the Python standard library.

    No wall clock, random UUID or dependency on SQLite file serialization.
"""
import calendar
import csv
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
import json
from pathlib import Path
import random
import re

ROOT = Path(__file__).resolve().parents[1]
RANDOM_SEED = 20260112
REGIONS = ('north', 'east', 'south', 'west')
CSV_COLUMNS = ('清洁效率', '耗材', '对比')
COMPONENT_KEYWORDS = {
    'main_brush': ('主刷',), 'side_brush': ('边刷',), 'rubber_brush': ('胶刷',),
    'filter': ('滤网', 'HEPA'), 'dustbin': ('尘盒',), 'water_tank': ('水箱', '拖地'),
    'dust_bag': ('集尘袋',), 'battery': ('电池',), 'mechanical_arm': ('机械臂',),
    'multi_floor': ('跨楼层',), 'pet_hair': ('毛发',), 'carpet_boost': ('地毯增压',),
}
# Narrow exception: only this suggestion phrase in the comparison column.
# Other words in the same cell (e.g. 跨楼层) still count as actual evidence.
COMPONENT_EXCEPTIONS = (
    {'user_id': '1006', 'column': '对比', 'phrase': '建议增加机械臂配件',
     'reason': '建议新增的配件，不代表现有设备已经配备机械臂；不豁免同单元格的跨楼层功能。'},
)
COMMON_COMPONENTS = ('main_brush', 'side_brush', 'filter', 'dustbin', 'battery')
MODEL_SPECS = (
    ('SV-100', '基础扫地型', COMMON_COMPONENTS, 12, 24),
    ('SV-200', '扫拖一体型', COMMON_COMPONENTS + ('water_tank',), 24, 12),
    ('SV-300', '宠物型', COMMON_COMPONENTS + ('rubber_brush', 'pet_hair', 'carpet_boost'), 18, 24),
    ('SV-400', '自集尘旗舰型', COMMON_COMPONENTS + ('water_tank', 'dust_bag', 'multi_floor', 'mechanical_arm'), 24, 36),
)
CSV_MODEL_CODES = {
    '1001': 'SV-100', '1002': 'SV-200', '1003': 'SV-300', '1004': 'SV-100',
    '1005': 'SV-200', '1006': 'SV-400', '1007': 'SV-100', '1008': 'SV-200',
    '1009': 'SV-300', '1010': 'SV-100',
}
# Codes are deliberately fictional. E07 is model-specific.
COMMON_ERRORS = (
    ('E01', '驱动轮受阻', 1, 1, 0), ('E02', '边刷转动受阻', 1, 1, 0),
    ('E03', '主刷转动受阻', 1, 1, 0), ('E04', '滤网安装异常', 1, 1, 0),
    ('E05', '尘盒安装异常', 1, 1, 0), ('E06', '充电接触异常', 2, 1, 0),
    ('E08', '定位参考缺失', 2, 1, 0), ('E09', '电池保护异常', 3, 0, 1),
    ('E10', '风道堵塞', 2, 1, 0), ('E11', '跌落感应异常', 3, 0, 1),
    ('E12', '控制模块异常', 3, 0, 1),
)
E07_ERRORS = {
    'SV-100': ('尘盒锁扣未闭合', 1, 1, 0),
    'SV-200': ('水箱供水检测异常', 2, 0, 1),
    'SV-300': ('胶刷轴端阻力异常', 2, 1, 0),
    'SV-400': ('集尘通道密封异常', 3, 0, 1),
}
CONSUMABLE_SPECS = (
    ('SKU-FILTER', '通用滤网', 'filter', 3900, 80, 2, ('SV-100', 'SV-200', 'SV-300', 'SV-400')),
    ('SKU-SIDE', '通用边刷', 'side_brush', 1900, 100, None, ('SV-100', 'SV-200', 'SV-300', 'SV-400')),
    ('SKU-MAIN', '标准主刷', 'main_brush', 6900, 60, None, ('SV-100', 'SV-200', 'SV-400')),
    ('SKU-RUBBER', '宠物胶刷', 'rubber_brush', 7900, 30, 1, ('SV-300',)),
    ('SKU-MOP', '清洁拖布', 'mop_pad', 2900, 0, None, ('SV-200', 'SV-400')),
    ('SKU-BAG', '集尘袋', 'dust_bag', 2500, 40, 3, ('SV-400',)),
)


def read_csv(path=None):
    with Path(path or ROOT / 'data/external/records.csv').open(encoding='utf-8-sig', newline='') as handle:
        reader = csv.DictReader(handle)
        required = {'用户ID', '时间', *CSV_COLUMNS}
        if not required.issubset(reader.fieldnames or []):
            raise ValueError('CSV is missing required columns')
        rows = list(reader)
    keys = [(row['用户ID'], row['时间']) for row in rows]
    if len(keys) != len(set(keys)):
        raise ValueError('duplicate CSV user/month')
    return rows


def component_evidence(rows):
    """Retain user, month, column and matched word as reviewable evidence."""
    evidence = {}
    for row in rows:
        user = row['用户ID']
        evidence.setdefault(user, {})
        for column in CSV_COLUMNS:
            # The CSV stores two literal characters, backslash and n.
            text = row[column].replace('\\n', '\n')
            for exception in COMPONENT_EXCEPTIONS:
                if user == exception['user_id'] and column == exception['column']:
                    text = text.replace(exception['phrase'], '')
            for component, keywords in COMPONENT_KEYWORDS.items():
                for word in keywords:
                    if word in text:
                        item = {'month': row['时间'], 'column': column, 'word': word}
                        evidence[user].setdefault(component, []).append(item)
    return evidence


def add_months(value, months):
    """Calendar anniversary, clamping the day at the destination month end."""
    index = value.year * 12 + value.month - 1 + months
    year, month_index = divmod(index, 12)
    month = month_index + 1
    return date(year, month, min(value.day, calendar.monthrange(year, month)[1]))


def warranty_examples(connection, business_date):
    today = date.fromisoformat(business_date)
    rows = []
    for device, model, purchase, component, months in connection.execute(
        'SELECT d.device_id,d.model_code,d.purchase_date,w.component,w.months '
        'FROM devices d JOIN warranty_policies w USING(model_code) '
        "WHERE w.component != 'consumables' ORDER BY d.device_id,w.component"):
        expires = add_months(date.fromisoformat(purchase), months)
        rows.append({'device_id': device, 'model_code': model, 'purchase_date': purchase,
                     'component': component, 'expires_at': expires.isoformat(),
                     'in_warranty': months > 0 and date.fromisoformat(purchase) <= today <= expires})
    return rows


def assert_consistency(connection, *, business_date, csv_path=None):
    """Always-on assertions; explicit raises also work under python -O."""
    def require(condition, message):
        if not condition:
            raise AssertionError(message)

    rows = read_csv(csv_path)
    evidence = component_evidence(rows)
    for user, components in evidence.items():
        devices = connection.execute(
            'SELECT d.model_code,m.components_json FROM devices d JOIN models m USING(model_code) '
            'WHERE user_id=? ORDER BY device_id', (user,)).fetchall()
        require(bool(devices), f'CSV user {user} has no device')
        for model, supported in devices:
            require(model == CSV_MODEL_CODES[user], f'CSV model assignment mismatch: {user}')
            missing = set(components) - set(json.loads(supported))
            require(not missing, f'CSV component mismatch: {user}/{model}/{sorted(missing)}')
    for row in rows:
        match = re.search(r'日均清扫\s*[:：]\s*(\d+)㎡', row['清洁效率'].replace('\\n', '\n'))
        if not match:
            continue
        month = row['时间']
        first = date.fromisoformat(month + '-01')
        days = calendar.monthrange(first.year, first.month)[1]
        for (device,) in connection.execute('SELECT device_id FROM devices WHERE user_id=?', (row['用户ID'],)):
            count, total = connection.execute(
                'SELECT count(*),sum(area_m2) FROM telemetry_daily WHERE device_id=? AND date LIKE ?',
                (device, month + '-%')).fetchone()
            require(count == days, f'telemetry month incomplete: {device}/{month}')
            average = Decimal(str(total)) / Decimal(days)
            require(int(average.quantize(Decimal('1'), rounding=ROUND_HALF_UP)) == int(match[1]),
                    f'CSV daily area mismatch: {device}/{month}')
    for user in CSV_MODEL_CODES:
        for (device,) in connection.execute('SELECT device_id FROM devices WHERE user_id=?', (user,)):
            count, first, last = connection.execute(
                'SELECT count(*),min(date),max(date) FROM telemetry_daily WHERE device_id=?', (device,)).fetchone()
            require((count, first, last) == (365, '2025-01-01', '2025-12-31'), f'year incomplete: {device}')
    warranties = warranty_examples(connection, business_date)
    whole = [item for item in warranties if item['component'] == 'whole_machine']
    require(any(item['in_warranty'] for item in whole) and any(not item['in_warranty'] for item in whole),
            'both whole-machine warranty states must exist')
    states = {}
    for item in warranties:
        states.setdefault(item['device_id'], {})[item['component']] = item['in_warranty']
    require(any(item['whole_machine'] != item['battery'] for item in states.values()), 'component warranty split missing')
    require(connection.execute("SELECT count(*) FROM error_codes WHERE code='E07'").fetchone()[0] == 4, 'E07 missing')
    require(bool(connection.execute('SELECT code FROM error_codes GROUP BY code HAVING count(DISTINCT title)>1').fetchall()),
            'model-specific error meaning missing')
    require(connection.execute('SELECT count(*) FROM consumables WHERE stock=0').fetchone()[0] > 0, 'no out-of-stock item')
    require(connection.execute('SELECT count(*) FROM consumables WHERE max_per_order IS NOT NULL').fetchone()[0] > 0,
            'no purchase limit')
    today = date.fromisoformat(business_date)
    for region, in connection.execute('SELECT DISTINCT region FROM users'):
        for offset in range(1, 15):
            day = (today + timedelta(days=offset)).isoformat()
            available, full = connection.execute(
                'SELECT sum(booked<capacity),sum(booked=capacity) FROM service_slots WHERE region=? AND start_at LIKE ?',
                (region, day + '%')).fetchone()
            require(bool(available) and bool(full), f'slot coverage missing: {region}/{day}')
    require(not connection.execute('PRAGMA foreign_key_check').fetchall(), 'foreign key mismatch')
    for table in ('pending_actions', 'audit_log'):
        require(connection.execute(f'SELECT count(*) FROM {table}').fetchone()[0] == 0, f'{table} seed must be empty')
    return evidence


def seed_database(connection, *, business_date, csv_path=None):
    today = date.fromisoformat(business_date)
    rng = random.Random(RANDOM_SEED)
    rows = read_csv(csv_path)
    for model, family, components, whole, battery in MODEL_SPECS:
        connection.execute('INSERT INTO models VALUES (?,?,?,?,?)',
                           (model, family, family, '2023-01-01', json.dumps(sorted(components), separators=(',', ':'))))
        for component, months in (('whole_machine', whole), ('battery', battery), ('consumables', 0)):
            connection.execute('INSERT INTO warranty_policies VALUES (?,?,?,?)',
                               (model, component, months, '人为损坏、进液、未经许可拆修；耗材正常磨损不在保。'))
        errors = sorted((*COMMON_ERRORS, ('E07', *E07_ERRORS[model])))
        connection.executemany('INSERT INTO error_codes VALUES (?,?,?,?,?,?,?)',
                               [(model, code, title, severity, fix, visit,
                                 f'errors.txt#{model}-{code}' if code == 'E07' else f'errors.txt#{code}')
                                for code, title, severity, fix, visit in errors])
    devices = []
    old_dates = ('2024-07-12', '2024-07-12', '2024-08-20', '2023-10-05', '2023-11-08',
                 '2024-10-02', '2024-07-12', '2024-07-12', '2023-09-01', '2023-12-03')
    for index, user_number in enumerate(range(1001, 1051)):
        user = str(user_number)
        region = REGIONS[index % len(REGIONS)]
        connection.execute('INSERT INTO users VALUES (?,?,?)', (user, region, '2023-01-01T00:00:00+08:00'))
        count = 2 if user_number > 1010 and user_number % 5 == 0 else 1
        for number in range(1, count + 1):
            model = CSV_MODEL_CODES.get(user, MODEL_SPECS[(index + number - 1) % 4][0])
            purchase = old_dates[index] if index < 10 else (today - timedelta(days=rng.randint(180, 1100))).isoformat()
            device = f'D-{user}-{number:02d}'
            connection.execute('INSERT INTO devices VALUES (?,?,?,?,?,?)',
                               (device, user, model, f'SYN-{user}-{number:02d}-0000', purchase, '1.0.0'))
            devices.append((device, user, model, region))
    for sku, name, kind, price, stock, limit, compatible in CONSUMABLE_SPECS:
        connection.execute('INSERT INTO consumables VALUES (?,?,?,?,?,?)', (sku, name, kind, price, stock, limit))
        connection.executemany('INSERT INTO consumable_models VALUES (?,?)', [(sku, model) for model in compatible])
    for index, (device, user, model, region) in enumerate(devices[:18], 1):
        status = ('completed', 'processing', 'cancelled')[(index - 1) % 3]
        connection.execute('INSERT INTO orders VALUES (?,?,?,?,?,?,?,?,NULL)',
                           (f'O-{index:04d}', user, device, model, 'SKU-FILTER', 1, 3900, status))
    ticket_number = 0
    appointment_number = 0

    def appointment(slot, device_row, status):
        nonlocal ticket_number, appointment_number
        device, user, model, _ = device_row
        ticket_number += 1
        appointment_number += 1
        ticket = f'T-{ticket_number:04d}'
        connection.execute('INSERT INTO tickets VALUES (?,?,?,?,?,?,?,?,NULL)',
                           (ticket, user, device, model, 'E07', '设备显示 E07，申请检查。',
                            '已记录设备状态，按预约安排处理。', status))
        connection.execute('INSERT INTO appointments VALUES (?,?,?,?,?,NULL)',
                           (f'A-{appointment_number:04d}', ticket, slot, user, status))

    for region in REGIONS:
        regional_devices = [row for row in devices if row[3] == region]
        for offset in range(1, 15):
            day = (today + timedelta(days=offset)).isoformat()
            for period, hour in enumerate((9, 13, 16), 1):
                slot = f'S-{region}-{day.replace("-", "")}-{period}'
                booked = 2 if period == 1 else (1 if period == 2 and offset % 3 == 0 else 0)
                connection.execute('INSERT INTO service_slots VALUES (?,?,?,?,?,?)',
                                   (slot, region, f'{day}T{hour:02d}:00:00+08:00', f'{day}T{hour+2:02d}:00:00+08:00', 2, booked))
                for index in range(booked):
                    appointment(slot, regional_devices[(offset * 2 + index) % len(regional_devices)], 'scheduled')
        for status in ('completed', 'cancelled'):
            day = (today - timedelta(days=3 if status == 'completed' else 2)).isoformat()
            slot = f'S-{region}-{day.replace("-", "")}-H'
            connection.execute('INSERT INTO service_slots VALUES (?,?,?,?,?,?)',
                               (slot, region, f'{day}T09:00:00+08:00', f'{day}T11:00:00+08:00', 2, int(status == 'completed')))
            appointment(slot, regional_devices[0], status)
    for device, user, model, region in devices[:10]:
        ticket_number += 1
        connection.execute('INSERT INTO tickets VALUES (?,?,?,?,?,?,?,?,NULL)',
                           (f'T-{ticket_number:04d}', user, device, model, 'E06', '回充接触需要检查。',
                            '已受理，等待安排后续检查。', 'processing'))
    daily_targets = {}
    for row in rows:
        match = re.search(r'日均清扫\s*[:：]\s*(\d+)㎡', row['清洁效率'])
        if match:
            daily_targets[(row['用户ID'], row['时间'])] = int(match[1])
    for device, user, model, region in devices:
        first = date(2025, 1, 1) if user in CSV_MODEL_CODES else today - timedelta(days=30)
        last = date(2025, 12, 31) if user in CSV_MODEL_CODES else today - timedelta(days=1)
        day = first
        while day <= last:
            month = day.strftime('%Y-%m')
            target = daily_targets.get((user, month))
            # Integer, zero-sum paired variation gives an exact monthly mean.
            days = calendar.monthrange(day.year, day.month)[1]
            if target is not None:
                delta = 0 if day.day == days and days % 2 else (2 if day.day % 2 else -2)
                area = float(target + delta)
            else:
                area = float(rng.randint(25, 95))
            duration = int(area) + rng.randint(8, 25)
            events = int(rng.random() < 0.04)
            connection.execute('INSERT INTO telemetry_daily VALUES (?,?,?,?,?)',
                               (device, day.isoformat(), area, duration, events))
            day += timedelta(days=1)
    assert_consistency(connection, business_date=business_date, csv_path=csv_path)
