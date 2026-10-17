import QtQuick
import Quickshell
import Quickshell.Wayland

// Real scene refraction requires the compositor variant built by build-glass.py.
// One input-transparent surface per slab gives the compositor the correct lens geometry.
Scope {
    id: root
    required property Item target
    property real radius: 20
    readonly property bool enabled: Quickshell.env("MACSHELL_REAL_GLASS") === "1"
    readonly property var owner: target ? target.QsWindow.window : null
    property bool geometryReady: false
    property real paneOpacity: 0
    property real paneX: 0
    property real paneY: 0
    property real paneW: 1
    property real paneH: 1
    property int paneRadius: 20
    function updateGeometry() {
        if (!owner || !target) return;
        var p = target.mapToItem(owner.contentItem, 0, 0);
        var q = target.mapToItem(owner.contentItem, target.width, target.height);
        var bottomOffset = owner.anchors.bottom && !owner.anchors.top ? owner.screen.height - owner.height : 0;
        paneX = Math.round(p.x);
        paneY = Math.round(p.y + bottomOffset);
        paneW = Math.max(1, Math.round(q.x - p.x));
        paneH = Math.max(1, Math.round(q.y - p.y));
        paneRadius = Math.max(0, Math.min(64, Math.round(radius)));
        var alpha = 1, node = target;
        while (node && node !== owner.contentItem) { alpha *= node.opacity; node = node.parent; }
        paneOpacity = alpha;
        geometryReady = true;
    }
    FrameAnimation {
        running: root.enabled && root.owner && root.owner.visible && root.target.visible
        onTriggered: root.updateGeometry()
    }
    PanelWindow {
        screen: root.owner ? root.owner.screen : null
        visible: root.enabled && root.geometryReady && root.owner && root.owner.visible && root.target.visible && root.paneOpacity > 0.001
        color: "transparent"
        anchors { top: true; left: true }
        margins { top: root.paneY; left: root.paneX }
        implicitWidth: root.paneW
        implicitHeight: root.paneH
        // Setting exclusiveZone would reset Ignore to Normal and shift lenses below the bar.
        exclusionMode: ExclusionMode.Ignore
        WlrLayershell.namespace: "macglasspane-r" + root.paneRadius
        WlrLayershell.layer: WlrLayer.Top
        WlrLayershell.keyboardFocus: WlrKeyboardFocus.None
        mask: Region {}
        BackgroundEffect.blurRegion: Region { width: root.paneW; height: root.paneH; radius: root.paneRadius }
    }
}
