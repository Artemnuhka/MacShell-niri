// Logical-coordinate helpers shared by the niri backend, panels and widget layout.
// No compositor or Qt dependencies: covered by multi-display regression tests.
function ordered(screens) {
    return Array.prototype.slice.call(screens || []).filter(function(s) { return s && s.name; })
        .sort(function(a, b) { return (a.x || 0) - (b.x || 0) || (a.y || 0) - (b.y || 0) || a.name.localeCompare(b.name); });
}
function primary(screens, preferred, focused) {
    var list = ordered(screens);
    for (var i = 0; i < list.length; i++) if (list[i].name === preferred) return preferred;
    // Stable external-display preference, independent of connector enumeration order.
    for (var j = 0; j < list.length; j++) if (!/^(eDP|LVDS|DSI)/.test(list[j].name)) return list[j].name;
    for (var k = 0; k < list.length; k++) if (list[k].name === focused) return focused;
    return list.length ? list[0].name : "";
}
function target(screens, requested, main, focused) {
    var list = ordered(screens), wanted = requested === "@focused" ? focused : (requested === "@primary" ? main : requested);
    for (var i = 0; i < list.length; i++) if (list[i].name === wanted) return wanted;
    return primary(list, main, focused);
}
function monitors(outputs, workspaces) {
    var result = [], ws = workspaces || [];
    Object.keys(outputs || {}).forEach(function(name) {
        var o = outputs[name], l = o.logical;
        if (!l || !(l.width > 0) || !(l.height > 0)) return;
        var scale = isFinite(l.scale) && l.scale > 0 ? l.scale : 1;
        var active = ws.filter(function(w) { return w.output === name && w.is_active; })[0];
        result.push({id: name, name: name, x: l.x, y: l.y, logicalWidth: l.width, logicalHeight: l.height,
            width: l.width * scale, height: l.height * scale, scale: scale, transform: l.transform || "Normal", activeWorkspace: active || null});
    });
    return ordered(result);
}
function widgetPositions(widgets, screens, main, dims) {
    var list = ordered(screens), positions = {}, occupied = {};
    (widgets || []).forEach(function(w) {
        var name = target(list, w.screen || main, main, main);
        var screen = list.filter(function(s) { return s.name === name; })[0];
        if (!screen) return;
        var d = dims(w.size), maxX = Math.max(8, screen.width - d.w - 8), maxY = Math.max(36, screen.height - d.h - 8);
        var x = Math.max(8, Math.min(maxX, Number(w.x) || 32));
        var y = Math.max(36, Math.min(maxY, Number(w.y) || 64));
        var used = occupied[name] || [];
        function overlaps(cx, cy) { return used.some(function(p) { return cx < p.x+p.w+2 && cx+d.w+2 > p.x && cy < p.y+p.h+2 && cy+d.h+2 > p.y; }); }
        // Prefer the saved position. An unplugged display may bring widgets onto an occupied one.
        if (overlaps(x, y)) {
            var found = false;
            for (var cy = 36; cy <= maxY && !found; cy += 16)
                for (var cx = 8; cx <= maxX; cx += 16)
                    if (!overlaps(cx, cy)) { x = cx; y = cy; found = true; break; }
        }
        positions[w.id] = {screen: name, x: x, y: y};
        used.push({x: x, y: y, w: d.w, h: d.h}); occupied[name] = used;
    });
    return positions;
}

// Prefer MacShell's saved main output even if it loads after the screen list.
// Keep a stable fallback while the preferred output is unplugged.
function lockPrimary(screens, preferred, current, focused) {
    var names = ordered(screens).map(function(s) { return s.name; });
    if (names.indexOf(preferred) >= 0) return preferred;
    if (names.indexOf(current) >= 0) return current;
    if (names.indexOf(focused) >= 0) return focused;
    return primary(screens, "", focused);
}
