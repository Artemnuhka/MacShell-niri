const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const ctx = vm.createContext({});
vm.runInContext(fs.readFileSync(path.join(__dirname, '../NiriState.js'), 'utf8'), ctx);
let state = ctx.initial();
function event(e) { state = ctx.apply(state, e); }
event({WorkspacesChanged:{workspaces:[
  {id:100,idx:1,output:'A',is_active:true,is_focused:true},
  {id:200,idx:1,output:'B',is_active:true,is_focused:false},
  {id:300,idx:2,output:'A',is_active:false,is_focused:false}
]}});
event({WindowsChanged:{windows:[{id:1,workspace_id:100,is_focused:true},{id:2,workspace_id:200,is_focused:false}]}});
event({WorkspaceActivated:{id:300,focused:true}});
assert.equal(state.workspaces.find(w=>w.id===100).is_active,false);
assert.equal(state.workspaces.find(w=>w.id===200).is_active,true);
assert.equal(state.workspaces.find(w=>w.id===300).is_focused,true);
event({WindowOpenedOrChanged:{window:{id:3,workspace_id:300,is_focused:true,title:'quotes " and ; $(false)'}}});
assert.equal(state.windows.filter(w=>w.is_focused).length,1);
event({WindowFocusChanged:{id:null}});
assert.equal(state.windows.filter(w=>w.is_focused).length,0);
event({WindowLayoutsChanged:{changes:[[3,{tile_size:[800,600]}]]}});
assert.equal(state.windows.find(w=>w.id===3).layout.tile_size[0],800);
event({KeyboardLayoutsChanged:{keyboard_layouts:{names:['English (US)','Russian'],current_idx:0}}});
event({KeyboardLayoutSwitched:{idx:1}});
assert.equal(state.keyboard.current_idx,1);
event({WindowClosed:{id:3}});
assert.equal(state.windows.some(w=>w.id===3),false);
const snapshot = JSON.stringify(state);
event({UnknownFutureEvent:{some:'value'}});
assert.equal(JSON.stringify(state),snapshot);
// Initial snapshots replace stale state after reconnect.
event({WindowsChanged:{windows:[]}});
assert.equal(state.windows.length,0);
console.log('niri event reducer checks passed');
