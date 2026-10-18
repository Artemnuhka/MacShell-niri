import QtQuick
import Quickshell
import Quickshell.Wayland

// Register the actual rounded pane, not its rectangular layer window.
// The compositor renders the scene underneath, so this cannot capture itself.
Scope {
    id: root
    property bool enabled: false
    NiriGlassPane { active: root.enabled; target: root.target; radius: root.radius }
    required property Item target
    property real radius: 20
    readonly property var owner: target ? target.QsWindow.window : null
    property var registered: null
    property Region region: Region {
        item: root.target && root.target.visible && root.target.opacity > 0.001 ? root.target : null
        radius: Math.round(root.radius)
    }
    function detach() {
        if (registered && registered.glassRegions !== undefined)
            registered.glassRegions = registered.glassRegions.filter(function(r) { return r !== root.region; });
        registered = null;
    }
    function attach() {
        detach();
        if (enabled && owner && owner.glassRegions !== undefined) {
            registered = owner;
            owner.glassRegions = owner.glassRegions.concat([region]);
        }
    }
    function refresh() { region.changed(); }
    onEnabledChanged: Qt.callLater(attach)
    onOwnerChanged: Qt.callLater(attach)
    Component.onCompleted: attach()
    Component.onDestruction: detach()
    // Region geometry can otherwise lag behind scaled/animated ancestors (Qt/Quickshell).
    FrameAnimation {
        running: root.enabled && Quickshell.env("MACSHELL_REAL_GLASS") !== "1" && root.target && root.target.visible && root.target.opacity > 0.001 && root.owner && root.owner.visible
        onTriggered: root.refresh()
    }
    Connections {
        target: root.target
        function onXChanged() { root.refresh(); }
        function onYChanged() { root.refresh(); }
        function onWidthChanged() { root.refresh(); }
        function onHeightChanged() { root.refresh(); }
        function onVisibleChanged() { root.refresh(); }
    }
}
