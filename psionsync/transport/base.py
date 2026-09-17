"""Transport-Schnittstelle zum Gerät. Pfade sind immer Gerätepfade (``C:\\...``)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


class TransportError(RuntimeError):
    """Jeder Fehler beim Zugriff auf das Gerät. Der Sync bricht danach ab."""


@dataclass(frozen=True)
class Entry:
    path: str          # vollständiger Gerätepfad
    name: str
    is_dir: bool
    size: int
    mtime: datetime    # so wie der Transport sie meldet (unkalibriert, naiv)


class Transport(Protocol):
    def listdir(self, path: str) -> list[Entry]: ...
    def get(self, path: str) -> bytes: ...
    def put(self, path: str, data: bytes) -> None: ...
    def mkdir(self, path: str) -> None: ...
    def remove(self, path: str) -> None: ...
    def rmdir(self, path: str) -> None: ...
    def mtime(self, path: str) -> datetime: ...
    def exists(self, path: str) -> bool: ...


def walk(transport: Transport, root: str) -> tuple[dict[str, Entry], set[str]]:
    """Rekursiv alle Dateien unter ``root`` (Pfad -> Entry) und alle Ordnerpfade."""
    files: dict[str, Entry] = {}
    dirs: set[str] = set()
    stack = [root]
    while stack:
        current = stack.pop()
        for entry in transport.listdir(current):
            if entry.is_dir:
                dirs.add(entry.path)
                stack.append(entry.path)
            else:
                files[entry.path] = entry
    return files, dirs
