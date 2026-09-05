/* Headless test of draft_board.html's real embedded logic.
   Stubs the DOM + localStorage, extracts the inline <script>, runs it, then
   drives a full 10-team snake draft and checks behavior at each step. */
const fs = require("fs");
const path = require("path");

const html = fs.readFileSync(path.join(__dirname, "draft_board.html"), "utf8");

// ---- pull the two JSON blobs + the inline script ----
function blob(id) {
  const m = html.match(new RegExp('id="' + id + '">([\\s\\S]*?)</script>'));
  return m[1].replace(/<\\\//g, "</");
}
const playersJSON = blob("players");
const configJSON = blob("config");
const scriptM = html.match(/<script>\s*(\(function \(\)[\s\S]*?\}\)\(\);)\s*<\/script>/);
const scriptSrc = scriptM[1];

// ---- DOM / storage stubs ----
const store = {};
const localStorage = {
  getItem: (k) => (k in store ? store[k] : null),
  setItem: (k, v) => { store[k] = String(v); },
  removeItem: (k) => { delete store[k]; },
};
const handlers = {};       // id -> {event: fn}
const els = {};
function mkEl(id) {
  return {
    _id: id,
    innerHTML: "",
    value: "",
    className: "",
    textContent: id === "players" ? playersJSON : id === "config" ? configJSON : "",
    classList: { toggle() {}, add() {}, remove() {} },
    addEventListener(ev, fn) { (handlers[id] = handlers[id] || {})[ev] = fn; },
  };
}
const document = {
  getElementById: (id) => (els[id] = els[id] || mkEl(id)),
  body: { classList: { toggle() {} } },
};
const window = { confirm: () => true };

// ---- run the board script in this scope ----
eval(scriptSrc);

// ---- test helpers ----
let pass = 0, fail = 0;
function ok(cond, msg) { cond ? (pass++, console.log("  ok  " + msg)) : (fail++, console.log("  FAIL " + msg)); }
function fire(id, ev, arg) { handlers[id] && handlers[id][ev] && handlers[id][ev](arg); }
function setSlot(n) { const el = els.slotSel; el.value = String(n); fire("slotSel", "change", { target: { value: String(n) } }); }
function clickPlayer(pid) { fire("plist", "click", { target: { closest: () => ({ getAttribute: () => String(pid) }) } }); }
function undo() { fire("undoBtn", "click"); }
function state() {
  // storage only exists after the first mutation; fall back to rendered DOM
  if (store["b1boyzz_draft_v1"]) return JSON.parse(store["b1boyzz_draft_v1"]);
  return { pickNum: pickNumFromDom(), drafted: [], mySlot: null };
}
function pickNumFromDom() {
  const h = els.clock.innerHTML || "";
  if (/Draft complete/.test(h)) return 161;
  const m = h.match(/Pick (\d+)/);
  return m ? +m[1] : 1;
}
function recNames() {
  return (els.recs.innerHTML.match(/class='nm'>([^<]+)</g) || []).map((s) => s.replace(/.*>/, "").replace("<", ""));
}
function rosterText() { return els.rosterGrid.innerHTML.replace(/<[^>]+>/g, "|"); }
function countsText() { return els.countsRow.innerHTML.replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim(); }

const PLAYERS = JSON.parse(playersJSON);
const byId = {};
PLAYERS.forEach((p) => (byId[p.id] = p));
const bestBy = (pos) => PLAYERS.filter((p) => p.pos === pos).sort((a, b) => b.raw_vbd - a.raw_vbd);

console.log("\n== 1. fresh load ==");
ok(state().pickNum === 1, "starts at pick 1");
ok(state().drafted.length === 0, "no picks yet");
ok(recNames().length === 5, "5 recommendations shown, got " + recNames().length);

console.log("\n== 2. set my slot = 5, draft picks 1-4 (opponents) ==");
setSlot(5);
ok(state().mySlot === 5, "slot saved");
const firstFour = [bestBy("RB")[0], bestBy("RB")[1], bestBy("WR")[0], bestBy("RB")[2]];
firstFour.forEach((p) => clickPlayer(p.id));
ok(state().pickNum === 5, "pick counter at 5");
ok(state().drafted.length === 4, "4 drafted");
ok(state().drafted[0].team === 1 && state().drafted[3].team === 4, "picks 1-4 -> teams 1-4");
ok(rosterText().indexOf(firstFour[0].name) === -1, "none of my roster slots filled yet");

console.log("\n== 3. my pick (5) ==");
const clockHtml = els.clock.innerHTML + " " + els.clock.className;
ok(/YOU/.test(els.clock.innerHTML) || /mine/.test(els.clock.className), "clock shows it's my turn: " + clockHtml.trim());
const myGuy = recNames()[0];
const myGuyObj = PLAYERS.find((p) => p.name === myGuy);
clickPlayer(myGuyObj.id);
ok(state().drafted.length === 5 && state().drafted[4].team === 5, "pick 5 recorded to team 5 (me)");
ok(rosterText().indexOf(myGuy) !== -1, "my pick '" + myGuy + "' appears in my roster grid");

console.log("\n== 4. undo twice ==");
const beforeUndo = JSON.stringify(state());
clickPlayer(bestBy("WR")[3].id);          // opponents pick 6
undo();                                     // undo pick 6
ok(JSON.stringify(state()) === beforeUndo, "single draft+undo is byte-identical");
undo();                                     // undo my pick 5
ok(state().pickNum === 5 && state().drafted.length === 4, "undo my pick: back to pick 5, 4 drafted");
ok(rosterText().indexOf(myGuy) === -1, "my roster slot cleared after undo");

console.log("\n== 5. hard-exclude: K/DST never recommended while starters open ==");
ok(!recNames().some((n) => { const p = PLAYERS.find((x) => x.name === n); return p && (p.pos === "K" || p.pos === "DST"); }),
   "no K/DST in recommendations early");

console.log("\n== 6. position max: fill my RBs to 8, RB then excluded from recs mid-draft ==");
fire("resetBtn", "click");
setSlot(1);   // my picks: 1, 20, 21, 40, 41, 60, 61, 80, ...
function teamAt(n) { const r = Math.ceil(n / 10); const idx = (n - 1) % 10; return r % 2 ? idx + 1 : 10 - idx; }
const rbs = bestBy("RB");
let rbIdx = 0;
while (state().pickNum <= 160) {
  const n = state().pickNum;
  if (teamAt(n) === 1 && rbIdx < 8) {
    clickPlayer(rbs[rbIdx++].id);
  } else {
    const dset = {}; state().drafted.forEach((d) => (dset[d.playerId] = 1));
    const avail = PLAYERS.filter((p) => !dset[p.id] && p.pos !== "RB").sort((a, b) => b.raw_vbd - a.raw_vbd);
    clickPlayer(avail[0].id);
  }
  if (rbIdx === 8 && teamAt(n) === 1) break;   // stop right after my 8th RB
}
const myRBs = state().drafted.filter((d) => d.team === 1 && byId[d.playerId].pos === "RB").length;
ok(myRBs === 8, "drafted exactly 8 RBs to my team, got " + myRBs);
ok(/RB 8\/8/.test(countsText()), "counts row shows RB 8/8: [" + countsText() + "]");
ok(!recNames().some((nm) => { const p = PLAYERS.find((x) => x.name === nm); return p && p.pos === "RB"; }),
   "RB excluded from recommendations once I'm at the max (recs: " + recNames().join(", ") + ")");
// and a direct 9th-RB click is still allowed (draftable, just not recommended)
const before = state().drafted.length;
clickPlayer(rbs[8].id);
ok(state().drafted.length === before + 1, "a 9th RB is still click-draftable (only recs are blocked)");

console.log("\n== 7. full draft to completion ==");
fire("resetBtn", "click");
setSlot(5);
let g = 0;
while (state().pickNum <= 160 && g++ < 300) {
  const dset = {}; state().drafted.forEach((d) => (dset[d.playerId] = 1));
  // mimic clicking the top recommendation each pick; fall back to best available
  let pick = recNames()[0] && PLAYERS.find((p) => p.name === recNames()[0] && !dset[p.id]);
  if (!pick) pick = PLAYERS.filter((p) => !dset[p.id]).sort((a, b) => b.raw_vbd - a.raw_vbd)[0];
  clickPlayer(pick.id);
}
ok(state().pickNum === 161, "draft ends at pick 161, got " + state().pickNum);
const myTotal = state().drafted.filter((d) => d.team === 5).length;
ok(myTotal === 16, "my roster has 16 players, got " + myTotal);
const myByPos = {};
state().drafted.filter((d) => d.team === 5).forEach((d) => { const p = byId[d.playerId].pos; myByPos[p] = (myByPos[p] || 0) + 1; });
ok(myByPos.QB >= 1 && myByPos.RB >= 2 && myByPos.WR >= 2 && myByPos.TE >= 1 && myByPos.DST >= 1 && myByPos.K >= 1,
   "auto-draft filled every starting position: " + JSON.stringify(myByPos));
clickPlayer(bestBy("QB")[0].id);
ok(state().pickNum === 161, "clicks after completion are no-ops");
undo();
ok(state().pickNum === 160 && state().drafted.length === 159, "undo still works post-completion");

console.log("\n== 8. K/DST gating in 'best available by position' ==");
// after round >= 12 the bestpos panel should list DST and K
const showsLate = /DST/.test(els.bestpos.innerHTML) && /(>K<|>K )/.test(els.bestpos.innerHTML);
ok(showsLate, "late in draft, best-available panel includes K and DST");

console.log("\n----");
console.log(pass + " passed, " + fail + " failed");
process.exit(fail ? 1 : 0);
