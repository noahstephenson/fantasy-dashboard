# B1 Boyzz Fantasy Dashboard

**➡️ [Open the dashboard](https://noahstephenson.github.io/fantasy-dashboard/)**

Auto-updating status page for the B1 Boyzz ESPN Fantasy Football league:
this week's matchup, recommended lineup, and top waiver-wire targets. Data
refreshes automatically every ~4 hours via GitHub Actions — no need to open
Claude Code just to check it.

## What's in here

- `fantasy_mcp/` — the in-season MCP server (roster, lineup, waivers, trade
  eval) used from Claude Code
- `docs/` — the static dashboard site (GitHub Pages source)
- `scripts/generate_dashboard_data.py` — pulls live ESPN data and writes
  `docs/data.json`, run on a schedule by `.github/workflows/update-dashboard.yml`
- Everything else (`fetch_players.py`, `value_model.py`, `build_board.py`,
  `draft_board.html`, `tiers.html`) — the original draft-day tool, kept as-is

## Local setup

Requires `tool/.env` with `ESPN_LEAGUE_ID`, `ESPN_S2`, `ESPN_SWID`, `SEASON`
(never committed — see `.env.example`). Then:

```
venv/Scripts/python.exe verify_mcp.py                       # smoke test the MCP tools
venv/Scripts/python.exe scripts/generate_dashboard_data.py   # regenerate docs/data.json locally
```
