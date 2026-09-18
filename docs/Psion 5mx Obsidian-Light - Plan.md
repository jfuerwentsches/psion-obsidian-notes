---
erstellt: 2026-09-17
status: in-arbeit
ersetzt: "[[Psion 5mx Notiz Sync - Plan]]"
tags: [psion, obsidian, sync, opl, plan]
---

> Überarbeiteter Plan vom 2026-09-17, erstellt auf dem Zielrechner (Omarchy / Arch Linux, Psion am `/dev/ttyUSB0`).
> Ersetzt den Notiz-Sync-Plan. Kernentscheidung: **eigene OPL-App statt Notiz**, Notizen als Markdown-Dateien im Ordnerbaum auf dem Psion.

# Obsidian ↔ Psion 5mx: Dateisync + eigene „Obsidian-light“-App in OPL

## Übergabestand – 2026-09-17

### Omarchy-Sync-Widget

- `contrib/omarchy/jf.psionsync/`: Sync-Symbol in der Leiste, per Klick ein Panel
  im Stil des Homelab-Widgets mit lokalen Änderungen, letztem Sync-Stand,
  Sync-Button und Live-Verlauf. Keine periodischen
  Gerätezugriffe; Psion-seitige Änderungen werden erst beim Sync geprüft.
- `psionsync/desktop.py`: Status, Sperre gegen parallele Widget-Starts und
  persistentes Ergebnis (einschließlich Fehlern, Abbrüchen und Konflikten).
- Installation und Bedienung: [contrib/omarchy/README.md](../contrib/omarchy/README.md).
  Die Sperre umfasst nur Widget-Läufe; CLI nicht gleichzeitig verwenden.

### Review-Nacharbeit und Tests

- Sync prüft vor jedem geplanten Schritt beide Inhalte erneut. Abweichungen seit
  der Planung führen zum Abbruch vor diesem Schritt; bereits erledigte Schritte
  bleiben im State. Keine gemeinsame Schreibsperre: siehe Grenzen in
  [testing.md](testing.md).
- Konfliktkopien und Unicode-Backups überschreiben keine unterschiedlichen
  vorhandenen Fassungen; bei Namenskollisionen wird eine Nummer ergänzt.
- Unicode-Rückgewinnung berücksichtigt ASCII-Kollisionen und zusätzliche
  doppelte Zeilen; Verluste einzelner Unicode-Zeilen lösen eine Sicherung aus.
- Viewer-Endlosschleife bei übersprungenen Zeilen ≥ 255 Zeichen ohne Zeilenende
  im Lesefenster (Frontmatter, Code-Zäune, Tabellentrenner) am 2026-09-18 erneut
  behoben: `laymore:` rückt mit `eol&:` bis hinter das nächste `LF` vor, statt um
  `adv&=0`. Der Suchindex-Test wurde durch einen Test der Datei-für-Datei-Suche
  ersetzt (Index ist verworfen, siehe psion-notes). **Der neue Build ist noch nicht
  auf dem Gerät installiert.**
- Nach Push nur betroffene Geräteverzeichnisse neu einlesen.
- **97 Tests lokal bestanden (2026-09-18):** 82 Python-Tests und 15 OPL-Tests mit
  frischem Build in temporären Verzeichnissen, Ergebnisprüfungen und Prozess-Timeouts.
- CI: `.gitlab-ci.yml` und `.github/workflows/ci.yml` führen beide Suiten aus
  (OpoLua-Commit festgelegt).
- Ausführen: `OPOLUA_DIR=/tmp/psivault-opolua REQUIRE_OPL_TESTS=1 .venv/bin/pytest`.
  Weitere Hinweise: [testing.md](testing.md).

### Bisheriger Geräte- und Funktionsstand

**Gate 0–3 bestanden (2026-09-17).** Echter Vault synchronisiert; PsiVault (Browser, Viewer mit Tabellen/Zoom, Wikilinks, Editor, Suche, Anlegen/Löschen, Icon; `C:\System\Apps\PsiVault\PsiVault.app`, ~23 KB) läuft auf dem Gerät. Gate 3 am Gerät: Editor-Änderung (Ausschnitt in 48-KB-Notiz) + neue Notiz → `sync --apply` → Vault mit Unicode-Wiederherstellung; Vault-Änderung → Psion transliteriert; externe Änderung während der Bearbeitung → Warnung + Kopie `Test (PsiVault 2026-09-17 2123).md` → per Sync im Vault. Nächster Schritt: Phase 4 (vor allem `ncpd`-Autostart per udev, weil der USB-Adapter sich beim Abschalten des Psion neu anmeldet). Detailprotokoll: [psion-notes.md](psion-notes.md).

### Erledigt und geprüft

- Serielle Verbindung mit `ncpd`/`plpftp` bei 115200 Baud funktioniert; Gerät: deutscher Series 5mx, ROM 1.05(319).
- Dateibackup von C: und D: **vor Installation** abgeschlossen (lokal unter `~/psion-backup/2026-09-17-ohne-rom`), 44 Dateien, 106.090 Bytes. Größen und SHA-256-Prüfsummen gegen `manifest.json` lokal geprüft.
- **Benutzerentscheidung:** `D:\SYS$ROM.BIN` ausdrücklich auslassen, weil bereits lokal vorhanden; Ausnahme steht in `exclusions.json`. Kein erneuter ROM-Download nötig. Die alten Backup-Verzeichnisse `2026-09-17-phase0` und `2026-09-17-phase0-complete` sind abgebrochene Teilstände, keine vollständigen Sicherungen.
- OpoLua-Compiler und Qt-Runtime gebaut. Kompilierte Test-App liest eine CP1252/CRLF-Datei; automatischer Laufzeittest erfolgreich. Qt wurde geöffnet, eine gesonderte visuelle Qt-Abnahme ist nicht dokumentiert.
- Auf dem Psion installiert: `C:\System\Apps\PsiVault\PsiVault.app` (433 Bytes), `PsiVault.aif` (73 Bytes), `C:\Vault\Willkommen.md` (79 Bytes). Alle drei Dateien bytegleich zurückgelesen.
- PsiVault auf dem Gerät gestartet; Benutzer bestätigt Willkommenstext, Darstellung und `ä ö ü Ä Ö Ü ß` als korrekt. Beliebige Taste beendet den Lesetest.
- Umlaut-Dateipfade getestet: `C:\Vault\Entwürfe\Gemüse-Lasagne.md` angelegt, gelistet und bytegleich zurückgelesen (inzwischen wieder gelöscht).
- Echter Vault (112 `.md`, längster Gerätepfad 104 Zeichen, Tiefe bis 5) ist seit 2026-09-17 auf dem Psion; State in `~/.local/state/psionsync/` (62 Unicode-Snapshots). Die einzige Notiz mit `?` im Namen wurde im Vault umbenannt (`… or is it.md`).
- Optionaler Phase-1-Rest: Nextcloud-Statusprüfung vor dem Sync; `ren` im Transport geprüft, aber ungenutzt.
- **Pfadgrenzen:** verboten sind `? * | " < > :`; `& ( ) , ¥ –`, Umlaute, Leerzeichen sind ok. Pfad bis 253 Zeichen, Name bis 200 ok. `ren`/`rm`/`rmdir` funktionieren, ebenfalls nur relativ.
- **Zeitstempel geklärt:** Geräteuhr stimmt (~3 min hinter dem Rechner). plptools zeigt Dateizeiten (`ls`/`gtime`) **+2 h** und `machinfo` **+1 h** zu spät, weil es die als Ortszeit gespeicherten EPOC-Zeiten für UTC hält. `touch`/`settime` deshalb nie verwenden. Der Sync kalibriert das Delta pro Lauf über eine `put`-Datei (siehe Phase 1).
- **Durchsatz:** 8,8 KB/s put, 8,7 KB/s get bei 115200; ~0,5 s Fixaufwand pro plpftp-Aufruf → Vollsync ≈ 2 min.

### Vorhandener Code und Wiederaufnahme

- **`psionsync/`** (Phase 1, fertig): `transport/base.py` (Protokoll, `walk`), `transport/plp.py` (plpftp-Wrapper), `transport/fake.py` (Verzeichnis als Gerät), `sync/fsmap.py`, `sync/state.py`, `sync/engine.py`, `backup.py`, `cli.py`. Tests in `tests/` (`.venv/bin/pytest`), Fixture-Vault `tests/fixtures/vault/`. Installation: `python -m venv .venv && .venv/bin/pip install -e . pytest`. `tools/backup_device.py` ist durch `psionsync backup ZIEL` abgelöst.
- Abweichungen vom ursprünglichen Entwurf: auf dem Psion gelöschte Notizen werden im Vault nicht hart gelöscht, sondern nach `~/.local/state/psionsync/trash/` verschoben; Unicode-Originale, die beim Pull verloren gehen, landen in `unicode-backup/`; Snapshots in `snapshots/<vault_hash>.md`. Änderungserkennung auf dem Psion: Größe+mtime gegen den *eigenen* State-Eintrag entscheiden, ob heruntergeladen und gehasht wird (kein Vergleich zwischen den Geräten). Offene Konflikte (Zeiten < 60 s auseinander oder keine Kalibrierung) legen die Psion-Fassung als Kopie ab und bleiben ohne State-Update stehen. Konfliktkopien sind normale Notizen und werden beim nächsten Lauf gepusht. `status`/Dry-Run schreiben `C:\Vault\_psionsync.clock` zur Kalibrierung, sonst nichts. Nextcloud-Statusprüfung noch nicht umgesetzt.
- `app/src/main.opl` (Phase 2, eine Datei statt LOADM-Module): Index aller `.md` per rekursivem `DIR$` beim Start; Browser leitet Ordner aus dem Index ab; Viewer lädt die Datei in einen `ALLOC`-Puffer, bricht lazy per `gTWIDTH` um (Quellzeilen > 255 Zeichen in Fenstern), rendert `#`-Überschriften (Arial 18/15/13 fett), Listen mit hängendem Einzug, `> `-Zitate, `---`, Codeblöcke/`Inline-Code` in Courier, `**fett**`, eingeklapptes Frontmatter; `[[Links]]` unterstrichen, Tab/Enter, Zurück-Stack. Temporäre Entwicklungs-UID `0x0F015105`. Bedienung in `app/README.md`.
- `app/build.sh`: kompiliert APP/AIF. `tools/smoke_app.lua`: headless Tastenskript-Test bzw. Stresstest pro Notiz (alle 112 echten Notizen bestanden).
- `tools/backup_device.py`: rekursive Dateisicherung, neue Zielverzeichnisse erforderlich, optional `--skip-rom`. Phase-0-Hilfsskript, noch kein fertiger Sync-Transport.
- `.gitignore` schließt `app/dist/` und Python-Caches aus. Beim Übergabestand sind Projektdateien **noch unversioniert/uncommitted**; es wurde kein Commit erstellt.
- OpoLua liegt vorläufig unter `/tmp/psivault-opolua`, Commit `6bb10d5b60ce94abea20b9e1f0abb61d33218649`, einschließlich Submodulen. `/tmp` ist nicht dauerhaft; bei Verlust denselben Stand erneut beziehen und bauen.

Vom Repository-Verzeichnis aus:

```sh
OPOLUA_DIR=/tmp/psivault-opolua bash app/build.sh
lua tools/smoke_app.lua /tmp/psivault-opolua "$PWD/app/dist"
```

Verbindung vor Wiederaufnahme prüfen; keine alten Prozess- oder Tool-Session-IDs voraussetzen. Falls noch kein Daemon läuft: `ncpd -d -s /dev/ttyUSB0 -b 115200`. Fernverbindung am Psion über Strg-T einschalten. In der bisherigen Sandbox waren Gerät und lokale ncpd-Verbindung nur außerhalb der Sandbox zugänglich; am System wurden dafür keine Berechtigungen geändert.

Vor zukünftigen Backups Dokument-Apps wirklich **beenden**, nicht nur zur Systemansicht wechseln. `plpftp ps` sollte keine Dokument-Apps mehr zeigen; sonst können Dateien wie `Contacts.cdb` mit „in use“ gesperrt sein.

### Verifizierte Abweichungen vom ursprünglichen Plan

- Installiertes `plptools-git` enthält **kein `plpbackup`**. Das Backup-Hilfsskript nutzt rekursiv `plpftp`.
- Kein `plpftp ls -R`: Baum selbst rekursiv über `ls` einlesen.
- Einzelbefehle als getrennte Argumente übergeben, z. B. `plpftp ls 'C:\'`, nicht als einen zusammengefassten Befehlsstring.
- `ls`/`get` akzeptieren absolute Gerätepfade; `put`/`mkdir`/`gtime`/`ren`/`rm`/`rmdir` benötigen in dieser Version relative Pfade zum aktuellen Geräteverzeichnis (in einer neuen Sitzung C:\). `touch`/`settime` nicht verwenden (Zeitkonvertierung falsch).
- Umlaute in Prozessargumenten als CP1252-Bytes übergeben. Fehlerausgabe zusätzlich zum Exitcode prüfen; Exitcode allein ist nicht zuverlässig.
- Tatsächlich installiert: Lua 5.5.1, Qt 6.11.2. `KFontArialBold18&` existiert nicht in den mitgelieferten Headern; verwendet wird `KFontArialNormal18&` plus `gSTYLE 1`.
- Upstream-`runopo.lua` hat im verwendeten Stand Probleme mit APP-Erkennung bzw. Quelltext-Kompilierung; dafür existiert der eigene Laufzeittest.

### Nächste Schritte / noch offen

1. **Phase-2-Feinschliff am Gerät bestätigt** (Stift, Shortcuts, Tabellen, letzte Position; Ruckeln durch Mehrfachzeichnen behoben).
2. **Phase 3 fertig und am Gerät bestätigt (2026-09-17):** Editor (`dEDITMULTI`, 8 Zeilen, Strg-S/Esc; ≤ 28 KB komplett, sonst Ausschnitt ab aktueller Zeile; atomares Speichern; Text ist beim Öffnen komplett markiert → Kürzungs-Schutz < 50 %; externe Änderung → Kopie), Volltextsuche Strg-F (~9 s über 112 Notizen), Neue Notiz Strg-N (öffnet im Editor), Löschen Strg-D, Metadaten (Größe, Wörter) in den Titelzeilen, Zoomstufen (Lupen der Seitenleiste, +/−, Menü) für alle Ansichten, App-Icon, Menü Datei/Notiz/Ansicht.
3. **Phase 4:** (a) ✅ `ncpd` wird seit 2026-09-18 von `psionsync` selbst nur für die Dauer eines Laufs gestartet (`psionsync/link.py`; ein laufender fremder ncpd wird erkannt und benutzt). Grund: der dauerhafte systemd-User-Service (`contrib/ncpd-psion*`, jetzt optional) hielt die Steuerleitungen aktiv und pollte den Port; der Psion ging nach jedem Ausschalten wieder an, zusätzlich verstärkt durch den Neustart des Wrappers bei der Adapter-Neuanmeldung. (b) Suchindex versucht und **verworfen** (Benutzerentscheidung, Details in psion-notes). (c) ✅ Testnotizen entfernt. (d) Offen: Nextcloud-Statusprüfung vor dem Sync; **Omarchy-Plugin** (Sync-Status anzeigen, Sync anstoßen) – vom Benutzer gewünscht, als Nächstes.
4. **Phase 3 (Plan)**, Browser und Leseansicht. **Lesen ist dem Benutzer wichtiger als Schreiben**; Editor/Suche bleiben Phase 3. Bereits vereinbarte Unicode-Sicherung, Konfliktregeln und Warnung beim Speichern nach externer Änderung gelten unverändert.
4. Qt-Anzeige bei Gelegenheit visuell abnehmen (Gerätetest ist bestätigt, daher nicht blockierend).

## Kontext und Entscheidungen

Ziel: einen privaten Obsidian-Vault (`~/Documents/Obsidian/Vault`, per Nextcloud synchronisiert, 112 Notizen, 554 KB Markdown, 848 KB gesamt, keine Anhänge, bis zu vier Ordnerebenen) auf einem Psion 5mx lesen und bearbeiten. Transport ist die serielle Verbindung (Honda-Kabel + USB-RS232, `/dev/ttyUSB0`, Gruppe `uucp` ist gesetzt). Der Sync wird **immer vom Linux-Rechner angestoßen**.

Entscheidungen:
- **Nicht Notiz/Jotter.** Notiz speichert alles in einem undokumentierten DBMS-Store, kennt keine Ordner und keine Titel, und die Markdown↔Rich-Text-Übersetzung wäre in beide Richtungen verlustbehaftet. Der alte Plan hatte zwei Spike-Gates, deren Ausgang offen war. Diese beiden Risiken entfallen komplett.
- **Eigene App in OPL** (Arbeitsname `PsiVault`), die Obsidians Anzeige nachahmt: Ordnerbaum, Notiz lesen mit leichtem Markdown-Rendering, Notiz bearbeiten (roh als Text, wie Obsidians Editor), `[[Wikilinks]]` folgen, Volltextsuche. Kein Graph View.
- **Dateiformat auf dem Psion = das Markdown selbst.** Eine `.md`-Datei im Vault ↔ eine `.md`-Datei unter `C:\Vault\` mit identischem Relativpfad. Nur Umkodierung UTF-8 → CP1252 und LF → CRLF. Ordner, Frontmatter, alles bleibt erhalten; der Sync ist ein reiner Dateisync.
- **Nur `.md`-Dateien** werden synchronisiert. Anhänge gibt es im Vault derzeit nicht; sollten welche dazukommen, bleiben sie auf dem Rechner und `![[bild.png]]` wird in der App als Platzhalter angezeigt.
- Zwei-Wege-Sync, **neuere Änderung gewinnt**, unterlegene Version wird als Konfliktkopie im Vault abgelegt. Bei gleichen oder unzuverlässig vergleichbaren Zeitstempeln bleiben beide Fassungen erhalten; der Konflikt bleibt bis zur Entscheidung ungelöst. Dry-Run ist Default.
- **Lesen hat zunächst Vorrang vor Schreiben.** Leseansicht und späterer Roh-Markdown-Bearbeitungsmodus gehören beide zu PsiVault; es wird keine externe Editor-App benötigt.

## Toolchain (alles auf Linux, bereits geprüft)

| Zweck | Werkzeug | Stand |
|---|---|---|
| Serielle Verbindung, Dateitransfer, Backup | `plptools` (`ncpd`, `plpftp`, optional `plpfuse`) | `plptools-git` installiert; Backup über eigenes Skript, kein `plpbackup` |
| OPL kompilieren (`.opl` → `.opo`/`.app` + `.aif`) | OpoLua `bin/compile.lua` | Lua 5.5.1; Test-App erfolgreich kompiliert |
| OPL-App auf dem Desktop testen | OpoLua Qt-Runtime | Qt 6.11.2; Runtime aus Quellcode gebaut |
| SIS-Installer bauen (optional) | OpoLua `bin/makesis.lua` | |
| Sync-Tool | Python ≥ 3.11, stdlib, `pytest` | Python 3.14 |

Wichtige Einschränkung: OpoLua ist ein Interpreter, keine ARM-VM. Er ist die schnelle Iterationsschleife, aber **jede Phase wird am Ende auf dem echten Gerät verifiziert** (Fonts, Tastatur, Geschwindigkeit bei 36 MHz, Dateisperren).

## Projektlayout

```
pyproject.toml            # psionsync, Python ≥3.11, keine Laufzeit-Deps außer stdlib (+ pytest)
psionsync/
  transport/plp.py        # plpftp-Wrapper (Subprozess): ls mit Zeitstempeln, get, put, mkdir, rename, rm
  sync/fsmap.py           # Pfad- und Inhaltsabbildung: Dateinamen-Regeln, UTF-8↔CP1252, LF↔CRLF
  sync/state.py           # Sync-Zustand (JSON): pro Notiz Hash + mtime beider Seiten zum letzten Sync
  sync/engine.py          # Drei-Wege-Vergleich, „neuer gewinnt“, Konfliktkopien, Löschungen
  cli.py                  # psionsync status|sync [--apply]|push|pull|backup
app/
  src/*.opl               # OPL-Quelltext (Module: main, browser, viewer, editor, markdown, links, search)
  build.sh                # compile.lua → dist/PsiVault.app + .aif; optional makesis
  dist/                   # Build-Artefakte (gitignored)
tests/
  fixtures/vault/         # kleiner Test-Vault mit Ordnern, Umlauten, Frontmatter, Wikilinks
tools/                    # Wegwerf-Skripte
docs/                     # Pläne, Format-/Gerätenotizen (docs/psion-notes.md)
```

## Phase 0 – Toolchain und erste Verbindung

1. `yay -S plptools-git`. Verbindung: Psion Strg-T (Kommunikation, Fernverbindung an, 115200; deutsches Gerät, nicht Strg-L wie in englischen Anleitungen), `ncpd -s /dev/ttyUSB0 -b 115200`, `plpftp` → `ls C:\`. Baud ggf. auf 57600/19200 runter.
2. **Vollbackup** des Psion (plpftp-Rekursion mit `tools/backup_device.py`; ROM-Ausnahme siehe Übergabestand) nach `~/psion-backup/<datum>/`, bevor irgendetwas geschrieben wird.
3. Roundtrip: eine Datei `put`, wieder `get`, `cmp`. Dabei klären: wie überträgt plpftp Umlaute in Dateinamen, welche Zeichen sind in EPOC-Dateinamen verboten (`\ / : * ? " < > |`), wie lang darf ein Pfad sein, welche Zeitstempel-Auflösung liefert `ls`.
4. OpoLua aus GitHub klonen, `PKGBUILD` bauen (oder nur `bin/` mit Lua nutzen). Hello-World in OPL: Datei aus `C:\Vault\` lesen und mit `gPRINT` in zwei Schriftgrößen ausgeben. Mit `compile.lua --aif` bauen, in der Qt-Runtime starten, dann per plpftp nach `C:\System\Apps\PsiVault\` legen und auf dem Gerät starten.
5. `docs/psion-notes.md` anlegen: Gerätesprache/Pfade, gemessener Durchsatz (Erwartung ~8–10 KB/s bei 115200, d.h. Vollsync ~1 Minute), Dateinamen-Erkenntnisse.

**Gate 0**: `plpftp` listet `C:\`, get/put byte-identisch, Backup liegt vor, OPL-Hello-World läuft im Emulator **und** auf dem Gerät. ✅ Bestanden 2026-09-17.

## Phase 1 – Dateisync `psionsync`

Reines Python, TDD gegen `tests/fixtures/vault/` und einen gefakten Transport (Verzeichnis statt Psion), Ende-zu-Ende dann gegen das Gerät.

### Abbildung (`sync/fsmap.py`)
- Relativpfad im Vault ↔ `C:\Vault\<Relativpfad>` mit `/` → `\`. Datei- und Ordnernamen werden CP1252-kodiert (Umlaute kommen in beiden vor: `Entwürfe/`, `Veröffentlicht/`, `Gemüse-Lasagne.md`; `¥`, `–`, `&`, Klammern sind CP1252-fähig). Längster Pfad im Vault: 97 Zeichen. Nicht kodierbare Namen und Namen mit EPOC-verbotenen Zeichen (`? * | " < > :`) werden übersprungen und in `status` gemeldet, kein stilles Umbenennen; solche Notizen werden im Vault umbenannt (Stand 2026-09-17: alle 112 Namen sind CP1252-fähig, eine enthält `?`). Pfadlimit ≥ 253 Zeichen, Vault-Maximum 104 – kein Thema.
- Inhalt: UTF-8 → CP1252, LF → CRLF. Auf dem Rückweg: CP1252 → UTF-8, CRLF → LF.
- **Transliteration** statt `?`: 63 von 112 Notizen enthalten Zeichen außerhalb CP1252, und zwar überwiegend Struktur, nicht Deko: `→` (401×), Box-Drawing `─ │ ├ └` (~180×), `✅` (125×), `⚠`, `❌`, `✓`, `↔`, `≥`, `∙`, Zero-Width-Space (U+200B), Variation Selector (U+FE0F), Keycap (U+20E3). Feste Tabelle in `fsmap.py`: `→`→`->`, `↔`→`<->`, `─`→`-`, `│`→`|`, `├`/`└`→`+`, `✅`/`✓`→`[x]`, `❌`→`[ ]`, `⚠`→`(!)`, `≥`→`>=`, `∙`→`*`, `ō`→`o`, unsichtbare Zeichen (U+200B, U+FE0F, U+20E3) → weglassen; Rest → `?`. Alles Ersetzte wird beim Pull nur zurückgeschrieben, wenn die betroffene Zeile auf dem Psion unverändert blieb (Zeilenvergleich gegen den beim Push gemerkten Stand); geänderte Zeilen behalten die Transliteration. Der Sync verwaltet außerhalb des Vaults den ursprünglichen Unicode-Text des letzten gemeinsamen Sync-Stands sowie die verwendete Version der Übersetzungstabelle, um die damalige Psion-Fassung exakt rekonstruieren zu können. Diese lokale Sicherung ist Bestandteil des Sync-Tools; auf dem Psion liegt nur die normale Markdown-Datei. Unveränderte Zeilen werden per Textvergleich zugeordnet, auch nach eingefügten oder entfernten Zeilen. Bei uneindeutiger Zuordnung keine Wiederherstellung auf Verdacht. Wenn beim Pull Unicode-Zeichen verloren gehen, wird die ursprüngliche Unicode-Fassung vor dem Überschreiben zusätzlich gesichert.
- Ignoriert: alle Pfade mit `.`-Präfix (`.obsidian/`, `.claude/`, `.trash/`), alles außer `*.md`.

### Zustand und Engine (`sync/state.py`, `sync/engine.py`)
- State in `~/.local/state/psionsync/state.json`: pro Relativpfad Hash und mtime beider Seiten zum Zeitpunkt des letzten Syncs. Zugehörige Unicode-Ausgangsstände und Angaben zur Übersetzungstabelle werden vom Sync-Tool unter `~/.local/state/psionsync/` verwaltet und konsistent mit dem jeweiligen erfolgreichen Sync aktualisiert. Hashes allein reichen für die Unicode-Wiederherstellung nicht aus.
- Änderung wird **per Hash gegen den State** erkannt, nicht per Zeitstempelvergleich zwischen den Geräten (die Uhren driften). Zeitstempel entscheiden nur den Konflikt, sofern sie zuverlässig vergleichbar und unterschiedlich sind. **Kalibrierung:** plptools zeigt Psion-Dateizeiten 2 h zu spät (Phase 0). Der Sync legt zu Beginn `C:\Vault\_psionsync.clock` per `put` an, liest deren `gtime` und bildet `delta = gtime − Rechnerzeit`; alle Psion-mtimes werden um `delta` korrigiert (deckt Konvertierung und Uhrdrift zugleich ab). Ohne erfolgreiche Kalibrierung kein Zeitvergleich. Andernfalls beide Fassungen sichern und den Konflikt zur Entscheidung melden; keinen Gewinner wählen und den Konflikt nicht als erfolgreich synchronisiert markieren.
- Fälle pro Notiz: nur Linux geändert → push; nur Psion geändert → pull; beide → neuer gewinnt (Linux: Datei-mtime; Psion: mtime aus `plpftp ls`), Verlierer nach `<Pfad> (Konflikt Psion|Linux YYYY-MM-DD HHMM).md` im Vault; einseitig gelöscht + andere Seite unverändert → dort ebenfalls löschen; gelöscht + geändert → geänderte Version bleibt, wird als Konflikt gemeldet. Neu auf einer Seite → auf die andere kopieren. Umbenennen = löschen + neu (Obsidian-Renames sind selten genug).
- Ablauf `psionsync sync`: (1) `ncpd` erreichbar? (2) Psion-Baum durch rekursive `plpftp ls`-Aufrufe einlesen, (3) Vault einlesen, (4) Plan berechnen und anzeigen, (5) nur mit `--apply` ausführen: Konfliktkopien zuerst, dann get/put/rm, (6) State schreiben. Abbruch bei jedem Transportfehler, State wird nur für erfolgreich übertragene Dateien aktualisiert.
- `psionsync push --init` für den ersten Vollsync, `backup` als Komfortbefehl für Schritt 2 aus Phase 0.

**Gate 1** ✅ bestanden 2026-09-17: `pytest` deckt alle Fälle (nur Linux, nur Psion, beide, neu, gelöscht, Umlaute in Pfad und Inhalt, Transliteration hin und zurück, CRLF) gegen den Fake-Transport ab. Ende-zu-Ende: Vollsync auf das Gerät, Datei per `plpftp put` auf dem Psion ändern (simulierte Gerätebearbeitung), `sync --apply` holt sie in den Vault; beidseitige Änderung erzeugt eine Konfliktkopie. Bonus: Datei in Word auf dem Psion als Textdatei öffnen und lesen können.

## Phase 2 – App: Browser und Viewer

OPL, 640×240, 16 Graustufen. Entwicklung in der Qt-Runtime, Abnahme auf dem Gerät.

- **Browser**: Ordnerbaum unter `C:\Vault\`, Liste sortiert (Ordner zuerst), Navigation mit Pfeiltasten/Enter/Esc, Pfad in der Titelzeile, Letzte-Position merken (`C:\System\Apps\PsiVault\state.txt`). Toolbar rechts wie bei den eingebauten Apps.
- **Viewer** (`markdown.opl`): zeilenweises Rendering mit `gPRINT` und Fontwechsel. Mapping: `#`/`##`/`###` → Arial 18/15/13 fett, sonst Arial 11 (oder 13, am Gerät entscheiden); `- `/`* `/`1. ` → Einzug + `•`/Nummer; `**fett**`/`*kursiv*` → `gSTYLE` innerhalb der Zeile; Codeblöcke/Inline-Code → Courier; `---` → Linie; `> ` → Einzug + Randlinie; Frontmatter (`---`-Block am Anfang) → eingeklappt als eine Zeile `[Frontmatter]`; `[[Link]]`/`[[Link|Text]]` → unterstrichen; `![[Anhang]]` → `[Anhang: name]`; alles andere Klartext. Zeilenumbruch nach Pixelbreite (`gTWIDTH`), Seitenweises Scrollen, nur sichtbare Zeilen rendern.
- **Wikilinks** (`links.opl`, 226 Links im Vault, 79 Notizen mit Frontmatter, nur 2 Embeds): Tab/Pfeile springen zwischen Links, Enter folgt. Auflösung wie Obsidian: Dateiname (ohne `.md`) gegen einen Index aller Dateien; Index wird beim Start aus dem Baum gebaut und in `state.txt` gecacht (Neuaufbau, wenn sich die Anzahl/mtime des Baums geändert hat). Zurück-Stack.

**Gate 2**: Der komplette Vault lässt sich auf dem Gerät durchblättern und lesen, Wikilinks funktionieren, Umlaute stimmen, Öffnen der größten Notiz (`Homelab Audit Log.md`, 48 KB) dauert < 3 s am Gerät. ✅ Bestanden 2026-09-17 (~2 s, lazy Layout).

## Phase 3 – App: Editor und Suche

- **Editor**: Roh-Markdown in einem Bearbeitungsmodus innerhalb von PsiVault bearbeiten; die formatierte Leseansicht bleibt ein eigener Modus. Keine externe Editor-App. Erster Wurf mit `dEDITMULTI` (eingebautes mehrzeiliges OPL-Dialogfeld innerhalb der App). Lesen hat zunächst Vorrang; die Editor-Grenzen blockieren nicht die Abnahme von Browser und Viewer. Vorher klären: maximale Puffergröße von `dEDITMULTI` (Spike in Phase 2 nebenbei; falls < größte Notiz, Notiz abschnittsweise bearbeiten oder eigenen Editor bauen). Speichern schreibt die Datei atomar (`tmp` + Umbenennen), damit ein Sync nie eine halbe Datei sieht. Strg-S speichern, Esc mit Nachfrage.
- **Neue Notiz** im aktuellen Ordner (Name abfragen), **Löschen** mit Nachfrage.
- **Suche**: Volltext über alle `.md` (einfache Teilstringsuche, Trefferliste mit Kontextzeile). Bei 530 KB am Gerät vermutlich wenige Sekunden; wenn zu langsam, Index in Phase 4.
- Sync-Verträglichkeit: Die App hält keine Datei offen, außer während Lesen/Schreiben. Beim Öffnen zur Bearbeitung merkt sie sich den Dateiinhalt. Vor dem Speichern prüft sie, ob die Datei inzwischen extern verändert oder gelöscht wurde. Falls ja: Warnmeldung in PsiVault und die eigene Bearbeitung als separate Kopie sichern, statt die externe Fassung zu überschreiben. Beispiel: „Diese Notiz wurde seit dem Öffnen außerhalb von PsiVault geändert. Deine Bearbeitung wird als separate Kopie gespeichert.“ Eine sofortige Warnung während des Syncs ist für den ersten Stand nicht erforderlich. Die technische Absicherung gegen Änderungen zwischen Prüfung und Speicherung muss vor Umsetzung festgelegt werden; atomisches Umbenennen allein verhindert diesen Wettlauf nicht.

**Gate 3**: Notiz auf dem Psion bearbeiten → `psionsync sync --apply` → Änderung im Vault. Notiz im Vault ändern → sync → auf dem Psion sichtbar. Beide ändern → Konfliktkopie. Bei während der Bearbeitung extern veränderter oder gelöschter Datei warnt PsiVault beim Speichern und erhält beide Fassungen. ✅ Bestanden 2026-09-17 am Gerät.

## Phase 4 – Komfort (optional, nach Bedarf)

- `systemd --user`-Unit + udev-Regel, die `ncpd` startet, sobald `/dev/ttyUSB0` erscheint.
- Suchindex, Tags-Liste (aus Frontmatter/`#tag`), Daily-Note-Shortcut, Backlinks (aus dem Link-Index billig).
- `plpfuse`-Mount als Alternative zum plpftp-Wrapper, falls der Subprozess nervt.

## Vorgehen und Regeln

- Reihenfolge Phase 0 → 1 → 2 → 3; Phase 1 (Sync) und Phase 2 (App) sind voneinander unabhängig und können parallel laufen, aber Gate 0 kommt vor allem.
- Vor jedem ersten Schreibzugriff einer neuen Art auf das Gerät: Backup. `psionsync` schreibt ausschließlich unter `C:\Vault\`, nie woanders.
- Sync-Tool mit TDD; App-Code wird gegen den Emulator entwickelt und am Gerät abgenommen; Erkenntnisse über OPL/EPOC-Eigenheiten (Fonts, Grenzen, Bugs im Emulator vs. Gerät) landen in `docs/psion-notes.md`.
- Der Vault liegt in Nextcloud: `psionsync` schreibt Konfliktkopien und gepullte Änderungen direkt in den Vault, Nextcloud verteilt sie weiter. Nicht syncen, während Nextcloud gerade denselben Vault schreibt (Status prüfen, kein Hard-Lock nötig).

## Offene Fragen (in Phase 0/2 klären)

- `dEDITMULTI`-Puffergrenze; die größte Notiz hat 48 KB, vier weitere liegen über 20 KB. Falls die Grenze darunter liegt: abschnittsweise bearbeiten oder eigener Editor (deutlich mehr Aufwand, dann eigene Phase).
- OPL-Grenzen für Stringlängen (255 Zeichen pro String in OPL, Textzeilen müssen ggf. gestückelt werden) und Speicher bei großen Notizen.

## Quellen

- plptools: https://github.com/plptools/plptools, AUR `plptools-git`
- OpoLua (OPL-Compiler `bin/compile.lua`, Qt-Runtime, `makesis.lua`, `dumpdb.lua`): https://github.com/inseven/opolua
- OPL-Referenz (Series 5): OpoLua `reference/`-Verzeichnis; „Programming Psion Computers“ (Leigh Edwards): https://palmtop.cosi.com.pl/wp-content/uploads/2013/07/Programming-Psion-Computers.pdf
- Psion-Verbindung, Kabel, Strg-L (englisches Gerät, auf dem deutschen 5mx ist es Strg-T): https://smittytone.net/docs/psion_connectivity.html
- OPL-Übersicht: https://en.wikipedia.org/wiki/Open_Programming_Language
- Alter Plan mit der Notiz-Analyse (Fallback-Wissen): [[Psion 5mx Notiz Sync - Plan]]
