import QtQuick
import Quickshell

QtObject {
    readonly property url fallback: Qt.resolvedUrl("assets/icons/application.svg")
    function nameOf(id) {
        if (id === "macshell-clock") return "Clock";
        if (id === "macshell-settings" || id === "macshell-niri") return "System Settings";
        return "";
    }
    function source(name, appId) {
        var aliases = {
            "kitty":"kitty", "appimagekit-kitty":"kitty", "btop":"btop", "htop":"btop", "utilities-system-monitor":"btop",
            "macshell-clock":"clock", "clock":"clock", "org.gnome.clocks":"clock", "preferences-system-time":"clock",
            "org.gnome.settings":"settings", "gnome-control-center":"settings", "macshell-settings":"settings", "macshell-niri":"settings", "systemsettings":"settings", "preferences-system":"settings", "preferences-desktop":"settings",
            "org.gnome.texteditor":"text-editor", "org.gnome.gedit":"text-editor", "text-editor":"text-editor", "accessories-text-editor":"text-editor",
            "firefox":"firefox", "org.mozilla.firefox":"firefox", "firefox-esr":"firefox", "mozilla-firefox":"firefox",
            "org.gnome.nautilus":"files", "org.kde.dolphin":"files", "system-file-manager":"files", "file-manager":"files",
            "utilities-terminal":"terminal", "org.gnome.console":"terminal", "org.gnome.terminal":"terminal", "terminal":"terminal",
            "user-trash":"trash", "user-trash-full":"trash-full"
        };
        var id = String(appId || "").toLowerCase().replace(/\.desktop$/, "");
        var key = String(name || "").toLowerCase().replace(/\.desktop$/, "");
        var asset = aliases[id] || aliases[key];
        if (asset) return Qt.resolvedUrl("assets/icons/" + asset + ".svg");
        if (!name || /^(application-x-executable|application-default-icon|applications-other|org.quickshell)$/.test(key)) return fallback;
        if (String(name).indexOf("file:") === 0 || String(name).indexOf("image:") === 0) return name;
        if (String(name).charAt(0) === "/") return "file://" + name;
        var found = Quickshell.iconPath(name, true);
        return found !== "" ? found : fallback;
    }
}
