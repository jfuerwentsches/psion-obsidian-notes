"""Omarchy bridge: offline status, a device check (dry run) and an explicitly requested sync."""
from __future__ import annotations

import argparse
import fcntl
import json
import os
import sys
from datetime import datetime
from pathlib import Path

from .cli import DEFAULT_STATE, DEFAULT_VAULT, connect, pending, print_plan
from .sync.engine import Engine
from .sync.state import State


def lock(state_dir: Path):
    state_dir.mkdir(parents=True, exist_ok=True)
    handle = (state_dir / "desktop.lock").open("a")
    try:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        handle.close()
        return None
    return handle


def save_result(state_dir: Path, status: str, message: str) -> None:
    path = state_dir / "desktop-result.json"
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps({"status": status, "message": message,
                               "time": datetime.now().isoformat(timespec="seconds")}), encoding="utf-8")
    os.replace(tmp, path)


def status(vault: Path, state_dir: Path) -> dict:
    handle = lock(state_dir)
    if handle is None:
        return {"text": "Psion ↻", "status": "running", "tooltip": "Obsidian ↔ Psion: Sync läuft …"}
    try:
        info = pending(vault, state_dir) if vault.is_dir() else None
        if info is None:
            raise ValueError(f"Vault nicht gefunden: {vault}")
        path = state_dir / "desktop-result.json"
        result = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        kind = result.get("status", "idle")
        # A process that disappeared without finishing must not look successful.
        if kind == "running":
            kind = "error"
            result["message"] = "Letzter Lauf wurde unterbrochen. Erneut starten."
        count = info["pending"]
        text = "Psion !" if kind in ("error", "warning") else f"Psion ↑{count}" if count else "Psion ✓" if info["last_sync"] else "Psion ?"
        tooltip = (f"Obsidian ↔ Psion\n{count} lokale Änderung(en) · {len(info['skipped'])} übersprungen"
                   f"\nLetzter Sync-Stand: {info['last_sync'] or 'noch nie'}"
                   "\nPsion-Seite: „Psion prüfen“ (ändert nichts) oder Sync.")
        if result:
            tooltip += f"\nLetzter Widget-Lauf ({result.get('time', '?')}): {result['message']}"
        tooltip += "\nKlick: Sync-Details öffnen"
        return {"text": text, "status": kind, "tooltip": tooltip, "local": info, "result": result}
    finally:
        handle.close()


class Output:
    """Verlauf als Prosa (Terminal) oder als JSON-Zeilen (``--events``, Widget)."""

    def __init__(self, events: bool):
        self.events = events

    def emit(self, event: str, text: str, **data) -> None:
        if self.events:
            print(json.dumps({"event": event, "text": text, **data}, ensure_ascii=False), flush=True)
        else:
            print(text, flush=True)

    def plan(self, plan) -> None:
        if not self.events:
            print_plan(plan, "sync")
            return
        if plan.delta is not None:
            self.emit("note", f"Zeitkalibrierung: Psion-Zeiten werden um {plan.delta} korrigiert")
        for rel, reason in plan.skipped:
            self.emit("skipped", rel, rel=rel, reason=reason)
        for item in plan.items:
            self.emit("item", item.rel, action=item.action.value, rel=item.rel, reason=item.reason,
                      copy=item.conflict_copy)
        conflicts = sum(item.action.value.startswith("konflikt") for item in plan.items)
        self.emit("summary", f"{len(plan.transfers)} Übertragung(en) geplant, {len(plan.skipped)} übersprungen, "
                  f"{conflicts} Konflikt(e)", transfers=len(plan.transfers), skipped=len(plan.skipped),
                  conflicts=conflicts)


def run(args, apply: bool) -> int:
    """Widget-Lauf: ``apply=False`` prüft nur (Plan mit Psion-Seite), ``True`` synchronisiert."""
    what = "Sync" if apply else "Prüfung"
    out = Output(getattr(args, "events", False))
    handle = lock(args.state_dir)
    if handle is None:
        out.emit("error", "Ein Widget-Lauf läuft bereits.")
        return 1
    try:
        save_result(args.state_dir, "running", f"{what} läuft")
        if not args.vault.is_dir():
            raise ValueError(f"Vault nicht gefunden: {args.vault}")
        out.emit("phase", "Verbindung zum Psion wird aufgebaut …")
        with connect(args) as transport:
            out.emit("phase", "Änderungen auf beiden Seiten werden verglichen …")
            engine = Engine(args.vault, transport, State.load(args.state_dir))
            plan = engine.plan("sync")
            out.plan(plan)
            conflicts = sum(item.action.value.startswith("konflikt") for item in plan.items)
            if apply:
                if plan.items:
                    out.emit("phase", "Sync wird ausgeführt …")
                report = engine.apply(plan, progress=lambda item: out.emit(
                    "done", item.rel, action=item.action.value, rel=item.rel))
                if report.error:
                    raise RuntimeError(report.error)
                message = f"{len(report.done)} Schritt(e), {conflicts} Konflikt(e), {len(plan.skipped)} übersprungen."
            else:
                pulls = sum(item.action.value.endswith("pull") or item.action.value == "rm-vault" for item in plan.items)
                message = (f"Prüfung: {len(plan.transfers)} Übertragung(en) geplant, davon {pulls} vom Psion; "
                           f"{conflicts} Konflikt(e), {len(plan.skipped)} übersprungen. Nichts geändert.")
        status_ = "warning" if conflicts or plan.skipped else "success"
        save_result(args.state_dir, status_, message)
        out.emit("result", message, status=status_)
        return 0
    except (Exception, KeyboardInterrupt) as exc:
        message = str(exc) or f"{what} abgebrochen."
        save_result(args.state_dir, "error", message)
        out.emit("error", f"ABBRUCH: {message}")
        out.emit("note", "Kabel gesteckt und Fernverbindung am Psion (Strg-T) an?")
        return 1
    finally:
        handle.close()


def sync(args) -> int:
    return run(args, apply=True)


def check(args) -> int:
    return run(args, apply=False)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vault", type=Path, default=DEFAULT_VAULT)
    parser.add_argument("--state-dir", type=Path, default=DEFAULT_STATE)
    parser.add_argument("--fake-device", type=Path)
    parser.add_argument("command", choices=("status", "sync", "check"))
    parser.add_argument("--hold", action="store_true", help="Terminal nach dem Sync offen halten")
    parser.add_argument("--events", action="store_true", help="Verlauf als JSON-Zeilen (für das Widget)")
    args = parser.parse_args(argv)
    if args.command == "status":
        try:
            data = status(args.vault, args.state_dir)
        except Exception as exc:
            data = {"text": "Psion !", "status": "error", "tooltip": str(exc)}
        print(json.dumps(data, ensure_ascii=False))
        return 0
    code = check(args) if args.command == "check" else sync(args)
    if args.hold and sys.stdin.isatty():
        try:
            input("\nEnter schließt dieses Fenster …")
        except (EOFError, KeyboardInterrupt):
            pass
    return code


if __name__ == "__main__":
    sys.exit(main())
