"""Omarchy bridge: offline status and an explicitly requested sync."""
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
            result["message"] = "Letzter Sync wurde unterbrochen. Erneut starten."
        count = info["pending"]
        text = "Psion !" if kind in ("error", "warning") else f"Psion ↑{count}" if count else "Psion ✓" if info["last_sync"] else "Psion ?"
        tooltip = (f"Obsidian ↔ Psion\n{count} lokale Änderung(en) · {len(info['skipped'])} übersprungen"
                   f"\nLetzter Sync-Stand: {info['last_sync'] or 'noch nie'}"
                   "\nPsion-Änderungen werden erst beim Sync geprüft.")
        if result:
            tooltip += f"\nLetzter Widget-Lauf ({result.get('time', '?')}): {result['message']}"
        tooltip += "\nKlick: Sync-Details öffnen"
        return {"text": text, "status": kind, "tooltip": tooltip, "local": info, "result": result}
    finally:
        handle.close()


def sync(args) -> int:
    handle = lock(args.state_dir)
    if handle is None:
        print("Ein Widget-Sync läuft bereits.")
        return 1
    try:
        save_result(args.state_dir, "running", "Sync läuft")
        if not args.vault.is_dir():
            raise ValueError(f"Vault nicht gefunden: {args.vault}")
        print("Obsidian ↔ Psion – Verbindung und Änderungen prüfen …", flush=True)
        with connect(args) as transport:
            engine = Engine(args.vault, transport, State.load(args.state_dir))
            plan = engine.plan("sync")
            print_plan(plan, "sync")
            print("\nSync wird ausgeführt …", flush=True)
            report = engine.apply(plan)
        if report.error:
            raise RuntimeError(report.error)
        conflicts = sum(item.action.value.startswith("konflikt") for item in plan.items)
        message = f"{len(report.done)} Schritt(e), {conflicts} Konflikt(e), {len(plan.skipped)} übersprungen."
        save_result(args.state_dir, "warning" if conflicts or plan.skipped else "success", message)
        print(message)
        return 0
    except (Exception, KeyboardInterrupt) as exc:
        message = str(exc) or "Sync abgebrochen."
        save_result(args.state_dir, "error", message)
        print(f"ABBRUCH: {message}\nPsion einschalten und Fernverbindung (Strg-T) prüfen.", file=sys.stderr)
        return 1
    finally:
        handle.close()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vault", type=Path, default=DEFAULT_VAULT)
    parser.add_argument("--state-dir", type=Path, default=DEFAULT_STATE)
    parser.add_argument("--fake-device", type=Path)
    parser.add_argument("command", choices=("status", "sync"))
    parser.add_argument("--hold", action="store_true", help="Terminal nach dem Sync offen halten")
    args = parser.parse_args(argv)
    if args.command == "status":
        try:
            data = status(args.vault, args.state_dir)
        except Exception as exc:
            data = {"text": "Psion !", "status": "error", "tooltip": str(exc)}
        print(json.dumps(data, ensure_ascii=False))
        return 0
    code = sync(args)
    if args.hold and sys.stdin.isatty():
        try:
            input("\nEnter schließt dieses Fenster …")
        except (EOFError, KeyboardInterrupt):
            pass
    return code


if __name__ == "__main__":
    sys.exit(main())
