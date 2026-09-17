from pathlib import Path

import pytest

from psionsync.sync.state import FileState, State


def entry(**kw):
    base = dict(vault_hash="v1", vault_mtime="2026-09-17T10:00:00", device_hash="d1", device_size=3,
                device_mtime="2026-09-17T12:00:00", translit_version=1)
    base.update(kw)
    return FileState(**base)


def test_roundtrip(tmp_path: Path):
    s = State(tmp_path / "st")
    s.set("Entwürfe/Gemüse.md", entry())
    s.last_sync = "2026-09-17T10:00:00"
    s.save()
    s2 = State.load(tmp_path / "st")
    assert s2.get("Entwürfe/Gemüse.md") == entry()
    assert s2.last_sync == "2026-09-17T10:00:00"
    assert s2.get("fehlt.md") is None


def test_missing_state_is_empty(tmp_path: Path):
    assert State.load(tmp_path / "nix").files == {}


def test_unknown_version_rejected(tmp_path: Path):
    d = tmp_path / "st"; d.mkdir()
    (d / "state.json").write_text('{"version": 99, "files": {}}')
    with pytest.raises(ValueError):
        State.load(d)


def test_snapshot_written_read_and_garbage_collected(tmp_path: Path):
    s = State(tmp_path / "st")
    s.write_snapshot("v1", "A → B\n")
    s.write_snapshot("v_alt", "alt\n")
    s.set("a.md", entry(vault_hash="v1", has_snapshot=True))
    s.set("b.md", entry(vault_hash="v2", has_snapshot=False))
    s.save()
    assert s.read_snapshot("a.md") == "A → B\n"
    assert s.read_snapshot("b.md") is None
    assert not s.snapshot_path("v_alt").exists()
    assert s.snapshot_path("v1").exists()
