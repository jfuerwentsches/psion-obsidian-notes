import shutil
from pathlib import Path

from psionsync.cli import main

FIXTURES = Path(__file__).parent / "fixtures" / "vault"


def run(tmp_path, *args):
    return main(["--vault", str(tmp_path / "vault"), "--state-dir", str(tmp_path / "state"),
                 "--fake-device", str(tmp_path / "dev"), *args])


def test_status_sync_and_backup_with_fake_device(tmp_path, capsys):
    shutil.copytree(FIXTURES, tmp_path / "vault")
    assert run(tmp_path, "status") == 0
    out = capsys.readouterr().out
    assert "push           Willkommen.md" in out
    assert "übersprungen   Fragen/Was ist das?.md" in out
    assert "Dry-Run" in out
    assert not (tmp_path / "dev/C/Vault/Willkommen.md").exists()

    assert run(tmp_path, "sync", "--apply") == 0
    assert (tmp_path / "dev/C/Vault/Willkommen.md").read_bytes() == b"Willkommen bei PsiVault!\r\nZweite Zeile.\r\n"
    assert run(tmp_path, "sync") == 0
    assert "0 Übertragung(en)" in capsys.readouterr().out

    assert run(tmp_path, "backup", str(tmp_path / "bak")) == 0
    assert (tmp_path / "bak/C/Vault/Willkommen.md").exists()
    assert (tmp_path / "bak/manifest.json").exists()


def test_missing_vault(tmp_path, capsys):
    assert run(tmp_path, "status") == 2


def test_pending_counts_local_changes_without_device(tmp_path, capsys):
    import json
    shutil.copytree(FIXTURES, tmp_path / "vault")
    assert run(tmp_path, "sync", "--apply") == 0
    (tmp_path / "vault/Willkommen.md").write_text("neu\n")
    (tmp_path / "vault/Extra.md").write_text("x\n")
    (tmp_path / "vault/Projekte/Sub/Tief.md").unlink()
    capsys.readouterr()
    assert main(["--vault", str(tmp_path / "vault"), "--state-dir", str(tmp_path / "state"), "pending", "--json"]) == 0
    info = json.loads(capsys.readouterr().out)
    assert info["changed"] == ["Willkommen.md"] and info["new"] == ["Extra.md"] and info["deleted"] == ["Projekte/Sub/Tief.md"]
    assert info["pending"] == 3 and info["tracked"] == 4 and info["last_sync"]
