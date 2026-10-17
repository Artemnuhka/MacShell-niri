import QtQuick
import Quickshell
import Quickshell.Io

ShellRoot {
    NiriBackend { id: niri }
    AppIcons { id: appIcons }
    Scope {
        id: sharedHub
        property var compositor: niri
        property var icons: appIcons
        readonly property var closingWins: ({})
        readonly property bool previewHold: true
        readonly property var monData: niri.monitors
        // Niri does not expose Hyprland's per-window capture handles.
        // Scene effects are rendered by niri; never feed IPC objects to ScreencopyView.
        readonly property var glassClients: []
        property var wallpaperMap: ({})
        property var bar: macBar
        property var dock: macDock
        property var widgets: macWidgets
        property var clock: clockApp
        function openSettings(pane) { macDock.openPrefs(pane); }
        property bool barWantsGeo: false
        property bool dockWantsGeo: false
        property bool barWantsWallpaper: false
        property bool dockWantsWallpaper: false
        property bool widgetsWantWallpaper: false
        readonly property bool captureQuiet: true
        readonly property bool windowCapture: false
        readonly property bool captureHold: true
        readonly property bool captureCut: true
        readonly property bool glassHold: true
        readonly property int tlTick: 0
        function tlFor(addr) { return null; }
        function refreshWallpaper() { if (!wpProc.running) wpProc.running = true; }
        // wallpaper the glass refracts (Noctalia settings.toml -> awww/swww/hyprpaper)
        Process {
            id: wpProc
            command: ["sh", "-c",
                ""
                + "out=\"\"\n"
                + "st=\"${XDG_STATE_HOME:-$HOME/.local/state}/noctalia\"; ns=\"${NOCTALIA_STATE_HOME:-/nonexistent}\"\n"
                + "for f in \"$ns/settings.toml\" \"$st/settings.toml\" \"$HOME/.config/noctalia/settings.toml\" \"$HOME/.config/noctalia/config.toml\"; do\n"
                + "  [ -f \"$f\" ] || continue\n"
                + "  out=\"$out$(awk '\n"
                + "    /^[ \\t]*\\[\\[/ { sec = \"\"; next }\n"
                + "    /^[ \\t]*\\[/ { sec = $0; gsub(/[\\[\\] \\t\"]/, \"\", sec); next }\n"
                + "    sec ~ /^wallpaper\\.(default|last|monitors\\..+)$/ && /^[ \\t]*path[ \\t]*=/ {\n"
                + "      v = $0; sub(/^[^=]*=[ \\t]*\"/, \"\", v); sub(/\".*$/, \"\", v); print sec \"\\t\" v\n"
                + "    }' \"$f\")\n"
                + "\"\n"
                + "done\n"
                + "if [ -z \"$(printf %s \"$out\" | tr -d ' \\t\\n')\" ]; then\n"
                + "  p=$(swww query 2>/dev/null | sed -n 's/.*image: //p' | head -n1)\n"
                + "  [ -z \"$p\" ] && p=$(awww query 2>/dev/null | sed -n 's/.*image: //p' | head -n1)\n"
                + "  p=$(printf %s \"$p\" | sed 's/^[[:space:]]*//; s/[[:space:]]*$//')\n"
                + "  [ -n \"$p\" ] && out=\"wallpaper.default$(printf '\\t')$p\"\n"
                + "fi\n"
                + "printf '%s' \"$out\"\n"
            ]
            stdout: StdioCollector {
                onStreamFinished: {
                    var m = {}, lines = text.split("\n");
                    for (var i = 0; i < lines.length; i++) {
                        var k = lines[i].indexOf("\t");
                        if (k <= 0) continue;
                        var key = lines[i].substring(0, k).trim(), val = lines[i].substring(k + 1).trim();
                        if (val !== "" && m[key] === undefined) m[key] = val;
                    }
                    if (JSON.stringify(m) !== JSON.stringify(sharedHub.wallpaperMap)) sharedHub.wallpaperMap = m;
                }
            }
        }

        Timer {
            interval: 15000
            repeat: true
            running: sharedHub.barWantsWallpaper || sharedHub.dockWantsWallpaper || sharedHub.widgetsWantWallpaper
            onTriggered: sharedHub.refreshWallpaper()
        }
    }
    MacBar { id: macBar; hub: sharedHub }
    MacDock { id: macDock; hub: sharedHub }
    MacWidgets { id: macWidgets; hub: sharedHub }
    ClockApp { id: clockApp; hub: sharedHub }

    // reopen settings even when both the Dock and the Menu Bar are disabled:
    //   qs -c macbar ipc call settings open
    IpcHandler {
        target: "about"
        function open(): void { macBar.openAboutLinux(); }
    }
    IpcHandler {
        target: "settings"
        function open(): void { macDock.openPrefs("general"); }
        // qs -c MacShell ipc call settings pane wallpaper   (general, dock, menubar, appearance, wallpaper, behavior, apps, about)
        function pane(id: string): void { macDock.openPrefs(id); }
    }
    // qs -c MacShell ipc call clock open | tab alarms | stop | snooze
    IpcHandler {
        target: "clock"
        function open(): void { clockApp.open(); }
        function tab(name: string): void { clockApp.open(name); }
        function stop(): void { clockApp.stopRing(); }
        function snooze(): void { clockApp.snooze(); }
        function alarm(hour: int, minute: int, label: string): void { if (hour >= 0 && hour < 24 && minute >= 0 && minute < 60) clockApp.addAlarm(hour, minute, label, []); }
        function removeAlarm(id: string): void { clockApp.deleteAlarm(id); }
        function timer(seconds: int, label: string): void { if (seconds > 0) clockApp.startTimer(seconds * 1000, label); }
        function pause(): void { clockApp.pauseTimer(); }
        function resume(): void { clockApp.resumeTimer(); }
        function cancel(): void { clockApp.cancelTimer(); }
        function stopwatch(action: string): void {
            if (action === "start" && !clockApp.sw.running) clockApp.swStart();
            else if (action === "stop" && clockApp.sw.running) clockApp.swStop();
            else if (action === "lap" && clockApp.sw.running) clockApp.swLap();
            else if (action === "reset") clockApp.swReset();
        }
    }
    IpcHandler {
        target: "notifications"
        function open(): void { macBar.notifPopRequest(true); }
        function close(): void { macBar.notifPopRequest(false); }
        function clear(): void { macBar.notifClearAnimated(); }
        // the lock screen: a notification swiped away
        function dismiss(id: int): void { macBar.notifDelete(id); macBar.notifUnread = Math.max(0, macBar.notifUnread - 1); }
    }
    // qs -c MacShell ipc call gaming toggle | on | off
    IpcHandler {
        target: "gaming"
        function toggle(): void { macBar.gamingMode = !macBar.gaming; }
        function on(): void { macBar.gamingMode = true; }
        function off(): void { macBar.gamingMode = false; macBar.gamingAutoActive = false; }
    }
    IpcHandler {
        target: "glass"
        function captures(on: bool): void {
            console.info("[macshell-niri] Per-window capture unavailable; using app icons.");
        }
    }
}
