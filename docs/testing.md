# Automatisierte Tests

Alle Tests verwenden temporäre Verzeichnisse und Fake-Transport bzw. OpoLua.
Sie greifen weder auf den echten Vault noch auf den Psion zu. Die OPL-App wird
aus dem aktuellen Quelltext in ein temporäres Build-Verzeichnis kompiliert;
`app/dist/` wird dabei nicht verändert.

## Aktueller Prüflauf – 17.09.2026

Die Python-Suite mit `--ignore=tests/test_app.py` besteht mit **77 Tests**.
Im zuletzt ausgeführten Gesamtlauf scheiterten **9 OPL-Tests**: die acht Varianten
von `test_app_long_frontmatter_terminates` mit jeweils 20 Sekunden Timeout und
`test_app_reuses_search_index_and_rebuilds_after_sync` mit null statt einer
erwarteten Index-Neuerstellung. Die Gesamtsuite ist daher nicht grün. Die unten
beschriebene Abdeckung nennt die vorhandenen Tests, nicht ausschließlich
bestandene Prüfungen.

## Lokal

```sh
python -m venv .venv
.venv/bin/pip install -e '.[dev]'
.venv/bin/pytest
```

Die Python-Tests funktionieren ohne OpoLua. Für die App-Tests werden Lua und ein
OpoLua-Checkout benötigt (keine Qt-Runtime und keine Submodule). Geprüfter Stand:
`6bb10d5b60ce94abea20b9e1f0abb61d33218649` aus
<https://github.com/inseven/opolua>.

```sh
OPOLUA_DIR=/pfad/zu/opolua REQUIRE_OPL_TESTS=1 .venv/bin/pytest
```

Ohne `OPOLUA_DIR` wird `/tmp/psivault-opolua` versucht. Fehlt der Compiler oder
Lua, werden die App-Tests lokal ausdrücklich als übersprungen angezeigt.
`REQUIRE_OPL_TESTS=1` macht daraus einen Fehler. `LUA=lua5.4` kann einen bestimmten
Interpreter wählen. Die Compiler-Aufrufe haben 30 Sekunden, die einzelnen
App-Prozesse 20 Sekunden Zeit; Endlosschleifen führen zu einem fehlgeschlagenen
Test statt einem endlos laufenden Job.

## Was geprüft wird

- Python: Sync-Fälle, Kodierung, Unicode-Rückgewinnung, State, CLI und
  Transport-Parser; außerdem veraltete Pläne auf beiden Seiten, kollidierende
  Konfliktkopien, Unicode-Teilverluste und gezieltes Auffrischen der Geräteordner.
- Omarchy-Brücke: lokale Anzeige ohne Gerät, Sync gegen Fake-Transport,
  doppelte Starts, unterbrochene Läufe, fehlende Verbindung, beschädigter State
  und übersprungene Notizen. Das QML-Panel selbst ist nicht Teil der Python-Tests.
- OPL: Browser/Wikilinks/Umlaute, langes Frontmatter einschließlich Dateiende
  ohne Zeilenumbruch, Suchindex-Wiederverwendung und Generationenwechsel,
  vollständige Suchkontextzeilen, Anlegen/Löschen und Editor-Roundtrips für
  kleine Notizen und Ausschnitte großer Notizen.
- Die Flows prüfen echte Ergebnisse: gespeicherte Bytes, erhaltene Nachbartexte,
  gelöschte Dateien und sichtbare Treffer. Ein vorzeitig beendetes Tastenskript
  ist ein Fehler. Ein Negativtest prüft auch den Testtreiber selbst.

## CI

Das Projekt wird parallel auf GitHub und GitLab gepflegt.
`.github/workflows/ci.yml` führt auf GitHub Actions drei Jobs aus: die Python-Tests,
den Bau von `PsiVault.app`/`.aif` (als Workflow-Artefakt; bei einem `v*`-Tag zusätzlich
als ZIP an das Release angehängt) und die OPL-Tests. Der OPL-Job bezieht den oben
festgelegten Commit und verlangt, dass die OPL-Tests tatsächlich ausgeführt werden;
wegen der oben genannten neun bekannten Fehlschläge ist er mit `continue-on-error`
markiert und blockiert den Workflow nicht. Es gibt keinen Deploy-Schritt und keine
Geräte-/Vault-Zugangsdaten.

`.gitlab-ci.yml` führt auf GitLab dieselben Python- und OPL-Tests in getrennten
Jobs aus und veröffentlicht JUnit-Ergebnisse; der OPL-Job schlägt dort wegen der
bekannten Fehler fehl.

## Grenzen und Betriebsregel

OpoLua verwendet synthetische Schriftmetriken: Fonts, Layout und Geschwindigkeit
auf dem 36-MHz-Gerät benötigen weiterhin eine Geräteabnahme. Serielle Abbrüche
und Dateisperren werden nicht durch einen Emulator vollständig nachgebildet.

Der Sync prüft beide Dateiinhalte unmittelbar vor jedem geplanten Schritt erneut
und bricht bei einer Abweichung ohne diesen Schritt ab. Das kostet zusätzliche
Downloads für tatsächlich bearbeitete Dateien; unveränderte Dateien benötigen
weiterhin keinen Download. Diese optimistische Prüfung ist **keine gemeinsame
Sperre** zwischen Nextcloud, Editor und seriellen Dateioperationen. Änderungen
während der unmittelbar anschließenden Schreiboperation sind dadurch nicht
atomar ausgeschlossen. Während eines Syncs deshalb keine gleichzeitigen
Schreibvorgänge auf denselben Dateien starten. Eine gemeinsame Sperr-/Commit-
Vereinbarung mit PsiVault bleibt eine separate Erweiterung.

## Review-Korrektur

Die ursprüngliche Review-Aussage zum Suchindex-Header war falsch:
`PSIVAULT-IDX 1 ` hat 15 Zeichen, die ursprünglichen Offsets 15/16 sind korrekt.
Ein Regressionstest soll die Wiederverwendung absichern, schlägt im aktuellen
Prüflauf jedoch fehl (siehe oben). Die frühere Review dokumentierte außerdem
die Korrektur eines zusätzlich übersprungenen Zeichens in der Suchkontextzeile.
