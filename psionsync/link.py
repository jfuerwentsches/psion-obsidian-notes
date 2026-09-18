"""``ncpd`` nur für die Dauer eines Laufs starten.

Ein dauerhaft laufender ``ncpd`` hält die Steuerleitungen des seriellen Ports aktiv
und schickt laufend Verbindungsaufbau-Pakete; ein Psion mit eingeschalteter
Fernverbindung wacht davon immer wieder auf. Deshalb startet :class:`Link` den
Daemon erst vor dem Gerätezugriff und beendet ihn danach wieder. Läuft bereits ein
``ncpd`` (Port erreichbar, z. B. manuell oder als Dienst gestartet), wird er benutzt
und nicht angefasst.

Konfiguration über Umgebungsvariablen: ``PSION_SERIAL`` (Default ``/dev/ttyUSB0``),
``PSION_BAUD`` (Default ``115200``), ``PSION_NCPD`` (Programm, Default ``ncpd``).
"""
from __future__ import annotations

import os
import socket
import subprocess
import time
from pathlib import Path

from .transport.base import TransportError

DEFAULT_SERIAL = "/dev/ttyUSB0"
DEFAULT_BAUD = "115200"
NCPD_PORT = 7501


def ncpd_listening(port: int = NCPD_PORT, host: str = "127.0.0.1") -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.5):
            return True
    except OSError:
        return False


class Link:
    """Context-Manager: ``ncpd`` starten, falls keiner läuft; beim Verlassen beenden."""

    def __init__(self, serial: str | None = None, baud: str | None = None, port: int = NCPD_PORT,
                 executable: str | None = None, start_timeout: float = 10.0):
        self.serial = serial or os.environ.get("PSION_SERIAL", DEFAULT_SERIAL)
        self.baud = baud or os.environ.get("PSION_BAUD", DEFAULT_BAUD)
        self.port = port
        self.executable = executable or os.environ.get("PSION_NCPD", "ncpd")
        self.start_timeout = start_timeout
        self.process: subprocess.Popen | None = None

    @property
    def started_here(self) -> bool:
        return self.process is not None

    def __enter__(self) -> "Link":
        if ncpd_listening(self.port):
            return self
        if not Path(self.serial).exists():
            raise TransportError(f"serieller Adapter {self.serial} nicht gefunden (PSION_SERIAL setzen?)")
        cmd = [self.executable, "-d", "-s", self.serial, "-b", self.baud, "-p", f"127.0.0.1:{self.port}"]
        try:
            self.process = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                            stderr=subprocess.DEVNULL, start_new_session=True)
        except OSError as exc:
            raise TransportError(f"ncpd konnte nicht gestartet werden: {exc}") from exc
        deadline = time.monotonic() + self.start_timeout
        while time.monotonic() < deadline:
            rc = self.process.poll()
            if rc is not None:
                self.process = None
                raise TransportError(f"ncpd beendete sich sofort (rc={rc}); "
                                     f"Adapter {self.serial} belegt oder keine Berechtigung?")
            if ncpd_listening(self.port):
                return self
            time.sleep(0.1)
        self._stop()
        raise TransportError(f"ncpd meldet sich nicht auf Port {self.port}")

    def __exit__(self, *exc) -> None:
        self._stop()

    def _stop(self) -> None:
        if self.process is None:
            return
        self.process.terminate()
        try:
            self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait()
        self.process = None
