import os
import shutil
import time
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from psionsync.sync.engine import Engine
from psionsync.sync.state import State
from psionsync.transport.fake import FakeTransport

FIXTURES = Path(__file__).parent / "fixtures" / "vault"
# plptools meldet Psion-Zeiten 2 h zu spät (Phase 0); der Fake tut dasselbe.
OFFSET = timedelta(hours=2)


class Env:
    """Vault + Fake-Gerät + State in tmp_path, mit steuerbarer Rechnerzeit."""

    def __init__(self, tmp_path: Path):
        self.vault = tmp_path / "vault"
        shutil.copytree(FIXTURES, self.vault)
        self.device_root = tmp_path / "device"
        (self.device_root / "C").mkdir(parents=True)
        self.state_dir = tmp_path / "state"
        self.clock = datetime.now().replace(microsecond=0)
        self.transport = FakeTransport(self.device_root, clock_offset=OFFSET, now=self.now)

    def now(self):
        return self.clock

    def engine(self) -> Engine:
        return Engine(self.vault, self.transport, State.load(self.state_dir), now=self.now)

    def sync(self, mode="sync"):
        e = self.engine()
        plan = e.plan(mode)
        report = e.apply(plan)
        assert report.error is None, report.error
        return plan, report

    # -- Helfer für die Gegenseite --------------------------------------
    def device_path(self, rel: str) -> Path:
        return self.device_root / "C" / "Vault" / Path(rel)

    def device_read(self, rel: str) -> bytes:
        return self.device_path(rel).read_bytes()

    def device_write(self, rel: str, text: str, when: datetime | None = None):
        p = self.device_path(rel)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(text.replace("\n", "\r\n").encode("cp1252"))
        self.touch(p, when)

    def vault_write(self, rel: str, text: str, when: datetime | None = None):
        p = self.vault / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        self.touch(p, when)

    def touch(self, p: Path, when: datetime | None):
        when = when or self.clock
        os.utime(p, (when.timestamp(), when.timestamp()))

    def actions(self, plan):
        return {i.rel: i.action.value for i in plan.transfers}


@pytest.fixture
def env(tmp_path):
    return Env(tmp_path)
