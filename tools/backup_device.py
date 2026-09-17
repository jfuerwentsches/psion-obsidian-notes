"""Phase-0 file backup: read C: and D: through plpftp, never write to device.

Run with a NEW absolute destination directory. A manifest is written only after
all files have transferred with the size reported by the directory listing.
This is a file backup, not a disk image; close device applications first.
"""
import hashlib
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys


def command(*args):
    result = subprocess.run(
        [b"plpftp", *(arg.encode("cp1252") for arg in args)],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        env={**os.environ, "LC_ALL": "C"}, timeout=3600,
    )
    output = result.stdout.decode("cp1252")
    if result.returncode or result.stderr or "Error:" in output or "syntax error" in output:
        raise RuntimeError((result.stderr.decode("cp1252") + output).strip())
    return output


def backup(destination, skip_rom=False):
    destination.mkdir(parents=True, exist_ok=False)
    manifest = []
    entry = re.compile(r"^([d-][rwhsa-]{9})\s+(\d+) (.{24}) (.+)$")

    def walk(remote, local):
        local.mkdir(exist_ok=True)
        listing = command("ls", remote)
        for line in listing.splitlines():
            match = entry.fullmatch(line)
            if not match:
                raise RuntimeError(f"Unrecognized listing: {line!r}")
            attributes, size, timestamp, name = match.groups()
            if name in (".", "..") or any(c in name for c in '/\\\r\n'):
                raise RuntimeError(f"Unsafe filename: {name!r}")
            target = local / name
            source = remote + name
            if skip_rom and source.upper() == "D:\\SYS$ROM.BIN":
                print(f"Skipping {source}: already backed up locally by user", flush=True)
                continue
            if attributes.startswith("d"):
                walk(source + "\\", target)
            else:
                print(f"Reading {source} ({size} bytes)", flush=True)
                previous = Path.cwd()
                try:
                    os.chdir(local)
                    # ASCII temporary name avoids interpreting remote filename bytes
                    # as a local UTF-8 filename. The final rename is local only.
                    command("get", source, "transfer.partial")
                finally:
                    os.chdir(previous)
                temporary = local / "transfer.partial"
                if temporary.stat().st_size != int(size):
                    raise RuntimeError(f"Size mismatch: {source}")
                digest = hashlib.sha256(temporary.read_bytes()).hexdigest()
                temporary.rename(target)
                manifest.append(dict(path=source, size=int(size), sha256=digest,
                                     timestamp=timestamp, attributes=attributes))

    for drive in ("C", "D"):
        walk(drive + ":\\", destination / drive)
    (destination / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False))
    if skip_rom:
        (destination / "exclusions.json").write_text(json.dumps({
            "D:\\SYS$ROM.BIN": "Excluded at user request: already available locally"
        }, indent=2))
    print(f"Complete: {len(manifest)} files, {sum(f['size'] for f in manifest)} bytes", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--skip-rom", action="store_true")
    args = parser.parse_args()
    backup(args.destination.resolve(), args.skip_rom)
