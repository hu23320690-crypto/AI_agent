"""Per-call SQLite access and injected service session configuration."""
from contextlib import contextmanager
from pathlib import Path
import sqlite3

from service_desk.config import ROOT, load_config


def session_context(user_id, session_id, db_path=None):
    config = load_config()
    return {'toolset': 'service', 'user_id': user_id, 'session_id': session_id,
            'business_date': config['business_date'], 'service_config': config,
            'service_db_path': Path(db_path) if db_path is not None else ROOT / config['db_path']}


@contextmanager
def connection_for(context, *, readonly=True):
    """ro never creates a file; rw permits proposals but never initializes a DB."""
    config = context.get('service_config') or load_config()
    path = Path(context.get('service_db_path') or ROOT / config['db_path']).resolve()
    mode = 'ro' if readonly else 'rw'
    connection = sqlite3.connect(path.as_uri() + '?mode=' + mode, uri=True, timeout=2)
    connection.row_factory = sqlite3.Row
    try:
        connection.execute('PRAGMA foreign_keys=ON')
        connection.execute('BEGIN' if readonly else 'BEGIN IMMEDIATE')
        run = context.get('run_context')
        if run is not None:
            run.check()
        yield connection
    finally:
        # Each caller owns commit. Failed checks and read transactions roll back.
        connection.close()
