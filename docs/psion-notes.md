# Phase 0 – Geräte- und Toolchain-Erkenntnisse

Stand: 2026-09-17. Gate 0 bestanden: Verbindung, Backup, Roundtrip, Hello-World auf dem Gerät, Pfadgrenzen, Zeitstempel und Durchsatz sind geprüft (siehe unten).

## Verbindung

- Installiert: `plptools-git rel.1.0.12.r323.g68c54f7-1`.
- `ncpd -d -s /dev/ttyUSB0 -b 115200` meldet `Connected with a S5 at 115200 baud`.
- Adapter: Prolific/ATEN; stabiler Pfad unter `/dev/serial/by-id/usb-Prolific_Technology_Inc._USB-Serial_Controller_<Seriennummer>-if00-port0` (siehe `ls /dev/serial/by-id/`).
- In der Codex-Sandbox ist das Gerät nicht sichtbar. Verbindung und Zugriff auf den lokalen ncpd benötigen hier Ausführung außerhalb der Sandbox. Keine Änderung an Gruppen oder Geräteberechtigungen erforderlich gewesen.
- Laufwerke: C: intern (20.777.984 Bytes), D: Speicherkarte (15.974.400 Bytes), Z: ROM.
- D: enthält eine ca. 10 MB große `SYS$ROM.BIN`. Auf ausdrücklichen Benutzerwunsch wird sie vom Backup ausgenommen, da sie bereits lokal vorliegt. Die laufende ROM-Übertragung wurde abgebrochen; erneute Sicherung der übrigen Dateien nach `~/psion-backup/2026-09-17-ohne-rom`.

## plpftp

- Das installierte Paket enthält **kein `plpbackup`**. Vorbereitung eines rekursiven Dateibackups: `tools/backup_device.py`.
- Einzelbefehle mit getrennten Argumenten: `plpftp ls 'C:\'`. Ein einzelnes Argument mit eingebettetem Befehl samt Pfad funktioniert nicht.
- `ls` liefert Attribute, Größe, Datum samt Sekunden und Namen; tatsächliche Zeitauflösung und Zeitzone sind noch nicht gemessen.
- `mget` ist nicht rekursiv. Ein `ls -R` ist in der untersuchten Implementierung nicht vorgesehen; der Transport muss selbst Verzeichnisse durchlaufen.
- Befehlsfehler können auf stderr erscheinen, ohne zuverlässig einen Fehler-Exitcode auszulösen. Der Wrapper muss beides prüfen.
- Vor dem Backup Dokumente auf dem Gerät speichern und schließen. Erster Versuch scheiterte erwartungsgemäß an der gesperrten `Contacts.cdb`. Nach dem Schließen aller Apps war `plpftp ps` leer; vollständige Sicherung nach `~/psion-backup/2026-09-17-phase0-complete` gestartet. Solange `manifest.json` fehlt, ist diese Sicherung unvollständig.

## OpoLua und Test-App

- OpoLua aus `https://github.com/inseven/opolua`, Commit `6bb10d5b60ce94abea20b9e1f0abb61d33218649`, vorläufiger Checkout `/tmp/psivault-opolua` (nicht dauerhaft).
- Lua auf diesem Rechner: 5.5.1; Qt: 6.11.2. Qt-Runtime samt Submodulen mit `qmake6` und `make -j4` erfolgreich gebaut.
- Build: `OPOLUA_DIR=/tmp/psivault-opolua bash app/build.sh`.
- Erzeugt `app/dist/PsiVault.app`, `.aif` sowie `Willkommen.md` in CP1252 mit CRLF.
- Test-App liest ausschließlich `C:\Vault\Willkommen.md`, zeigt Text und wartet auf eine Taste. Noch kein Browser oder Sync.
- Schrift für Überschrift: `KFontArialNormal18&` mit `gSTYLE 1`; eine Konstante `KFontArialBold18&` existiert in den mitgelieferten Headern nicht.
- Temporäre Entwicklungs-UID `0x0F015105`; vor öffentlicher Verteilung ersetzen.
- Qt-App mit vorbereitetem `PsiVault.system/c/`-Dateibaum gestartet; visuelle Abnahme steht aus.
- Upstream-CLI `runopo.lua` akzeptiert die kompilierte APP nicht (erwartet `opo`, erkennt APP als `opa`). Der Quelltextpfad des CLI scheitert außerdem am fehlenden Compiler-Versionsargument. Dies ist kein bestandener Laufzeittest.

## Noch offene Prüfungen

- Gesonderte visuelle Qt-Abnahme ist nicht dokumentiert; der echte Gerätetest wurde bestätigt.

Automatischer Laufzeittest `tools/smoke_app.lua` bestanden: kompilierte APP liest Testnotiz und emittiert alle erwarteten CP1252-Umlaute. Synthetische Schriftmetriken; keine visuelle Abnahme.

## Ergebnis Geräteinstallation

- Dateibackup ohne ROM abgeschlossen: `~/psion-backup/2026-09-17-ohne-rom`, 44 Dateien, 106.090 Bytes. Alle lokalen Größen und SHA-256-Prüfsummen gegen `manifest.json` geprüft; ROM-Ausnahme in `exclusions.json` dokumentiert.
- Frühere Verzeichnisse `2026-09-17-phase0` und `2026-09-17-phase0-complete` enthalten nur abgebrochene Teilstände und sind keine abgeschlossenen Backups.
- `mkdir` und `put` verlangen in dieser plpftp-Version zum aktuellen Verzeichnis relative Zielpfade; absolute Pfade werden dort fehlerhaft an `C:\` angehängt. `get` und `ls` akzeptieren absolute Pfade.
- `C:\System\Apps\PsiVault\PsiVault.app` (433 Bytes), `.aif` (73 Bytes) und `C:\Vault\Willkommen.md` (79 Bytes) übertragen und jeweils bytegleich zurückgelesen.
- PsiVault auf dem Gerät gestartet. Benutzer bestätigte anschließend ausdrücklich, dass Darstellung, Willkommenstext und Umlaute korrekt funktionieren.

- Umlaut-Roundtrip bestanden: `C:\Vault\Entwürfe\Gemüse-Lasagne.md` via CP1252-kodierte Prozessargumente angelegt, gelistet und bytegleich zurückgelesen. Testdatei bleibt vorläufig auf dem Gerät.
- `gtime` verlangt ebenfalls einen relativen Pfad. Zeitangaben sind noch **nicht** zuverlässig vergleichbar: `ls/gtime` und `machinfo` zeigen unterschiedliche Stunden; Geräte-Zeitzone meldet UTC-Offset 3600 Sekunden mit aktivem DST. Keine Uhrzeit automatisch korrigiert. Zeitkonvertierung muss vor der Konfliktentscheidung untersucht werden.
- `plpftp ps` bestätigt laufenden Prozess `PsiVault` (PID 21). Visuelle Geräteabnahme anschließend durch den Benutzer bestätigt.

## Phase-0-Restprüfungen (2026-09-17, unter `C:\Vault\_test\`, danach gelöscht)

### Dateinamen und Pfade

- **Verboten** (plpftp meldet `Error: invalid name`, Exitcode bleibt 0): `? * | " < > :`. Im echten Vault betroffen: `Privat/Blog/Entwürfe/OpenClaw/2026-02-15 OpenClaw - The hype is real, or is it?.md` → muss im Vault umbenannt oder vom Sync übersprungen werden.
- **Erlaubt und bytegleich gelistet:** `& ( ) , ¥ –`, Umlaute, Leerzeichen, führendes Leerzeichen, `..md` (doppelter Punkt).
- **Pfadlänge:** 253 Zeichen (inkl. `C:\`) funktioniert; 270 → `Error: numeric overflow`. Dateiname 200 Zeichen ok, 250 → `Error: too big`. Längster Vault-Pfad ist 104 Zeichen (`C:\Vault\Agent-Access\Projekte\omarchy-kids\Eigene Apps\Musik-Player (Spotify) - Implementierungsplan.md`), längster Name 68 → weit unter der Grenze. Ordnertiefe 5 unter `C:\Vault\` getestet.
- `ren`, `rm`, `rmdir` funktionieren, aber wie `put`/`mkdir` **nur mit relativen Pfaden** (absolut → `Error: invalid name`). `rmdir` verlangt einen leeren Ordner. Fehlendes Ziel → `Error: no such file`.

### Zeitstempel

Messung mit Psion-Uhr laut Display ≈ 17:22, Rechner 17:22 (Psion ~3 Minuten hinter dem Rechner, beide CEST):

| Quelle | Anzeige | Verhältnis zur Geräteuhr |
|---|---|---|
| `machinfo` „Current time“ | 18:18 | **+1 h** (UTC-Offset 3600 s addiert) |
| `ls` / `gtime` nach `put` | 19:18 | **+2 h** (UTC-Offset + DST addiert) |
| `gtime` nach `touch` | 17:21:54 = Rechnerzeit | symmetrisch: touch rechnet −2 h, gtime +2 h |

- Ursache: EPOC speichert Dateizeiten als Ortszeit; plptools behandelt den Rohwert als UTC und addiert Offset und DST. Der Rohwert in Klammern (`00e33964:07576600` = µs seit Jahr 0) entspricht der Geräte-Ortszeit.
- **Konsequenz:** `settime` und `touch` **nicht** verwenden – sie würden Uhr bzw. Dateizeit 2 h zu früh setzen.
- Auflösung: Sekunden in `ls`, Rohwert in Mikrosekunden.
- **Sync-Regel:** Psion-mtime aus `ls` nur nach Kalibrierung vergleichen. Beim Sync eine Datei `put`en, deren `gtime` gegen die Rechnerzeit stellen → Delta (Konvertierungsfehler + Uhrdrift) und alle Psion-Zeiten um dieses Delta korrigieren. Heute: Delta ≈ +1:56 h. Damit sind Zeitvergleiche im Konfliktfall zuverlässig auf ~1 Minute.

### Durchsatz

43 KB Testdatei bei 115200 Baud: `put` 8,8 KB/s (4,8 s), `get` 8,7 KB/s (4,9 s), Roundtrip bytegleich. Kleine Dateien kosten ~0,3–0,7 s Fixaufwand pro Aufruf (Prozessstart plpftp + Übertragung). Vollsync von 554 KB ≈ 65 s reine Übertragung plus ~112 × 0,5 s Aufwand ≈ 2 Minuten.

## Phase 1 – `psionsync` am Gerät (2026-09-17)

- `plpftp put`/`get` brauchen **lokale** Dateinamen relativ zum Arbeitsverzeichnis; absolute lokale Pfade → `Error: no such file` (put) bzw. `Error: general` (get). Der Wrapper startet plpftp deshalb in einem Temp-Verzeichnis.
- `plpftp test <relpfad>` gibt für Dateien und Ordner eine ls-Zeile aus, sonst `Error: no such file`; `ls` auf fehlenden Ordner → `Error: no such directory`.
- Gate-1-e2e mit Fixture-Vault bestanden: Erstsync (Push + Konflikt mit vorhandenen Testdateien), Psion-Änderung per `put` → Pull mit Unicode-Wiederherstellung, beidseitige Änderung → Konfliktkopie, Löschung auf dem Psion → Vault-Datei nach `state/trash/`. Vollständiger Lauf mit 4 Übertragungen: ~2 s; `status` gegen den echten Vault (112 Notizen, nur Listing + Kalibrierung): 3,6 s.
- Kalibrierungsdelta lag bei 2:00:17–2:00:19 (zuvor 1:56:26; der Benutzer hat die Geräteuhr zwischendurch gestellt). Das Delta wird bei jedem Lauf neu gemessen, daher unkritisch.
- Alle Testnotizen aus Fixture und Phase 0 sowie `_psionsync.clock` wurden anschließend mit Zustimmung des Benutzers vom Gerät gelöscht; `C:\Vault\` ist leer und bereit für den ersten echten Sync.

## Phase 2 – App (2026-09-17; Gate 2 am Gerät bestanden: Ordner/Umlaute ok, 48-KB-Notiz öffnet in ~2 s, „sehr responsiv“)

### OPL-Erkenntnisse (Compiler/Sprache)

- **String-Parameter nie beschreiben:** am Gerät ist ihre Maximallänge die Länge des übergebenen Werts → `Fehler in PSIVAULT\BASE$ String zu lang` (OpoLua prüft das nicht). Parameter zuerst in eine LOCAL mit fester Größe kopieren.
- **Max. 64 KB Variablen pro Prozedur** (Compilerfehler „Procedure variables exceed maximum size“). Große GLOBAL-Arrays deshalb über verschachtelte Prozeduren `main: → init2: → run:` verteilt.
- `OR`/`AND` werden **nicht verkürzt** ausgewertet: `IF q%=0 OR LEFT$(s$,q%-1)…` wirft bei `q%=0` „Invalid args“. Getrennte IFs verwenden.
- `DIR$` hält einen globalen Iterationszustand: erst alle Namen eines Ordners einsammeln, dann rekursiv absteigen. Im Emulator kommen Ordner **ohne** abschließendes `\`; die App prüft Ordner dann per `DIR$(name$+"\*")`. Am Gerät erwartet: Ordner mit `\` am Ende – verifizieren.
- Ereignisse per `GETEVENT32 ev&()`: Tastencode direkt in `ev&(1)` (Pfeile 4103–4106, Bild 4100/4101, Home/End 4098/4099, Menü 4150, Strg-Buchstabe = Buchstabe−64, also Strg-W = 23), Modifier in `ev&(4)`; Stift `&408` mit Typ in `ev&(4)` (0 = Stift ab) und x/y in `ev&(6)/(7)`; `&404` = Systembefehl (Schließen: `CMD$(3)="X"`). Mit `GET` (16 Bit) kollidierten End und Strg-E (beide 5).
- **Seitenleiste (am Gerät ermittelt):** Menü-Icon = Tastencode 10000 (`KKeySidebarMenu32%`). Die Lupen erzeugen **keinen Tastencode**, nur Key-Down/-Up (`&406`/`&407`) mit Scancode in `ev&(3)`: Lupe + = 10003, Lupe − = 10004. Vorsicht bei der Ereignis-Klassifizierung: `t& AND KEvNotKeyMask&` ist für 10000 wahr (Bit &400 gesetzt) – Nicht-Tasten-Ereignisse sind genau `&401`–`&40A`.
- `IOWRITE` im Textmodus schreibt am Gerät nur LF, OpoLua CRLF (`state.txt`); Lesen im Textmodus verkraftet beides.
- Headless-Handler von OpoLua kennt nur `GET`; `tools/smoke_app.lua` liefert `GETEVENT32`-Ereignisse selbst (16 Longs als `<i4`-String).
- Dateien werden komplett in einen `ALLOC`-Puffer gelesen (`IOSEEK` Modus 2 für die Größe, `IOREAD` in 16-KB-Stücken); Teilstrings holt `PEEK$` über ein temporär gesetztes Längenbyte. Quellzeilen > 255 Zeichen werden in 255-Byte-Fenstern umgebrochen.
- Layout ist **lazy**: nur bis ~30 Zeilen hinter der Sichtseite; End berechnet den Rest („Layout…“).

### OpoLua-Eigenheiten (nur Emulator)

- **Qt-Runtime: Verzeichnislisten kommen UTF-8**, Pfadargumente werden CP1252 interpretiert → Ordner mit Umlauten (`Entwürfe`, `Veröffentlicht`) sind im Qt-Emulator nicht betretbar (`KErrNotExists`). Für Qt-Tests eine Kopie mit ASCII-Namen verwenden (`app/dist/PsiVault.system/c/Vault`). Headless (`tools/smoke_app.lua`) betrifft das nicht.
- **String-Vergleich `<` ist in OpoLua kaputt** (`core/src/ops.lua`, `strcmp`: vergleicht nur das erste Zeichen, dann die Länge). Lokal in `/tmp/psivault-opolua` gepatcht (`byte(a, i) - byte(b, i)`); die Qt-Binärdatei nutzt vorkompilierte `.luac` und zeigt weiter falsche Sortierung. Upstream melden.
- `gTWIDTH` ist in der Qt-Runtime sehr teuer (Thread-Wechsel pro Aufruf): Voll-Layout der 48-KB-Notiz ~25 s in Qt, ~1 s headless. Keine Aussage über das Gerät möglich – dort messen.
- Headless-Test: `lua tools/smoke_app.lua OPOLUA DIST VAULTDIR` (Tastenskript durch Browser/Viewer/Wikilink) bzw. mit 4. Argument `C:\Vault\…md` als „mit Dokument gestartet“ (Stresstest, alle 112 Notizen bestanden). Testvault per `psionsync --fake-device DIR sync --apply` erzeugen.
- Screenshots der Qt-Runtime unter Hyprland: `grim -g` mit Geometrie aus `hyprctl clients -j`; Tasten per `wtype -k`.

## Phase 3 – Editor, Suche (2026-09-17, Emulator; Gerätetest steht aus)

- `dEDITMULTI ptr&,p$,breite%,zeilen%,maxLen%`: Puffer = 4-Byte-Länge + Text, `maxLen%` ist 16 Bit → max. ~32 KB. Absatztrenner `CHR$(6)`, erzwungener Umbruch `CHR$(7)`; die App wandelt CRLF ↔ `CHR$(6)` und schreibt `CHR$(6)/(7)/(8)` als CRLF zurück. Größere Notizen werden als Ausschnitt ab der aktuellen Zeile (28 KB) bearbeitet; Prefix/Suffix werden roh aus dem Dateipuffer geschrieben.
- Rohdaten in/aus Speicher ohne Längenbyte: `POKE$`/`PEEK$` an `addr-1` mit gesichertem Nachbarbyte (`pokeraw:`/`peekraw$:`).
- Atomares Ersetzen: `.tmp` schreiben, Original → `.bak`, `.tmp` → Name, `.bak` löschen (EPOC `RENAME` überschreibt nicht).
- Externe Änderung erkennen: Größe + chunkweiser Stringvergleich (255 Bytes) gegen den geladenen Puffer – 48 KB in ~190 nativen Vergleichen.
- Qt-Runtime: Beim Tippen in den Editor-Dialog kam es wiederholt zu „Completed“ (die Runtime erhielt eine Fenster-Schließanfrage → Systembefehl `X` → App beendet sich korrekt). Ursache liegt in der `wtype`/Hyprland-Kette, nicht in der App. Editor-Tests deshalb headless mit simuliertem Dialog (`tools/smoke_app.lua`, `SMOKE_EDIT=<PgDn-Anzahl>`; der Fake-Dialog hängt „ smoke“ an und drückt Speichern).
- Headless-Handler kennt kein `rename`-fsop; der Smoke-Test ergänzt es.
- Am Gerät bestätigt: `dEDITMULTI` markiert beim Öffnen den gesamten Text (nicht abschaltbar; die App fragt nach, wenn der Text beim Speichern auf < 50 % schrumpft). Zeilenhöhe im Dialog ist am Gerät größer als in OpoLua: 10 Zeilen ragen über das Display, 8 passen. Suche über 112 Notizen: ~9 s.
- Wortzählung per Byte-Schleife wäre am Gerät zu langsam; `words&:` nutzt `LOC` je Segment (Trenner Leerzeichen/CR/LF/Tab). Headless ~1,5 s für 48 KB → in der Leseansicht nur bis 12 KB exakt, sonst Schätzung (Bytes/8).

## App-Icon (2026-09-17)

- Icons liegen als Windows-BMP in `docs/psion_5mx_appicon_package/` (24/32/48 px, 4-bpp Graustufen + 1-bpp Masken). Kein BMCONV nötig: `tools/make_mbm.lua` baut mit OpoLuas `mbm.makeMbm` eine EPOC-MBM (`app/icon/PsiVault.mbm`), `build.sh` ruft es auf; `APP … ICON "../icon/PsiVault.mbm"` (Pfad relativ zum Arbeitsverzeichnis von `compile.lua`). `compile.lua --aif` bettet die Bitmaps in die AIF ein (`dumpaif.lua` zeigt sie).
- **Maskenpolarität am Gerät verifiziert:** EPOC zeichnet das Icon dort, wo die Maske **schwarz** ist (weiß = transparent). Die Paket-Masken sind innen weiß → ohne Invertierung erschien nur ein dünner Rahmen; `--invert-masks` behebt das. (OpoLuas Qt-Launcher interpretiert es genauso: QBitmap color1 = opak.)
- Die Extras-Leiste cacht AIF-Icons; nach dem Ersetzen der `.aif` einmal schließen/öffnen.

## Suchindex-Versuch (2026-09-17, verworfen)

- Bench am Gerät: 550-KB-Blob lesen 1 s, mit `LOC` in 255er-Blöcken durchsuchen 2 s; die restlichen ~6 s der 9-s-Suche sind das Öffnen der 112 Einzeldateien (~55 ms/Datei).
- `DIR$` liefert **am Gerät** Ordner ohne abschließenden `\` (wie OpoLua); die Bench-App fand deshalb nur Root-Dateien. PsiVault prüft nun jeden Nicht-`.md`-Eintrag per `isdir%:` (DIR$ mit `ONERR`), unabhängig von Punkten im Namen.
- Ein selbstgebauter Blob-Index (`search.idx`) scheiterte am Gerät mit „Datentypdiskrepanz“ beim Schreiben des ersten Notizinhalts (`IOWRITE` aus dem `ALLOC`-Puffer in die Indexdatei, während eine zweite Datei über `IOOPEN` geladen wurde); weder `ONERR` in der aufrufenden noch in der schreibenden Prozedur fing den Fehler. Ursache ungeklärt; im Emulator lief es. Benutzerentscheidung: Suche bleibt Datei-für-Datei (~9 s), Index verworfen. `psionsync` schreibt weiterhin `C:\Vault\_psionsync.gen` (Generationszähler), aktuell ohne Nutzer.
- OpoLua-Headless: `IOWRITE`/`ALLOC`-Sequenzen mit großen Dateien werden extrem langsam (Minuten); Editor-Tests mit `SMOKE_EDIT` funktionieren, Indexaufbau nicht praktikabel.
- `ncpd-psion.service` (User-Service, Wrapper folgt dem Adapter) hat den Adapter-Wechsel beim Aus-/Einschalten des Psion mehrfach automatisch überstanden.
