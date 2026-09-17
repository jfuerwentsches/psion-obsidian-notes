"""Verzeichnis-basierter Fake-Transport für Tests und Trockenläufe ohne Gerät.

``C:\\Vault\\a\\b.md`` wird auf ``<root>/C/Vault/a/b.md`` abgebildet. Dateizeiten
sind echte mtimes; ``clock_offset`` simuliert die Zeitverschiebung, die plptools
bei Psion-Zeiten meldet (Phase 0: +2 h).
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta
from pathlib import Path

from .base import Entry, TransportError


class FakeTransport:
    def __init__(self, root: Path, clock_offset: timedelta = timedelta(0), now=datetime.now):
        self.root = Path(root)
        self.clock_offset = clock_offset
        self.now = now   # "Geräteuhr": neue Dateien bekommen diese Zeit als mtime
        self.log: list[tuple] = []
        self.fail_on: set[str] = set()   # Befehlsnamen, die TransportError werfen sollen

    def _local(self, path: str) -> Path:
        drive, _, rest = path.partition(":\\")
        if not drive or ":" in rest:
            raise TransportError(f"ungültiger Gerätepfad {path!r}")
        parts = [p for p in rest.split("\\") if p]
        return self.root.joinpath(drive.upper(), *parts)

    def _check(self, op: str, path: str) -> None:
        self.log.append((op, path))
        if op in self.fail_on:
            raise TransportError(f"simulierter Fehler bei {op} {path}")

    def _mtime(self, p: Path) -> datetime:
        return datetime.fromtimestamp(p.stat().st_mtime).replace(microsecond=0) + self.clock_offset

    def listdir(self, path: str) -> list[Entry]:
        self._check("ls", path)
        local = self._local(path)
        if not local.is_dir():
            raise TransportError(f"kein Verzeichnis: {path}")
        entries = []
        for child in sorted(local.iterdir()):
            entries.append(Entry(path=path.rstrip("\\") + "\\" + child.name, name=child.name,
                                 is_dir=child.is_dir(), size=0 if child.is_dir() else child.stat().st_size,
                                 mtime=self._mtime(child)))
        return entries

    def get(self, path: str) -> bytes:
        self._check("get", path)
        try:
            return self._local(path).read_bytes()
        except OSError as exc:
            raise TransportError(f"get {path}: {exc}") from exc

    def put(self, path: str, data: bytes) -> None:
        self._check("put", path)
        local = self._local(path)
        if not local.parent.is_dir():
            raise TransportError(f"put {path}: Ordner fehlt")
        local.write_bytes(data)
        stamp = self.now().timestamp()
        os.utime(local, (stamp, stamp))

    def mkdir(self, path: str) -> None:
        self._check("mkdir", path)
        local = self._local(path)
        if not local.parent.is_dir():
            raise TransportError(f"mkdir {path}: Elternordner fehlt")
        local.mkdir(exist_ok=True)

    def remove(self, path: str) -> None:
        self._check("rm", path)
        try:
            self._local(path).unlink()
        except OSError as exc:
            raise TransportError(f"rm {path}: {exc}") from exc

    def rmdir(self, path: str) -> None:
        self._check("rmdir", path)
        try:
            self._local(path).rmdir()
        except OSError as exc:
            raise TransportError(f"rmdir {path}: {exc}") from exc

    def mtime(self, path: str) -> datetime:
        self._check("gtime", path)
        local = self._local(path)
        if not local.exists():
            raise TransportError(f"gtime {path}: fehlt")
        return self._mtime(local)

    def exists(self, path: str) -> bool:
        return self._local(path).exists()
