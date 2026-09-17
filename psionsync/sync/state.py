"""Sync-Zustand: pro Notiz Hash und mtime beider Seiten zum letzten erfolgreichen Sync.

Zusätzlich liegen unter ``<state_dir>/snapshots/<vault_hash>.md`` die Unicode-
Originaltexte der Notizen, die beim Push transliteriert wurden, damit beim Pull
unveränderte Zeilen exakt wiederhergestellt werden können.
"""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path, PurePosixPath

STATE_VERSION = 1


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@dataclass
class FileState:
    vault_hash: str          # sha256 der Vault-Datei (UTF-8-Bytes)
    vault_mtime: str         # ISO, lokale Zeit
    device_hash: str         # sha256 der Gerätebytes (CP1252/CRLF)
    device_size: int
    device_mtime: str        # ISO, so wie der Transport sie meldet (unkalibriert)
    translit_version: int
    has_snapshot: bool = False

    @classmethod
    def from_dict(cls, d: dict) -> "FileState":
        return cls(**d)


class State:
    def __init__(self, state_dir: Path):
        self.state_dir = Path(state_dir)
        self.path = self.state_dir / "state.json"
        self.snapshots = self.state_dir / "snapshots"
        self.files: dict[str, FileState] = {}
        self.last_sync: str | None = None
        self.generation: int = 0

    # -- Laden/Speichern -------------------------------------------------
    @classmethod
    def load(cls, state_dir: Path) -> "State":
        state = cls(state_dir)
        if state.path.exists():
            data = json.loads(state.path.read_text(encoding="utf-8"))
            if data.get("version") != STATE_VERSION:
                raise ValueError(f"unbekannte State-Version {data.get('version')!r} in {state.path}")
            state.files = {k: FileState.from_dict(v) for k, v in data["files"].items()}
            state.last_sync = data.get("last_sync")
            state.generation = int(data.get("generation", 0))
        return state

    def save(self) -> None:
        self.state_dir.mkdir(parents=True, exist_ok=True)
        data = {"version": STATE_VERSION, "last_sync": self.last_sync, "generation": self.generation,
                "files": {k: asdict(v) for k, v in sorted(self.files.items())}}
        tmp = self.path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, self.path)
        self.gc_snapshots()

    # -- Zugriff ---------------------------------------------------------
    def get(self, rel: PurePosixPath | str) -> FileState | None:
        return self.files.get(str(rel))

    def set(self, rel: PurePosixPath | str, entry: FileState) -> None:
        self.files[str(rel)] = entry

    def remove(self, rel: PurePosixPath | str) -> None:
        self.files.pop(str(rel), None)

    # -- Unicode-Snapshots ------------------------------------------------
    def snapshot_path(self, vault_hash: str) -> Path:
        return self.snapshots / f"{vault_hash}.md"

    def write_snapshot(self, vault_hash: str, text: str) -> None:
        self.snapshots.mkdir(parents=True, exist_ok=True)
        self.snapshot_path(vault_hash).write_text(text, encoding="utf-8")

    def read_snapshot(self, rel: PurePosixPath | str) -> str | None:
        entry = self.get(rel)
        if not entry or not entry.has_snapshot:
            return None
        p = self.snapshot_path(entry.vault_hash)
        return p.read_text(encoding="utf-8") if p.exists() else None

    def gc_snapshots(self) -> None:
        if not self.snapshots.exists():
            return
        keep = {e.vault_hash for e in self.files.values() if e.has_snapshot}
        for p in self.snapshots.glob("*.md"):
            if p.stem not in keep:
                p.unlink()


def iso(dt: datetime) -> str:
    return dt.replace(microsecond=0).isoformat()


def from_iso(s: str) -> datetime:
    return datetime.fromisoformat(s)
