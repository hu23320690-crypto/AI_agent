"""Offline primitives shared by the service runner, scorer and review tools."""
import hashlib
import json
import re
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def result_sha256(row):
    return hashlib.sha256(canonical(row).encode('utf-8')).hexdigest()


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_rows(path):
    return [json.loads(line) for line in Path(path).read_text(encoding='utf-8-sig').splitlines() if line.strip()]


def dump(path, value):
    path = Path(path)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(canonical(value) + '\n', encoding='utf-8')
    temporary.replace(path)


def write_rows(path, rows):
    Path(path).write_text(''.join(canonical(row) + '\n' for row in rows), encoding='utf-8')


def parse_content(content):
    try:
        return json.loads(content) if isinstance(content, str) else content
    except (ValueError, TypeError):
        return content


def matches(expected, actual):
    """Strict normalized card args; only the two frozen exceptions are special."""
    if expected.get('tool') != actual.get('tool'):
        return False
    wanted, got = dict(expected.get('args', {})), dict(actual.get('args', {}))
    description = got.pop('description', None)
    if 'description' in wanted:
        got['description'] = description
    elif expected.get('tool') == 'propose_service_visit':
        if not isinstance(description, str):
            return False
        text = unicodedata.normalize('NFC', description)
        if any(unicodedata.normalize('NFC', word) not in text
               for word in expected.get('description_must_include', [])):
            return False
    elif description is not None:
        return False
    if 'slot_id_in' in expected:
        if got.get('slot_id') not in expected['slot_id_in']:
            return False
        got.pop('slot_id', None)
        wanted.pop('slot_id', None)
    return canonical(wanted) == canonical(got)


def forbidden_match(rule, actual):
    if isinstance(rule, str):
        return actual.get('tool') == rule
    got = actual.get('args', {})
    return (actual.get('tool') == rule.get('tool') and
            all(key in got and canonical(got[key]) == canonical(value)
                for key, value in rule.get('args', {}).items()))


def distinct_proposals(proposals):
    seen, result = set(), []
    for item in proposals:
        action = item.get('action_id')
        if action and action in seen:
            continue
        if action:
            seen.add(action)
        result.append(item)
    return result


def match_pairs(expected, actual):
    """Maximum one-to-one matching, including overlapping accepted slot sets."""
    owners = {}
    def assign(index, visited):
        for j, item in enumerate(actual):
            if j in visited or not matches(expected[index], item):
                continue
            visited.add(j)
            if j not in owners or assign(owners[j], visited):
                owners[j] = index
                return True
        return False
    for i in range(len(expected)):
        assign(i, set())
    return sorted((i, j) for j, i in owners.items())


def proposal_ref(value):
    match = re.fullmatch(r't([1-9][0-9]*)\.p([0-9]+)', value)
    if not match:
        raise ValueError('Invalid proposal_ref')
    return int(match[1]), int(match[2])


def database_snapshot(path):
    import sqlite3
    from contextlib import closing
    with closing(sqlite3.connect(Path(path).resolve().as_uri() + '?mode=ro', uri=True)) as connection:
        connection.row_factory = sqlite3.Row
        tables = [row[0] for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
        return {name: [dict(row) for row in connection.execute('SELECT * FROM "' + name.replace('"', '""') + '"')]
                for name in tables}
