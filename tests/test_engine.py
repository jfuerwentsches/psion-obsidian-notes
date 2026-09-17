from datetime import timedelta
from pathlib import Path
import pytest

from psionsync.sync.engine import CLOCK_FILE, GEN_FILE, Action
from psionsync.sync.state import State
from psionsync.transport.base import TransportError

SYNCED = {"Willkommen.md", "Entwürfe/Gemüse-Lasagne.md", "Projekte/Plan.md", "Projekte/Sub/Tief.md"}


def test_initial_sync_pushes_all_and_reports_skipped(env):
    plan, report = env.sync()
    assert env.actions(plan) == {rel: "push" for rel in SYNCED}
    assert [rel for rel, _ in plan.skipped] == ["Fragen/Was ist das?.md"]
    assert "verbotene Zeichen" in plan.skipped[0][1]
    assert env.device_read("Entwürfe/Gemüse-Lasagne.md").startswith("---\r\ntags: [rezept]\r\n".encode("cp1252"))
    assert "Gemüse-Lasagne".encode("cp1252") in env.device_read("Entwürfe/Gemüse-Lasagne.md")
    assert not env.device_path("Bilder/foto.png").exists()
    assert not env.device_path(".obsidian").exists()
    assert env.device_path(CLOCK_FILE).exists()
    assert env.device_path(GEN_FILE).read_bytes() == b"1"
    assert plan.delta == timedelta(hours=2)
    state = State.load(env.state_dir)
    assert set(state.files) == SYNCED
    assert state.get("Projekte/Plan.md").has_snapshot
    assert not state.get("Willkommen.md").has_snapshot


def test_second_sync_is_a_noop_without_downloads(env):
    env.sync()
    env.transport.log.clear()
    plan, _ = env.sync()
    assert plan.transfers == []
    assert not [op for op, _ in env.transport.log if op == "get"]
    # Generation steigt nur, wenn etwas übertragen wurde
    assert env.device_path(GEN_FILE).read_bytes() == b"1"
    assert State.load(env.state_dir).generation == 1


def test_transliteration_on_push(env):
    env.sync()
    data = env.device_read("Projekte/Plan.md").decode("cp1252")
    assert "- Schritt A -> Schritt B\r\n" in data
    assert "- [x] erledigt\r\n" in data
    assert "- (!) Achtung >= 3\r\n" in data
    assert "+-- src\r\n|   +-- main.opl\r\n+-- build.sh\r\n" in data
    assert "Zerowidth und Keycap 1 hier." in data


def test_vault_change_is_pushed(env):
    env.sync()
    env.clock += timedelta(minutes=5)
    env.vault_write("Willkommen.md", "Geändert im Vault\n")
    plan, _ = env.sync()
    assert env.actions(plan) == {"Willkommen.md": "push"}
    assert env.device_read("Willkommen.md") == "Geändert im Vault\r\n".encode("cp1252")


def test_device_change_is_pulled_with_crlf_and_umlauts(env):
    env.sync()
    env.clock += timedelta(minutes=5)
    env.device_write("Willkommen.md", "Auf dem Psion: ä ö ü ß\nZeile 2\n")
    plan, _ = env.sync()
    assert env.actions(plan) == {"Willkommen.md": "pull"}
    assert (env.vault / "Willkommen.md").read_text(encoding="utf-8") == "Auf dem Psion: ä ö ü ß\nZeile 2\n"
    # danach Ruhe
    plan, _ = env.sync()
    assert plan.transfers == []


def test_pull_restores_unicode_only_on_unchanged_lines(env):
    env.sync()
    env.clock += timedelta(minutes=5)
    original = (env.vault / "Projekte/Plan.md").read_text(encoding="utf-8")
    device = env.device_read("Projekte/Plan.md").decode("cp1252").replace("\r\n", "\n")
    edited = device.replace("- [x] erledigt", "- [x] erledigt, geprüft").replace("Zerowidth", "Neuer Text")
    env.device_write("Projekte/Plan.md", edited)
    plan, _ = env.sync()
    assert env.actions(plan) == {"Projekte/Plan.md": "pull"}
    result = (env.vault / "Projekte/Plan.md").read_text(encoding="utf-8")
    assert "- Schritt A → Schritt B\n" in result          # unverändert -> wiederhergestellt
    assert "- ⚠ Achtung ≥ 3\n" in result
    assert "├── src\n│   └── main.opl\n└── build.sh\n" in result
    assert "- [x] erledigt, geprüft\n" in result          # geändert -> bleibt transliteriert
    assert "Neuer Text und Keycap 1 hier.\n" in result
    # Original wurde gesichert, weil Unicode verloren ging
    backups = list((env.state_dir / "unicode-backup").rglob("*.md"))
    assert len(backups) == 1 and backups[0].read_text(encoding="utf-8") == original
    # Snapshot für die nächste Runde vorhanden, und Ruhe danach
    plan, _ = env.sync()
    assert plan.transfers == []


def test_new_file_on_device_is_pulled_into_new_folder(env):
    env.sync()
    env.device_write("Neu/Vom Psion.md", "Hallo\n")
    plan, _ = env.sync()
    assert env.actions(plan) == {"Neu/Vom Psion.md": "pull"}
    assert (env.vault / "Neu/Vom Psion.md").read_text() == "Hallo\n"


def test_new_file_in_vault_creates_device_folders(env):
    env.sync()
    env.vault_write("A/B/C/Tief.md", "x\n")
    plan, _ = env.sync()
    assert env.actions(plan) == {"A/B/C/Tief.md": "push"}
    assert env.device_read("A/B/C/Tief.md") == b"x\r\n"


def test_deleted_in_vault_is_deleted_on_device(env):
    env.sync()
    (env.vault / "Projekte/Sub/Tief.md").unlink()
    plan, _ = env.sync()
    assert env.actions(plan) == {"Projekte/Sub/Tief.md": "rm-psion"}
    assert not env.device_path("Projekte/Sub/Tief.md").exists()
    assert "Projekte/Sub/Tief.md" not in State.load(env.state_dir).files


def test_deleted_on_device_is_deleted_in_vault_with_trash_copy(env):
    env.sync()
    env.device_path("Willkommen.md").unlink()
    plan, _ = env.sync()
    assert env.actions(plan) == {"Willkommen.md": "rm-vault"}
    assert not (env.vault / "Willkommen.md").exists()
    assert list((env.state_dir / "trash").glob("Willkommen.md *.md"))


def test_deleted_on_one_side_changed_on_other_keeps_change(env):
    env.sync()
    env.clock += timedelta(minutes=5)
    env.device_path("Willkommen.md").unlink()
    env.vault_write("Willkommen.md", "Neu im Vault\n")
    (env.vault / "Projekte/Sub/Tief.md").unlink()
    env.device_write("Projekte/Sub/Tief.md", "Neu auf Psion\n")
    plan, _ = env.sync()
    assert env.actions(plan) == {"Willkommen.md": "push", "Projekte/Sub/Tief.md": "pull"}
    assert env.device_read("Willkommen.md") == b"Neu im Vault\r\n"
    assert (env.vault / "Projekte/Sub/Tief.md").read_text() == "Neu auf Psion\n"


def test_conflict_vault_newer_pushes_and_keeps_psion_copy(env):
    env.sync()
    t_device = env.clock + timedelta(minutes=10)
    t_vault = env.clock + timedelta(minutes=30)
    env.device_write("Willkommen.md", "Psion-Fassung\n", when=t_device)
    env.vault_write("Willkommen.md", "Vault-Fassung\n", when=t_vault)
    env.clock += timedelta(hours=1)
    plan, _ = env.sync()
    item = plan.transfers[0]
    assert item.action == Action.CONFLICT_PUSH
    copy = f"Willkommen (Konflikt Psion {t_device:%Y-%m-%d %H%M}).md"
    assert item.conflict_copy == copy
    assert env.device_read("Willkommen.md") == b"Vault-Fassung\r\n"
    assert (env.vault / copy).read_text() == "Psion-Fassung\n"
    # Die Konfliktkopie ist eine normale Notiz und wandert beim nächsten Sync mit
    plan, _ = env.sync()
    assert env.actions(plan) == {copy: "push"}


def test_conflict_psion_newer_pulls_and_keeps_linux_copy(env):
    env.sync()
    t_vault = env.clock + timedelta(minutes=10)
    t_device = env.clock + timedelta(minutes=30)
    env.vault_write("Willkommen.md", "Vault-Fassung\n", when=t_vault)
    env.device_write("Willkommen.md", "Psion-Fassung\n", when=t_device)
    env.clock += timedelta(hours=1)
    plan, _ = env.sync()
    item = plan.transfers[0]
    assert item.action == Action.CONFLICT_PULL
    copy = f"Willkommen (Konflikt Linux {t_vault:%Y-%m-%d %H%M}).md"
    assert item.conflict_copy == copy
    assert (env.vault / "Willkommen.md").read_text() == "Psion-Fassung\n"
    assert (env.vault / copy).read_text() == "Vault-Fassung\n"


def test_conflict_with_equal_times_stays_open(env):
    env.sync()
    t = env.clock + timedelta(minutes=10)
    env.vault_write("Willkommen.md", "Vault-Fassung\n", when=t)
    env.device_write("Willkommen.md", "Psion-Fassung\n", when=t + timedelta(seconds=30))
    env.clock += timedelta(hours=1)
    plan, _ = env.sync()
    item = plan.transfers[0]
    assert item.action == Action.CONFLICT_OPEN
    assert (env.vault / "Willkommen.md").read_text() == "Vault-Fassung\n"
    assert env.device_read("Willkommen.md") == b"Psion-Fassung\r\n"
    assert (env.vault / item.conflict_copy).read_text() == "Psion-Fassung\n"
    # bleibt offen, erzeugt aber keine zweite Kopie
    plan2, _ = env.sync()
    assert env.actions(plan2) == {"Willkommen.md": "konflikt-offen", item.conflict_copy: "push"}
    assert len(list(env.vault.glob("Willkommen (Konflikt*"))) == 1


def test_conflict_without_calibration_stays_open(env):
    env.sync()
    env.clock += timedelta(minutes=5)
    env.vault_write("Willkommen.md", "V\n")
    env.device_write("Willkommen.md", "P\n")
    e = env.engine()
    plan = e.plan(calibrate=False)
    assert plan.delta is None
    assert plan.transfers[0].action == Action.CONFLICT_OPEN


def test_identical_untracked_files_are_adopted_without_transfer(env):
    env.sync()
    # State verlieren, Dateien bleiben -> nichts übertragen, nur State neu aufbauen
    import shutil
    shutil.rmtree(env.state_dir)
    env.transport.log.clear()
    plan, _ = env.sync()
    assert plan.transfers == []
    assert {i.action for i in plan.items} == {Action.ADOPT}
    assert not [op for op, pth in env.transport.log if op == "put" and not pth.endswith((CLOCK_FILE, GEN_FILE))]
    assert set(State.load(env.state_dir).files) == SYNCED


def test_transport_error_aborts_and_keeps_state_for_done_items(env):
    env.sync()
    env.clock += timedelta(minutes=5)
    env.vault_write("A.md", "a\n")
    env.vault_write("B.md", "b\n")
    env.transport.fail_on.add("put")
    e = env.engine()
    plan = e.plan(calibrate=False)
    report = e.apply(plan)
    assert report.error and "simulierter Fehler" in report.error
    assert report.done == []
    state = State.load(env.state_dir)
    assert "A.md" not in state.files and "B.md" not in state.files
    env.transport.fail_on.clear()
    plan, _ = env.sync()
    assert env.actions(plan) == {"A.md": "push", "B.md": "push"}


def test_push_mode_forces_vault_version_and_lists_extra_device_files(env):
    env.sync()
    env.clock += timedelta(minutes=5)
    env.device_write("Willkommen.md", "Psion-Fassung\n")
    env.device_write("Nur Psion.md", "x\n")
    plan, _ = env.sync("push")
    assert env.actions(plan) == {"Willkommen.md": "push"}
    assert plan.device_extra == ["Nur Psion.md"]
    assert env.device_read("Willkommen.md") == b"Willkommen bei PsiVault!\r\nZweite Zeile.\r\n"


def test_pull_mode_forces_device_version(env):
    env.sync()
    env.clock += timedelta(minutes=5)
    env.vault_write("Willkommen.md", "Vault-Fassung\n")
    env.device_write("Willkommen.md", "Psion-Fassung\n")
    plan, _ = env.sync("pull")
    assert env.actions(plan) == {"Willkommen.md": "pull"}
    assert (env.vault / "Willkommen.md").read_text() == "Psion-Fassung\n"


def test_dry_run_plan_changes_nothing(env):
    env.sync()
    env.clock += timedelta(minutes=5)
    env.vault_write("Willkommen.md", "V\n")
    e = env.engine()
    plan = e.plan()
    assert env.actions(plan) == {"Willkommen.md": "push"}
    assert env.device_read("Willkommen.md") != b"V\r\n"
    assert State.load(env.state_dir).get("Willkommen.md").vault_hash != "x"


def test_empty_device_root_is_created_on_first_push(env):
    assert not env.device_path("").exists()
    env.sync()
    assert env.device_path("Willkommen.md").exists()


@pytest.mark.parametrize("action", ["push", "pull", "delete-device", "delete-vault", "adopt"])
@pytest.mark.parametrize("changed_side", ["vault", "device"])
def test_plan_refuses_later_changes(env, action, changed_side):
    env.sync()
    env.clock += timedelta(minutes=5)
    rel = "Willkommen.md"
    if action == "push":
        env.vault_write(rel, "planned push\n")
    elif action == "pull":
        env.device_write(rel, "planned pull\n")
    elif action == "delete-device":
        (env.vault / rel).unlink()
    elif action == "delete-vault":
        env.device_path(rel).unlink()
    engine = env.engine()
    plan = engine.plan("push" if action == "adopt" else "sync")
    state_before = engine.state.get(rel)
    if changed_side == "vault":
        env.vault_write(rel, "concurrent local edit\n")
    else:
        env.device_write(rel, "concurrent remote edit\n")
    local = (env.vault / rel).read_bytes() if (env.vault / rel).exists() else None
    remote = env.device_read(rel) if env.device_path(rel).exists() else None
    report = engine.apply(plan)
    assert "Seit Planung verändert" in report.error
    assert ((env.vault / rel).read_bytes() if (env.vault / rel).exists() else None) == local
    assert (env.device_read(rel) if env.device_path(rel).exists() else None) == remote
    assert State.load(env.state_dir).get(rel) == state_before


def test_conflict_copies_with_same_timestamp_preserve_both_versions(env):
    env.sync()
    env.clock += timedelta(minutes=5)
    env.vault_write("Willkommen.md", "local\n")
    env.device_write("Willkommen.md", "remote first\n")
    first, _ = env.sync()
    first_name = first.transfers[0].conflict_copy
    env.device_write("Willkommen.md", "remote second\n")  # same minute
    second, _ = env.sync()
    item = next(i for i in second.items if i.action == Action.CONFLICT_OPEN)
    assert item.conflict_copy != first_name
    assert (env.vault / first_name).read_text() == "remote first\n"
    assert (env.vault / item.conflict_copy).read_text() == "remote second\n"
    # Repeated runs reuse an identical copy, never create an endless series.
    third, _ = env.sync()
    assert next(i for i in third.items if i.action == Action.CONFLICT_OPEN).conflict_copy == item.conflict_copy


def test_partial_unicode_loss_preserves_original_after_snapshot_gc(env):
    env.vault_write("Unicode.md", "→\n→\n")
    env.sync()
    previous = State.load(env.state_dir).get("Unicode.md").vault_hash
    env.clock += timedelta(minutes=5)
    env.device_write("Unicode.md", "->\n-> edited\n")
    env.sync()
    assert (env.vault / "Unicode.md").read_text() == "→\n-> edited\n"
    assert not (env.state_dir / "snapshots" / (previous + ".md")).exists()
    backups = list((env.state_dir / "unicode-backup").rglob("*.md"))
    assert len(backups) == 1
    assert backups[0].read_text() == "→\n→\n"


def test_unicode_backups_do_not_overwrite_within_same_second(env):
    engine = env.engine()
    path = env.vault / "U.md"
    path.write_text("first →")
    engine._backup_unicode("U.md", path)
    path.write_text("second →")
    engine._backup_unicode("U.md", path)
    assert {p.read_text() for p in (env.state_dir / "unicode-backup").rglob("*.md")} == {"first →", "second →"}


def test_push_refresh_lists_only_affected_directory(env):
    env.sync()
    env.vault_write("Willkommen.md", "changed\n")
    engine = env.engine()
    plan = engine.plan()
    env.transport.log.clear()
    assert engine.apply(plan).error is None
    assert [path for op, path in env.transport.log if op == "ls"] == ["C:\\Vault"]


def test_local_edit_during_device_revalidation_is_not_overwritten(env):
    env.sync()
    env.clock += timedelta(minutes=5)
    env.device_write("Willkommen.md", "remote\n")
    engine = env.engine()
    plan = engine.plan()
    original_get = env.transport.get

    def changing_get(path):
        data = original_get(path)
        env.vault_write("Willkommen.md", "edit during slow download\n")
        return data

    env.transport.get = changing_get
    report = engine.apply(plan)
    assert "Seit Planung verändert" in report.error
    assert (env.vault / "Willkommen.md").read_text() == "edit during slow download\n"
