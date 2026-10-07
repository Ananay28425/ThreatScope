"""Prepare an isolated agent ledger and credential, then drop root privileges."""
import os
import stat
import sys
import tempfile
from pathlib import Path

APP_UID = 10001
APP_GID = 10001
STATE_DIR = Path("/state")
RUNTIME_DIR = Path("/run")


def private_credential(arguments: list[str]) -> list[str]:
    """Copy a host-mounted key into the container; bind-mount ownership varies by OS."""
    if arguments.count("--credentials") != 1:
        raise RuntimeError("agent_credential_path_required")
    index = arguments.index("--credentials") + 1
    if index >= len(arguments):
        raise RuntimeError("agent_credential_path_required")
    source = Path(arguments[index])
    descriptor = os.open(source, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    with os.fdopen(descriptor, "rb") as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise RuntimeError("invalid_agent_credential_file")
        content = stream.read(8193)
    if not 0 < len(content) <= 8192:
        raise RuntimeError("invalid_agent_credential_size")

    directory = Path(tempfile.mkdtemp(prefix="threatscope-agent-", dir=RUNTIME_DIR))
    target = directory / "node.json"
    descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(content)
    os.chown(directory, APP_UID, APP_GID)
    os.chmod(directory, 0o700)
    os.chown(target, APP_UID, APP_GID)
    os.chmod(target, 0o600)
    arguments[index] = str(target)
    return arguments


def main() -> None:
    if os.geteuid() != 0:
        raise RuntimeError("agent_startup_requires_root")

    state = STATE_DIR
    os.chown(state, APP_UID, APP_GID)
    os.chmod(state, 0o700)
    for name in ("ledger.db", "ledger.db-wal", "ledger.db-shm"):
        path = state / name
        try:
            mode = path.lstat().st_mode
        except FileNotFoundError:
            continue
        if not stat.S_ISREG(mode):
            raise RuntimeError("invalid_agent_state_file")
        os.chown(path, APP_UID, APP_GID, follow_symlinks=False)
        os.chmod(path, 0o600)

    arguments = private_credential(sys.argv[1:])
    os.setgroups([])
    os.setgid(APP_GID)
    os.setuid(APP_UID)
    os.execv(sys.executable, [sys.executable, "-m", "node_simulator.agent", *arguments])


if __name__ == "__main__":
    main()
