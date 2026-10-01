"""Agent startup preserves SQLite and isolates keys before dropping root."""
import os
import sys
from pathlib import Path

import pytest

from node_simulator import container_entrypoint


def test_agent_startup_reowns_existing_ledger_then_drops_privileges(tmp_path, monkeypatch):
    ledger = tmp_path / "ledger.db"
    ledger.write_bytes(b"existing-state")
    mounted_key = tmp_path / "mounted-node.json"
    mounted_key.write_bytes(b'{"api_key":"private"}')
    runtime = tmp_path / "run"
    runtime.mkdir()
    monkeypatch.setattr(container_entrypoint, "STATE_DIR", tmp_path)
    monkeypatch.setattr(container_entrypoint, "RUNTIME_DIR", runtime)
    monkeypatch.setattr(sys, "argv", ["container_entrypoint", "--credentials", str(mounted_key),
                                  "--state", str(ledger)])
    monkeypatch.setattr(os, "geteuid", lambda: 0, raising=False)
    calls = []
    monkeypatch.setattr(os, "chown", lambda *args, **kwargs: calls.append(("chown", args)), raising=False)
    monkeypatch.setattr(os, "chmod", lambda *args: calls.append(("chmod", args)))
    monkeypatch.setattr(os, "setgroups", lambda groups: calls.append(("setgroups", groups)), raising=False)
    monkeypatch.setattr(os, "setgid", lambda gid: calls.append(("setgid", gid)), raising=False)
    monkeypatch.setattr(os, "setuid", lambda uid: calls.append(("setuid", uid)), raising=False)

    def execv(executable, argv):
        calls.append(("execv", argv))
        raise SystemExit(0)

    monkeypatch.setattr(os, "execv", execv)
    with pytest.raises(SystemExit) as result:
        container_entrypoint.main()
    assert result.value.code == 0
    assert ledger.read_bytes() == b"existing-state"
    assert any(call == ("chown", (ledger, 10001, 10001)) for call in calls)
    arguments = calls[-1][1]
    copied_key = Path(arguments[arguments.index("--credentials") + 1])
    assert copied_key != mounted_key
    assert copied_key.read_bytes() == mounted_key.read_bytes()
    assert copied_key.parent.parent == runtime
    assert [name for name, _ in calls[-4:]] == ["setgroups", "setgid", "setuid", "execv"]


def test_agent_startup_requires_root_for_private_copy(tmp_path, monkeypatch):
    monkeypatch.setattr(container_entrypoint, "STATE_DIR", tmp_path)
    monkeypatch.setattr(os, "geteuid", lambda: 10001, raising=False)
    with pytest.raises(RuntimeError, match="agent_startup_requires_root"):
        container_entrypoint.main()


def test_oversized_mount_is_rejected_without_private_copy(tmp_path, monkeypatch):
    mounted_key = tmp_path / "mounted-node.json"
    mounted_key.write_bytes(b"x" * 8193)
    runtime = tmp_path / "run"
    runtime.mkdir()
    monkeypatch.setattr(container_entrypoint, "RUNTIME_DIR", runtime)
    with pytest.raises(RuntimeError, match="invalid_agent_credential_size"):
        container_entrypoint.private_credential(["--credentials", str(mounted_key)])
    assert list(runtime.iterdir()) == []
