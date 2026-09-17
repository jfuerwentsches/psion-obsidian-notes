# Obsidian ↔ Psion 5mx

Two-way sync of an Obsidian vault with a Psion 5mx over a serial connection,
the Psion app **PsiVault**, and an **Omarchy widget** for showing and starting
the sync.

Only Markdown notes are synced. On the Psion they live under `C:\Vault\` as
CP1252/CRLF files; on Linux they stay UTF-8. Attachments and hidden directories
such as `.obsidian` are not transferred.

## Requirements

- A Psion 5mx (or another EPOC R5 device) with its serial link cable and a
  USB-to-RS232 adapter. The Linux side works with any adapter that shows up as
  `/dev/ttyUSB*`.
- Linux with Python ≥ 3.11 and [plptools](https://github.com/plptools/plptools)
  (`ncpd` and `plpftp`). On Arch: `plptools-git` from the AUR; on Debian/Ubuntu:
  `apt install plptools`.
- Your user needs access to the serial device: group `uucp` on Arch, `dialout`
  on Debian/Ubuntu (`sudo usermod -aG uucp $USER`, then log in again).
- An Obsidian vault of Markdown files. Nothing Obsidian-specific is required;
  any folder of `.md` files works.
- The Omarchy widget additionally needs [Omarchy](https://omarchy.org) with
  Quickshell. Sync and app work without it.

Note: the CLI messages and the widget UI are currently in German; the code,
this README and the app README are in English.

## Setup and sync

All commands below run in the repository directory.

```sh
git clone https://github.com/jfuerwentsches/psion-obsidian-notes.git
cd psion-obsidian-notes
python -m venv .venv
.venv/bin/pip install -e '.[dev]'
```

On the Psion, open the communication settings (**Ctrl-L** on an English
device, **Ctrl-T** on a German one, or via the System screen's Tools menu):
turn the link on, cable, 115200 baud. Then start the link daemon on Linux:

```sh
ncpd -s /dev/ttyUSB0 -b 115200
plpftp ls 'C:\'      # should list the Psion's C: drive
```

Alternatively, `bash contrib/install-ncpd-service.sh` installs a systemd user
service that waits for the USB adapter and restarts `ncpd` whenever the adapter
reappears. The default adapter path is `/dev/ttyUSB0`; a stable
`/dev/serial/by-id/...` path or another baud rate can be set with
`PSION_SERIAL` and `PSION_BAUD` in a systemd service override
(`systemctl --user edit ncpd-psion.service`). Do not run a manual `ncpd` and
the service at the same time.

Default vault: `~/Documents/Obsidian/Vault`. Default state directory:
`~/.local/state/psionsync/`. Pass `--vault DIR` and `--state-dir DIR` before the
subcommand to use other directories.

First sync:

```sh
# 1. Back up the device (read-only; D:\SYS$ROM.BIN is excluded by default)
.venv/bin/psionsync backup ~/psion-backup/$(date +%F)

# 2. Look at the plan. On a fresh device every note is a push to C:\Vault\
.venv/bin/psionsync status

# 3. Apply it
.venv/bin/psionsync sync --apply
```

`C:\Vault\` and its subfolders are created on the device as needed. Later runs
are the same `status` / `sync --apply` pair; `pending` counts local changes
since the last sync without talking to the device. Notes changed on both sides
are resolved by timestamp, and the losing version is kept in the vault as
`<name> (Konflikt Psion|Linux YYYY-MM-DD HHMM).md`.

Without `--apply`, `sync` is a dry run. `status` and dry runs only write the
time-calibration file on the Psion. While a sync is running, do not let
Nextcloud, an editor or another sync run write to the same notes. Filenames
that cannot be encoded in CP1252 or contain characters EPOC forbids
(`? * | " < > :`) are skipped and reported by `status`; rename them in the
vault.

## Omarchy widget

```sh
python3 contrib/install-omarchy-plugin.py
```

A sync icon in the bar opens a panel in the style of the Homelab widget: local
changes, last sync result, a sync button and a live log. Changes on the Psion
are only checked when a sync runs. The installer backs up existing
configuration files. Details: [widget README](contrib/omarchy/README.md).

## PsiVault app

Browser, Markdown viewer with tables and wikilinks, editor, full-text search,
new notes and delete. The app is not required for syncing: the notes are plain
text files on the Psion and can also be opened with the built-in Word app.
Usage, building with OpoLua and installing on the device:
[app README](app/README.md). The
[icon package](docs/psion_5mx_appicon_package/README.md) contains the graphic
sources; the Linux build does not need BMCONV.

## Tests and technical details

```sh
# Python sync and widget bridge, without device or OpoLua
.venv/bin/pytest --ignore=tests/test_app.py

# Including the OPL app tests, with an existing OpoLua checkout
OPOLUA_DIR=/tmp/psivault-opolua REQUIRE_OPL_TESTS=1 .venv/bin/pytest
```

Last local test run (2026-09-17): **77 Python tests passed**. In the separate
full run, **9 OPL app tests failed** (eight frontmatter timeouts and one search
index test); the full suite is currently not green. Coverage, CI and
limitations: [test documentation](docs/testing.md).

The project plan and the device notes are written in German:

- [Project plan and handover state](docs/Psion%205mx%20Obsidian-Light%20-%20Plan.md)
- [Device and transport notes](docs/psion-notes.md)
