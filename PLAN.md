# Fantasy Football Draft Decision Tool — Build Plan

## Context

Snake draft tomorrow, **Aug 28, 9:00 PM EDT** (~24h). Hard deadline.

**Goal:** a local tool that, at any point in the draft, says who to take next
given the board state and current roster.

**League:** ESPN "B1 Boyzz", 2026, 10 teams, snake, 90s/pick, full PPR.
- Starters (9): QB1, RB2, WR2, TE1, FLEX1 (RB/WR/TE), D/ST1, K1. 16 spots, 7 bench.
- Position max: QB4, RB8, WR8, TE3, D/ST3, K3.
- PPR: 1/rec, 0.1/yd, 6/rush+rec TD, 0.04/pass yd, 4/pass TD, -2/INT, -2/FL.
- Draft order randomized 1h before start → tool must work from any slot.
- Waivers = inverse standings, no FAAB. Winners pick near-last all season →
  late picks weight **upside + contingent value**, not floor.

### What I already verified (from espn-api 0.46.0 source)

1. **`free_agents(size=N)`** requests `view=kona_player_info` with an
   `x-fantasy-filter` header carrying `"limit": N`. Single request, **no
   pagination**, filters `status in [FREEAGENT, WAIVERS]`, sorts by % owned.
   Builds `BoxPlayer` objects; `projected_total_points` is read from ESPN's
   precomputed `stats[0].appliedTotal` (projection source), **not** recomputed
   from league scoring. Pre-draft everyone is a free agent, so the pool = full
   player universe. **Unverified:** whether ESPN honors `limit=400` in one
   response or silently caps (~50). → Milestone 0.

2. **Known gotcha CONFIRMED in code.** `base_league._fetch_draft()`:
   ```python
   data = self.espn_request.get_league_draft()          # view=mDraftDetail
   if not data.get('draftDetail', {}).get('drafted'):   # <-- early return
       return
   picks = data.get('draftDetail', {}).get('picks', [])
   ```
   `league.draft` stays **empty until ESPN flips `draftDetail.drafted` → true**,
   which is typically only at draft *completion*. The `picks` array may or may
   not populate live — ESPN-side behavior, cannot confirm without a live draft.
   League endpoint: `/seasons/2026/segments/0/leagues/{id}?view=mDraftDetail`.

3. **No venv / espn-api currently on this machine** (checked `./venv`, maxdepth-3
   scan, `pip show`). The "already installed in ./venv" assumption is not true
   yet — Milestone 0 creates it.

---

## 1. Data source — confirm or kill (Milestone 0, ~1.5h, BLOCKS everything)

**Prereqs from you:** real `league_id`; whether the league is private (if so,
`espn_s2` + `SWID` cookies from espn.com DevTools → Application → Cookies).
Stored in a gitignored `.env`, never committed.

**`verify_data.py` does:**
1. `python -m venv venv` (at `<project>/venv`), `pip install espn-api==0.46.0`.
2. `League(league_id=..., year=2026, espn_s2=..., swid=...)`.
3. `fa = league.free_agents(size=400)` — check:
   - `len(fa)` — is it ~400 or capped? If capped → loop `free_agents(position=p,
     size=200)` over QB/RB/WR/TE/DST/K and merge (~6 calls).
   - `% with projected_total_points > 0`. If ~0 → retry with explicit
     `scoringPeriodId=0`; if still 0 → CSV fallback (you export ESPN projections).
   - Print top 15 overall + top 10 per position by projection; eyeball vs known
     2026 studs.
   - Full-PPR sanity: a high-reception WR should out-project a similar-yardage
     low-reception RB.
4. Raw GET `…/leagues/{id}?view=mDraftDetail` against **last year's** league or
   an ESPN instant mock — confirm we can parse `draftDetail.picks[]`
   (`playerId`, `overallPickNumber`, `roundId`, `roundPickNumber`, `teamId`).

**Decision gate:**
- Pool OK + projections present → proceed, write `players.json`
  (name, pos, proTeam, bye, proj_pts, espn_draft_rank, rookie/age if present).
- Pool truncated but per-position loop works → proceed with that.
- Projections missing / auth broken and unfixable → **switch to CSV import**
  (you download ESPN's projections export; tool ingests it). Same downstream code.

---

## 2. Live draft sync — decision

**Commit to manual one-click as the backbone.** The confirmed early-return plus
unconfirmable live latency makes it unsafe to build on. Manual click-off is the
design; the tool assumes nothing from ESPN during the draft.

**Stretch only (Milestone 4, hard cutoff 2h pre-draft):** a local `poll.py`
hitting raw `mDraftDetail` every 5s, bypassing the `drafted` check, reading
`picks[]` directly. **Test tonight** by pointing it at a live ESPN instant mock
and watching whether picks appear within seconds. If not reliable → document
"manual only" and drop it. Manual override always wins regardless.

---

## 3. Value model (assumptions stated for your sanity check)

**Replacement level derived from THIS league**, from the actual projection pull
(not a published table).

Starter demand across 10 teams:

| Pos | Non-flex starters | + FLEX share | Replacement rank | Buffer used |
|-----|-------------------|--------------|------------------|-------------|
| QB  | 10                | —            | **QB12**         | +2 (light streaming) |
| RB  | 20                | +4           | **RB24**         | FLEX split 40% RB |
| WR  | 20                | +5           | **WR25**         | FLEX split 50% WR |
| TE  | 10                | +1           | **TE11**         | FLEX split 10% TE |
| D/ST| 10                | —            | **DST11**        | +1 |
| K   | 10                | —            | **K11**          | +1 |

**Key assumption to check:** FLEX 10 spots split **40 RB / 50 WR / 10 TE** (full
PPR, 10-team). All buffers are named constants in `value_model.py` — trivially
retunable after you see the M1 board.

**Why this differs from off-the-shelf (which you flagged correctly):**
published VBD tables assume 12 teams → RB replacement ~RB34, WR ~WR38. At 10
teams it's RB24 / WR25 — replacement players score *more*, so value-over-
replacement **compresses** for RB/WR. Result: less reason to reach for RB/WR
early; the top-heavy positions (elite TE, elite QB) gain relative standing.

**Score:**
```
raw_VBD(p) = p.proj_pts − replacement_pts(p.position)
   replacement_pts = proj_pts of the player at that position's replacement rank,
   taken from this pull.
```

**Pick recommendation (layered across milestones):**
- **M1:** rank available by `raw_VBD`. Static board + tiers (gap-based: new tier
  when the drop to the next player exceeds a per-position threshold).
- **M2:** `final = raw_VBD × need_multiplier + upside_bonus`
  - `need_multiplier`: ×1.15 fills an empty non-flex starter slot; ×1.07 fills
    empty FLEX; ×0.6 if already deep (RB/WR ≥5, QB/TE ≥2) before round 10;
    K/DST ×0.2 before round 13.
  - **Hard block:** position at its maximum → excluded. Never K/DST while a
    non-K/DST starter slot is empty.
  - Output: top 5 with score + one-line reason.
- **M3 (as time allows):**
  - **Positional cliff bonus (VONA-lite):** `bonus = best_avail_VBD −
    k-th_best_avail_VBD` at that position, `k` ≈ (picks until your next turn)
    scaled by that position's recent draft rate; capped.
  - **Late-round upside tilt** (round >10): boost younger/rookie skill players
    and — most important given the waiver rule — **handcuffs to my own starting
    RBs** (same proTeam, RB, I roster the lead back) as contingent value.
  - **Bye-clash soft warning:** flag if a pick puts 3+ of my projected starters
    on the same bye. Not a score factor.

---

## 4. Interface — single self-contained HTML file, no server

Python build emits **`draft_board.html`** with all player data + precomputed VBD
+ tiers embedded as a `<script>` JSON blob and vanilla JS for interaction.

**Why file:// and not a localhost app:** nothing to crash mid-draft, survives
wifi drops, no network/LLM in the pick path (guaranteed), and the same file *is*
the static fallback.

**Layout:**
- **Top bar:** draft-slot selector (set once, after the 1h-before randomization —
  no rebuild needed); current round/pick; "on the clock: Team N"; my roster by
  slot; position counts with max indicators.
- **Left:** big scrollable board, one row per player (name, pos, team, proj,
  VBD, tier), tier-colored, sorted by current recommendation score.
  **One click on a row = drafted by whoever is on the clock** (snake order
  known). If it's my pick → adds to my roster slot. No mode toggle.
- **Right:** "RECOMMENDED NOW" — top 5 with reason strings; plus best-available
  per position.
- **Controls:** Undo (critical), search-to-find-a-player (secondary path only),
  Reset, Print/plain view.
- **Autosave:** board state to `localStorage` (wrapped in try/catch) so an
  accidental tab close doesn't wipe the draft.

**Guaranteed fallback:** the build also writes `tiers.html` + `tiers.txt`
(overall VBD ranking + per-position tier columns + the assumptions block at top).

---

## Execution — ruflo swarm

Build is delegated to a **ruflo swarm** run from `C:\Users\noahh\fantasy-bot`.

- I write the plan + `players.json` schema + the value-model constants into the
  repo as the swarm's spec, then `ruflo swarm "<implement per PLAN.md, milestone
  order, stop at each review gate>"`.
- I orchestrate: monitor `ruflo swarm status`, review each milestone's output at
  the M0 decision gate and the M1/M2 review gates before letting it continue.
- **Deadline safety valve:** if the swarm stalls, loops, or misses the M1 target
  by more than ~2h, I take over and build the remaining milestones directly.
  A working `tiers.txt` by M1 is non-negotiable.
- Live sync (M4) stays a stretch goal with a hard cutoff 2h before the draft.

## 5. Build order (something usable after M1, not just at the end)

| # | Deliverable | Est | Usable? |
|---|-------------|-----|---------|
| **M0** | venv + `verify_data.py` + `players.json` + sanity report. Decision gate on pool/projections. | 1.5h | data confirmed |
| **M1** | `value_model.py` → `tiers.html` + `tiers.txt`. Assumptions block printed. **Review gate: you sanity-check replacement levels + top 40.** | 2.5h | **Yes — draftable off the sheet alone** |
| **M2** | `build_board.py` → `draft_board.html`: snake tracking, one-click draft-off, roster/max logic, top-5 recommender (VBD × need), Undo, autosave. **Gate: full ESPN mock draft, click every pick, confirm sync + speed.** | 4h | **Yes — the tool** |
| **M3** | Cliff bonus, late-round upside + RB handcuff detection, bye-clash warning, print view. Ship whichever land. | 2h | incremental |
| **M4** | *Stretch — chosen: attempt only if M0–M3 solid.* `poll.py` live sync. Test vs live mock. Hard cutoff 2h pre-draft; drop if flaky. | 2h | optional |

Core M0–M3 ≈ 10h → fits 24h with sleep and buffer.

**Project location:** `C:\Users\noahh\fantasy-bot\tool\` (venv at
`fantasy-bot/tool/venv`). Cookies in `fantasy-bot/tool/.env` (gitignored).

---

## Verification

- **M0:** `python verify_data.py` prints pool size, projection coverage %, top-N
  tables; you eyeball against known studs. Raw `mDraftDetail` parse test passes
  on a mock/last-year league.
- **M1:** open `tiers.html`; replacement-level numbers and top-40 order pass your
  gut check; adjust constants and rerun if not.
- **M2:** run a complete ESPN instant mock — click all ~160 picks, confirm the
  clock/round never desyncs, Undo restores exactly, recommendations stay sane,
  each interaction <5s. Test from an early slot and a late slot.
- **M3:** unit-check handcuff detection and bye-clash on your post-mock roster.
- **M4:** side-by-side a live mock: does `poll.py` surface picks within ~10s of
  them happening? If no → mark manual-only.
