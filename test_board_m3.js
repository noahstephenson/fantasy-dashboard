/* Milestone 3 headless tests for draft_board.html.
   Same harness style as test_board.js: stub the DOM + localStorage, extract the
   inline <script>, run it, then exercise the M3 additions:
     - upsideBonus / upsideInfo (round gate, RB handcuff, rookie ramp)
     - handcuff reason threaded through scoreBoard into the recommendations
     - bye-clash persistent warning + per-rec "(bye W: makes N)" tag
     - a full 160-pick auto-draft still completes cleanly
     - undo stays byte-identical after an upside-influenced pick
*/
const fs = require("fs");
const path = require("path");

const html = fs.readFileSync(path.join(__dirname, "draft_board.html"), "utf8");

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
const handlers = {};
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

eval(scriptSrc);
const B = window.__board;

// ---- helpers ----
let pass = 0, fail = 0;
function ok(cond, msg) { cond ? (pass++, console.log("  ok  " + msg)) : (fail++, console.log("  FAIL " + msg)); }
function fire(id, ev, arg) { handlers[id] && handlers[id][ev] && handlers[id][ev](arg); }
function setSlot(n) { els.slotSel.value = String(n); fire("slotSel", "change", { target: { value: String(n) } }); }
function clickPlayer(pid) { fire("plist", "click", { target: { closest: () => ({ getAttribute: () => String(pid) }) } }); }
function undo() { fire("undoBtn", "click"); }
function reset() { fire("resetBtn", "click"); }
function st() {
  if (store["b1boyzz_draft_v1"]) return JSON.parse(store["b1boyzz_draft_v1"]);
  return { pickNum: 1, drafted: [], mySlot: null };
}
function whyByName() {
  // returns { name: reasonText } parsed out of the recs panel
  const out = {};
  const re = /class='nm'>([^<]+)<\/span>[\s\S]*?class='why'>([^<]*)</g;
  let m;
  while ((m = re.exec(els.recs.innerHTML))) out[m[1]] = m[2];
  return out;
}
function recNames() {
  return (els.recs.innerHTML.match(/class='nm'>([^<]+)</g) || []).map((s) => s.replace(/.*>/, "").replace("<", ""));
}

const PLAYERS = JSON.parse(playersJSON);
const byId = {};
PLAYERS.forEach((p) => (byId[p.id] = p));
const byName = (n) => PLAYERS.find((p) => p.name === n);
function avail(blocked, noRB) {
  const dset = {}; st().drafted.forEach((d) => (dset[d.playerId] = 1));
  return PLAYERS
    .filter((p) => !blocked[p.id] && !dset[p.id] && (!noRB || p.pos !== "RB"))
    .sort((a, b) => b.raw_vbd - a.raw_vbd)[0];
}

// drive the draft up to (not including) pick number `target`. Everyone else
// takes best-available (minus `blocked`); my own turns take `myPicks` in order,
// then fall back to best-available non-RB (keeps my RB count controllable).
function teamAt(n) { const r = Math.ceil(n / 10); const idx = (n - 1) % 10; return r % 2 ? idx + 1 : 10 - idx; }
function driveTo(target, mySlot, blocked, myPicks) {
  let mi = 0;
  while (st().pickNum < target && st().pickNum <= 160) {
    const n = st().pickNum;
    if (teamAt(n) === mySlot) {
      clickPlayer(mi < myPicks.length ? myPicks[mi++] : avail(blocked, true).id);
    } else {
      clickPlayer(avail(blocked, false).id);
    }
  }
}

const SWIFT = byName("D'Andre Swift");       // CHI RB, proj 211.7
const MONANGAI = byName("Kyle Monangai");     // CHI RB, proj 176.2  (the handcuff)
const KYREN = byName("Kyren Williams");       // LAR RB, proj 232.1
const CORUM = byName("Blake Corum");          // LAR RB, proj 159.4

console.log("\n== M3.1 upsideBonus round gate ==");
const synthRB = { id: -1, pos: "RB", pro_team: "CHI", proj: 100, bye: 9, rookie: null };
const synthWRrook = { id: -2, pos: "WR", pro_team: "ZZZ", proj: 100, bye: 9, rookie: true };
const slotsSwift = { QB: null, RB1: SWIFT.id, RB2: null, WR1: null, WR2: null, TE: null, FLEX: null };
ok(B.upsideBonus(MONANGAI, 8, slotsSwift) === 0, "upsideBonus == 0 before round 9 (handcuff case)");
ok(B.upsideBonus(synthWRrook, 8, {}) === 0, "upsideBonus == 0 before round 9 (rookie case)");
ok(B.upsideBonus(synthWRrook, 1, {}) === 0, "upsideBonus == 0 in round 1");

console.log("\n== M3.2 RB handcuff to my starting RB ==");
let hi = B.upsideInfo(MONANGAI, 9, slotsSwift);
ok(hi.bonus >= 10 && hi.handcuff === true, "lower-proj CHI RB handcuffs my CHI starter, bonus " + hi.bonus);
ok(hi.reason === "handcuff to your CHI RB", "reason string: '" + hi.reason + "'");
ok(B.upsideInfo(SWIFT, 9, slotsSwift).handcuff === false, "a player never handcuffs himself");
const slotsMon = { RB1: MONANGAI.id, RB2: null, FLEX: null };
ok(B.upsideInfo(SWIFT, 9, slotsMon).handcuff === false, "higher-proj RB is not a handcuff to a lower-proj starter");
ok(B.upsideInfo(MONANGAI, 9, { RB1: null, RB2: null, FLEX: null }).handcuff === false,
   "no handcuff when I roster no RB from that team");
const slotsFlexRB = { RB1: null, RB2: null, FLEX: SWIFT.id };
ok(B.upsideInfo(MONANGAI, 9, slotsFlexRB).handcuff === true, "handcuff also fires off a FLEX-RB starter");

console.log("\n== M3.3 rookie upside ramps with the round ==");
const r9 = B.upsideInfo(synthWRrook, 9, {});
const r13 = B.upsideInfo(synthWRrook, 13, {});
ok(r9.bonus === 5 && r9.reason === "rookie upside", "rookie WR: +5 at round 9");
ok(r13.bonus === 5 + 3 * 1.5, "rookie WR: +" + r13.bonus + " at round 13 (ramps)");
ok(r13.bonus > r9.bonus, "later round => bigger rookie boost");
ok(B.upsideInfo({ id: -3, pos: "QB", rookie: true, proj: 100 }, 12, {}).bonus === 0, "rookie QB gets no boost (skill pos only)");

console.log("\n== M3.4 handcuff reason threaded into the recommendations (round >= 9) ==");
// WITHOUT the handcuff: draft a LAR RB (Kyren) at pick 1, run to round 9.
reset(); setSlot(1);
const blockNoHc = {}; blockNoHc[MONANGAI.id] = 1; blockNoHc[CORUM.id] = 1; blockNoHc[SWIFT.id] = 1;
driveTo(81, 1, blockNoHc, [KYREN.id]);
let rows = B.scoreBoard().rows;
const monNo = rows.findIndex((r) => r.p.id === MONANGAI.id);
const reasonNo = rows[monNo].reason;
ok(!/handcuff/.test(reasonNo), "no handcuff reason when I roster no CHI RB (reason: '" + reasonNo + "')");

// WITH the handcuff: same run but Swift (CHI) at pick 1.
reset(); setSlot(1);
const blockHc = {}; blockHc[MONANGAI.id] = 1; blockHc[CORUM.id] = 1; blockHc[SWIFT.id] = 1;
driveTo(81, 1, blockHc, [SWIFT.id]);
rows = B.scoreBoard().rows;
const monYes = rows.findIndex((r) => r.p.id === MONANGAI.id);
ok(rows[monYes].reason === "handcuff to your CHI RB", "handcuff reason shows on the CHI backup (reason: '" + rows[monYes].reason + "')");
ok(monYes < monNo, "handcuffed RB jumps up the board: rank " + (monYes + 1) + " vs " + (monNo + 1) + " without");
ok(rows[monYes].score > MONANGAI.raw_vbd, "handcuff adds to score (" + rows[monYes].score.toFixed(1) + " > vbd " + MONANGAI.raw_vbd + ")");

console.log("\n== M3.5 bye-clash warning + per-rec bye tag ==");
reset(); setSlot(1);
const GIBBS = byName("Jahmyr Gibbs");         // DET RB, bye 6
const CHASE = byName("Ja'Marr Chase");        // CIN WR, bye 6
const STBROWN = byName("Amon-Ra St. Brown");  // DET WR, bye 6
const JJ = byName("Justin Jefferson");        // MIN WR, bye 6
const byeBlock = {};
[GIBBS, CHASE, STBROWN, JJ].forEach((p) => (byeBlock[p.id] = 1));
// pick 1 -> Gibbs (RB1), picks 20 -> Chase (WR1); keep JJ + StBrown available
driveTo(21, 1, byeBlock, [GIBBS.id, CHASE.id]);
ok(st().pickNum === 21 && teamAt(21) === 1, "at my pick 21");
const why21 = whyByName();
const jjWhy = why21[JJ.name] || "";
ok(recNames().indexOf(JJ.name) !== -1, "Justin Jefferson is a top rec at pick 21");
ok(/\(bye 6: makes 3\)/.test(jjWhy), "his rec reason carries the bye tag: '" + jjWhy + "'");
// now draft JJ as WR2 -> 3 starters (Gibbs, Chase, JJ) all bye 6
clickPlayer(JJ.id);
ok(/Bye clash: 3 starters on bye week 6/.test(els.byeWarn.innerHTML),
   "persistent bye-clash warning appears: '" + els.byeWarn.innerHTML + "'");
ok(/Gibbs/.test(els.byeWarn.innerHTML) && /Chase/.test(els.byeWarn.innerHTML) && /Jefferson/.test(els.byeWarn.innerHTML),
   "warning names the three clashing starters");
// undo the JJ pick -> warning clears (only 2 starters on bye 6)
undo();
ok(els.byeWarn.innerHTML === "", "warning clears after undo drops us back to 2 on the bye");

console.log("\n== M3.6 bye-clash never changes score / exclusion ==");
// bye clash must not penalize: JJ (a WR2-need pick) still outscores a deep WR
rows = B.scoreBoard().rows;
const jjRow = rows.find((r) => r.p.id === JJ.id);
const deepWr = rows.find((r) => r.p.pos === "WR" && r.p._vbdRank > 55 && !r.excluded);
ok(jjRow && !jjRow.excluded, "clashing bye player is not excluded");
ok(jjRow && deepWr && jjRow.score > deepWr.score,
   "clashing bye player still outscores a deep WR (no bye penalty applied)");

console.log("\n== M3.7 full 160-pick auto-draft still completes ==");
reset(); setSlot(7);
let g = 0;
let threw = null;
try {
  while (st().pickNum <= 160 && g++ < 400) {
    const dset = {}; st().drafted.forEach((d) => (dset[d.playerId] = 1));
    let pick = recNames()[0] && PLAYERS.find((p) => p.name === recNames()[0] && !dset[p.id]);
    if (!pick) pick = PLAYERS.filter((p) => !dset[p.id]).sort((a, b) => b.raw_vbd - a.raw_vbd)[0];
    clickPlayer(pick.id);
  }
} catch (e) { threw = e; }
ok(!threw, "no exception during a full auto-draft" + (threw ? ": " + threw : ""));
ok(st().pickNum === 161, "draft ends at pick 161, got " + st().pickNum);
const mine = st().drafted.filter((d) => d.team === 7);
ok(mine.length === 16, "my roster has exactly 16 players, got " + mine.length);
const bp = {};
mine.forEach((d) => { const p = byId[d.playerId].pos; bp[p] = (bp[p] || 0) + 1; });
ok(bp.QB >= 1 && bp.RB >= 2 && bp.WR >= 2 && bp.TE >= 1 && bp.DST >= 1 && bp.K >= 1,
   "every starting slot filled: " + JSON.stringify(bp));
const POS_MAX = { QB: 4, RB: 8, WR: 8, TE: 3, DST: 3, K: 3 };
ok(Object.keys(bp).every((p) => bp[p] <= POS_MAX[p]), "no position over its max: " + JSON.stringify(bp));

console.log("\n== M3.8 undo byte-identical after an upside-influenced pick ==");
reset(); setSlot(1);
const blk = {}; blk[MONANGAI.id] = 1; blk[SWIFT.id] = 1;
driveTo(81, 1, blk, [SWIFT.id]);
ok(st().pickNum === 81, "at my round-9 pick");
const snap = JSON.stringify(st());
clickPlayer(MONANGAI.id);          // upside-influenced pick (handcuff)
ok(st().drafted.length === 81 && st().drafted[80].playerId === MONANGAI.id, "handcuff RB drafted");
clickPlayer(byName("Rome Odunze").id);
undo();                             // undo the odunze pick
ok(JSON.stringify(st()) !== snap, "still one pick past the snapshot");
undo();                            // undo the handcuff pick
ok(JSON.stringify(st()) === snap, "single draft + undo of an upside pick is byte-identical");

console.log("\n----");
console.log(pass + " passed, " + fail + " failed");
process.exit(fail ? 1 : 0);
