# Obsidian ↔ Psion 5mx

Two-way sync of an Obsidian vault with a Psion 5mx over a serial connection,
the Psion app **PsiVault**, and an **Omarchy widget** for showing and starting
the sync.

Only Markdown notes are synced. On the Psion they live under `C:\Vault\` as
CP1252/CRLF files; on Linux they stay UTF-8. Attachments and hidden directories
such as `.obsidian` are not transferred.

## Setup and sync

Python ≥ 3.11 is required, plus `plptools` with `ncpd`/`plpftp` for the real
device. All commands below run in the repository directory.

```sh
python -m venv .venv
.venv/bin/pip install -e '.[dev]'
```

On a German Psion, **Ctrl-T** opens the communication settings (Ctrl-L on an
English device): turn the remote link on, 115200 baud. Then start the link on
Linux:

```sh
ncpd -s /dev/ttyUSB0 -b 115200
```

Alternatively, `bash contrib/install-ncpd-service.sh` installs a systemd user
service that waits for the USB adapter and restarts `ncpd` whenever the adapter
reappears. The default adapter path is set in `contrib/ncpd-psion`; other
adapters can be configured via `PSION_SERIAL` and `PSION_BAUD` in a systemd
service override. Do not run a manual `ncpd` and the service at the same time.

Default vault: `~/Documents/Obsidian/Vault`. Default state directory:
`~/.local/state/psionsync/`. Pass `--vault DIR` and `--state-dir DIR` before the
subcommand to use other directories.

```sh
# Local only, no connection to the device
.venv/bin/psionsync pending

# Check changes on both sides, then sync
.venv/bin/psionsync status
.venv/bin/psionsync sync --apply
```

Without `--apply`, `sync` is a dry run. `status` and dry runs only write the
time-calibration file on the Psion. Make a device backup before the first sync,
for example with `.venv/bin/psionsync backup /path/to/new-backup`
(`D:\SYS$ROM.BIN` is excluded by default). While a sync is running, do not let
Nextcloud, an editor or another sync run write to the same notes.

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
new notes and delete. Usage, building with OpoLua and installing on the device:
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
