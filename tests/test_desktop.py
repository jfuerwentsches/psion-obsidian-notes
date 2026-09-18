import argparse
import json
import shutil
from pathlib import Path

from psionsync.desktop import lock, main, save_result, status, sync


def environment(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "Notiz.md").write_text("Hallo\n")
    return argparse.Namespace(vault=vault, state_dir=tmp_path / "state", fake_device=tmp_path / "device")


def test_offline_status_then_sync(tmp_path):
    args = environment(tmp_path)
    assert status(args.vault, args.state_dir)["text"] == "Psion ↑1"
    assert not args.fake_device.exists()
    assert sync(args) == 0
    assert (args.fake_device / "C/Vault/Notiz.md").read_bytes() == b"Hallo\r\n"
    data = status(args.vault, args.state_dir)
    assert data["text"] == "Psion ✓"
    assert data["status"] == "success"
    (args.vault / "Notiz.md").write_text("Geändert\n")
    assert status(args.vault, args.state_dir)["text"] == "Psion ↑1"


def test_double_start_and_stale_running_result(tmp_path):
    args = environment(tmp_path)
    handle = lock(args.state_dir)
    try:
        assert status(args.vault, args.state_dir)["status"] == "running"
        assert sync(args) == 1
        assert not args.fake_device.exists()
    finally:
        handle.close()
    save_result(args.state_dir, "running", "Sync läuft")
    assert status(args.vault, args.state_dir)["status"] == "error"
    assert sync(args) == 0


def test_failed_sync_persists_error_and_releases_lock(tmp_path):
    args = environment(tmp_path)
    shutil.rmtree(args.vault)
    assert sync(args) == 1
    result = json.loads((args.state_dir / "desktop-result.json").read_text())
    assert result["status"] == "error"
    handle = lock(args.state_dir)
    assert handle is not None
    handle.close()


def test_corrupt_state_returns_visible_error(tmp_path, capsys):
    args = environment(tmp_path)
    args.state_dir.mkdir()
    (args.state_dir / "state.json").write_text("broken")
    assert main(["--vault", str(args.vault), "--state-dir", str(args.state_dir), "status"]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "error"


def test_skipped_notes_are_warning(tmp_path):
    args = environment(tmp_path)
    (args.vault / "Frage?.md").write_text("Nicht übertragbar\n")
    assert sync(args) == 0
    assert status(args.vault, args.state_dir)["status"] == "warning"


def test_disconnected_device_keeps_local_note_and_reports_error(tmp_path, monkeypatch):
    from psionsync.transport.base import TransportError
    args = environment(tmp_path)

    from contextlib import contextmanager

    @contextmanager
    def disconnected(_args):
        raise TransportError("Keine Verbindung")
        yield

    monkeypatch.setattr("psionsync.desktop.connect", disconnected)
    assert sync(args) == 1
    assert (args.vault / "Notiz.md").read_text() == "Hallo\n"
    data = status(args.vault, args.state_dir)
    assert data["status"] == "error"
    assert "Keine Verbindung" in data["tooltip"]
