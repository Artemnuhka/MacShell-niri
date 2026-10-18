import QtQuick
import QtQuick.Controls
import Quickshell.Io

Column {
    id: root
    required property var theme
    spacing: 10
    property var available: []
    property var shortcuts: []
    property var layouts: []
    property string shortcut: ""
    property string message: "Loading input sources…"
    property bool failed: false
    property bool saving: false
    property string query: ""
    readonly property var choices: available.filter(function (v) { return (v.name + " " + v.code).toLowerCase().indexOf(query.toLowerCase()) >= 0; })
    readonly property var variants: source.currentIndex >= 0 && choices[source.currentIndex] ? choices[source.currentIndex].variants : []
    readonly property string helper: Qt.resolvedUrl("scripts/niri-settings.py").toString().replace(/^file:\/\//, "")
    function label(value) {
        for (var i = 0; i < available.length; i++) {
            var item = available[i];
            if (item.code !== value.code) continue;
            for (var j = 0; j < item.variants.length; j++)
                if (item.variants[j].code === value.variant)
                    return item.name + (value.variant ? " · " + item.variants[j].name : "");
        }
        return value.code + (value.variant ? " · " + value.variant : "");
    }
    function apply() {
        if (request.running) return;
        failed = false; saving = true; message = "Applying…";
        request.command = ["python3", helper, "keyboard", JSON.stringify({layouts: layouts, shortcut: shortcut})];
        request.running = true;
    }
    Component.onCompleted: { request.command = ["python3", helper, "keyboard"]; request.running = true; }
    Process {
        id: request
        property string errorText: ""
        onRunningChanged: if (running) errorText = ""
        stdout: StdioCollector {
            onStreamFinished: {
                try {
                    var info = JSON.parse(text);
                    root.available = info.available; root.shortcuts = info.shortcuts;
                    root.layouts = info.layouts; root.shortcut = info.shortcut;
                    if (root.query === "" && info.layouts.length) {
                        for (var i = 0; i < root.choices.length; i++)
                            if (root.choices[i].code === info.layouts[0].code) { source.currentIndex = i; break; }
                    }
                    root.message = root.saving ? "Applied. Your input sources and shortcut are saved." : "Changes apply when you click Apply.";
                } catch (e) { request.errorText = "Could not read keyboard settings."; }
            }
        }
        stderr: StdioCollector { onStreamFinished: if (text.trim()) request.errorText = text.trim().split("\n").slice(-1)[0] }
        onExited: (code, status) => {
            root.failed = code !== 0 || request.errorText !== "";
            if (root.failed) root.message = request.errorText || "Could not apply keyboard settings. Existing settings were kept.";
            root.saving = false;
        }
    }
    component Picker: ComboBox {
        id: picker
        contentItem: Text {
            leftPadding: 10; rightPadding: 24
            text: picker.displayText; color: root.theme.text
            font: picker.font; verticalAlignment: Text.AlignVCenter; elide: Text.ElideRight
        }
        indicator: Text { x: parent.width - 20; anchors.verticalCenter: parent.verticalCenter; text: "⌄"; color: root.theme.text; font.pixelSize: 15 }
        background: Rectangle { radius: 6; color: root.theme.ctrl; border.color: root.theme.cardBorder }
        delegate: ItemDelegate {
            required property var modelData
            required property int index
            width: picker.width
            contentItem: Text { text: parent.modelData.name; color: root.theme.text; font: picker.font; elide: Text.ElideRight }
            background: Rectangle { radius: 5; color: parent.highlighted ? root.theme.accent : "transparent" }
            highlighted: picker.highlightedIndex === index
        }
        popup: Popup {
            y: picker.height + 3; width: Math.max(220, picker.width); padding: 6
            implicitHeight: Math.min(contentItem.implicitHeight + 12, 260)
            background: Rectangle { radius: 8; color: root.theme.card; border.color: root.theme.cardBorder }
            contentItem: ListView {
                clip: true; implicitHeight: contentHeight
                model: picker.popup.visible ? picker.delegateModel : null
                currentIndex: picker.highlightedIndex
                ScrollIndicator.vertical: ScrollIndicator { }
            }
        }
        font.family: root.theme.fam; font.pixelSize: 12
        height: 32
        palette.button: root.theme.ctrl
        palette.buttonText: root.theme.text
        palette.base: root.theme.card
        palette.text: root.theme.text
        palette.window: root.theme.card
        palette.windowText: root.theme.text
        palette.highlight: root.theme.accent
        textRole: "name"
    }
    component ActionButton: Button {
        implicitWidth: Math.max(68, contentItem.implicitWidth + 22); implicitHeight: 30
        contentItem: Text { text: parent.text; color: root.theme.text; font.family: root.theme.fam; font.pixelSize: 12; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
        background: Rectangle { radius: 6; color: parent.down ? root.theme.ctrlSel : root.theme.ctrl; border.color: root.theme.cardBorder; opacity: parent.enabled ? 1 : 0.4 }
    }
    Text { text: "Input Sources"; color: root.theme.text; font.family: root.theme.fam; font.pixelSize: 13; font.weight: Font.DemiBold }
    Rectangle {
        width: parent.width; height: sourcesColumn.implicitHeight; radius: 10
        color: root.theme.card; border.color: root.theme.cardBorder
        Column {
            id: sourcesColumn; width: parent.width
            Repeater {
                model: root.layouts
                delegate: Item {
                    id: sourceRow
                    required property var modelData
                    required property int index
                    width: sourcesColumn.width; height: 46
                    Text {
                        x: 14; anchors.verticalCenter: parent.verticalCenter
                        width: parent.width - 70; elide: Text.ElideRight
                        text: root.label(sourceRow.modelData)
                        color: root.theme.text; font.family: root.theme.fam; font.pixelSize: 13
                    }
                    ActionButton {
                        anchors.right: parent.right; anchors.rightMargin: 10; anchors.verticalCenter: parent.verticalCenter
                        width: 30; height: 28; text: "−"; enabled: root.layouts.length > 1 && !request.running
                        onClicked: { var next = root.layouts.slice(); next.splice(sourceRow.index, 1); root.layouts = next; }
                    }
                }
            }
        }
    }
    TextField {
        width: parent.width; height: 32
        placeholderText: "Search input sources…"
        font.family: root.theme.fam; font.pixelSize: 12
        color: root.theme.text; placeholderTextColor: root.theme.text2
        background: Rectangle { radius: 7; color: root.theme.ctrl; border.color: root.theme.cardBorder }
        onTextChanged: { root.query = text; source.currentIndex = 0; variant.currentIndex = 0; }
    }
    Row {
        width: parent.width; spacing: 8
        Picker { id: source; width: (parent.width - 76) * 0.48; model: root.choices; onActivated: variant.currentIndex = 0 }
        Picker { id: variant; width: (parent.width - 76) * 0.52; model: root.variants }
        ActionButton {
            text: "+"; width: 60; height: 32
            enabled: root.layouts.length < 4 && root.choices.length > 0 && !request.running
            onClicked: {
                var selected = root.choices[source.currentIndex];
                var v = root.variants[Math.max(0, variant.currentIndex)];
                if (!selected || !v) return;
                for (var i = 0; i < root.layouts.length; i++)
                    if (root.layouts[i].code === selected.code && root.layouts[i].variant === v.code) return;
                root.layouts = root.layouts.concat([{code: selected.code, variant: v.code}]);
            }
        }
    }
    Text { text: "Switch input source"; color: root.theme.text; font.family: root.theme.fam; font.pixelSize: 13 }
    Picker {
        width: parent.width; model: root.shortcuts
        currentIndex: { for (var i = 0; i < root.shortcuts.length; i++) if (root.shortcuts[i].code === root.shortcut) return i; return -1; }
        onActivated: root.shortcut = root.shortcuts[currentIndex].code
    }
    Text {
        width: parent.width; wrapMode: Text.WordWrap
        text: root.message; color: root.failed ? root.theme.danger : root.theme.text2
        font.family: root.theme.fam; font.pixelSize: 12
    }
    ActionButton { text: root.saving ? "Applying…" : "Apply"; enabled: !request.running && root.layouts.length > 0; onClicked: root.apply() }
}
