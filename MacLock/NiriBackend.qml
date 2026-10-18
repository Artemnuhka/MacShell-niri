import QtQuick
import Quickshell
import Quickshell.Io
import "NiriState.js" as State
import "DisplayState.js" as Displays

Scope {
    id: root
    signal changed()
    signal windowRemoved(var window)
    property var state: State.initial()
    property var windows: []
    readonly property var workspaces: state.workspaces
    readonly property var keyboardLayouts: state.keyboard
    property var outputs: ({})
    property bool connected: false
    property var handles: ({})
    property var lastFocusedWindowId: null
    property string lastFocusedOutput: ""
    readonly property var activeWindow: {
        for (var i = 0; i < windows.length; i++) if (windows[i].activated) return windows[i];
        for (var j = 0; j < windows.length; j++) if (windows[j].windowId === lastFocusedWindowId && focusedWorkspace && windows[j].workspace && windows[j].workspace.id === focusedWorkspace.id) return windows[j];
        return null;
    }
    readonly property var focusedWorkspace: {
        for (var i = 0; i < workspaces.length; i++) if (workspaces[i].is_focused) return workspaces[i];
        return null;
    }
    readonly property var focusedMonitor: {
        var name = focusedWorkspace && focusedWorkspace.output ? focusedWorkspace.output : lastFocusedOutput;
        if (name && (!Object.keys(outputs).length || (outputs[name] && outputs[name].logical))) return {name: name};
        var fallback = Displays.primary(Quickshell.screens, "", "");
        return fallback ? {name: fallback} : null;
    }
    readonly property var monitors: Displays.monitors(outputs, workspaces)
    function refreshOutputs() { if (!outputQuery.running) outputQuery.running = true; }
    Connections { target: Quickshell; function onScreensChanged() { outputsSoon.restart(); } }
    Timer { id: outputsSoon; interval: 100; onTriggered: root.refreshOutputs() }
    function monitorFor(screen) {
        for (var i = 0; i < monitors.length; i++) if (monitors[i].name === screen.name) return monitors[i];
        return null;
    }
    function action(name, args) { Quickshell.execDetached(["niri", "msg", "action", name].concat(args || [])); }
    function request(payload) {
        Quickshell.execDetached(["python3", decodeURIComponent(Qt.resolvedUrl("scripts/niri-ipc.py").toString().replace("file://", "")), JSON.stringify(payload)]);
    }
    function windowAction(id, name, args) {
        Quickshell.execDetached(["python3", decodeURIComponent(Qt.resolvedUrl("scripts/niri-ipc.py").toString().replace("file://", "")),
            "--window-action", String(id), name].concat(args || []));
    }
    function focusWindow(id) { request({Action:{FocusWindow:{id:id}}}); }
    function focusWorkspace(id) { request({Action:{FocusWorkspace:{reference:{Id:id}}}}); }
    function switchLayout(index) { request({Action:{SwitchLayout:{layout:{Index:index}}}}); }

    Component {
        id: windowComponent
        QtObject {
            property var data: ({})
            readonly property var windowId: data.id
            readonly property string address: String(data.id)
            readonly property string appId: data.app_id || ""
            readonly property string title: data.title || ""
            readonly property bool activated: data.is_focused === true
            readonly property bool urgent: data.is_urgent === true
            readonly property bool minimized: false
            readonly property bool fullscreen: {
                var o = workspace ? root.outputs[workspace.output] : null;
                var z = data.layout ? data.layout.tile_size : [0,0];
                return !!(o && o.logical && z[0] >= o.logical.width && z[1] >= o.logical.height);
            }
            readonly property bool maximized: false
            readonly property var workspace: {
                var ws = root.workspaces;
                for (var i = 0; i < ws.length; i++) if (ws[i].id === data.workspace_id) return ws[i];
                return null;
            }
            readonly property var lastIpcObject: ({id:data.id, address:String(data.id), class:appId,
                title:title, pid:data.pid || 0, floating:data.is_floating === true, fullscreen:fullscreen ? 1 : 0,
                mapped:true, hidden:false, monitor:workspace ? workspace.output : null, workspace:workspace})
            function activate() { root.focusWindow(data.id); }
            function close() { root.action("close-window", ["--id", String(data.id)]); }
        }
    }
    function synchronize() {
        var live = {}, list = [];
        state.windows.forEach(function(data) {
            var key = String(data.id), handle = handles[key];
            if (!handle) handle = windowComponent.createObject(root, {data:data});
            else handle.data = data;
            live[key] = handle;
            list.push(handle);
        });
        var focused = state.windows.filter(function(w) { return w.is_focused; })[0];
        if (focused) lastFocusedWindowId = focused.id;
        var old = handles;
        handles = Object.assign({}, old, live);
        windows = list;
        // Clear stale references before destroying closed-window objects.
        Object.keys(old).forEach(function(key) {
            if (!live[key]) {
                delete root.handles[key];
                root.windowRemoved(old[key]);
                old[key].destroy(0);
            }
        });
        if (focusedWorkspace && focusedWorkspace.output) lastFocusedOutput = focusedWorkspace.output;
        changed();
    }
    Process {
        id: stream
        command: ["niri", "msg", "--json", "event-stream"]
        running: true
        stdout: SplitParser {
            onRead: line => {
                try {
                    var e = JSON.parse(line);
                    root.connected = true;
                    root.state = State.apply(root.state, e);
                    if (e.WorkspacesChanged) outputsSoon.restart();
                    root.synchronize();
                } catch (err) { console.warn("[macshell-niri] Invalid IPC event:", err); }
            }
        }
        stderr: StdioCollector { onStreamFinished: if (text.trim()) console.warn("[macshell-niri]", text.trim()) }
        onExited: {
            root.connected = false;
            root.state = State.initial();
            root.synchronize();
            reconnect.restart();
        }
    }
    Timer { id: reconnect; interval: 2000; onTriggered: stream.running = true }
    Process {
        id: outputQuery
        command: ["niri", "msg", "--json", "outputs"]
        stdout: StdioCollector {
            onStreamFinished: {
                try { root.outputs = JSON.parse(text); root.changed(); }
                catch (err) { console.warn("[macshell-niri] Could not read outputs:", err); }
            }
        }
    }
    // Output geometry is not part of the event stream. Window/workspace state never polls.
    Timer { interval: 2000; repeat: true; running: true; triggeredOnStart: true; onTriggered: root.refreshOutputs() }
}
