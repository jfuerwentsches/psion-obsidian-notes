---
erstellt: 2026-09-17
status: verworfen
ersetzt-durch: "[[Psion 5mx Obsidian-Light - Plan]]"
tags: [psion, obsidian, sync, plan]
---

> **Verworfen am 2026-09-17** zugunsten einer eigenen OPL-App mit Markdown-Dateien im Ordnerbaum, siehe [[Psion 5mx Obsidian-Light - Plan]]. Bleibt als Dokumentation der Notiz/Jotter-Analyse und als Fallback-Wissen erhalten.

> Umsetzungsplan aus einer Claude-Code-Brainstorming-Session am 2026-09-17 auf dem Mac.
> Zielrechner für die Umsetzung: Omarchy (Arch Linux). Mac-spezifische Pfade unten sind nur Entwicklungsnotizen.
> Vault-Pfad auf dem Zielrechner: der per Nextcloud synchronisierte Ordner `Obsidian/Vault`.

# Obsidian ↔ Psion 5mx „Notiz" (Jotter) Sync über seriell

## Kontext

Ziel: einen privaten Obsidian-Vault (Nextcloud, `…/Obsidian/Vault`, 111 Notizen, ~530 KB Markdown, verschachtelte Ordner) mit der eingebauten App **Notiz** (deutsche Version von Jotter) auf einem Psion 5mx synchronisieren. Transport ist die serielle Verbindung (Honda-Kabel + USB-RS232-Adapter, beides vorhanden). Die Software soll auf dem Linux-Rechner (Omarchy, Arch-basiert) laufen; entwickelt wird auf dem Mac.

Entscheidungen aus dem Brainstorming:
- Ziel-App ist **Notiz**, nicht Word/Textdateien.
- **Ganzer Vault**, Zwei-Wege-Sync, **neuere Änderung gewinnt**, unterlegene Version wird als Konfliktkopie im Vault abgelegt.
- Markdown wird **nach Rich-Text übersetzt** (Überschriften fett/größer, Listen eingerückt, fett/kursiv) und auf dem Rückweg zurückübersetzt.

### Das zentrale Risiko

Notiz speichert alle Einträge in **einer** EPOC-Datenbankdatei (DBMS-Store) mit Rich-Text-Spalten. Dieses Format ist nirgends dokumentiert (psiconv/Frodo Looijaard decken Word, Sheet, Sketch, Record ab, nicht Jotter/Data/Agenda). Die Abkürzung: Symbian OS ist Open Source ([cdaffara/symbiandump-os1](https://github.com/cdaffara/symbiandump-os1)), und die Store-, DBMS- und Text-Bibliotheken (`estor`, `edbms`, `etext`) sind abwärtskompatibel zu EPOC R5 auf dem 5mx. Statt blindem Hex-Raten bauen wir die Parser nach dem Quellcode nach. Außerdem dokumentiert psiconv die Rich-Text-Formatschichten (Paragraph/Character Layout) für Word, und dieselben `etext`-Strukturen stecken in Jotter.

Deshalb ist das Projekt in **zwei Spike-Gates** und die eigentliche Sync-Implementierung geteilt. Erst wenn Gate 2 (Schreiben) bestanden ist, wird die Sync gebaut. Scheitert es, Fallback siehe unten.

## Projektlayout

Neues Python-Projekt (leeres Verzeichnis, git init nötig):

```
pyproject.toml            # Python ≥3.11, keine Laufzeit-Deps außer stdlib (+ pytest, markdown-it-py)
psionsync/
  transport/plp.py        # Dateien vom/zum Psion via plpftp (Subprozess), später optional direkt NCP auf ncpd:7501
  epoc/store.py           # CPermanentFileStore-Leser/-Schreiber (Streams, TStreamId, Frames)
  epoc/dbms.py            # DBMS-Tabellenlayout: Spalten, Cluster, Records, Long-Columns (Streams)
  epoc/richtext.py        # CRichText/CPlainText: Text, Paragraph- und Zeichenformat-Schichten
  jotter/codec.py         # Notiz-Datei → Liste[Note], Liste[Note] → Notiz-Datei
  convert/md_to_rich.py   # Markdown → Rich-Text-Modell
  convert/rich_to_md.py   # Rich-Text-Modell → Markdown
  sync/state.py           # Sync-Zustand (JSON): pro Notiz Hash beider Seiten, Jotter-Record-ID, Zeitstempel
  sync/engine.py          # Drei-Wege-Vergleich, „neuer gewinnt", Konfliktkopien
  cli.py                  # psionsync pull|push|sync|dump|status
tests/
  fixtures/               # echte Notiz-Dateien vom Gerät (klein, anonymisiert)
docs/superpowers/specs/   # Design-Doc (Brainstorming-Ergebnis) und Format-Notizen
tools/                    # Wegwerf-Skripte des Spikes (hexdump-Helfer etc.)
```

## Phase 0 – Toolchain und erste Verbindung (Mac zum Entwickeln, Linux als Ziel)

1. **plptools bauen**
   - Mac (Apple Silicon): Fork `jbmorley/plptools`, brew `coreutils readline pkg-config libtool automake gettext`, `./bootstrap --skip-po && ./configure && make`. macFUSE nicht nötig, nur `ncpd` + `plpftp`.
   - Omarchy: AUR-Paket `plptools` falls vorhanden, sonst `plptools/plptools` aus GitHub bauen. `udev`-Regel oder Gruppe `uucp` für `/dev/ttyUSB0`.
2. **Verbindung**: Psion Strg-L (Fernverbindung, 115200), `ncpd -s /dev/cu.usbserial-* -b 115200`, dann `plpftp` → `ls C:\`. Baud ggf. auf 57600/19200 runter.
3. **Notiz-Datei finden und sichern**: Dateiname auf dem deutschen Gerät ermitteln (vermutlich `C:\Dokumente\Notiz` o.ä.), per `get` holen, als `tests/fixtures/notiz-original.bin` ablegen. Zusätzlich **Vollbackup** des Psion vor jedem Schreibtest (`plpbackup` oder plpftp-Rekursion).
4. Auf dem Psion drei Testnotizen anlegen (eine leer, eine nur Klartext, eine mit fett/kursiv/Einzug) und die Datei erneut holen. Diff der beiden Dateien ist der Einstieg in die Analyse.

**Gate 0**: Datei liegt auf dem Mac, Roundtrip get/put einer beliebigen Datei funktioniert.

## Phase 1 – Spike: Notiz-Datei lesen (Wegwerfcode erlaubt, wird später aufgeräumt)

Quellen zum Nachbauen, in dieser Reihenfolge:
- `estor`: `CPermanentFileStore`, `TStreamId`, Frame-Layout, Root-Stream, TOC. (Symbian: `os/persistentdata/persistentstorage/store/`)
- `edbms`: DBMS-Store-Layout, Tabellen-Definition, Cluster mit Records, Long-Columns als eigene Streams. (`os/persistentdata/persistentstorage/dbms/`)
- `etext`: `CPlainText`/`CRichText` Externalize: Textstream, `CParaFormatLayer`, `CCharFormatLayer`, Format-Schichten mit Laufwerten. (`os/textandloc/textrendering/texthandling/`) Quervergleich mit psiconv-Doku „Word / Paragraph Layouts / Character Layouts".
- Header: UID1 `0x10000050` (Datenbank), UID2 = Jotter-App-UID, UID3, Checksumme; Vergleich mit psiconv-Header-Doku.

Deliverable: `psionsync dump notiz.bin` gibt alle Notizen mit Text und Formatlauf aus. Tests gegen die Fixtures aus Phase 0 (die drei Testnotizen müssen mit exakt ihrem Inhalt herauskommen).

Nebenbei klären: **Haben Jotter-Records einen Änderungszeitstempel?** Wenn nein, brauchen wir für „neuer gewinnt" den Dateizeitstempel der Notiz-Datei plus Hash-Vergleich (siehe Sync-Engine).

**Gate 1**: Alle Notizen der echten Datei werden korrekt gelesen, Umlaute (CP1252) stimmen.

## Phase 2 – Spike: Notiz-Datei schreiben

1. Gelesene Datei byte-identisch zurückschreiben (Roundtrip-Test, harte Anforderung).
2. In der Kopie eine Notiz ändern, eine hinzufügen, eine löschen. Unter **anderem Dateinamen** (z.B. `C:\Dokumente\NotizTest`) auf den Psion legen, in Notiz öffnen (Datei → Öffnen). Zusätzlich Store-Kompaktierung prüfen: es reicht, immer eine frische, kompakte Datei zu erzeugen statt in-place zu patchen.
3. Notiz auf dem Psion die Testdatei bearbeiten lassen, zurückholen, erneut lesen → sicherstellen, dass unser Writer nichts erzeugt, das Notiz beim Speichern zerstört.

**Gate 2**: Vom Linux/Mac generierte Datei öffnet und speichert fehlerfrei in Notiz. Erst jetzt Phase 3.

## Phase 3 – Sync-Tool

### Datenmodell
- Eine Markdown-Datei ↔ eine Notiz. Notiz kennt keine Ordner und keine Titel (die Liste zeigt die erste Zeile). Deshalb ist die **erste Zeile jeder Notiz der Vault-Pfad ohne `.md`** (z.B. `Agent-Access/Charly/Homelab Audit Log`), fett formatiert, danach Leerzeile, dann Inhalt. Ändert man die erste Zeile auf dem Psion, ist das ein Rename/Move im Vault.
- Frontmatter (YAML) bleibt wörtlich am Anfang des Inhalts (Klartext), damit der Rückweg verlustfrei ist.
- Zeichensatz: Vault UTF-8 ↔ Psion CP1252. Nicht darstellbare Zeichen (Emoji etc.) werden beim Push durch `?` ersetzt und der Rückweg schreibt sie nur zurück, wenn der Absatz auf dem Psion unverändert blieb (sonst geht Text verloren, Konfliktkopie schützt).

### Markdown ↔ Rich-Text (`convert/`)
Push: `markdown-it-py` parsen → Überschriften (fett, Schriftgröße nach Ebene), Absätze, Listen (Einzug + `•`/Nummer als Text), fett/kursiv, Codeblöcke (Einzug, Zeichensatz Courier), Links `[[x]]` und `[t](u)` als Klartext. Pull: Umkehrung nach den gleichen Regeln; was nicht abgebildet werden kann, wird Klartext. Roundtrip-Tests mit den echten Vault-Notizen: `md → rich → md` muss für unterstützte Konstrukte identisch sein; der Rest wird als bekannter Verlust dokumentiert.

### Sync-Engine (`sync/`)
- Zustand in `~/.local/state/psionsync/state.json`: pro Notiz Vault-Pfad, Jotter-Record-ID, Hash Markdown zuletzt gesehen, Hash Rich-Text zuletzt gesehen, Zeitpunkt letzter Sync.
- Ablauf `psionsync sync`: (1) Notiz-Datei per plpftp holen, (2) Vault einlesen, (3) Drei-Wege-Vergleich je Notiz gegen State: nur Mac geändert → Psion überschreiben; nur Psion geändert → Vault überschreiben; beide geändert → **neuer gewinnt** (Mac: Datei-mtime; Psion: Record-Zeitstempel falls vorhanden, sonst Notiz-Dateimtime als Näherung), Verlierer nach `<Pfad> (Konflikt Psion|Mac YYYY-MM-DD HHMM).md`; (4) neue Notiz-Datei erzeugen, alte auf dem Psion nach `Notiz.bak` umbenennen, neue hochladen, (5) State schreiben.
- Notiz muss während des Syncs auf dem Psion **geschlossen** sein (Datei ist sonst gesperrt). Das Tool prüft das über Fehler beim `put` und bricht sauber ab.
- `psionsync status` zeigt den geplanten Diff ohne zu schreiben (Dry-Run als Default, `--apply` schreibt).

### Transport (`transport/plp.py`)
Wrapper um `plpftp` im Skriptmodus (`plpftp get/put/rename`) mit `ncpd` als Voraussetzung, plus ein `systemd --user`-Unit für Omarchy, das `ncpd` startet, wenn der Adapter erscheint. Direkter NCP-Client gegen Port 7501 ist optional und nicht Teil des ersten Wurfs.

## Fallback, falls Gate 2 scheitert

Jede Notiz wird ein EPOC-**Word**-Dokument in `C:\Dokumente\Obsidian\<Pfad>` (psiconv kann Word schreiben, Format vollständig dokumentiert, Ordner bleiben erhalten). Sync-Engine, Konverter und Transport bleiben identisch, nur der Codec wird getauscht. Diese Möglichkeit ist der Grund, warum `jotter/codec.py` hinter einer schmalen Schnittstelle (`read(bytes) -> list[Note]`, `write(list[Note]) -> bytes`) steckt.

## Vorgehen und Regeln

- Reihenfolge strikt Phase 0 → 1 → 2 → 3; die Spikes sind Wegwerfcode, der erst nach Gate 2 in die Modulstruktur überführt wird (TDD ab Phase 3, Fixtures aus Phase 0/1).
- Vor jedem Schreibtest auf dem Gerät: Backup der Notiz-Datei auf dem Mac, Tests nur gegen Dateien mit anderem Namen als der echten.
- Design-Doc nach diesem Plan in `docs/superpowers/specs/2026-09-17-psion-notiz-sync-design.md`, Format-Erkenntnisse aus den Spikes in `docs/format-notiz.md`.

## Verifikation

- Phase 0: `plpftp` listet `C:\`, get/put Roundtrip einer Datei byte-identisch (`cmp`).
- Phase 1: `pytest tests/test_jotter_read.py` liest die drei Testnotizen exakt; `psionsync dump` gegen die echte Datei zeigt alle Einträge.
- Phase 2: Writer-Roundtrip byte-identisch; generierte Testdatei öffnet in Notiz auf dem Gerät, wird dort gespeichert und ist danach wieder lesbar.
- Phase 3: `pytest` für Konverter-Roundtrips und Sync-Engine (Szenarien: nur Mac, nur Psion, beide, Rename, Löschen); Ende-zu-Ende: Notiz im Vault ändern → `psionsync sync --apply` → am Psion sichtbar; am Psion ändern → sync → im Vault; beide ändern → Konfliktkopie liegt im Vault.

## Quellen

- plptools: https://github.com/plptools/plptools (Apple-Silicon-Fork: https://github.com/jbmorley/plptools)
- plptools auf macOS, Kabel/Adapter, Strg-L: https://smittytone.net/docs/psion_connectivity.html
- Psion-Dateiformate (Word, Sheet, Sketch, Record …): https://frodo.looijaard.name/project/psifiles
- psiconv (kann Word schreiben, Fallback): https://frodo.looijaard.name/project/psiconv
- Symbian-OS-Quellcode (estor, edbms, etext): https://github.com/cdaffara/symbiandump-os1
- Jotter-Tipps, nConvert (Jotter → Word/RTF auf dem Gerät): http://www.ericlindsay.com/epoc/bjot5.htm
