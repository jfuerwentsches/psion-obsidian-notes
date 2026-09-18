import QtQuick
import Quickshell
import Quickshell.Io
import qs.Commons
import qs.Ui

BarWidget {
    id: root
    moduleName: "jf.psionsync"
    property bool menuOpen: false
    property string detail: "Sync-Status wird geladen …"
    property string syncState: "idle"
    property var local: ({})
    property var result: ({})
    property string output: ""
    property bool showOutput: false
    readonly property bool checking: checkProc.running
    readonly property bool busy: syncProc.running || checkProc.running || syncState === "running"
    readonly property color foreground: bar ? bar.foreground : Color.foreground
    readonly property string fontFamily: bar ? bar.fontFamily : Style.font.family
    readonly property string python: setting("python", "python3")
    readonly property string vault: setting("vault", Quickshell.env("HOME") + "/Documents/Obsidian/Vault")
    readonly property string stateDir: setting("stateDir", Quickshell.env("HOME") + "/.local/state/psionsync")
    readonly property var baseCommand: [python, "-u", "-m", "psionsync.desktop", "--vault", vault, "--state-dir", stateDir]
    readonly property string headline: checking ? "Psion wird geprüft …"
        : busy ? "Synchronisierung läuft …"
        : syncState === "error" ? "Sync prüfen"
        : syncState === "warning" ? "Sync mit Hinweisen"
        : local.pending > 0 ? local.pending + " lokale Änderungen"
        : local.last_sync ? "Lokal auf aktuellem Stand" : "Bereit für den ersten Sync"
    readonly property var changes: [].concat(
        (local.new || []).map(function(p) { return {name: p, kind: "+"} }),
        (local.changed || []).map(function(p) { return {name: p, kind: "~"} }),
        (local.deleted || []).map(function(p) { return {name: p, kind: "−"} }))
    implicitWidth: button.implicitWidth
    implicitHeight: button.implicitHeight

    function close() { menuOpen = false }
    function refresh() { if (!statusProc.running) statusProc.running = true }
    function appendOutput(line) { output = (output + line + "\n").slice(-12000) }
    function startSync() {
        if (busy) return
        output = ""
        showOutput = true
        syncProc.running = true
    }
    function startCheck() {
        if (busy) return
        output = ""
        showOutput = true
        checkProc.running = true
    }
    function formattedTime(value) {
        if (!value) return "Noch nie"
        const date = new Date(value)
        return isNaN(date.getTime()) ? value : Qt.formatDateTime(date, "dd.MM.yyyy · HH:mm")
    }

    Process {
        id: statusProc
        command: root.baseCommand.concat(["status"])
        stdout: StdioCollector {
            onStreamFinished: {
                try {
                    const data = JSON.parse(text)
                    root.detail = data.tooltip
                    root.syncState = data.status
                    if (data.local) root.local = data.local
                    if (data.result) root.result = data.result
                } catch (error) {
                    root.detail = "Status konnte nicht gelesen werden. Installation prüfen."
                    root.syncState = "error"
                }
            }
        }
        onExited: function(code) {
            if (code !== 0) {
                root.detail = "Statusabfrage fehlgeschlagen. Installation prüfen."
                root.syncState = "error"
            }
        }
    }

    Process {
        id: syncProc
        command: root.baseCommand.concat(["sync"])
        stdout: SplitParser { onRead: function(line) { root.appendOutput(line) } }
        stderr: SplitParser { onRead: function(line) { root.appendOutput(line) } }
        onExited: function(code) {
            if (code !== 0) root.appendOutput("Sync fehlgeschlagen (" + code + ").")
            root.refresh()
        }
    }

    // Dry-Run mit Gerät: startet ncpd, holt den Plan inklusive Psion-Seite, ändert nichts.
    Process {
        id: checkProc
        command: root.baseCommand.concat(["check"])
        stdout: SplitParser { onRead: function(line) { root.appendOutput(line) } }
        stderr: SplitParser { onRead: function(line) { root.appendOutput(line) } }
        onExited: function(code) {
            if (code !== 0) root.appendOutput("Prüfung fehlgeschlagen (" + code + ").")
            root.refresh()
        }
    }

    Timer {
        interval: root.menuOpen || root.busy ? 2000 : 10000
        repeat: true
        running: true
        triggeredOnStart: true
        onTriggered: root.refresh()
    }

    BarIconButton {
        id: button
        anchors.fill: parent
        bar: root.bar
        text: "󰜉"
        tooltipText: "Psion Sync · " + root.headline
        active: root.busy || root.syncState === "error" || root.syncState === "warning" || root.local.pending > 0
        onPressed: {
            root.refresh()
            root.menuOpen = !root.menuOpen
        }
    }

    PopupCard {
        id: menu
        anchorItem: button
        owner: root
        bar: root.bar
        open: root.menuOpen
        contentWidth: menu.fittedContentWidth(Style.space(360))
        contentHeight: menu.fittedContentHeight(menuColumn.implicitHeight)

        Flickable {
            anchors.fill: parent
            contentHeight: menuColumn.implicitHeight
            clip: true
            boundsBehavior: Flickable.StopAtBounds

            Column {
                id: menuColumn
                width: parent.width
                spacing: Style.space(12)

                PanelHero {
                    id: hero
                    width: parent.width
                    title: "Psion Sync"
                    meta: "Obsidian ↔ Psion 5mx"
                    foreground: root.foreground
                    fontFamily: root.fontFamily
                    iconComponent: Component {
                        Text {
                            text: "󰜉"
                            color: hero.foreground
                            font.family: hero.fontFamily
                            font.pixelSize: Style.font.display
                        }
                    }
                }

                PanelSeparator { foreground: root.foreground }

                Copy {
                    text: root.headline
                    font.pixelSize: Style.font.body
                    font.bold: true
                }

                Row {
                    width: parent.width
                    Repeater {
                        model: [
                            {label: "Neu", count: (root.local.new || []).length},
                            {label: "Geändert", count: (root.local.changed || []).length},
                            {label: "Gelöscht", count: (root.local.deleted || []).length}
                        ]
                        Column {
                            required property var modelData
                            width: menuColumn.width / 3
                            spacing: Style.space(3)
                            Copy { text: modelData.count; font.pixelSize: Style.font.title }
                            Copy { text: modelData.label; opacity: 0.6 }
                        }
                    }
                }

                Copy {
                    text: "Letzter Sync-Stand\n" + root.formattedTime(root.local.last_sync)
                    opacity: 0.75
                }

                Copy {
                    visible: !root.busy && (root.syncState === "error" || root.syncState === "warning")
                    text: root.result.message || root.detail
                }

                Flickable {
                    visible: root.changes.length > 0 && !root.showOutput
                    width: parent.width
                    height: Math.min(fileList.implicitHeight, Style.space(120))
                    contentHeight: fileList.implicitHeight
                    clip: true
                    boundsBehavior: Flickable.StopAtBounds
                    Column {
                        id: fileList
                        width: parent.width
                        spacing: Style.space(5)
                        Repeater {
                            model: root.changes
                            Copy {
                                required property var modelData
                                text: modelData.kind + "  " + modelData.name
                                elide: Text.ElideMiddle
                                wrapMode: Text.NoWrap
                                opacity: 0.75
                            }
                        }
                    }
                }

                Copy {
                    text: "„Psion prüfen“ zeigt den geplanten Sync inklusive Psion-Seite, ohne etwas zu ändern."
                    opacity: 0.55
                }

                PanelSeparator { foreground: root.foreground }

                Row {
                    width: parent.width
                    spacing: Style.space(8)
                    Button {
                        width: parent.width - checkButton.width - parent.spacing
                        text: root.checking ? "Psion wird geprüft …"
                            : root.busy ? "Synchronisierung läuft …" : "Jetzt synchronisieren"
                        iconText: "󰜉"
                        iconSpinning: root.busy && !root.checking
                        bordered: true
                        selected: true
                        enabled: !root.busy
                        foreground: root.foreground
                        fontFamily: root.fontFamily
                        onClicked: root.startSync()
                    }
                    Button {
                        id: checkButton
                        text: "Psion prüfen"
                        iconText: "󰍉"
                        iconSpinning: root.checking
                        bordered: true
                        enabled: !root.busy
                        foreground: root.foreground
                        fontFamily: root.fontFamily
                        onClicked: root.startCheck()
                    }
                }

                Button {
                    visible: root.output !== ""
                    text: root.showOutput ? "Verlauf ausblenden" : "Verlauf anzeigen"
                    foreground: root.foreground
                    fontFamily: root.fontFamily
                    fontSize: Style.font.bodySmall
                    onClicked: root.showOutput = !root.showOutput
                }

                Flickable {
                    id: logView
                    visible: root.showOutput && root.output !== ""
                    width: parent.width
                    height: Math.min(logText.implicitHeight, Style.space(140))
                    contentHeight: logText.implicitHeight
                    clip: true
                    boundsBehavior: Flickable.StopAtBounds
                    Copy {
                        id: logText
                        text: root.output
                        opacity: 0.7
                        onTextChanged: Qt.callLater(function() {
                            logView.contentY = Math.max(0, logView.contentHeight - logView.height)
                        })
                    }
                }
            }
        }
    }

    component Copy: Text {
        width: parent.width
        textFormat: Text.PlainText
        color: root.foreground
        font.family: root.fontFamily
        font.pixelSize: Style.font.bodySmall
        wrapMode: Text.Wrap
    }
}
