"""ncpd-Lebenszyklus mit einem Fake-ncpd (Python-Skript, das nur den Port öffnet)."""
import os
import socket
import subprocess
import sys
import textwrap

import pytest

from psionsync.link import Link, ncpd_listening
from psionsync.transport.base import TransportError

FAKE_NCPD = textwrap.dedent("""\
    import os, socket, sys, time
    if os.environ.get("FAKE_NCPD_FAIL"):
        sys.exit(3)
    host, port = sys.argv[sys.argv.index("-p") + 1].split(":")
    s = socket.socket(); s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind((host, int(port))); s.listen()
    while True:
        time.sleep(1)
    """)


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def fake_ncpd(tmp_path, monkeypatch):
    script = tmp_path / "ncpd"
    script.write_text(f"#!{sys.executable}\n{FAKE_NCPD}")
    script.chmod(0o755)
    serial = tmp_path / "ttyUSB0"
    serial.touch()
    monkeypatch.setenv("PSION_NCPD", str(script))
    monkeypatch.setenv("PSION_SERIAL", str(serial))
    monkeypatch.delenv("FAKE_NCPD_FAIL", raising=False)
    return script, serial


def test_starts_ncpd_and_stops_it_afterwards(fake_ncpd):
    port = free_port()
    with Link(port=port) as link:
        assert link.started_here
        assert ncpd_listening(port)
        process = link.process
    assert process.poll() is not None
    assert not ncpd_listening(port)


def test_reuses_running_ncpd(fake_ncpd):
    port = free_port()
    with Link(port=port) as outer:
        with Link(port=port) as inner:
            assert not inner.started_here
        assert ncpd_listening(port), "innerer Link darf einen fremden ncpd nicht beenden"
    assert not ncpd_listening(port)


def test_ncpd_exiting_immediately_is_reported(fake_ncpd, monkeypatch):
    monkeypatch.setenv("FAKE_NCPD_FAIL", "1")
    with pytest.raises(TransportError, match="beendete sich sofort \\(rc=3\\)"):
        with Link(port=free_port()):
            pass


def test_missing_serial_adapter_is_reported(fake_ncpd, monkeypatch):
    monkeypatch.setenv("PSION_SERIAL", "/dev/does-not-exist")
    with pytest.raises(TransportError, match="nicht gefunden"):
        with Link(port=free_port()):
            pass


def test_ncpd_never_listening_is_stopped(fake_ncpd, tmp_path, monkeypatch):
    script = tmp_path / "ncpd"
    script.write_text(f"#!{sys.executable}\nimport time\nwhile True: time.sleep(1)\n")
    with pytest.raises(TransportError, match="meldet sich nicht"):
        with Link(port=free_port(), start_timeout=0.5):
            pass
    assert not any(p for p in subprocess.run(["pgrep", "-f", str(script)], capture_output=True).stdout.split())
