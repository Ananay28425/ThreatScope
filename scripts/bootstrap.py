"""Generate private Compose settings without replacing existing credentials."""
import os
import secrets
from pathlib import Path


def main():
    root = Path(__file__).resolve().parents[1]
    (root / '.runtime' / 'private').mkdir(parents=True, exist_ok=True)
    with (root / '.env').open('x', encoding='utf-8') as stream:
        stream.write(f'POSTGRES_PASSWORD={secrets.token_urlsafe(32)}\nLLM_ENABLED=false\n')
        stream.write(f'APP_DATABASE_PASSWORD={secrets.token_urlsafe(32)}\n')
        stream.write(f'LOCAL_UID={os.getuid() if hasattr(os, "getuid") else 10001}\n')
        stream.write(f'LOCAL_GID={os.getgid() if hasattr(os, "getgid") else 10001}\n')
    print('Private settings created. Start migrations, then enroll the demo organizations.')


if __name__ == '__main__':
    main()
