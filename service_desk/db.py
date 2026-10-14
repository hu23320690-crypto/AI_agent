"""SQLite initialization and version-independent canonical content hashing."""
import hashlib
from contextlib import closing
import json
import os
import shutil
from pathlib import Path
import sqlite3
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def canonical_json(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False)


def content_sha256(path):
    """Hash table content, excluding SQLite internals, ordered by full primary key.

    Schema, triggers and file bytes are deliberately not part of this digest.
    Empty tables are included; composite primary keys keep their declared order.
    """
    digest = hashlib.sha256()
    with closing(sqlite3.connect(Path(path).resolve().as_uri() + '?mode=ro', uri=True)) as connection:
        connection.row_factory = sqlite3.Row
        with connection:
            connection.execute('BEGIN')
            tables = [row[0] for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
            content = {}
            for table in tables:
                quoted = '"' + table.replace('"', '""') + '"'
                columns = connection.execute(f'PRAGMA table_info({quoted})').fetchall()
                keys = [row['name'] for row in sorted(columns, key=lambda row: row['pk']) if row['pk']]
                if not keys:
                    raise ValueError(f'table {table} has no primary key')
                order = ','.join('"' + key.replace('"', '""') + '"' for key in keys)
                content[table] = [dict(row) for row in connection.execute(f'SELECT * FROM {quoted} ORDER BY {order}')]
            digest.update(canonical_json(content).encode('utf-8'))
    return digest.hexdigest()


def init_db(path, *, force=False, business_date=None, csv_path=None):
    """Build and validate a complete seed before publishing it at path.

    Default publication uses exclusive creation, so racing initializers cannot
    overwrite an existing database. --force explicitly permits atomic replacement.
    """
    from service_desk.seed import seed_database
    if business_date is None:
        from service_desk.config import load_config
        business_date = load_config()['business_date']
    path = Path(path)
    if path.exists() and not force:
        raise FileExistsError('database exists; use --force to replace it')
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary_name = tempfile.mkstemp(prefix='.service-', suffix='.db', dir=path.parent)
    os.close(handle)
    temporary = Path(temporary_name)
    try:
        connection = sqlite3.connect(temporary)
        try:
            connection.executescript((ROOT / 'service_desk/schema.sql').read_text(encoding='utf-8'))
            with connection:
                seed_database(connection, business_date=business_date, csv_path=csv_path)
        finally:
            connection.close()
        if force:
            os.replace(temporary, path)
        else:
            with path.open('xb') as destination:
                try:
                    with temporary.open('rb') as source:
                        shutil.copyfileobj(source, destination)
                except BaseException:
                    destination.close()
                    path.unlink(missing_ok=True)
                    raise
    finally:
        temporary.unlink(missing_ok=True)
    return path
