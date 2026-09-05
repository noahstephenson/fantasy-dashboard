# Implementation Spec (for the build swarm)

Read `PLAN.md` first. This file pins the concrete contracts so milestones can be
built and reviewed independently. Do not deviate without flagging it.

## Environment

- Python venv at `tool/venv` (already created; `espn-api==0.46.0` installed).
- Secrets in `tool/.env` (gitignored), loaded with `python-dotenv`:
  `ESPN_LEAGUE_ID`, `ESPN_S2`, `ESPN_SWID`, `SEASON` (=2026).
- All scripts run from `tool/` as `venv/Scripts/python.exe <script>.py`.
- No new network calls anywhere except `verify_data.py` / `fetch_players.py`
  (ESPN) and the optional `poll.py` (M4). The board HTML makes ZERO network
  calls.

## File contracts

### `players.json` (output of M0, input to M1)
```json
{
  "meta": {
    "generated_at": "ISO-8601",
    "season": 2026,
    "scoring": "full_ppr",
    "source": "espn_free_agents" | "espn_per_position" | "csv_import",
    "pool_size": 400,
    "projection_coverage": 0.0
  },
  "players": [
    {
      "id": 4241457,
      "name": "Ja'Marr Chase",
      "pos": "WR",                     // one of QB RB WR TE DST K
      "pro_team": "CIN",
      "bye": 10,                        // int or null
      "proj_pts": 312.4,               // full-PPR season projection
      "espn_draft_rank": 3,            // STANDARD draft rank, int or null
      "rookie": false,                 // bool or null
      "age": 25                        // int or null
    }
  ]
}
```

### `tiers.txt` + `tiers.html` (output of M1) — the guaranteed fallback
- Header block: replacement rank + replacement points per position, the FLEX
  split assumption, generation timestamp.
- Overall list ranked by `raw_vbd` desc: rank, name, pos, team, bye, proj_pts,
  raw_vbd, tier.
- Per-position columns with tier breaks marked.
- `tiers.txt` must be readable in a terminal at 100 cols.

### `draft_board.html` (output of M2) — single self-contained file
- All player data + precomputed `raw_vbd` + tier embedded as one `<script
  type="application/json" id="players">` blob.
- Vanilla JS only. No external requests, no CDN, no build step.
- State (drafted set, my slot, pick number, rosters) persisted to
  `localStorage` under key `b1boyzz_draft_v1`, every mutation, wrapped in
  try/catch.

## Value model constants (`value_model.py` — all module-level, retunable)

```python
TEAMS = 10
STARTERS = {"QB": 1, "RB": 2, "WR": 2, "TE": 1, "DST": 1, "K": 1}  # + 1 FLEX
FLEX_SPLIT = {"RB": 0.40, "WR": 0.50, "TE": 0.10}   # of TEAMS flex spots
REPLACEMENT_BUFFER = {"QB": 2, "RB": 0, "WR": 0, "TE": 0, "DST": 1, "K": 1}
POS_MAX = {"QB": 4, "RB": 8, "WR": 8, "TE": 3, "DST": 3, "K": 3}

# replacement_rank(pos) = STARTERS[pos]*TEAMS
#                       + round(FLEX_SPLIT.get(pos, 0) * TEAMS)
#                       + REPLACEMENT_BUFFER[pos]
# -> QB12, RB24, WR25, TE11, DST11, K11
# replacement_pts(pos) = proj_pts of the player at that rank within pos,
#                        from THIS players.json (not a table).
# raw_vbd(p) = p.proj_pts - replacement_pts(p.pos)
```

## Recommender (`build_board.py` JS + a Python reference impl for tests)

```
final_score(p, my_roster, round) =
    raw_vbd(p) * need_multiplier(p, my_roster, round) + upside_bonus(p, round)

need_multiplier:
  1.15  if p.pos fills an empty non-FLEX starter slot I have
  1.07  elif p.pos in {RB,WR,TE} and my FLEX slot is empty
  0.60  elif count(my_roster, p.pos) >= {RB:5, WR:5, QB:2, TE:2}.get(pos, 99)
        and round < 10
  0.20  if p.pos in {K, DST} and round < 13
  1.00  otherwise
HARD EXCLUDE if count(my_roster, p.pos) >= POS_MAX[p.pos]
HARD EXCLUDE K/DST while any non-K/DST starter slot of mine is empty

upside_bonus (M3, 0 until then):
  round <= 10: 0
  round  > 10: + w_hc * is_handcuff_to_my_starting_rb(p)      # w_hc ~ 8
             + w_yr * (p.rookie or (p.age and p.age <= 24)) * (p.pos in RB/WR/TE)
```

Output: top 5 available by `final_score`, each with a one-line reason derived
from which branch of `need_multiplier` / `upside_bonus` fired.

## Snake tracking (board JS)

- `my_slot` in 1..10 chosen in the UI (after ESPN's 1h-before randomization).
- Pick `n` (1-indexed): `round = ceil(n/10)`; within round, order is
  `1..10` on odd rounds, `10..1` on even. Team on the clock = that mapping.
  My picks = pick numbers where team == my_slot.
- One click on a player row = that player drafted by the team currently on the
  clock; advance `n`. If it was my slot, assign to my first open slot that the
  player is eligible for (position slot before FLEX before bench).
- Undo pops the last pick and restores exact prior state.

## Milestone gates (STOP and wait for human review)

- After **M0**: print the sanity report, write `players.json`, STOP.
- After **M1**: open `tiers.html`, STOP for assumption review.
- After **M2**: STOP for the full mock-draft test.
- **M4** only if M0–M3 are done and it is >2h before 2026-08-28 21:00 EDT.
