# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project state

Two-way sync between an Obsidian vault (`~/Documents/Obsidian/Vault`, Nextcloud-synced, 112 notes / 554 KB Markdown, no attachments) and a Psion 5mx over serial (`/dev/ttyUSB0`), plus a custom "Obsidian-light" app written in OPL that runs on the Psion. The sync is always initiated from this Linux machine (Omarchy / Arch).

**Phases 0–3 are done and verified on the device (sync tool; app with browser, viewer, tables, zoom, wikilinks, editor, search, new/delete, icon). Phase 4 (comfort: ncpd autostart via udev, Nextcloud check, search index) is next.** The source of truth is `docs/Psion 5mx Obsidian-Light - Plan.md` (German): scope, decisions, phases, gates, module layout and open questions — its "Übergabestand" section is the current handover. Read it before starting work and update it when decisions change. `docs/Psion 5mx Notiz Sync - Plan.md` is the *rejected* earlier approach (syncing into the built-in Notiz/Jotter app); it is kept only for its analysis of the Jotter format and as fallback knowledge — don't build on it.

Commands:
- Sync tool: Python ≥ 3.11, stdlib only at runtime. Setup `python -m venv .venv && .venv/bin/pip install -e . pytest`; tests `.venv/bin/pytest` (fast, no device; fake transport in `psionsync/transport/fake.py`). CLI `.venv/bin/psionsync [--vault DIR] [--state-dir DIR] [--fake-device DIR] status|sync [--apply]|push [--apply]|pull [--apply]|backup DEST`. Dry-run is the default; `status`/dry-run still write `C:\Vault\_psionsync.clock` for time calibration. Never run `sync --apply` against the real vault without checking `status` first.
- App: `app/build.sh` wraps OpoLua's `bin/compile.lua` (`--aif` for the icon) to produce `app/dist/PsiVault.app`; the OpoLua Qt runtime runs it on the desktop; `plpftp` copies it to `C:\System\Apps\PsiVault\` on the device.
- Device link: `ncpd -s /dev/ttyUSB0 -b 115200` (Psion: **Ctrl-T** opens "Kommunikation" on the German device, not Ctrl-L; turn the remote link on there), then `plpftp`. plpftp quirks (relative device paths for put/mkdir/rm, relative *local* paths for put/get, errors on stderr with exit code 0, no `touch`/`settime`) are in `docs/psion-notes.md` and encapsulated in `psionsync/transport/plp.py`.

## Core design decisions

- **Notes on the Psion are the Markdown files themselves**, under `C:\Vault\<same relative path>`, only re-encoded UTF-8 → CP1252 and LF → CRLF. No rich-text conversion, no database format. Folders and frontmatter survive unchanged. Only `*.md` is synced; attachments stay on the computer.
- The sync is a plain file sync with a state file (`~/.local/state/psionsync/state.json`, plus `snapshots/`, `trash/`, `unicode-backup/` next to it). Changes are detected by **hash against the state**, never by comparing timestamps across devices (clocks drift); timestamps only decide conflicts, after per-run calibration (plptools reports Psion file times +2 h; the engine measures the delta with a freshly written file). Both sides changed → newer wins, loser becomes `<path> (Konflikt Psion|Linux YYYY-MM-DD HHMM).md` in the vault; times within 60 s → conflict stays open. Dry-run is the default; `--apply` writes.
- 63 of 112 notes use characters outside CP1252 (`→`, box-drawing, `✅`, `⚠` …). They are **transliterated** on push via a fixed table in `sync/fsmap.py` (`→`→`->`, `─`→`-`, `✅`→`[x]` …), not replaced by `?`, and restored on pull only if that line was unchanged on the Psion (line-wise match against the snapshot of the last synced Unicode text). Filenames that can't be CP1252-encoded or contain EPOC-forbidden `? * | " < > :` are skipped and reported, never silently renamed.
- The app renders Markdown per line with `gPRINT` and font switches (headings Arial 18/15/13 bold, lists indented, bold/italic via `gSTYLE`, code in Courier, `[[wikilinks]]` resolved by filename against an index built from the tree). Editing is raw Markdown (first attempt: `dEDITMULTI`). The app never holds a file open outside read/save; saves are atomic (tmp + rename).

## Phases and gates

Strict order Phase 0 → 1 → 2 → 3; each gate must pass on the **real device**, not just in the emulator (OpoLua is an interpreter, not an ARM VM — fonts, speed, file locking differ).

- **Phase 0** toolchain: `plptools-git` (AUR), full device backup, byte-identical get/put roundtrip, OPL hello-world running on the device. Also settles filename rules (umlauts, forbidden chars, path length) and timestamp resolution.
- **Phase 1** `psionsync` (TDD against a fake directory transport; e2e against the device).
- **Phase 2** app browser + viewer + wikilinks.
- **Phase 3** app editor + search.
Phases 1 and 2 are independent and may run in parallel after Gate 0.

## Device safety rules

- Full backup (`plpbackup` or recursive `plpftp`) before the first write of any new kind to the device.
- `psionsync` writes **only** under `C:\Vault\`; the app writes only under `C:\Vault\` and its own `C:\System\Apps\PsiVault\`.
- Abort on any transport error; update state only for files that were actually transferred.
- Findings about OPL/EPOC quirks and emulator-vs-device differences go to `docs/psion-notes.md`.

## Layout

```
psionsync/            transport/{base,plp,fake}.py, sync/{fsmap,state,engine}.py, backup.py, cli.py  (done)
app/src/main.opl      single file: index, events, browser, viewer/markdown/tables, links, search, editor
app/icon/             icon BMPs + PsiVault.mbm (built by tools/make_mbm.lua)
app/build.sh, app/dist/ (gitignored)
tests/                test_{fsmap,state,engine,plp,cli}.py, conftest.py (Env helper), fixtures/vault/
tools/                throwaway scripts (backup_device.py superseded by `psionsync backup`, smoke_app.lua)
docs/                 plans, psion-notes.md
```
