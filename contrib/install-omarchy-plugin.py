#!/usr/bin/env python3
"""Install the Psion widget and add it to the existing Omarchy bar."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
from datetime import datetime


def main():
    repo = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config-dir", type=Path, default=Path.home() / ".config/omarchy")
    parser.add_argument("--python", type=Path, default=repo / ".venv/bin/python")
    args = parser.parse_args()
    python = str(args.python.absolute())  # Preserve the venv symlink.
    subprocess.run([python, "-c", "import psionsync.desktop"], cwd="/", check=True)
    shell = args.config_dir / "shell.json"
    config = json.loads(shell.read_text()) if shell.exists() else {"version": 1}
    layout = config.setdefault("bar", {}).setdefault("layout", {})
    widget = next((w for section in ("left", "center", "right") for w in layout.get(section, [])
                   if w.get("id") == "jf.psionsync"), None)
    if widget is None:
        widget = {"id": "jf.psionsync", "python": python}
        layout.setdefault("right", []).insert(0, widget)
    else:
        widget["python"] = python
    destination = args.config_dir / "plugins/jf.psionsync"
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    if destination.exists():
        backup = args.config_dir / "backups" / f"jf.psionsync-{stamp}"
        shutil.copytree(destination, backup)
    if shell.exists():
        shutil.copy2(shell, shell.with_name(f"shell.json.bak-{stamp}"))
    shutil.copytree(repo / "contrib/omarchy/jf.psionsync", destination, dirs_exist_ok=True)
    tmp = shell.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(config, indent=2, ensure_ascii=False) + "\n")
    os.replace(tmp, shell)
    print(f"Installiert: {destination}\nOmarchy lädt das Widget automatisch neu.")


if __name__ == "__main__":
    main()
