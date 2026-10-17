// Pure event reducer. Unknown events are ignored for forwards compatibility.
function initial() { return {windows: [], workspaces: [], keyboard: {names: [], current_idx: 0}}; }
function apply(state, event) {
    var s = {windows: state.windows.slice(), workspaces: state.workspaces.slice(), keyboard: state.keyboard};
    function update(list, id, values) {
        return list.map(function(item) {
            if (item.id !== id) return item;
            var copy = Object.assign({}, item);
            Object.keys(values).forEach(function(k) { copy[k] = values[k]; });
            return copy;
        });
    }
    if (event.WindowsChanged) s.windows = event.WindowsChanged.windows;
    else if (event.WindowOpenedOrChanged) {
        var w = event.WindowOpenedOrChanged.window;
        s.windows = s.windows.filter(function(t) { return t.id !== w.id; });
        if (w.is_focused) s.windows = s.windows.map(function(t) { return Object.assign({}, t, {is_focused:false}); });
        s.windows.push(w);
    } else if (event.WindowClosed) s.windows = s.windows.filter(function(w) { return w.id !== event.WindowClosed.id; });
    else if (event.WindowFocusChanged) s.windows = s.windows.map(function(w) {
        return Object.assign({}, w, {is_focused: w.id === event.WindowFocusChanged.id});
    });
    else if (event.WindowLayoutsChanged) event.WindowLayoutsChanged.changes.forEach(function(c) {
        s.windows = update(s.windows, c[0], {layout:c[1]});
    });
    else if (event.WindowUrgencyChanged) s.windows = update(s.windows, event.WindowUrgencyChanged.id, {is_urgent:event.WindowUrgencyChanged.urgent});
    else if (event.WindowFocusTimestampChanged) s.windows = update(s.windows, event.WindowFocusTimestampChanged.id, {focus_timestamp:event.WindowFocusTimestampChanged.focus_timestamp});
    else if (event.WorkspacesChanged) s.workspaces = event.WorkspacesChanged.workspaces;
    else if (event.WorkspaceActivated) {
        var e = event.WorkspaceActivated, hit = s.workspaces.filter(function(w) { return w.id === e.id; })[0];
        s.workspaces = s.workspaces.map(function(w) {
            var copy = Object.assign({}, w);
            if (hit && w.output === hit.output) copy.is_active = w.id === e.id;
            if (e.focused) copy.is_focused = w.id === e.id;
            return copy;
        });
    } else if (event.WorkspaceActiveWindowChanged) {
        var e = event.WorkspaceActiveWindowChanged;
        s.workspaces = update(s.workspaces, e.workspace_id, {active_window_id:e.active_window_id});
    } else if (event.KeyboardLayoutsChanged) s.keyboard = event.KeyboardLayoutsChanged.keyboard_layouts;
    else if (event.KeyboardLayoutSwitched) s.keyboard = Object.assign({}, s.keyboard, {current_idx:event.KeyboardLayoutSwitched.idx});
    return s;
}
