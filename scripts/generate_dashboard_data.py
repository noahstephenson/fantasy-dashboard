"""Generates docs/data.json for the GitHub Pages dashboard.

Calls the existing fantasy_mcp package directly (same pattern as
verify_mcp.py: one League object, threaded through), and writes a single
JSON file the static dashboard reads. Run manually or by the scheduled
GitHub Actions workflow (.github/workflows/update-dashboard.yml).

Run from tool/:
    venv/Scripts/python.exe scripts/generate_dashboard_data.py
"""
import datetime
import json
import sys
from pathlib import Path

# fantasy_mcp lives in the repo root (tool/), one directory up from scripts/.
# Running this file directly (`python scripts/generate_dashboard_data.py`)
# only puts scripts/ on sys.path, so add the repo root explicitly.
_REPO_ROOT = str(Path(__file__).resolve().parent.parent)
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from fantasy_mcp import espn_client, lineup, waivers  # noqa: E402


def main():
    league = espn_client.get_league()
    my_team = espn_client.get_my_team(league)
    week = espn_client.get_current_week(league)
    matchup = espn_client.get_my_matchup(league=league)
    slot_counts = league.settings.position_slot_counts
    rec = lineup.recommend_lineup(matchup, slot_counts)
    wt = waivers.get_waiver_targets(top_n=15, league=league)

    opponent_name = next(
        (t.team_name for t in league.teams if t.team_id == matchup["opponent_team_id"]),
        None,
    )

    data = {
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "week": week,
        "team_name": my_team.team_name,
        "matchup": {
            "opponent_name": opponent_name,
            "my_score": matchup["my_score"],
            "opp_score": matchup["opp_score"],
            "my_projected": matchup["my_projected"],
            "opp_projected": matchup["opp_projected"],
        },
        "lineup": {
            "recommended_starters": rec["recommended_starters"],
            "bench": rec["bench"],
            "reasoning": rec["reasoning"],
            "projected_total": rec["projected_total"],
        },
        "waiver_targets": wt["targets"],
    }

    out = Path(__file__).resolve().parent.parent / "docs" / "data.json"
    out.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
    print(f"Wrote {out} ({out.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
