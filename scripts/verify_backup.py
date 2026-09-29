"""Back up the isolated demo database and verify restoration into a newly named database."""
import hashlib
import json
import os
import subprocess
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]


def main():
    config = json.loads((ROOT / '.runtime/local-config.json').read_text())
    binaries = ROOT / '.runtime/postgres/pgsql/bin'
    env = dict(os.environ, PGPASSWORD=config['postgres_password'])
    common = ['-h', '127.0.0.1', '-p', '55432', '-U', 'threatscope']
    restored = 'restore_test_' + uuid4().hex[:12]
    dump = ROOT / '.runtime/verified-backup.dump'
    def run(tool, args, capture=False):
        return subprocess.run([str(binaries / (tool + '.exe')), *common, *args], env=env,
                              check=True, capture_output=capture, text=capture)
    run('pg_dump', ['-d', 'threatscope', '-Fc', '-f', str(dump)])
    run('createdb', [restored])
    run('pg_restore', ['--exit-on-error', '-d', restored, str(dump)])
    query = "SELECT (SELECT count(*) FROM ts_signals), (SELECT count(*) FROM ts_evidence), (SELECT count(*) FROM ts_evidence_history), (SELECT count(*) FROM ts_notifications), (SELECT count(*) FROM ts_credentials)"
    source = run('psql', ['-d', 'threatscope', '-tAc', query], True).stdout.strip()
    target = run('psql', ['-d', restored, '-tAc', query], True).stdout.strip()
    assert source == target, 'restored_counts_mismatch'
    report = {'restored_database': restored, 'counts_match': True, 'counts': source.split('|'),
              'tables': ['signals', 'evidence', 'evidence_history', 'notifications', 'credentials'],
              'dump_sha256': hashlib.sha256(dump.read_bytes()).hexdigest()}
    (ROOT / 'research/results/backup-verification.json').write_text(json.dumps(report, indent=2))
    print('Backup restored into a separate database; five table counts match.')


if __name__ == '__main__':
    main()
