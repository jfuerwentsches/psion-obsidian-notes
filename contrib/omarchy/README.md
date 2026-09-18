# Psion Sync for Omarchy

The `jf.psionsync` widget uses the same Omarchy building blocks as the Homelab
widget: a sync icon in the bar and a popup with header, status and actions.
A click opens the panel with:

- the number of new, changed and deleted local notes, plus the file list;
- the last sync result and hints about errors or conflicts;
- "Sync now" and "Refresh";
- an expandable live log directly in the panel.

The display refreshes every ten seconds, and every two seconds while the panel is
open or a sync is running. It does not query the device: even when it says the
local side is up to date, there may be changes on the Psion. "Sync now" checks the
connection, builds the plan and runs the two-way sync. The panel can be closed and
reopened meanwhile. The log stays visible until the next run or until the plugin is
reloaded. Restarting the shell during a sync can abort it; an incomplete run is then
shown as interrupted.

## Installation

Prerequisites: the project venv with `psionsync` installed, Omarchy with Quickshell,
and `plptools`. Setting up the venv and the device connection is described in the
[project README](../../README.md); `ncpd` is started by the sync itself and stopped
afterwards. All commands here run in the repository directory.

```sh
python3 contrib/install-omarchy-plugin.py
```

The installer backs up existing files, copies the plugin to
`~/.config/omarchy/plugins/jf.psionsync/` and adds it to the right section of the
bar in `~/.config/omarchy/shell.json`. Omarchy reloads automatically. The venv and
this repository must stay where they were installed from. Re-run the installer after
changes. `--python /absolute/path/bin/python` selects a different Python interpreter
that has `psionsync` installed.

Optional fields on the widget entry in `shell.json` are `vault` and `stateDir`
(absolute paths). The defaults are `~/Documents/Obsidian/Vault` and
`~/.local/state/psionsync`. The display stores its result there in
`desktop-result.json`. The separate lock prevents parallel **widget syncs**; do not
start an additional CLI sync at the same time. Nextcloud should not write vault
files meanwhile. The existing sync preserves conflicts and aborts on transport
errors; the display never starts syncs automatically.

To remove the widget, delete the `jf.psionsync` entry from the bar in `shell.json`.
