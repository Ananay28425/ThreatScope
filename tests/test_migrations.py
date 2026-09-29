"""A fresh migration preserves and quarantines legacy evidence instead of trusting its identity."""
import os
import sqlite3
import subprocess
import sys


def test_migration_preserves_legacy_rows(tmp_path):
    path = tmp_path / 'legacy.db'
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE signals(id TEXT PRIMARY KEY, legacy_value TEXT)')
        db.execute("INSERT INTO signals VALUES ('old-1','unverified-source')")
    result = subprocess.run([sys.executable, '-m', 'alembic', 'upgrade', 'head'],
        env=dict(os.environ, DATABASE_URL=f'sqlite+aiosqlite:///{path}', APP_ENV='test'),
        capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr
    with sqlite3.connect(path) as db:
        assert db.execute('SELECT COUNT(*) FROM signals').fetchone()[0] == 1
        assert db.execute('SELECT research_eligible FROM ts_legacy_archive').fetchone()[0] == 0
        assert db.execute('SELECT COUNT(*) FROM ts_signals').fetchone()[0] == 0
