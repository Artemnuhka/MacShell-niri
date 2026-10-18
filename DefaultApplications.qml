import QtQuick
import QtQuick.Controls
import Quickshell
import Quickshell.Io

Column {
    id: root
    required property var theme
    property var bar: null
    property var roles: []
    property var pending: ({})
    property string message: "Loading installed applications…"
    property bool failed: false
    property bool saving: false
    readonly property bool dirty: Object.keys(pending).length > 0
    readonly property string helper: Qt.resolvedUrl("scripts/default-apps.py").toString().replace(/^file:\/\//, "")
    spacing: 12
    function choose(role, appId) {
        var next = Object.assign({}, pending);
        if (appId === role.current) delete next[role.id];
        else next[role.id] = appId;
        pending = next;
    }
    function iconSource(icon) {
        if (!icon) return "";
        return icon.charAt(0) === "/" ? "file://" + icon : Quickshell.iconPath(icon, true);
    }
    function apply() {
        if (request.running || !dirty) return;
        saving = true; failed = false; message = "Applying…";
        request.changes = Object.assign({}, pending);
        request.command = ["python3", helper, "apply", JSON.stringify(request.changes)];
        request.running = true;
    }
    Component.onCompleted: { request.command = ["python3", helper]; request.running = true; }
    Process {
        id: request
        property var changes: ({})
        property string errorText: ""
        onRunningChanged: if (running) errorText = ""
        stdout: StdioCollector {
            onStreamFinished: {
                try {
                    root.roles = JSON.parse(text).roles;
                    if (root.saving) {
                        if (request.changes.terminal && root.bar) root.bar.terminal = "default";
                        if (request.changes.files && root.bar) root.bar.filesCmd = 'xdg-open "$HOME"';
                        root.pending = ({});
                    }
                    root.message = root.saving ? "Default applications saved." : "Choose applications, then click Apply.";
                } catch (error) { request.errorText = "Could not read application preferences."; }
            }
        }
        stderr: StdioCollector { onStreamFinished: if (text.trim()) request.errorText = text.trim().split("\n").slice(-1)[0] }
        onExited: (code, status) => {
            root.failed = code !== 0 || errorText !== "";
            if (root.failed) root.message = errorText || "Could not save application preferences.";
            root.saving = false;
        }
    }
    Text {
        width: parent.width; wrapMode: Text.WordWrap
        text: "Choose which apps open links and files for your user account. Terminal is used by MacShell and its terminal shortcut."
        color: root.theme.text2; font.family: root.theme.fam; font.pixelSize: 12
    }
    Repeater {
        model: root.roles
        delegate: Column {
            id: roleRow
            required property var modelData
            width: root.width; spacing: 5
            Text { text: roleRow.modelData.name; color: root.theme.text; font.family: root.theme.fam; font.pixelSize: 13; font.weight: Font.Medium }
            ComboBox {
                id: picker
                width: parent.width; height: 36
                model: roleRow.modelData.apps; textRole: "name"
                enabled: !request.running && count > 0
                currentIndex: {
                    var value = root.pending[roleRow.modelData.id] || roleRow.modelData.current;
                    for (var i = 0; i < roleRow.modelData.apps.length; i++) if (roleRow.modelData.apps[i].id === value) return i;
                    return -1;
                }
                onActivated: root.choose(roleRow.modelData, roleRow.modelData.apps[currentIndex].id)
                font.family: root.theme.fam; font.pixelSize: 13
                contentItem: Item {
                    Image {
                        id: currentIcon
                        x: 10; width: 22; height: 22; anchors.verticalCenter: parent.verticalCenter
                        source: picker.currentIndex >= 0 ? root.iconSource(roleRow.modelData.apps[picker.currentIndex].icon) : ""
                        fillMode: Image.PreserveAspectFit; sourceSize: Qt.size(48, 48)
                    }
                    Text {
                        x: 42; width: parent.width - 68; anchors.verticalCenter: parent.verticalCenter
                        text: picker.currentIndex >= 0 ? picker.displayText : (picker.count ? "Not set" : "No compatible application installed")
                        color: root.theme.text; font: picker.font; elide: Text.ElideRight
                    }
                }
                indicator: Text { x: parent.width - 22; anchors.verticalCenter: parent.verticalCenter; text: "⌄"; color: root.theme.text; font.pixelSize: 16 }
                background: Rectangle { radius: 7; color: root.theme.card; border.color: root.theme.cardBorder }
                delegate: ItemDelegate {
                    id: option
                    required property var modelData
                    required property int index
                    width: picker.width; height: 36
                    highlighted: picker.highlightedIndex === index
                    contentItem: Row {
                        spacing: 10
                        Image { width: 22; height: 22; anchors.verticalCenter: parent.verticalCenter; source: root.iconSource(option.modelData.icon); sourceSize: Qt.size(48, 48); fillMode: Image.PreserveAspectFit }
                        Text { width: parent.width - 42; anchors.verticalCenter: parent.verticalCenter; text: option.modelData.name; font: picker.font; color: option.highlighted ? "white" : root.theme.text; elide: Text.ElideRight }
                    }
                    background: Rectangle { radius: 5; color: option.highlighted ? root.theme.accent : "transparent" }
                }
                popup: Popup {
                    y: picker.height + 3; width: picker.width; padding: 6
                    implicitHeight: Math.min(contentItem.implicitHeight + 12, 260)
                    background: Rectangle { radius: 9; color: root.theme.card; border.color: root.theme.cardBorder }
                    contentItem: ListView {
                        clip: true; implicitHeight: contentHeight
                        model: picker.popup.visible ? picker.delegateModel : null
                        currentIndex: picker.highlightedIndex
                        ScrollIndicator.vertical: ScrollIndicator { }
                    }
                }
            }
        }
    }
    Text {
        width: parent.width; text: root.message; wrapMode: Text.WordWrap
        color: root.failed ? root.theme.danger : root.theme.text2; font.family: root.theme.fam; font.pixelSize: 12
    }
    Button {
        text: root.saving ? "Applying…" : "Apply"; enabled: root.dirty && !request.running
        implicitWidth: 90; implicitHeight: 30
        contentItem: Text { text: parent.text; color: root.theme.text; font.family: root.theme.fam; font.pixelSize: 13; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
        background: Rectangle { radius: 6; color: parent.down ? root.theme.ctrlSel : root.theme.ctrl; border.color: root.theme.cardBorder; opacity: parent.enabled ? 1 : 0.4 }
        onClicked: root.apply()
    }
}
