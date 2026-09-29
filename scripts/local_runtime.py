"""Prepare an isolated Windows PostgreSQL cluster and private runtime configuration."""
import json
import os
import secrets
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / '.runtime'


def main():
    """Initialize only a new task-owned cluster; never modify an existing system database."""
    config_file = RUNTIME / 'local-config.json'
    if config_file.exists():
        config = json.loads(config_file.read_text())
    else:
        config = {'postgres_password': secrets.token_urlsafe(32), 'llm_api_key': secrets.token_urlsafe(32)}
        config_file.write_text(json.dumps(config), encoding='utf-8')
    binaries = RUNTIME / 'postgres' / 'pgsql' / 'bin'
    data = RUNTIME / 'pgdata'
    password_file = RUNTIME / 'pg-password.secret'
    password_file.write_text(config['postgres_password'], encoding='utf-8')
    if not (data / 'PG_VERSION').exists():
        subprocess.run([str(binaries / 'initdb.exe'), '-D', str(data), '-U', 'threatscope',
                        '--pwfile', str(password_file), '--auth=scram-sha-256', '--encoding=UTF8',
                        '--locale=C'], check=True)
        with (data / 'postgresql.conf').open('a') as stream:
            stream.write("\nlisten_addresses = '127.0.0.1'\nport = 55432\nmax_connections = 40\n")
    status = subprocess.run([str(binaries / 'pg_ctl.exe'), '-D', str(data), 'status'], capture_output=True)
    if status.returncode:
        subprocess.run([str(binaries / 'pg_ctl.exe'), '-D', str(data), '-l', str(RUNTIME / 'postgres.log'),
                        '-w', 'start'], check=True)
    env = dict(os.environ, PGPASSWORD=config['postgres_password'])
    for database in ('threatscope', 'threatscope_test'):
        exists = subprocess.run([str(binaries / 'psql.exe'), '-h', '127.0.0.1', '-p', '55432', '-U',
                                 'threatscope', '-d', 'postgres', '-tAc',
                                 f"SELECT 1 FROM pg_database WHERE datname='{database}'"],
                                env=env, check=True, capture_output=True, text=True)
        if exists.stdout.strip() != '1':
            subprocess.run([str(binaries / 'createdb.exe'), '-h', '127.0.0.1', '-p', '55432',
                            '-U', 'threatscope', database], env=env, check=True)
    config['database_url'] = f"postgresql+asyncpg://threatscope:{config['postgres_password']}@127.0.0.1:55432/threatscope"
    config_file.write_text(json.dumps(config), encoding='utf-8')
    (RUNTIME / 'llama-key.secret').write_text(config['llm_api_key'], encoding='utf-8')
    print('Isolated PostgreSQL ready on loopback port 55432. Private settings remain in .runtime.')


if __name__ == '__main__':
    main()
