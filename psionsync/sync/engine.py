"""Sync-Engine: Vault und Gerät einlesen, Plan berechnen, Plan ausführen.

Änderungen werden per Hash gegen den State erkannt. Zeitstempel entscheiden nur
Konflikte, und nur nach Kalibrierung (Delta zwischen gemeldeter Psion-Zeit und
Rechnerzeit, gemessen an einer frisch geschriebenen Datei).
"""
from __future__ import annotations

import os
import shutil
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path, PurePosixPath

from ..transport.base import Entry, Transport, TransportError, walk
from . import fsmap
from .fsmap import (UnmappablePath, decode_content, device_to_vault, encode_content,
                    is_synced_path, needs_transliteration, restore_unicode, vault_to_device)
from .state import FileState, State, from_iso, iso, sha256

CLOCK_FILE = "_psionsync.clock"
# Generationszähler: steigt bei jedem Sync, der etwas übertragen hat. Gedacht für
# einen App-Suchindex, der verworfen wurde (docs/psion-notes.md); derzeit ohne Leser.
GEN_FILE = "_psionsync.gen"
# Zeitunterschiede unterhalb dieser Schwelle gelten als "gleich" -> Konflikt bleibt offen.
CONFLICT_TOLERANCE = timedelta(seconds=60)


class Action(Enum):
    PUSH = "push"
    PULL = "pull"
    DELETE_DEVICE = "rm-psion"
    DELETE_VAULT = "rm-vault"
    CONFLICT_PUSH = "konflikt>push"      # Vault neuer: push, Psion-Fassung als Konfliktkopie
    CONFLICT_PULL = "konflikt>pull"      # Psion neuer: pull, Vault-Fassung als Konfliktkopie
    CONFLICT_OPEN = "konflikt-offen"     # nicht entscheidbar: Psion-Fassung als Kopie, kein State
    ADOPT = "übernehmen"                 # beide Seiten identisch, nur State schreiben
    FORGET = "vergessen"                 # beidseitig weg, State-Eintrag löschen


@dataclass
class VaultFile:
    rel: str
    path: Path
    data: bytes
    hash: str
    mtime: datetime

    @property
    def text(self) -> str:
        return self.data.decode("utf-8")


@dataclass
class DeviceFile:
    rel: str
    path: str
    size: int
    mtime_raw: datetime
    hash: str | None = None
    data: bytes | None = None


@dataclass
class PlanItem:
    action: Action
    rel: str
    reason: str = ""
    conflict_copy: str | None = None    # Relativpfad der Konfliktkopie im Vault

    def __str__(self) -> str:
        s = f"{self.action.value:<14} {self.rel}"
        if self.conflict_copy:
            s += f"  [Kopie: {self.conflict_copy}]"
        if self.reason:
            s += f"  ({self.reason})"
        return s


@dataclass
class Plan:
    items: list[PlanItem] = field(default_factory=list)
    skipped: list[tuple[str, str]] = field(default_factory=list)   # (rel, Grund)
    delta: timedelta | None = None
    device_extra: list[str] = field(default_factory=list)          # nur push/pull: Dateien der Gegenseite
    expected: dict[str, tuple[str | None, str | None]] = field(default_factory=dict)

    @property
    def transfers(self) -> list[PlanItem]:
        return [i for i in self.items if i.action not in (Action.ADOPT, Action.FORGET)]


@dataclass
class Report:
    done: list[PlanItem] = field(default_factory=list)
    error: str | None = None


class Engine:
    def __init__(self, vault: Path, transport: Transport, state: State,
                 device_root: str = fsmap.DEVICE_ROOT, now=datetime.now):
        self.vault = Path(vault)
        self.transport = transport
        self.state = state
        self.device_root = device_root
        self.now = now
        self._device_dirs: set[str] = set()
        self._device: dict[str, DeviceFile] = {}

    # -- Einlesen ---------------------------------------------------------
    def scan_vault(self) -> tuple[dict[str, VaultFile], list[tuple[str, str]]]:
        files: dict[str, VaultFile] = {}
        skipped: list[tuple[str, str]] = []
        for path in sorted(self.vault.rglob("*.md")):
            if not path.is_file():
                continue
            rel = PurePosixPath(path.relative_to(self.vault).as_posix())
            if not is_synced_path(rel):
                continue
            try:
                vault_to_device(rel, self.device_root)
            except UnmappablePath as exc:
                skipped.append((str(rel), str(exc)))
                continue
            data = path.read_bytes()
            try:
                data.decode("utf-8")
            except UnicodeDecodeError:
                skipped.append((str(rel), "kein gültiges UTF-8"))
                continue
            st = path.stat()
            files[str(rel)] = VaultFile(str(rel), path, data, sha256(data),
                                        datetime.fromtimestamp(st.st_mtime).replace(microsecond=0))
        return files, skipped

    def scan_device(self) -> dict[str, DeviceFile]:
        if not self.transport.exists(self.device_root):
            self._device_dirs = set()
            return {}
        entries, dirs = walk(self.transport, self.device_root)
        self._device_dirs = dirs
        files: dict[str, DeviceFile] = {}
        for path, entry in entries.items():
            rel = device_to_vault(path, self.device_root)
            if not is_synced_path(rel):
                continue
            files[str(rel)] = DeviceFile(str(rel), path, entry.size, entry.mtime)
        self._device = files
        return files

    def _device_hash(self, d: DeviceFile) -> str:
        """Hash der Gerätedatei; ohne Download, wenn Größe und mtime dem State entsprechen."""
        if d.hash:
            return d.hash
        s = self.state.get(d.rel)
        if s and s.device_size == d.size and s.device_mtime == iso(d.mtime_raw):
            d.hash = s.device_hash
        else:
            d.data = self.transport.get(d.path)
            d.hash = sha256(d.data)
        return d.hash

    def _device_data(self, d: DeviceFile) -> bytes:
        if d.data is None:
            d.data = self.transport.get(d.path)
            d.hash = sha256(d.data)
        return d.data

    # -- Zeitkalibrierung ---------------------------------------------------
    def calibrate(self) -> timedelta:
        """Delta = vom Transport gemeldete Zeit einer frisch geschriebenen Datei minus Rechnerzeit."""
        path = self.device_root + "\\" + CLOCK_FILE
        if not self.transport.exists(self.device_root):
            self.transport.mkdir(self.device_root)
        now = self.now().replace(microsecond=0)
        self.transport.put(path, now.isoformat().encode("ascii"))
        reported = self.transport.mtime(path)
        return reported - now

    # -- Plan -------------------------------------------------------------
    def plan(self, mode: str = "sync", calibrate: bool = True) -> Plan:
        vault, skipped = self.scan_vault()
        device = self.scan_device()
        plan = Plan(skipped=skipped)
        if calibrate:
            plan.delta = self.calibrate()
        if mode == "push":
            self._plan_oneway(plan, vault, device, push=True)
        elif mode == "pull":
            self._plan_oneway(plan, vault, device, push=False)
        else:
            self._plan_sync(plan, vault, device)
        plan.items.sort(key=lambda i: i.rel)
        # Store preconditions even for absent files: a newly created file must
        # not be overwritten by a plan made before it existed.
        plan.expected = {
            i.rel: (vault[i.rel].hash if i.rel in vault else None,
                    self._device_hash(device[i.rel]) if i.rel in device else None)
            for i in plan.items
        }
        return plan

    def _plan_oneway(self, plan: Plan, vault: dict[str, VaultFile], device: dict[str, DeviceFile], push: bool) -> None:
        if push:
            for rel, v in vault.items():
                d = device.get(rel)
                if d and self._device_hash(d) == sha256(encode_content(v.text)):
                    plan.items.append(PlanItem(Action.ADOPT, rel))
                else:
                    plan.items.append(PlanItem(Action.PUSH, rel, "neu" if d is None else "erzwungen"))
            plan.device_extra = sorted(set(device) - set(vault))
        else:
            for rel, d in device.items():
                v = vault.get(rel)
                if v and self._device_hash(d) == sha256(encode_content(v.text)):
                    plan.items.append(PlanItem(Action.ADOPT, rel))
                else:
                    plan.items.append(PlanItem(Action.PULL, rel, "neu" if v is None else "erzwungen"))
            plan.device_extra = sorted(set(vault) - set(device))

    def _plan_sync(self, plan: Plan, vault: dict[str, VaultFile], device: dict[str, DeviceFile]) -> None:
        skipped = {rel for rel, _ in plan.skipped}
        for rel in sorted(set(vault) | set(device) | set(self.state.files)):
            if rel in skipped:
                continue
            v, d, s = vault.get(rel), device.get(rel), self.state.get(rel)
            v_hash = v.hash if v else None
            d_hash = self._device_hash(d) if d else None
            v_changed = v_hash != (s.vault_hash if s else None)
            d_changed = d_hash != (s.device_hash if s else None)
            if not v_changed and not d_changed:
                continue
            if v and not d:
                if s is None:
                    plan.items.append(PlanItem(Action.PUSH, rel, "neu im Vault"))
                elif v_changed:
                    plan.items.append(PlanItem(Action.PUSH, rel, "auf Psion gelöscht, im Vault geändert -> Vault-Fassung bleibt"))
                else:
                    plan.items.append(PlanItem(Action.DELETE_VAULT, rel, "auf Psion gelöscht"))
            elif d and not v:
                if s is None:
                    plan.items.append(PlanItem(Action.PULL, rel, "neu auf Psion"))
                elif d_changed:
                    plan.items.append(PlanItem(Action.PULL, rel, "im Vault gelöscht, auf Psion geändert -> Psion-Fassung bleibt"))
                else:
                    plan.items.append(PlanItem(Action.DELETE_DEVICE, rel, "im Vault gelöscht"))
            elif not v and not d:
                plan.items.append(PlanItem(Action.FORGET, rel))
            elif v_changed and not d_changed:
                plan.items.append(PlanItem(Action.PUSH, rel, "im Vault geändert"))
            elif d_changed and not v_changed:
                plan.items.append(PlanItem(Action.PULL, rel, "auf Psion geändert"))
            else:
                assert v is not None and d is not None
                if sha256(encode_content(v.text)) == d_hash:
                    plan.items.append(PlanItem(Action.ADOPT, rel, "beide Seiten identisch"))
                else:
                    plan.items.append(self._resolve_conflict(plan.delta, v, d))

    def _resolve_conflict(self, delta: timedelta | None, v: VaultFile, d: DeviceFile) -> PlanItem:
        if delta is None:
            return PlanItem(Action.CONFLICT_OPEN, v.rel, "keine Zeitkalibrierung",
                            conflict_copy=self._conflict_name(v.rel, "Psion", d.mtime_raw))
        d_local = d.mtime_raw - delta
        diff = v.mtime - d_local
        stamp = f"Vault {v.mtime:%Y-%m-%d %H:%M}, Psion {d_local:%Y-%m-%d %H:%M}"
        if abs(diff) <= CONFLICT_TOLERANCE:
            return PlanItem(Action.CONFLICT_OPEN, v.rel, f"Zeiten zu nah beieinander: {stamp}",
                            conflict_copy=self._conflict_name(v.rel, "Psion", d_local))
        if diff > timedelta(0):
            return PlanItem(Action.CONFLICT_PUSH, v.rel, f"Vault neuer: {stamp}",
                            conflict_copy=self._conflict_name(v.rel, "Psion", d_local))
        return PlanItem(Action.CONFLICT_PULL, v.rel, f"Psion neuer: {stamp}",
                        conflict_copy=self._conflict_name(v.rel, "Linux", v.mtime))

    @staticmethod
    def _conflict_name(rel: str, side: str, when: datetime) -> str:
        p = PurePosixPath(rel)
        return str(p.with_name(f"{p.stem} (Konflikt {side} {when:%Y-%m-%d %H%M}){p.suffix}"))

    # -- Ausführen ----------------------------------------------------------
    def apply(self, plan: Plan) -> Report:
        """Führt den Plan aus. Bricht beim ersten Transportfehler ab; der State wird
        nur für tatsächlich abgeschlossene Schritte fortgeschrieben und immer gespeichert."""
        report = Report()
        # Konfliktkopien zuerst, damit keine Fassung verloren geht, egal wo es abbricht.
        order = sorted(plan.items, key=lambda i: 0 if i.action in (
            Action.CONFLICT_OPEN, Action.CONFLICT_PUSH, Action.CONFLICT_PULL) else 1)
        pushed: list[tuple[str, str]] = []   # (rel, Gerätepfad) -> mtime/size nachträglich holen
        try:
            for item in order:
                self._check_preconditions(item.rel, plan)
                self._apply_item(item, pushed)
                report.done.append(item)
            self._refresh_pushed(pushed)
            if any(i.action not in (Action.ADOPT, Action.FORGET) for i in report.done):
                self.state.generation += 1
                self.transport.put(self.device_root + "\\" + GEN_FILE, str(self.state.generation).encode("ascii"))
        except TransportError as exc:
            report.error = str(exc)
        except Exception as exc:  # noqa: BLE001 - State trotzdem sichern
            report.error = f"{type(exc).__name__}: {exc}"
        finally:
            if pushed and report.error:
                # mtimes der bereits gepushten Dateien so gut wie möglich nachtragen
                try:
                    self._refresh_pushed(pushed)
                except Exception:  # noqa: BLE001
                    pass
            self.state.last_sync = iso(self.now())
            self.state.save()
        return report

    def _check_preconditions(self, rel: str, plan: Plan) -> None:
        if rel not in plan.expected:
            raise TransportError(f"Plan ohne Vergleichsstand: {rel}; bitte neu planen")
        expected_vault, expected_device = plan.expected[rel]
        path = self.vault / rel
        device_path = vault_to_device(rel, self.device_root)
        data = self.transport.get(device_path) if self.transport.exists(device_path) else None
        current_device = sha256(data) if data is not None else None
        # Check the local side after the potentially slow serial download.
        current_vault = sha256(path.read_bytes()) if path.exists() else None
        if (current_vault, current_device) != (expected_vault, expected_device):
            raise TransportError(f"Seit Planung verändert: {rel}; keine Übertragung, bitte neu planen")
        # Do not use an earlier download after successful revalidation.
        if data is not None and rel in self._device:
            self._device[rel].data = data
            self._device[rel].hash = current_device

    def _apply_item(self, item: PlanItem, pushed: list[tuple[str, str]]) -> None:
        rel = item.rel
        a = item.action
        if a == Action.FORGET:
            self.state.remove(rel)
        elif a == Action.ADOPT:
            self._adopt(rel, pushed)
        elif a == Action.PUSH:
            self._push(rel, pushed)
        elif a == Action.PULL:
            self._pull(rel)
        elif a == Action.DELETE_DEVICE:
            self.transport.remove(vault_to_device(rel, self.device_root))
            self.state.remove(rel)
        elif a == Action.DELETE_VAULT:
            self._delete_vault(rel)
            self.state.remove(rel)
        elif a == Action.CONFLICT_PUSH:
            item.conflict_copy = self._write_conflict_copy(item.conflict_copy, self._device_text(rel))
            self._push(rel, pushed)
        elif a == Action.CONFLICT_PULL:
            item.conflict_copy = self._write_conflict_copy(item.conflict_copy, (self.vault / rel).read_text(encoding="utf-8"))
            self._pull(rel)
        elif a == Action.CONFLICT_OPEN:
            item.conflict_copy = self._write_conflict_copy(item.conflict_copy, self._device_text(rel))
            # bewusst kein State-Update: Konflikt bleibt offen
        else:  # pragma: no cover
            raise ValueError(a)

    def _device_text(self, rel: str) -> str:
        """Text der Gerätedatei (Unicode wiederhergestellt, soweit eindeutig)."""
        d = self._device.get(rel) or DeviceFile(rel, vault_to_device(rel, self.device_root), 0, self.now())
        text = decode_content(self._device_data(d))
        snapshot = self.state.read_snapshot(rel)
        return restore_unicode(text, snapshot) if snapshot else text

    def _ensure_device_dir(self, device_path: str) -> None:
        parent = device_path.rsplit("\\", 1)[0]
        if parent.upper() == self.device_root.upper() or parent in self._device_dirs:
            return
        self._ensure_device_dir(parent)
        if not self.transport.exists(parent):
            self.transport.mkdir(parent)
        self._device_dirs.add(parent)

    def _push(self, rel: str, pushed: list[tuple[str, str]]) -> None:
        path = self.vault / rel
        data = path.read_bytes()
        text = data.decode("utf-8")
        encoded = encode_content(text)
        device_path = vault_to_device(rel, self.device_root)
        self._ensure_device_dir(device_path)
        self.transport.put(device_path, encoded)
        self._record(rel, data, text, path, encoded, None)
        pushed.append((rel, device_path))

    def _pull(self, rel: str) -> None:
        device_path = vault_to_device(rel, self.device_root)
        d = self._device.get(rel) or DeviceFile(rel, device_path, 0, self.now())
        encoded = self._device_data(d)
        text = decode_content(encoded)
        snapshot = self.state.read_snapshot(rel)
        if snapshot:
            text = restore_unicode(text, snapshot)
        path = self.vault / rel
        if path.exists():
            old = path.read_bytes().decode("utf-8", errors="replace")
            if needs_transliteration(old) and self._loses_unicode(old, text):
                self._backup_unicode(rel, path)
        self._write_atomic(path, text.encode("utf-8"))
        mtime = self.transport.mtime(device_path)
        self._record(rel, text.encode("utf-8"), text, path, encoded, mtime)

    def _adopt(self, rel: str, pushed: list[tuple[str, str]]) -> None:
        path = self.vault / rel
        data = path.read_bytes()
        text = data.decode("utf-8")
        self._record(rel, data, text, path, encode_content(text), None)
        pushed.append((rel, vault_to_device(rel, self.device_root)))

    def _record(self, rel: str, data: bytes, text: str, path: Path, encoded: bytes,
                device_mtime: datetime | None) -> None:
        vault_hash = sha256(data)
        has_snapshot = needs_transliteration(text)
        if has_snapshot:
            self.state.write_snapshot(vault_hash, text)
        st = path.stat()
        self.state.set(rel, FileState(
            vault_hash=vault_hash,
            vault_mtime=iso(datetime.fromtimestamp(st.st_mtime)),
            device_hash=sha256(encoded), device_size=len(encoded),
            device_mtime=iso(device_mtime) if device_mtime else "",
            translit_version=fsmap.TRANSLIT_VERSION, has_snapshot=has_snapshot))

    def _refresh_pushed(self, pushed: list[tuple[str, str]]) -> None:
        """Nach dem Push Größe und mtime vom Gerät nachtragen (ein ls pro Ordner statt gtime pro Datei)."""
        if not pushed:
            return
        parents = {path.rsplit("\\", 1)[0] for _, path in pushed}
        entries = {e.path: e for parent in sorted(parents) for e in self.transport.listdir(parent)}
        for rel, device_path in pushed:
            entry = entries.get(device_path)
            s = self.state.get(rel)
            if entry and s:
                s.device_mtime = iso(entry.mtime)
                s.device_size = entry.size
        pushed.clear()

    @staticmethod
    def _loses_unicode(old: str, new: str) -> bool:
        # Preserve originals whenever a Unicode-bearing line is removed or
        # changed, even when the same characters remain elsewhere in the note.
        old_lines = Counter(line for line in old.splitlines() if needs_transliteration(line))
        return bool(old_lines - Counter(new.splitlines()))

    def _backup_unicode(self, rel: str, path: Path) -> None:
        target = self.state.state_dir / "unicode-backup" / f"{rel} {self.now():%Y-%m-%d %H%M%S}.md"
        self._preserve_copy(target, path.read_bytes())

    def _delete_vault(self, rel: str) -> None:
        path = self.vault / rel
        if path.exists():
            target = self.state.state_dir / "trash" / f"{rel} {self.now():%Y-%m-%d %H%M%S}.md"
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(path, target)

    def _write_conflict_copy(self, rel: str | None, text: str) -> str:
        assert rel
        path = self._preserve_copy(self.vault / rel, text.encode("utf-8"))
        return path.relative_to(self.vault).as_posix()

    @staticmethod
    def _preserve_copy(path: Path, data: bytes) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        number = 1
        while True:
            candidate = path if number == 1 else path.with_name(f"{path.stem} ({number}){path.suffix}")
            try:
                with candidate.open("xb") as out:
                    out.write(data)
                return candidate
            except FileExistsError:
                if candidate.read_bytes() == data:
                    return candidate
                number += 1

    @staticmethod
    def _write_atomic(path: Path, data: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".psionsync-tmp")
        tmp.write_bytes(data)
        os.replace(tmp, path)
