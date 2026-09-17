"""Rekursive Dateisicherung des Geräts über den Transport (nur lesend)."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .transport.base import Transport, TransportError, walk

ROM_FILE = "D:\\SYS$ROM.BIN"


def backup(transport: Transport, destination: Path, drives=("C", "D"), skip_rom: bool = True,
           log=print) -> int:
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=False)
    manifest = []
    for drive in drives:
        root = f"{drive}:\\"
        try:
            files, _ = walk(transport, root)
        except TransportError as exc:
            if drive == "C":
                raise
            log(f"Laufwerk {root} nicht lesbar, übersprungen ({exc})")
            continue
        for path, entry in sorted(files.items()):
            if skip_rom and path.upper() == ROM_FILE:
                log(f"überspringe {path} (ROM)")
                continue
            rel = path[len(root):].split("\\")
            target = destination.joinpath(drive, *rel)
            target.parent.mkdir(parents=True, exist_ok=True)
            log(f"{path} ({entry.size} Bytes)")
            data = transport.get(path)
            if len(data) != entry.size:
                raise RuntimeError(f"Größe weicht ab: {path}: {len(data)} statt {entry.size}")
            target.write_bytes(data)
            manifest.append(dict(path=path, size=entry.size, sha256=hashlib.sha256(data).hexdigest(),
                                 mtime=entry.mtime.isoformat()))
    (destination / "manifest.json").write_text(json.dumps(manifest, indent=1, ensure_ascii=False), encoding="utf-8")
    if skip_rom:
        (destination / "exclusions.json").write_text(json.dumps({ROM_FILE: "ROM ausgelassen (--skip-rom)"}, indent=1))
    return len(manifest)
