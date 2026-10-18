// Adapter: original MacShell visuals use the existing niri data and settings.
import QtQuick
import Quickshell

QtObject {
    required property var source
    readonly property var bar: source.bar
    readonly property var dock: source.dock
    readonly property real widgetScale: source.widgetScale
    readonly property string fontFamily: source.fam
    property string glassState: "ready"
    readonly property string glassShaderOut: decodeURIComponent(Qt.resolvedUrl("liquidglass.frag.qsb").toString().replace("file://", ""))
    readonly property real glassOpacity: dock ? dock.glassOpacity : 0.42
    readonly property real glassBlur: dock ? dock.glassBlur : 5
    readonly property real glassLiquid: source.glassAmt * 2
    readonly property real glassRim: dock ? dock.glassRim : 0.45
    readonly property real glassGrain: dock ? dock.glassGrain : 0.03
    readonly property bool darkGlass: source.dark
    readonly property bool editing: source.editing
    readonly property real playerScale: 0.8
    readonly property var player: source.player
    readonly property var lyricsLines: source.mLyrLines
    readonly property string lyricsState: source.mLyrStatus
    readonly property bool lyricsSynced: source.mLyrLines.length > 0 && source.mLyrLines[0].t >= 0
    property bool lyricsWanted: false
    onLyricsWantedChanged: source.musicLyrics = lyricsWanted
    readonly property var wx: source.weather
    readonly property bool wxReady: wx !== null
    readonly property bool wxLocated: source.geo.city !== ""
    readonly property string wxCity: source.geo.city || source.cityName || "Choose a city"
    readonly property string wxError: source.weatherError
    readonly property bool wxDay: wx ? !!wx.current.is_day : true
    readonly property int wxTemp: wx ? Math.round(wx.current.temperature_2m) : 0
    readonly property int wxHi: wx ? Math.round(wx.daily.temperature_2m_max[0]) : 0
    readonly property int wxLo: wx ? Math.round(wx.daily.temperature_2m_min[0]) : 0
    readonly property var wxInfo: {
        var v = wx ? source.wmo(wx.current.weather_code, wxDay) : ["Loading…", "cloud"];
        return { t: v[0], k: v[1] };
    }
    readonly property var wxHourly: {
        if (!wx) return [];
        var out = [], h = wx.hourly;
        for (var i = 0; i < Math.min(7, h.time.length); i++)
            out.push({ h: i === 0 ? "Now" : Qt.formatTime(new Date(h.time[i]), "hAP"), t: Math.round(h.temperature_2m[i]), k: source.wmo(h.weather_code[i], h.is_day[i])[1] });
        return out;
    }
    readonly property var wxDaily: {
        if (!wx) return [];
        var out = [], d = wx.daily;
        for (var i = 0; i < Math.min(6, d.time.length); i++)
            out.push({ d: i === 0 ? "Today" : Qt.formatDate(new Date(d.time[i]), "ddd"), lo: Math.round(d.temperature_2m_min[i]), hi: Math.round(d.temperature_2m_max[i]), k: source.wmo(d.weather_code[i], true)[1] });
        return out;
    }
    function wallpaperFor(screen) { return dock && dock.wallpaperPath ? dock.wallpaperPath : (bar ? bar.wallpaperPath : ""); }
    function fileUrl(path) { return path ? "file://" + String(path).split("/").map(encodeURIComponent).join("/") : ""; }
}
