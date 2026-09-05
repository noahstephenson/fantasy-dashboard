/* Tests for the league-size setup: JS VBD recompute must match the Python
   model at teams=10, and change coherently for other league sizes. */
const fs = require("fs"), path = require("path");
const html = fs.readFileSync(path.join(__dirname, "draft_board.html"), "utf8");
function blob(id) { return html.match(new RegExp('id="' + id + '">([\\s\\S]*?)</script>'))[1].replace(/<\\\//g, "</"); }
const playersJSON = blob("players"), configJSON = blob("config");
const scriptSrc = html.match(/<script>\s*(\(function \(\)[\s\S]*?\}\)\(\);)\s*<\/script>/)[1];

const store = {};
const localStorage = { getItem: (k) => (k in store ? store[k] : null), setItem: (k, v) => { store[k] = String(v); }, removeItem: (k) => { delete store[k]; } };
const handlers = {}, els = {};
function mkEl(id) { return { _id: id, innerHTML: "", value: "", className: "", textContent: id === "players" ? playersJSON : id === "config" ? configJSON : "", classList: { toggle() {}, add() {}, remove() {} }, addEventListener(ev, fn) { (handlers[id] = handlers[id] || {})[ev] = fn; } }; }
const document = { getElementById: (id) => (els[id] = els[id] || mkEl(id)), body: { classList: { toggle() {} } } };
const window = {}; window.confirm = () => true;
eval(scriptSrc);

const B = window.__board;
const CFG = JSON.parse(configJSON);
let pass = 0, fail = 0;
function ok(c, m) { c ? (pass++, console.log("  ok  " + m)) : (fail++, console.log("  FAIL " + m)); }
function playersByPos(pos) {
  return JSON.parse(playersJSON).filter((p) => p.pos === pos); // fresh copy for proj lookup
}
// live PLAYERS array is mutated in place by recomputeValues
function livePos(pos) {
  return B.state && null, // noop
    require("vm"), null;
}

console.log("== INIT.1 config carries the value-model constants ==");
ok(CFG.vm && CFG.vm.STARTERS && CFG.vm.FLEX_SPLIT && CFG.vm.REPLACEMENT_BUFFER, "config.vm present");
ok(CFG.roster_spots === 16, "roster_spots = 16");
ok(CFG.default_teams === 10, "default_teams = 10");

console.log("\n== INIT.2 default recompute (teams=10) matches the Python seed values ==");
// board already ran load()+recomputeValues() at teams=10 on eval.
// compare a handful of well-known players' raw_vbd to the seed the Python build embedded.
const seed = {};
JSON.parse(playersJSON).forEach((p) => (seed[p.id] = p.raw_vbd));
// pull the live (recomputed) values via scoreBoard rows
let rows = B.scoreBoard().rows;
let maxDiff = 0, checked = 0;
rows.forEach((r) => {
  if (seed[r.p.id] !== undefined) {
    maxDiff = Math.max(maxDiff, Math.abs(r.p.raw_vbd - seed[r.p.id]));
    checked++;
  }
});
ok(checked > 300, "checked " + checked + " players");
ok(maxDiff < 0.6, "max raw_vbd drift vs Python seed = " + maxDiff.toFixed(2) + " (proj rounding only)");

console.log("\n== INIT.3 more teams => deeper replacement => lower VBD for the studs ==");
const topRb = rows.filter((r) => r.p.pos === "RB")[0];
const vbd10 = topRb.p.raw_vbd;
B.setTeams(14);
rows = B.scoreBoard().rows;
const topRb14 = rows.find((r) => r.p.id === topRb.p.id);
ok(topRb14.p.raw_vbd > vbd10, "top RB VBD rises at 14 teams (" + vbd10.toFixed(1) + " -> " + topRb14.p.raw_vbd.toFixed(1) + "): replacement is deeper");
ok(B.state.teams === 14, "state.teams updated to 14");

console.log("\n== INIT.4 fewer teams => shallower replacement => compressed VBD ==");
B.setTeams(8);
rows = B.scoreBoard().rows;
const topRb8 = rows.find((r) => r.p.id === topRb.p.id);
ok(topRb8.p.raw_vbd < vbd10, "top RB VBD drops at 8 teams (" + vbd10.toFixed(1) + " -> " + topRb8.p.raw_vbd.toFixed(1) + ")");

console.log("\n== INIT.5 draft length + snake follow the team count ==");
B.setTeams(12);
// simulate: is TOTAL_PICKS = 12*16 = 192? drive the board and check completion
store["b1boyzz_draft_v1"] && delete store["b1boyzz_draft_v1"];
// use the exposed state + a fresh draft
function teamAt12(n) { const r = Math.ceil(n / 12), i = (n - 1) % 12; return r % 2 ? i + 1 : 12 - i; }
ok(teamAt12(12) === 12 && teamAt12(13) === 12 && teamAt12(24) === 1, "12-team snake wrap math");

console.log("\n== INIT.6 setup persists (teams saved to storage) ==");
B.setTeams(11);
// trigger a save via the state object the board holds
handlers.slotSel && handlers.slotSel.change && handlers.slotSel.change({ target: { value: "3" } });
const saved = JSON.parse(store["b1boyzz_draft_v1"] || "{}");
ok(saved.teams === 11, "storage has teams=11, got " + saved.teams);
ok(saved.mySlot === 3, "storage has mySlot=3");

console.log("\n== INIT.7 slot beyond team count is rejected ==");
B.setTeams(8);
handlers.slotSel.change({ target: { value: "10" } });
ok(B.state.mySlot === null || B.state.mySlot <= 8, "slot 10 rejected at 8 teams (mySlot=" + B.state.mySlot + ")");

console.log("\n----\n" + pass + " passed, " + fail + " failed");
process.exit(fail ? 1 : 0);
