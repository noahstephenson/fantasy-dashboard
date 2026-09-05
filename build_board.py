"""Milestone 2: interactive draft board -> draft_board.html

Pure standard library. Reuses value_model.build_model() for the VBD math.

Run from tool/:
    venv/Scripts/python.exe build_board.py

Reads:  players.json (via value_model)
Writes: draft_board.html  (one self-contained file, zero network calls)
"""

import json
import os
import datetime

import value_model

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_PATH = os.path.join(HERE, "draft_board.html")

# League config the JS needs (mirrors SPEC.md / value_model constants).
POS_MAX = {"QB": 4, "RB": 8, "WR": 8, "TE": 3, "DST": 3, "K": 3}


def collect_players(model):
    """One flat list, only the fields the board renders. K/DST included;
    `pos` itself is the gate flag the UI uses."""
    out = []
    for p in model["players"]:
        if "raw_vbd" not in p:
            continue
        out.append({
            "id": p["id"],
            "name": p["name"],
            "pos": p["pos"],
            "pro_team": p.get("pro_team") or "",
            "bye": p.get("bye"),
            "proj": round(p["proj_pts"], 2),   # JS recomputes VBD from this
            "raw_vbd": p["raw_vbd"],            # seed value (teams=10); JS overwrites
            "tier": p["tier"],
            "tier_label": p["tier_label"],
            "espn_draft_rank": p.get("espn_draft_rank"),
        })
    # initial order = raw_vbd desc; the JS re-sorts by live score anyway
    out.sort(key=lambda x: x["raw_vbd"], reverse=True)
    return out


def blob(obj):
    """JSON safe to drop inside a <script> element."""
    return json.dumps(obj, ensure_ascii=False).replace("</", "<\\/")


CSS = r"""
/* Explicit color tokens only - no CSS system-color keywords and no blend
   functions - so it renders on any phone browser, offline, light or dark. */
:root {
  color-scheme: light dark;
  --bg: #ffffff; --fg: #111111;
  --panel: #f4f4f6;         /* topbar, sticky headers, hover */
  --row-active: #e7e7ec;
  --border: #c9c9cf; --border-soft: #e3e3e8;
  --muted: #6b7280;
  --qb: #c0392b; --rb: #1f8a4c; --wr: #2673b3; --te: #c15600;
  --dst: #7c3aad; --k: #6b7280;
  --accent-green: #2e7d32; --accent-red: #c0392b;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #16171a; --fg: #e9e9ec;
    --panel: #212227;
    --row-active: #2c2d33;
    --border: #3a3b41; --border-soft: #2a2b31;
    --muted: #9aa0a6;
    --qb: #ff6b5e; --rb: #3ecf7a; --wr: #5aa9e6; --te: #ff9d4d;
    --dst: #c58be6; --k: #9aa0a6;
  }
}
* { box-sizing: border-box; }
html { -webkit-text-size-adjust: 100%; }
body { font-family: system-ui, -apple-system, "Segoe UI", Roboto, Arial, sans-serif;
       margin: 0; font-size: 14px; line-height: 1.3;
       background: var(--bg); color: var(--fg);
       -webkit-tap-highlight-color: transparent; }
h3 { margin: 0 0 6px; font-size: 14px; }

#topbar { position: sticky; top: 0; z-index: 20; background: var(--panel);
          border-bottom: 1px solid var(--border); padding: 8px 12px;
          display: flex; flex-wrap: wrap; gap: 14px 24px; align-items: flex-start; }
.tb-block { font-size: 13px; }
.tb-block .lbl { font-weight: 700; display: block; margin-bottom: 2px; }
#clock.mine { background: var(--accent-green); color: #fff; padding: 3px 8px;
              border-radius: 4px; display: inline-block; }
#clock.mine .big { color: #fff; }
.big { font-size: 16px; font-weight: 700; }

.roster-grid { display: grid; grid-template-columns: repeat(2, minmax(150px, 1fr));
               gap: 1px 14px; font-size: 12px; }
.rs { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.rs .slot { display: inline-block; width: 42px; color: var(--muted); }
.rs.filled .slot { color: inherit; }

.counts span { display: inline-block; margin-right: 10px; font-variant-numeric: tabular-nums; }
.counts .full { color: var(--accent-red); font-weight: 700; }

/* M3: persistent bye-clash warning, sits full-width under the topbar blocks */
.bye-warn { flex-basis: 100%; background: var(--accent-red); color: #fff;
            padding: 4px 10px; border-radius: 4px; font-weight: 700; font-size: 12px; }
#byeWarn:empty { display: none; }

#main-wrap { display: flex; gap: 14px; padding: 12px; align-items: flex-start; }
#list-col { flex: 1 1 auto; min-width: 0; }
#right-col { flex: 0 0 330px; }

.controls { margin-bottom: 8px; display: flex; gap: 8px; flex-wrap: wrap; }
button { font: inherit; padding: 4px 12px; cursor: pointer;
         background: var(--panel); color: var(--fg);
         border: 1px solid var(--border); border-radius: 4px; }
#search { font: inherit; padding: 4px 8px; width: 220px;
          background: var(--bg); color: var(--fg); border: 1px solid var(--border); }
#search-wrap { margin-bottom: 8px; }

.plist { max-height: 74vh; overflow: auto; border: 1px solid var(--border-soft);
         border-radius: 4px; }
.phead, .prow { display: grid;
  grid-template-columns: 1.7fr 42px 46px 32px 52px 50px 52px;
  gap: 6px; padding: 4px 8px; align-items: center; }
.phead { position: sticky; top: 0; background: var(--panel);
         border-bottom: 1px solid var(--border); font-weight: 700; font-size: 12px; }
.prow { cursor: pointer; border-bottom: 1px solid var(--border-soft);
        font-variant-numeric: tabular-nums; }
.prow:hover { background: var(--row-active); }
.prow .num { text-align: right; }
.prow.excluded { opacity: 0.45; }
.tiersep { border-top: 2px solid var(--border); }

.pos { font-weight: 700; font-size: 12px; }
.pos-QB { color: var(--qb); } .pos-RB { color: var(--rb); }
.pos-WR { color: var(--wr); } .pos-TE { color: var(--te); }
.pos-DST { color: var(--dst); } .pos-K { color: var(--k); }

#right-col .panel { border: 1px solid var(--border-soft); border-radius: 4px;
                    padding: 8px 10px; margin-bottom: 12px; }
.rec { padding: 5px 0; border-bottom: 1px solid var(--border-soft); }
.rec:last-child { border-bottom: 0; }
.rec .nm { font-weight: 700; }
.rec .why { font-size: 12px; color: var(--muted); }
.bestpos div { padding: 3px 0; font-size: 13px; }

/* Plain view keeps .controls visible so Undo / the toggle stay reachable. */
body.plain #topbar .chrome, body.plain #right-col,
body.plain #search-wrap { display: none; }
body.plain .prow { cursor: default; }
.done-banner { background: var(--accent-red); color: #fff; padding: 4px 10px;
               border-radius: 4px; }

/* name cell: ellipsis + min-width:0 so a long name can never widen the grid */
.pname { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

/* ---- init / setup screen ---- */
#initScreen { position: fixed; top: 0; left: 0; right: 0; bottom: 0; z-index: 100;
              background: var(--bg); display: flex; align-items: flex-start;
              justify-content: center; overflow-y: auto; padding: 24px 16px; }
#initScreen.hidden { display: none; }
.init-card { width: 100%; max-width: 460px; }
.init-card h2 { margin: 4px 0 16px; }
.init-q { font-weight: 700; margin: 18px 0 8px; }
.init-sub { font-weight: 400; color: var(--muted); font-size: 12px; }
.init-note { color: var(--muted); font-size: 12px; margin: 8px 0 0; }
.team-btns { display: grid; grid-template-columns: repeat(5, 1fr); gap: 8px; }
.team-btns button { min-height: 48px; font-size: 16px; font-weight: 700;
                    border: 1px solid var(--border); border-radius: 6px;
                    background: var(--panel); color: var(--fg); cursor: pointer; }
.team-btns button.sel { background: var(--accent-green); color: #fff;
                        border-color: var(--accent-green); }
#initSlot { min-height: 44px; font: inherit; width: 100%; margin-top: 4px;
            background: var(--bg); color: var(--fg); border: 1px solid var(--border); }
.init-start { margin-top: 22px; width: 100%; min-height: 50px; font-size: 16px;
              font-weight: 700; border: 0; border-radius: 6px;
              background: var(--accent-green); color: #fff; cursor: pointer; }
#leagueInfo { font-size: 13px; }

/* ---- phone / narrow screens (<= ~700px): single column ---- */
@media (max-width: 700px) {
  body { font-size: 15px; padding-bottom: 76px; }   /* clearance for floating Undo */
  #topbar { max-height: 42vh; overflow-y: auto; gap: 8px 18px; }
  #main-wrap { flex-direction: column; padding: 8px; gap: 10px; }
  #list-col, #right-col { flex: 1 1 auto; width: 100%; min-width: 0; }
  #right-col { order: -1; }                 /* RECOMMENDED NOW above the list */
  #right-col .panel { margin-bottom: 8px; }
  .roster-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .controls { gap: 6px; }
  .controls button { min-height: 44px; padding: 10px 14px; flex: 1 1 auto; }
  #search { width: 100%; min-height: 44px; }
  .plist { max-height: 72vh; overflow-x: hidden; }  /* list scrolls independently */
  .prow, .phead { min-height: 44px; }
  .prow:active { background: var(--row-active); }
  /* floating Undo — always reachable without scrolling, vs the 90s pick clock */
  #undoBtn { position: fixed; right: 14px; bottom: 14px; z-index: 50;
             min-height: 52px; padding: 0 24px; border-radius: 26px;
             box-shadow: 0 3px 12px rgba(0,0,0,0.5); background: var(--accent-red);
             color: #fff; border: 0; font-weight: 700; flex: 0 0 auto; }
}

/* ---- very narrow (<= 480px): drop Bye + Proj columns ---- */
@media (max-width: 480px) {
  /* keep: name / pos / team / VBD / tier */
  .phead, .prow { grid-template-columns: minmax(0, 1.6fr) 34px 40px 46px 44px; gap: 5px; }
  .phead > :nth-child(4), .phead > :nth-child(5),
  .prow  > :nth-child(4), .prow  > :nth-child(5) { display: none; }
}
"""


PAGE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>B1 Boyzz Draft Board</title>
<style>__CSS__</style>
</head>
<body>

<div id="initScreen">
  <div class="init-card">
    <h2>B1 Boyzz &mdash; Draft Setup</h2>
    <p class="init-q">How many teams are in your league?</p>
    <div id="teamBtns" class="team-btns"></div>
    <p class="init-note">The league started at 10. If people were added, set the real
      number here &mdash; it recalculates every player's value and the draft length.</p>
    <p class="init-q">Your draft slot <span class="init-sub">(optional now &mdash; set it once the order is posted)</span></p>
    <select id="initSlot"><option value="">-- not set yet --</option></select>
    <button id="initStart" class="init-start">Start draft board</button>
  </div>
</div>

<div id="topbar">
  <div class="tb-block">
    <span class="lbl">My draft slot</span>
    <select id="slotSel"><option value="">-- pick --</option></select>
  </div>
  <div class="tb-block chrome">
    <span class="lbl">League</span>
    <span id="leagueInfo"></span>
  </div>
  <div class="tb-block chrome">
    <span class="lbl">On the clock</span>
    <span id="clock"></span>
  </div>
  <div class="tb-block chrome">
    <span class="lbl">My roster</span>
    <div class="roster-grid" id="rosterGrid"></div>
  </div>
  <div class="tb-block chrome">
    <span class="lbl">Position counts</span>
    <div class="counts" id="countsRow"></div>
  </div>
  <div id="byeWarn" class="bye-warn"></div>
</div>

<div id="main-wrap">
  <div id="list-col">
    <div class="controls">
      <button id="undoBtn">Undo</button>
      <button id="resetBtn">Reset</button>
      <button id="plainBtn">Plain view</button>
      <button id="setupBtn">&#9881; Setup</button>
    </div>
    <div id="search-wrap">
      <input id="search" type="search" placeholder="filter available players...">
    </div>
    <div id="banner"></div>
    <div class="plist" id="plist"></div>
  </div>
  <div id="right-col">
    <div class="panel">
      <h3>Recommended now</h3>
      <div id="recs"></div>
    </div>
    <div class="panel">
      <h3>Best available by position</h3>
      <div class="bestpos" id="bestpos"></div>
    </div>
  </div>
</div>

<script type="application/json" id="players">__PLAYERS_JSON__</script>
<script type="application/json" id="config">__CONFIG_JSON__</script>
<script>
(function () {
  "use strict";

  var PLAYERS = JSON.parse(document.getElementById("players").textContent);
  var CONFIG = JSON.parse(document.getElementById("config").textContent);
  var POS_MAX = CONFIG.POS_MAX;
  var VM = CONFIG.vm;                       // value-model constants for JS recompute
  var ROSTER_SPOTS = CONFIG.roster_spots || 16;
  var LS_KEY = "b1boyzz_draft_v1";
  var TEAMS = CONFIG.default_teams || 10;   // reassigned by setTeams()
  var TOTAL_PICKS = TEAMS * ROSTER_SPOTS;

  var byId = {};
  PLAYERS.forEach(function (p) { byId[p.id] = p; });

  // ---- state (everything else is derived by replay, which makes Undo exact) ----
  var state = { teams: TEAMS, mySlot: null, pickNum: 1, drafted: [] };
  var ui = { search: "", plain: false };

  // ---- value model: recomputed in-browser so any league size works ----
  function replacementRank(pos) {
    return VM.STARTERS[pos] * TEAMS
         + Math.round((VM.FLEX_SPLIT[pos] || 0) * TEAMS)
         + (VM.REPLACEMENT_BUFFER[pos] || 0);
  }
  function assignTiers(pos, list) {         // list already sorted raw_vbd desc
    var range = VM.TIER_RANGE[pos] || 20;
    var rng = list.slice(0, range);
    var thr = VM.TIER_MIN_GAP;
    if (rng.length >= 3) {
      var spread = rng[0].raw_vbd - rng[rng.length - 1].raw_vbd;
      thr = Math.max(VM.TIER_MIN_GAP, VM.TIER_FACTOR * (spread / (rng.length - 1)));
    }
    var tier = 1, prev = null;
    for (var i = 0; i < list.length; i++) {
      var p = list[i];
      if (prev !== null && (prev - p.raw_vbd) > thr) tier = Math.min(tier + 1, VM.TIER_MAX);
      p.tier = tier; p.tier_label = pos + tier; prev = p.raw_vbd;
    }
  }
  function recomputeValues() {
    var byPos = { QB: [], RB: [], WR: [], TE: [], DST: [], K: [] };
    for (var i = 0; i < PLAYERS.length; i++) {
      if (byPos[PLAYERS[i].pos]) byPos[PLAYERS[i].pos].push(PLAYERS[i]);
    }
    ["QB", "RB", "WR", "TE", "DST", "K"].forEach(function (pos) {
      var list = byPos[pos];
      list.sort(function (a, b) { return b.proj - a.proj; });   // == raw_vbd desc
      var idx = Math.min(replacementRank(pos) - 1, list.length - 1);
      var rp = idx >= 0 ? list[idx].proj : 0;
      for (var j = 0; j < list.length; j++) {
        list[j].raw_vbd = Math.round((list[j].proj - rp) * 100) / 100;
      }
      assignTiers(pos, list);
    });
    PLAYERS.sort(function (a, b) { return b.raw_vbd - a.raw_vbd; });
    for (var k = 0; k < PLAYERS.length; k++) PLAYERS[k]._vbdRank = k + 1;
  }
  function setTeams(n) {
    n = parseInt(n, 10);
    if (!(n >= 4 && n <= 20)) return;
    TEAMS = n;
    state.teams = n;
    TOTAL_PICKS = TEAMS * ROSTER_SPOTS;
    if (state.mySlot && state.mySlot > TEAMS) state.mySlot = null;
    recomputeValues();
    renderSlotOptions();
  }
  function renderSlotOptions() {
    var o = "<option value=''>-- pick --</option>";
    for (var i = 1; i <= TEAMS; i++) o += "<option>" + i + "</option>";
    var sel = document.getElementById("slotSel");
    sel.innerHTML = o;
    sel.value = state.mySlot ? String(state.mySlot) : "";
  }

  // returns true if a valid saved team count was found (=> skip the setup screen)
  function load() {
    try {
      var raw = localStorage.getItem(LS_KEY);
      if (!raw) return false;
      var o = JSON.parse(raw);
      if (!o || typeof o !== "object") return false;
      var hadTeams = false;
      var t = parseInt(o.teams, 10);
      if (t >= 4 && t <= 20) {
        TEAMS = t; state.teams = t; TOTAL_PICKS = TEAMS * ROSTER_SPOTS; hadTeams = true;
      }
      var s = parseInt(o.mySlot, 10);
      state.mySlot = (s >= 1 && s <= TEAMS) ? s : null;
      state.pickNum = (typeof o.pickNum === "number" && o.pickNum >= 1) ? o.pickNum : 1;
      state.drafted = Array.isArray(o.drafted) ? o.drafted.filter(function (d) {
        return d && typeof d.playerId !== "undefined" && byId[d.playerId];
      }) : [];
      return hadTeams;
    } catch (e) { return false; }
  }
  function save() {
    try { localStorage.setItem(LS_KEY, JSON.stringify(state)); } catch (e) { /* ignore */ }
  }

  // ---- snake math ----
  function teamOnClock(n) {
    if (n < 1 || n > TOTAL_PICKS) return null;
    var round = Math.ceil(n / TEAMS);
    var idx = (n - 1) % TEAMS;               // 0-based position within the round
    return (round % 2 === 1) ? idx + 1 : TEAMS - idx;
  }
  function roundOf(n) { return Math.ceil(n / TEAMS); }

  // Picks until my next MEANINGFUL turn, for opportunity-cost math. On a snake
  // wrap my next pick is 1-2 away — I won't "miss" a player I can still grab
  // one pick later, so the real horizon is the turn after that.
  function picksUntilNextTurn() {
    var n = state.pickNum;
    if (!state.mySlot) return 18;               // no slot yet: assume ~mid
    if (n > TOTAL_PICKS) return 0;
    var turns = [];
    for (var k = 1; k <= TOTAL_PICKS - n && turns.length < 2; k++) {
      if (teamOnClock(n + k) === state.mySlot) turns.push(k);
    }
    if (!turns.length) return TOTAL_PICKS - n;
    if (turns.length > 1 && turns[0] <= 2) return turns[1];
    return turns[0];
  }

  // Rough share of upcoming picks that go to each position (early/mid draft).
  // Used only to estimate what will still be on the board at my next turn.
  var POS_RUN_RATE = { RB: 0.34, WR: 0.40, QB: 0.11, TE: 0.11, DST: 0.02, K: 0.02 };
  // How much VONA (value over next available) drives the pick vs raw VBD.
  var VONA_WEIGHT = 0.6;

  // ---- derived roster ----
  function draftedIdSet() {
    var s = {};
    state.drafted.forEach(function (d) { s[d.playerId] = true; });
    return s;
  }
  function myIds() {
    var out = [];
    state.drafted.forEach(function (d) { if (d.team === state.mySlot) out.push(d.playerId); });
    return out;
  }
  function myCount(pos) {
    var c = 0;
    myIds().forEach(function (id) { if (byId[id] && byId[id].pos === pos) c++; });
    return c;
  }

  var SLOTS = ["QB", "RB1", "RB2", "WR1", "WR2", "TE", "FLEX", "DST", "K",
               "BN1", "BN2", "BN3", "BN4", "BN5", "BN6", "BN7"];
  var BENCH = ["BN1", "BN2", "BN3", "BN4", "BN5", "BN6", "BN7"];
  function eligibleSlots(pos) {
    if (pos === "QB") return ["QB"];
    if (pos === "RB") return ["RB1", "RB2", "FLEX"];
    if (pos === "WR") return ["WR1", "WR2", "FLEX"];
    if (pos === "TE") return ["TE", "FLEX"];
    if (pos === "DST") return ["DST"];
    if (pos === "K") return ["K"];
    return [];
  }
  function computeRoster() {
    var slots = {};
    SLOTS.forEach(function (s) { slots[s] = null; });
    myIds().forEach(function (id) {
      var p = byId[id];
      if (!p) return;
      var placed = false;
      var elig = eligibleSlots(p.pos);
      for (var i = 0; i < elig.length; i++) {
        if (slots[elig[i]] === null) { slots[elig[i]] = id; placed = true; break; }
      }
      if (!placed) {
        for (var b = 0; b < BENCH.length; b++) {
          if (slots[BENCH[b]] === null) { slots[BENCH[b]] = id; placed = true; break; }
        }
      }
    });
    return slots;
  }
  function rosterNeeds(slots) {
    return {
      QB: slots.QB === null,
      RB: slots.RB1 === null || slots.RB2 === null,
      WR: slots.WR1 === null || slots.WR2 === null,
      TE: slots.TE === null,
      flexEmpty: slots.FLEX === null,
      anyStarterEmpty: slots.QB === null || slots.RB1 === null || slots.RB2 === null ||
                       slots.WR1 === null || slots.WR2 === null || slots.TE === null ||
                       slots.FLEX === null
    };
  }

  // ---- recommender ----
  // Past this many at a position, extra players there are strongly deprioritized
  // in the recommendations (any round) - stops the VBD board from suggesting a
  // 3rd QB / 4th TE just because backups elsewhere have gone negative.
  var SOFT_CAP = { QB: 2, RB: 6, WR: 6, TE: 2, DST: 1, K: 1 };

  // ---- M3: late-round upside tilt ------------------------------------------
  // League waivers are inverse-standings with no FAAB: a winning team picks
  // near-last on waivers all season, so late picks should chase UPSIDE and
  // CONTINGENT value over safe floor. All constants below are retunable.
  var UPSIDE_MIN_ROUND = 9;    // no upside bonus at all before this round
  var HANDCUFF_BONUS   = 10;   // p backs up one of MY starting RBs (same NFL team)
  var ROOKIE_BONUS     = 5;    // base boost for a rookie RB / WR / TE
  var ROOKIE_RAMP      = 1.5;  // extra rookie boost per round past round 10

  // The NFL teams of the RBs currently in my STARTING lineup (RB1, RB2, and
  // FLEX when a RB fills it), taken from computeRoster().
  function myStartingRbs(slots) {
    var ids = [slots.RB1, slots.RB2];
    if (slots.FLEX && byId[slots.FLEX] && byId[slots.FLEX].pos === "RB") ids.push(slots.FLEX);
    var out = [];
    ids.forEach(function (id) { if (id && byId[id]) out.push(byId[id]); });
    return out;
  }

  // Returns { bonus, reason, handcuff }. reason is null when nothing fired.
  function upsideInfo(p, round, slots) {
    if (round < UPSIDE_MIN_ROUND) return { bonus: 0, reason: null, handcuff: false };
    slots = slots || {};
    var bonus = 0, reason = null, handcuff = false;

    // (a) handcuff to one of my starting RBs: same NFL team, a RB, not the same
    //     player, and lower-projected than the back I already roster. High-value
    //     contingent insurance given the waiver rule.
    if (p.pos === "RB") {
      var starters = myStartingRbs(slots);
      for (var i = 0; i < starters.length; i++) {
        var rb = starters[i];
        if (rb.id === p.id) continue;
        if (rb.pro_team && p.pro_team === rb.pro_team && p.proj < rb.proj) {
          bonus += HANDCUFF_BONUS;
          reason = "handcuff to your " + p.pro_team + " RB";
          handcuff = true;
          break;
        }
      }
    }

    // (b) young upside: a rookie skill player, ramping slightly with the round.
    if (p.rookie === true && (p.pos === "RB" || p.pos === "WR" || p.pos === "TE")) {
      bonus += ROOKIE_BONUS + Math.max(0, round - 10) * ROOKIE_RAMP;
      if (reason === null) reason = "rookie upside";   // handcuff reason wins if set
    }

    return { bonus: bonus, reason: reason, handcuff: handcuff };
  }

  // number-only helper, kept for direct unit checks (0 before round 9).
  function upsideBonus(p, round, slots) {
    return upsideInfo(p, round, slots).bonus;
  }

  // ---- M3: display-only tags for the top-5 recs (NEVER change score) --------
  var CLIFF_VBD_WINDOW = 15;   // "within 15 raw_vbd" == his tier-or-better
  var CLIFF_MAX_REMAIN = 2;    // <= this many left at that tier => "last of tier"
  var BYE_CLASH_MIN    = 3;    // N of my starters on one bye week == a clash

  // My projected starters' bye weeks; returns [{week, names:[...]}, ...] for
  // any single week shared by >= BYE_CLASH_MIN starters (null byes ignored).
  function byeClashWeeks(slots) {
    var starterIds = [slots.QB, slots.RB1, slots.RB2, slots.WR1, slots.WR2, slots.TE, slots.FLEX];
    var weeks = {};
    starterIds.forEach(function (id) {
      if (!id || !byId[id]) return;
      var b = byId[id].bye;
      if (b === null || typeof b === "undefined") return;
      (weeks[b] = weeks[b] || []).push(byId[id].name);
    });
    var out = [];
    Object.keys(weeks).forEach(function (w) {
      if (weeks[w].length >= BYE_CLASH_MIN) out.push({ week: +w, names: weeks[w] });
    });
    out.sort(function (a, b) { return a.week - b.week; });
    return out;
  }

  // Append the bye-clash and positional-cliff tags to a rec's reason string.
  function decorateReason(r, board) {
    var reason = r.reason;
    var p = r.p;
    var s = board.slots;
    var starterIds = [s.QB, s.RB1, s.RB2, s.WR1, s.WR2, s.TE, s.FLEX];

    if (p.bye !== null && typeof p.bye !== "undefined") {
      var same = 0;
      starterIds.forEach(function (id) {
        if (id && byId[id] && byId[id].bye === p.bye) same++;
      });
      if (same + 1 >= BYE_CLASH_MIN)
        reason += " (bye " + p.bye + ": makes " + (same + 1) + ")";
    }

    var remain = 0;
    board.rows.forEach(function (x) {
      if (x.p.pos === p.pos && x.p.id !== p.id &&
          x.p.raw_vbd >= p.raw_vbd - CLIFF_VBD_WINDOW) remain++;
    });
    if (remain <= CLIFF_MAX_REMAIN) reason += " (last of tier)";

    return reason;
  }

  // Need weighting. A player that fills an EMPTY starter slot gets an ADDITIVE
  // urgency bonus that ramps with the round — multiplying doesn't work once
  // late-round players go below replacement (negative VBD), which would make a
  // needed TE rank below a useless backup WR. See test_board.js case 7.
  function needInfo(p, slots, needs, round) {
    var pos = p.pos;
    var fillsCore =
      (pos === "QB" && needs.QB) || (pos === "RB" && needs.RB) ||
      (pos === "WR" && needs.WR) || (pos === "TE" && needs.TE);
    var fillsKDST =
      (pos === "DST" && slots.DST === null) || (pos === "K" && slots.K === null);

    if (fillsCore) {
      var b = 10 + Math.max(0, round - 6) * 7;   // r6:+10  r10:+38  r14:+66
      return { mult: 1.0, bonus: b, reason: "fills your empty " + pos + " starter" };
    }
    if (fillsKDST) {
      if (round < 12)
        return { mult: 0.20, bonus: 0, reason: "kicker/defense — can wait" };
      var kb = 8 + Math.max(0, round - 11) * 10;  // r12:+18  r14:+38  r16:+58
      return { mult: 1.0, bonus: kb, reason: "you still need a " + pos };
    }
    // FLEX boost goes to RB/WR (and TE only if I don't already have a TE1 —
    // a 2nd TE in the flex is rarely right in full PPR).
    if (needs.flexEmpty &&
        (pos === "RB" || pos === "WR" || (pos === "TE" && myCount("TE") === 0))) {
      var fb = 6 + Math.max(0, round - 7) * 4;
      return { mult: 1.0, bonus: fb, reason: "FLEX need (" + p.tier_label + ")" };
    }
    if (myCount(pos) >= (SOFT_CAP[pos] || 99))
      return { mult: 0.35, bonus: 0, reason: "you're set at " + pos };
    // a 2nd QB or TE is a luxury while startable RB/WR/FLEX value is on the
    // board - deprioritize it until the mid-late rounds.
    if ((pos === "QB" || pos === "TE") && myCount(pos) >= 1 && round < 11)
      return { mult: 0.5, bonus: 0, reason: "you already have your " + pos + "1" };
    if ((pos === "K" || pos === "DST") && round < 13)
      return { mult: 0.20, bonus: 0, reason: "kicker/defense — can wait" };
    return { mult: 1.00, bonus: 0, reason: "best value available (" + p.tier_label + ")" };
  }

  function hardExcluded(p, needs, round) {
    if (myCount(p.pos) >= (POS_MAX[p.pos] || 99)) return true;
    // block K/DST while a real starter slot is open — but only up to round 12;
    // after that you need K/DST too and can't keep waiting forever.
    if ((p.pos === "K" || p.pos === "DST") && needs.anyStarterEmpty && round < 12)
      return true;
    // past a sensible count at a position, keep it out of the recommendations
    // (still fully click-draftable) so the VBD board can't push a 3rd QB.
    if (myCount(p.pos) >= (SOFT_CAP[p.pos] || 99)) return true;
    return false;
  }

  // Best raw_vbd still on the board per position, sorted desc.
  function availByPos(dset) {
    var m = { QB: [], RB: [], WR: [], TE: [], DST: [], K: [] };
    PLAYERS.forEach(function (p) { if (!dset[p.id] && m[p.pos]) m[p.pos].push(p); });
    return m;                                   // PLAYERS is already vbd-desc
  }

  // The raw_vbd I can still realistically get at this position at my NEXT turn,
  // after the expected run of picks there. This is what makes the engine value
  // scarcity: waiting on QB costs little (deep), waiting on elite RB costs a lot.
  function nextTurnVbd(pos, abp) {
    var list = abp[pos] || [];
    if (!list.length) return -400;
    var gone = Math.round(picksUntilNextTurn() * (POS_RUN_RATE[pos] || 0));
    return list[Math.min(gone, list.length - 1)].raw_vbd;
  }

  function scoreBoard() {
    var round = roundOf(state.pickNum);
    var slots = computeRoster();
    var needs = rosterNeeds(slots);
    var dset = draftedIdSet();
    var abp = availByPos(dset);
    var nextVbd = {};
    ["QB", "RB", "WR", "TE", "DST", "K"].forEach(function (pos) {
      nextVbd[pos] = nextTurnVbd(pos, abp);
    });

    var rows = [];
    PLAYERS.forEach(function (p) {
      if (dset[p.id]) return;
      var ni = needInfo(p, slots, needs, round);
      var ui = upsideInfo(p, round, slots);
      // VONA: how much better is p than what I could get here next time around.
      var vona = p.raw_vbd - nextVbd[p.pos];
      // market-vs-projection upside: ADP rates him well above the board (late only)
      var adpDelta = p.espn_draft_rank ? (p._vbdRank - p.espn_draft_rank) : 0;
      var adpBonus = 0, adpReason = null;
      if (round >= 11 && adpDelta > 20) {
        adpBonus = Math.min(adpDelta * 0.18, 12);
        adpReason = "market rates him higher — breakout upside";
      }
      // reason priority: handcuff > need/upside (larger bonus) > adp upside
      var reason = ni.reason;
      if (ui.reason && (ui.handcuff || ui.bonus > ni.bonus)) reason = ui.reason;
      else if (adpReason && adpBonus > ni.bonus) reason = adpReason;

      var blended = VONA_WEIGHT * vona + (1 - VONA_WEIGHT) * p.raw_vbd;
      rows.push({
        p: p,
        score: blended * ni.mult + ni.bonus + ui.bonus + adpBonus,
        vona: vona,
        reason: reason,
        excluded: hardExcluded(p, needs, round)
      });
    });
    rows.sort(function (a, b) { return b.score - a.score; });
    return { rows: rows, slots: slots, needs: needs, round: round };
  }

  // ---- mutations ----
  function draftPlayer(id) {
    if (state.pickNum > TOTAL_PICKS) return;
    if (draftedIdSet()[id]) return;
    var team = teamOnClock(state.pickNum);
    state.drafted.push({ playerId: id, overallPick: state.pickNum, team: team });
    state.pickNum += 1;
    save();
    render();
  }
  function undo() {
    if (state.drafted.length === 0) return;
    state.drafted.pop();
    state.pickNum -= 1;
    if (state.pickNum < 1) state.pickNum = 1;
    save();
    render();
  }
  function reset() {
    if (!window.confirm("Reset the entire draft? This clears all picks.")) return;
    state.drafted = [];
    state.pickNum = 1;
    try { localStorage.removeItem(LS_KEY); } catch (e) { /* ignore */ }
    save();
    render();
  }

  // ---- rendering ----
  function esc(s) {
    return String(s).replace(/[&<>"]/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
    });
  }
  function byeStr(b) { return (b === null || typeof b === "undefined") ? "-" : String(b); }

  function renderClock() {
    var el = document.getElementById("clock");
    if (state.pickNum > TOTAL_PICKS) {
      el.className = "";
      el.innerHTML = "<span class='big'>Draft complete</span>";
      return;
    }
    var team = teamOnClock(state.pickNum);
    var mine = (team === state.mySlot);
    el.className = mine ? "mine" : "";
    el.innerHTML =
      "<span class='big'>R" + roundOf(state.pickNum) + " &middot; Pick " + state.pickNum + "</span><br>" +
      "Team " + team + (mine ? " (YOU)" : "");
  }

  function renderRoster(slots) {
    var labels = {
      QB: "QB", RB1: "RB1", RB2: "RB2", WR1: "WR1", WR2: "WR2", TE: "TE",
      FLEX: "FLEX", DST: "DST", K: "K",
      BN1: "BN", BN2: "BN", BN3: "BN", BN4: "BN", BN5: "BN", BN6: "BN", BN7: "BN"
    };
    var html = "";
    SLOTS.forEach(function (s) {
      var id = slots[s];
      var nm = id ? esc(byId[id].name) : "—";
      html += "<div class='rs" + (id ? " filled" : "") + "'>" +
              "<span class='slot'>" + labels[s] + "</span>" + nm + "</div>";
    });
    document.getElementById("rosterGrid").innerHTML = html;
  }

  function renderCounts() {
    var order = ["QB", "RB", "WR", "TE", "DST", "K"];
    var html = "";
    order.forEach(function (pos) {
      var c = myCount(pos), m = POS_MAX[pos];
      html += "<span class='" + (c >= m ? "full" : "") + "'>" + pos + " " + c + "/" + m + "</span>";
    });
    document.getElementById("countsRow").innerHTML = html;
  }

  function rowHtml(r, rank, prevTier) {
    var p = r.p;
    var sep = (prevTier !== null && prevTier !== p.tier_label) ? " tiersep" : "";
    return "<div class='prow" + sep + (r.excluded ? " excluded" : "") +
           "' data-id='" + p.id + "'>" +
           "<span class='pname'>" + esc(p.name) + "</span>" +
           "<span class='pos pos-" + p.pos + "'>" + p.pos + "</span>" +
           "<span>" + esc(p.pro_team) + "</span>" +
           "<span class='num'>" + byeStr(p.bye) + "</span>" +
           "<span class='num'>" + p.proj.toFixed(1) + "</span>" +
           "<span class='num'>" + p.raw_vbd.toFixed(1) + "</span>" +
           "<span>" + p.tier_label + "</span>" +
           "</div>";
  }

  function renderList(board) {
    var term = ui.search.trim().toLowerCase();
    var rows = board.rows;
    if (term) {
      rows = rows.filter(function (r) {
        return r.p.name.toLowerCase().indexOf(term) !== -1 ||
               r.p.pro_team.toLowerCase().indexOf(term) !== -1 ||
               r.p.pos.toLowerCase() === term;
      });
    }
    var head = "<div class='phead'><span class='pname'>Player</span><span>Pos</span><span>Tm</span>" +
               "<span>Bye</span><span>Proj</span><span>VBD</span><span>Tier</span></div>";
    var body = "";
    var prevTier = null;
    for (var i = 0; i < rows.length; i++) {
      body += rowHtml(rows[i], i + 1, prevTier);
      prevTier = rows[i].p.tier_label;
    }
    if (!rows.length) body = "<div class='prow'>no matching players</div>";
    document.getElementById("plist").innerHTML = head + body;
  }

  function renderRecs(board) {
    var picks = [];
    for (var i = 0; i < board.rows.length && picks.length < 5; i++) {
      if (!board.rows[i].excluded) picks.push(board.rows[i]);
    }
    // roster essentially set - nothing un-excluded left. Show best bench upside
    // (highest VBD still available) rather than an empty panel.
    if (!picks.length) {
      for (var j = 0; j < board.rows.length && picks.length < 5; j++) {
        var r = board.rows[j];
        if (myCount(r.p.pos) < (POS_MAX[r.p.pos] || 99)) {
          r.reason = "roster set - best bench value left";
          picks.push(r);
        }
      }
    }
    var html = "";
    if (state.pickNum > TOTAL_PICKS) {
      html = "<div class='rec'>Draft complete.</div>";
    } else {
      picks.forEach(function (r) {
        html += "<div class='rec'><span class='nm'>" + esc(r.p.name) + "</span> " +
                "<span class='pos pos-" + r.p.pos + "'>" + r.p.pos + "</span> " +
                r.p.pro_team + " &middot; VBD " + r.p.raw_vbd.toFixed(1) +
                "<div class='why'>" + esc(decorateReason(r, board)) + "</div></div>";
      });
      if (!picks.length) html = "<div class='rec'>No recommendation.</div>";
    }
    document.getElementById("recs").innerHTML = html;

    // best available by position
    var showLate = board.round >= 12;
    var positions = ["QB", "RB", "WR", "TE"];
    if (showLate) positions = positions.concat(["DST", "K"]);
    var seen = {};
    board.rows.forEach(function (r) {
      if (!seen[r.p.pos]) seen[r.p.pos] = r;
    });
    var bp = "";
    positions.forEach(function (pos) {
      var r = seen[pos];
      bp += "<div><span class='pos pos-" + pos + "'>" + pos + "</span> " +
            (r ? esc(r.p.name) + " (VBD " + r.p.raw_vbd.toFixed(1) + ", " + r.p.tier_label + ")"
               : "—") + "</div>";
    });
    document.getElementById("bestpos").innerHTML = bp;
  }

  function renderByeWarn(slots) {
    var clashes = byeClashWeeks(slots);
    document.getElementById("byeWarn").innerHTML = clashes.map(function (c) {
      return "Bye clash: " + c.names.length + " starters on bye week " + c.week +
             " (" + c.names.map(esc).join(", ") + ")";
    }).join("<br>");
  }

  function renderBanner() {
    var el = document.getElementById("banner");
    if (state.pickNum > TOTAL_PICKS) {
      el.innerHTML = "<div class='done-banner'>All " + TOTAL_PICKS +
                     " picks made &mdash; draft complete.</div>";
    } else {
      el.innerHTML = "";
    }
  }

  function render() {
    var board = scoreBoard();
    document.getElementById("slotSel").value = state.mySlot ? String(state.mySlot) : "";
    document.getElementById("leagueInfo").innerHTML =
      TEAMS + " teams &middot; " + ROSTER_SPOTS + " rounds &middot; " + TOTAL_PICKS + " picks";
    document.body.classList.toggle("plain", ui.plain);
    renderClock();
    renderRoster(board.slots);
    renderByeWarn(board.slots);
    renderCounts();
    renderBanner();
    renderList(board);
    renderRecs(board);
  }

  // ---- setup / init screen ----
  var initSel = TEAMS;   // pending team count while the setup screen is open

  function renderTeamBtns() {
    var html = "";
    for (var n = 8; n <= 16; n++) {
      html += "<button data-n='" + n + "'" + (n === initSel ? " class='sel'" : "") +
              ">" + n + "</button>";
    }
    document.getElementById("teamBtns").innerHTML = html;
  }
  function renderInitSlot() {
    var el = document.getElementById("initSlot");
    var keep = el.value;
    var o = "<option value=''>-- not set yet --</option>";
    for (var i = 1; i <= initSel; i++) o += "<option>" + i + "</option>";
    el.innerHTML = o;
    if (keep && parseInt(keep, 10) <= initSel) el.value = keep;
  }
  function openInit() {
    initSel = TEAMS;
    renderTeamBtns();
    renderInitSlot();
    document.getElementById("initSlot").value = state.mySlot ? String(state.mySlot) : "";
    document.getElementById("initScreen").className = "";
  }
  function closeInit() { document.getElementById("initScreen").className = "hidden"; }

  document.getElementById("teamBtns").addEventListener("click", function (e) {
    var b = e.target && e.target.closest ? e.target.closest("button[data-n]") : null;
    if (!b) return;
    initSel = parseInt(b.getAttribute("data-n"), 10);
    renderTeamBtns();
    renderInitSlot();
  });
  document.getElementById("initStart").addEventListener("click", function () {
    var slot = parseInt(document.getElementById("initSlot").value, 10);
    setTeams(initSel);
    if (slot >= 1 && slot <= TEAMS) state.mySlot = slot;
    if (state.mySlot && state.mySlot > TEAMS) state.mySlot = null;
    save();
    closeInit();
    render();
  });
  document.getElementById("setupBtn").addEventListener("click", openInit);

  // ---- events ----
  document.getElementById("slotSel").addEventListener("change", function (e) {
    var v = parseInt(e.target.value, 10);
    state.mySlot = (v >= 1 && v <= TEAMS) ? v : null;
    save();
    render();
  });
  document.getElementById("plist").addEventListener("click", function (e) {
    if (ui.plain) return;
    var row = e.target.closest ? e.target.closest(".prow") : null;
    if (!row) return;
    var id = row.getAttribute("data-id");
    if (id) draftPlayer(isNaN(+id) ? id : +id);
  });
  document.getElementById("search").addEventListener("input", function (e) {
    ui.search = e.target.value;
    render();
  });
  document.getElementById("undoBtn").addEventListener("click", undo);
  document.getElementById("resetBtn").addEventListener("click", reset);
  document.getElementById("plainBtn").addEventListener("click", function () {
    ui.plain = !ui.plain;
    render();
  });

  // test hook — used by the headless harness only; harmless in the browser.
  if (typeof window !== "undefined") {
    window.__board = {
      scoreBoard: scoreBoard, upsideInfo: upsideInfo, upsideBonus: upsideBonus,
      computeRoster: computeRoster, byeClashWeeks: byeClashWeeks, state: state,
      setTeams: setTeams, recomputeValues: recomputeValues
    };
  }

  var hadConfig = load();
  recomputeValues();              // always recompute for the active team count
  renderSlotOptions();
  if (hadConfig) { closeInit(); } else { openInit(); }
  render();
})();
</script>
</body>
</html>
"""


def main():
    model = value_model.build_model()
    players = collect_players(model)
    config = {
        "POS_MAX": POS_MAX,
        "repl_pts": model["repl_pts"],
        "roster_spots": 16,               # fixed league setting (9 starters + 7 bench)
        "default_teams": value_model.TEAMS,
        # everything the browser needs to recompute VBD + tiers for any league size
        "vm": {
            "STARTERS": value_model.STARTERS,
            "FLEX_SPLIT": value_model.FLEX_SPLIT,
            "REPLACEMENT_BUFFER": value_model.REPLACEMENT_BUFFER,
            "TIER_FACTOR": value_model.TIER_FACTOR,
            "TIER_MIN_GAP": value_model.TIER_MIN_GAP,
            "TIER_MAX": value_model.TIER_MAX,
            "TIER_RANGE": value_model.TIER_RANGE,
        },
        "generated_at": model["meta"].get("generated_at"),
        "built_at": datetime.datetime.now(datetime.timezone.utc)
        .replace(microsecond=0).isoformat(),
    }
    page = (
        PAGE.replace("__CSS__", CSS)
        .replace("__PLAYERS_JSON__", blob(players))
        .replace("__CONFIG_JSON__", blob(config))
    )
    with open(OUT_PATH, "w", encoding="utf-8") as fh:
        fh.write(page)

    size = os.path.getsize(OUT_PATH)
    print("Wrote", OUT_PATH)
    print("Players embedded:", len(players))
    print("File size: %d bytes (%.1f KB)" % (size, size / 1024.0))


if __name__ == "__main__":
    main()
