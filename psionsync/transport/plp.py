"""Transport über ``plpftp`` (plptools) als Subprozess; ``ncpd`` muss laufen.

Eigenheiten der eingesetzten Version (Phase 0, siehe docs/psion-notes.md):
- Jeder Aufruf ist eine eigene Sitzung mit Gerätverzeichnis ``C:\\``.
- ``ls``/``get`` nehmen absolute Pfade; ``put``/``mkdir``/``rm``/``rmdir``/``ren``/
  ``gtime``/``test`` nur Pfade relativ zu ``C:\\``.
- Fehler landen auf stderr oder als ``Error: …`` auf stdout, der Exitcode bleibt 0.
- Argumente werden CP1252-kodiert übergeben (Umlaute in Namen).
- Lokale Dateinamen bei ``put``/``get`` müssen relativ zum Arbeitsverzeichnis
  sein (absolute Pfade -> ``Error: no such file`` / ``Error: general``).
- Gemeldete Zeiten sind um UTC-Offset+DST verschoben; der Sync kalibriert das.
"""
from __future__ import annotations

import os
import re
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path

from .base import Entry, TransportError

ENCODING = "cp1252"
LS_LINE = re.compile(r"^([d-][rwhsa-]{9})\s+(\d+) (.{24}) (.+)$")
TIME_FORMAT = "%a %b %d %H:%M:%S %Y"


def parse_ls(output: str, directory: str) -> list[Entry]:
    entries = []
    prefix = directory.rstrip("\\") + "\\"
    for line in output.splitlines():
        if not line.strip():
            continue
        m = LS_LINE.fullmatch(line)
        if not m:
            raise TransportError(f"unerwartete ls-Zeile: {line!r}")
        attrs, size, stamp, name = m.groups()
        try:
            mtime = datetime.strptime(stamp.strip(), TIME_FORMAT)
        except ValueError as exc:
            raise TransportError(f"unerwartete Zeitangabe {stamp!r}: {exc}") from None
        entries.append(Entry(path=prefix + name, name=name, is_dir=attrs.startswith("d"),
                             size=int(size), mtime=mtime))
    return entries


def parse_gtime(output: str) -> datetime:
    m = re.match(r"^(.{24})\(", output.strip())
    if not m:
        raise TransportError(f"unerwartete gtime-Ausgabe: {output!r}")
    return datetime.strptime(m.group(1), TIME_FORMAT)


class PlpTransport:
    def __init__(self, executable: str = "plpftp", timeout: float = 600, drive: str = "C:"):
        self.executable = executable
        self.timeout = timeout
        self.drive = drive.upper()
        self.calls = 0

    # -- Grundlagen -------------------------------------------------------
    def run(self, *args: str, cwd: str | Path | None = None) -> str:
        self.calls += 1
        try:
            result = subprocess.run(
                [self.executable.encode(), *(a.encode(ENCODING) for a in args)],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=cwd,
                env={**os.environ, "LC_ALL": "C"}, timeout=self.timeout, check=False)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise TransportError(f"plpftp {' '.join(args)}: {exc}") from exc
        out = result.stdout.decode(ENCODING, errors="replace")
        err = result.stderr.decode(ENCODING, errors="replace").strip()
        if result.returncode or err or "Error:" in out or "syntax error" in out:
            raise TransportError(f"plpftp {' '.join(args)}: {(err + ' ' + out).strip()} (rc={result.returncode})")
        return out

    def relative(self, path: str) -> str:
        """Gerätepfad relativ zu ``C:\\`` (Sitzungsverzeichnis); nur dieses Laufwerk wird unterstützt."""
        prefix = self.drive + "\\"
        if not path.upper().startswith(prefix):
            raise TransportError(f"{path!r} liegt nicht auf {self.drive}")
        rel = path[len(prefix):]
        if not rel:
            raise TransportError(f"Wurzel {path!r} nicht als relativer Pfad darstellbar")
        return rel

    def check_connection(self) -> None:
        out = self.run("pwd")
        if f'Psion dir: "{self.drive}\\"' not in out:
            raise TransportError(f"unerwartetes Sitzungsverzeichnis: {out.strip()!r}")

    # -- Transport-Schnittstelle --------------------------------------------
    def listdir(self, path: str) -> list[Entry]:
        return parse_ls(self.run("ls", path.rstrip("\\") + "\\"), path)

    def get(self, path: str) -> bytes:
        with tempfile.TemporaryDirectory(prefix="psionsync-") as tmp:
            local = Path(tmp) / "transfer.bin"
            self.run("get", path, local.name, cwd=tmp)
            if not local.exists():
                raise TransportError(f"get {path}: keine lokale Datei erzeugt")
            return local.read_bytes()

    def put(self, path: str, data: bytes) -> None:
        with tempfile.TemporaryDirectory(prefix="psionsync-") as tmp:
            local = Path(tmp) / "transfer.bin"
            local.write_bytes(data)
            self.run("put", local.name, self.relative(path), cwd=tmp)

    def mkdir(self, path: str) -> None:
        self.run("mkdir", self.relative(path))

    def remove(self, path: str) -> None:
        self.run("rm", self.relative(path))

    def rmdir(self, path: str) -> None:
        self.run("rmdir", self.relative(path))

    def mtime(self, path: str) -> datetime:
        return parse_gtime(self.run("gtime", self.relative(path)))

    def exists(self, path: str) -> bool:
        try:
            self.run("test", self.relative(path))
        except TransportError as exc:
            if "no such file" in str(exc) or "no such directory" in str(exc):
                return False
            raise
        return True
