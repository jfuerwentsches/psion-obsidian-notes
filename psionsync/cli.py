"""``psionsync status|sync|push|pull [--apply] | backup ZIEL``"""
from __future__ import annotations

import argparse
import json
import sys
import time
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path

from .backup import backup
from .sync.engine import Engine, Plan
from .sync.state import State
from .transport.base import TransportError

DEFAULT_VAULT = Path.home() / "Documents" / "Obsidian" / "Vault"
DEFAULT_STATE = Path.home() / ".local" / "state" / "psionsync"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="psionsync", description="Obsidian-Vault <-> Psion 5mx (C:\\Vault)")
    p.add_argument("--vault", type=Path, default=DEFAULT_VAULT, help=f"Vault-Verzeichnis (Default {DEFAULT_VAULT})")
    p.add_argument("--state-dir", type=Path, default=DEFAULT_STATE, help=f"State-Verzeichnis (Default {DEFAULT_STATE})")
    p.add_argument("--fake-device", type=Path, metavar="DIR",
                   help="statt plpftp ein lokales Verzeichnis als Gerät verwenden (Entwicklung)")
    sub = p.add_subparsers(dest="command", required=True)
    for name, help_ in (("status", "Plan anzeigen, nichts ändern"),
                        ("sync", "Zwei-Wege-Sync (Dry-Run ohne --apply)"),
                        ("push", "Vault-Fassung erzwingen (Dry-Run ohne --apply)"),
                        ("pull", "Psion-Fassung erzwingen (Dry-Run ohne --apply)")):
        s = sub.add_parser(name, help=help_)
        if name != "status":
            s.add_argument("--apply", action="store_true", help="Plan wirklich ausführen")
    pe = sub.add_parser("pending", help="lokale Änderungen seit dem letzten Sync zählen (ohne Gerät)")
    pe.add_argument("--json", action="store_true", help="maschinenlesbar")
    b = sub.add_parser("backup", help="alle Dateien von C: und D: sichern (nur lesend)")
    b.add_argument("destination", type=Path, help="neues Zielverzeichnis")
    b.add_argument("--with-rom", action="store_true", help="D:\\SYS$ROM.BIN mitsichern (~10 MB)")
    return p


# Nach dem Start von ncpd braucht der Psion einen Moment zum Aufwachen und Verbinden.
CONNECT_TIMEOUT = 20.0


@contextmanager
def connect(args):
    """Transport für die Dauer eines Laufs; startet ``ncpd`` bei Bedarf (siehe link.py)."""
    if args.fake_device:
        from .transport.fake import FakeTransport
        args.fake_device.joinpath("C").mkdir(parents=True, exist_ok=True)
        yield FakeTransport(args.fake_device, clock_offset=timedelta(hours=2))
        return
    from .link import Link
    from .transport.plp import PlpTransport
    with Link() as link:
        t = PlpTransport()
        deadline = time.monotonic() + (CONNECT_TIMEOUT if link.started_here else 0)
        while True:
            try:
                t.check_connection()
                break
            except TransportError:
                if time.monotonic() >= deadline:
                    raise
                time.sleep(1)
        yield t


def print_plan(plan: Plan, mode: str) -> None:
    if plan.delta is not None:
        print(f"Zeitkalibrierung: Psion-Zeiten werden um {plan.delta} korrigiert")
    for rel, reason in plan.skipped:
        print(f"{'übersprungen':<14} {rel}  ({reason})")
    for item in plan.items:
        print(item)
    for rel in plan.device_extra:
        side = "nur auf Psion" if mode == "push" else "nur im Vault"
        print(f"{side:<14} {rel}")
    n = len(plan.transfers)
    print(f"{n} Übertragung(en) geplant, {len(plan.skipped)} übersprungen, "
          f"{sum(1 for i in plan.items if i.action.value.startswith('konflikt'))} Konflikt(e)")


def pending(vault: Path, state_dir: Path) -> dict:
    """Vault-seitige Änderungen gegen den State, ohne Gerätezugriff (für Statusanzeigen)."""
    from .sync.state import State
    state = State.load(state_dir)
    engine = Engine(vault, None, state)  # type: ignore[arg-type]  # nur scan_vault
    files, skipped = engine.scan_vault()
    changed = [rel for rel, f in files.items() if (s := state.get(rel)) and s.vault_hash != f.hash]
    new = [rel for rel in files if state.get(rel) is None]
    deleted = [rel for rel in state.files if rel not in files]
    return {"last_sync": state.last_sync, "generation": state.generation, "tracked": len(state.files),
            "changed": changed, "new": new, "deleted": deleted, "skipped": [rel for rel, _ in skipped],
            "pending": len(changed) + len(new) + len(deleted)}


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "pending":
        if not args.vault.is_dir():
            print(f"Vault nicht gefunden: {args.vault}", file=sys.stderr)
            return 2
        info = pending(args.vault, args.state_dir)
        if args.json:
            print(json.dumps(info, ensure_ascii=False))
        else:
            print(f"Letzter Sync: {info['last_sync'] or 'nie'}; {info['tracked']} Notizen im State")
            for label, key in (("geändert", "changed"), ("neu", "new"), ("gelöscht", "deleted")):
                for rel in info[key]:
                    print(f"{label:<10} {rel}")
            print(f"{info['pending']} lokale Änderung(en) seit dem letzten Sync")
        return 0
    if args.command != "backup" and not args.vault.is_dir():
        print(f"Vault nicht gefunden: {args.vault}", file=sys.stderr)
        return 2
    try:
        with connect(args) as transport:
            if args.command == "backup":
                n = backup(transport, args.destination, skip_rom=not args.with_rom)
                print(f"Fertig: {n} Dateien in {args.destination}")
                return 0
            mode = "sync" if args.command == "status" else args.command
            engine = Engine(args.vault, transport, State.load(args.state_dir))
            plan = engine.plan(mode)
            print_plan(plan, mode)
            if args.command == "status" or not args.apply:
                if plan.transfers:
                    print("Dry-Run. Mit --apply ausführen.")
                return 0
            if not plan.transfers and not plan.items:
                return 0
            started = datetime.now()
            report = engine.apply(plan)
            print(f"{len(report.done)} Schritt(e) ausgeführt in {(datetime.now() - started).seconds}s")
            if report.error:
                print(f"ABBRUCH: {report.error}", file=sys.stderr)
                print("State wurde für die abgeschlossenen Schritte gespeichert.", file=sys.stderr)
                return 1
            return 0
    except TransportError as exc:
        print(f"Transportfehler: {exc}", file=sys.stderr)
        print("Ist der Psion eingeschaltet, das Kabel gesteckt und die Fernverbindung an (Strg-T)? "
              "Adapter: PSION_SERIAL (Default /dev/ttyUSB0).", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
