"""Run the ThreatScope evaluation on loopback without Docker or PostgreSQL."""
import argparse
import asyncio
import os
import shutil
import subprocess
from contextlib import contextmanager
from pathlib import Path

import uvicorn
from alembic import command
from alembic.config import Config
from pydantic import ValidationError

from backend.app.admin import seed_demo
from backend.app.config import Settings
from backend.app.database import Database
from backend.app.replay import LocalModel, Replay
from backend.main import create_app
from node_simulator.replay_data import generate

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / ".runtime" / "native-demo"


@contextmanager
def demo_lock(directory):
    """The SQLite coordinator has exactly one writer process."""
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / "server.lock").open("a+b") as lock:
        lock.seek(0)
        try:
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            raise SystemExit("This demo directory is already in use. Stop the other ThreatScope process.") from None
        yield


async def prepare(settings, directory):
    db = Database(settings)
    try:
        migration = Config(str(ROOT / "alembic.ini"))
        migration.set_main_option("script_location", str(ROOT / "migrations").replace("%", "%%"))

        def upgrade(connection):
            migration.attributes["connection"] = connection
            command.upgrade(migration, "head")

        async with db.engine.begin() as connection:
            await connection.run_sync(upgrade)
    finally:
        await db.close()
    credentials = directory / "demo-credentials.json"
    if not credentials.exists():
        await seed_demo(credentials, settings)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", default=15173, type=int, metavar="PORT")
    parser.add_argument("--state-dir", type=Path, default=STATE, help="Use a separate directory for a clean demo.")
    parser.add_argument("--no-build", action="store_true", help="Reuse an existing frontend build.")
    parser.add_argument("--llama-server", type=Path, help="Path to a local llama-server executable.")
    parser.add_argument("--model", type=Path, help="Path to a local GGUF model.")
    parser.add_argument("--model-port", type=int, default=18081)
    parser.add_argument("--logs-dir", type=Path, help="Use existing Orion, Lyra and Vega replay CSVs.")
    args = parser.parse_args()
    if bool(args.llama_server) != bool(args.model):
        parser.error("pass both --llama-server and --model to enable local inference")
    if args.llama_server and not (args.llama_server.is_file() and args.model.is_file()):
        parser.error("both the llama-server executable and GGUF model must exist")
    if args.model_port == args.port or not 1024 <= args.model_port <= 65535:
        parser.error("--model-port must be distinct from --port and between 1024 and 65535")
    if not 1024 <= args.port <= 65535:
        parser.error("--port must be between 1024 and 65535")
    directory = args.state_dir.resolve()
    origin = f"http://127.0.0.1:{args.port}"
    try:
        settings = Settings(
            _env_file=ROOT / ".env",
            app_env="demo", demo_access=True, cookie_secure=False, allowed_origins=origin,
            database_url="sqlite+aiosqlite:///" + (directory / "coordinator.db").as_posix(),
        )
    except ValidationError:
        raise SystemExit("Invalid inference settings. Check .env.example; hosted inference needs HTTPS, a model and an API key.") from None
    frontend = ROOT / "frontend"
    with demo_lock(directory):
        if not args.no_build:
            npm = shutil.which("npm.cmd" if os.name == "nt" else "npm")
            if not npm:
                raise SystemExit("Install Node.js and npm, then run npm --prefix frontend ci.")
            if any(not (frontend / "node_modules" / dep).exists() for dep in ("vite", "echarts")):
                subprocess.run([npm, "ci"], cwd=frontend, check=True)
            subprocess.run([npm, "run", "build"], cwd=frontend, check=True)
        if not (frontend / "dist" / "index.html").is_file():
            raise SystemExit("Frontend build not found. Run the launcher without --no-build.")
        asyncio.run(prepare(settings, directory))
        logs = args.logs_dir or directory / "replay-logs"
        if not args.logs_dir:
            generate(logs)
        model = LocalModel(args.llama_server.resolve(), args.model.resolve(), args.model_port, directory) if args.model else None
        replay = Replay(directory, logs, model)
        print(f"Dashboard: {origin}  |  Synthetic demo  |  "
              f"Inference: {'hosted API' if settings.llm_enabled else 'checked template'}", flush=True)
        uvicorn.run(create_app(settings, demo_workers=True, frontend_dir=frontend / "dist", replay=replay),
                    host="127.0.0.1", port=args.port, proxy_headers=False)


if __name__ == "__main__":
    main()
