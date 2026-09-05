"""Milestone 0 - confirm or kill the ESPN data source.

Checks, in order:
  1. Can we authenticate to the league at all.
  2. Does free_agents(size=400) return a full pool or a silent cap.
  3. Do players carry a full-PPR season projection (projected_total_points).
  4. Sanity: high-reception WRs should out-project similar low-reception backs.
  5. Can we read raw mDraftDetail picks (structure only - draft has not happened).

Run:  venv/Scripts/python.exe verify_data.py
"""
import json
import os
import sys
from collections import Counter
from datetime import datetime, timezone

from dotenv import load_dotenv

load_dotenv()

LEAGUE_ID = int(os.environ["ESPN_LEAGUE_ID"])
ESPN_S2 = os.environ["ESPN_S2"]
SWID = os.environ["ESPN_SWID"]
SEASON = int(os.environ.get("SEASON", "2026"))

POS_KEEP = {"QB", "RB", "WR", "TE", "D/ST", "K"}
POS_NORM = {"D/ST": "DST"}


def hr(title):
    print("\n" + "=" * 72 + f"\n{title}\n" + "=" * 72)


def connect(year):
    from espn_api.football import League

    return League(league_id=LEAGUE_ID, year=year, espn_s2=ESPN_S2, swid=SWID)


def main():
    from espn_api.football import League  # noqa: F401  (import check)

    hr(f"1. AUTH  league={LEAGUE_ID} season={SEASON}")
    year = SEASON
    try:
        league = connect(year)
    except Exception as e:  # noqa: BLE001
        print(f"  {SEASON} failed: {e!r}")
        year = SEASON - 1
        print(f"  retrying with {year} ...")
        league = connect(year)
    print(f"  OK  connected. year={year}  teams={len(league.teams)}  "
          f"current_week={getattr(league, 'current_week', '?')}")

    hr("2. POOL SIZE  free_agents(size=400)")
    fa = league.free_agents(size=400)
    print(f"  returned {len(fa)} players")
    per_pos_used = False
    if len(fa) < 300:
        print("  -> looks capped. Trying per-position merge ...")
        merged = {}
        for pos in ["QB", "RB", "WR", "TE", "D/ST", "K"]:
            try:
                chunk = league.free_agents(size=200, position=pos)
            except Exception as e:  # noqa: BLE001
                print(f"     {pos}: error {e!r}")
                continue
            for p in chunk:
                merged[p.playerId] = p
            print(f"     {pos}: {len(chunk)}")
        if len(merged) > len(fa):
            fa = list(merged.values())
            per_pos_used = True
        print(f"  merged pool: {len(fa)}")

    hr("3. PROJECTIONS  projected_total_points")
    with_proj = [p for p in fa if (p.projected_total_points or 0) > 0]
    coverage = len(with_proj) / max(len(fa), 1)
    print(f"  {len(with_proj)}/{len(fa)} have projected_total_points > 0  "
          f"({coverage:.0%})")
    posc = Counter(getattr(p, "position", "?") for p in fa)
    print(f"  positions in pool: {dict(posc)}")

    hr("4. TOP BY PROJECTION (overall + per position)")
    ranked = sorted(fa, key=lambda p: -(p.projected_total_points or 0))
    print("  -- overall top 15 --")
    for i, p in enumerate(ranked[:15], 1):
        print(f"   {i:>2}. {p.name:<24} {getattr(p,'position','?'):<4} "
              f"{p.projected_total_points:>7.1f}")
    for pos in ["QB", "RB", "WR", "TE", "D/ST", "K"]:
        pp = [p for p in ranked if getattr(p, "position", None) == pos][:10]
        print(f"  -- {pos} top 10 --")
        for i, p in enumerate(pp, 1):
            print(f"   {i:>2}. {p.name:<24} {p.projected_total_points:>7.1f}")

    hr("5. RAW mDraftDetail  (structure check - draft has not happened yet)")
    try:
        import requests

        base = ("https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl"
                f"/seasons/{year}/segments/0/leagues/{LEAGUE_ID}")
        r = requests.get(
            base,
            params={"view": "mDraftDetail"},
            cookies={"espn_s2": ESPN_S2, "SWID": SWID},
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=20,
        )
        r.raise_for_status()
        dd = r.json().get("draftDetail", {})
        print(f"  draftDetail.drafted = {dd.get('drafted')!r}   "
              f"picks present: {len(dd.get('picks', []))}")
        print("  keys:", sorted(dd.keys()))
    except Exception as e:  # noqa: BLE001
        print(f"  raw draft request failed: {e!r}")

    hr("WRITING players.json")
    out = {
        "meta": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "season": year,
            "scoring": "full_ppr",
            "source": "espn_per_position" if per_pos_used else "espn_free_agents",
            "pool_size": len(fa),
            "projection_coverage": round(coverage, 3),
        },
        "players": [],
    }
    for p in fa:
        pos = getattr(p, "position", None)
        if pos not in POS_KEEP:
            continue
        out["players"].append({
            "id": p.playerId,
            "name": p.name,
            "pos": POS_NORM.get(pos, pos),
            "pro_team": getattr(p, "proTeam", None),
            "bye": None,
            "proj_pts": round(p.projected_total_points or 0, 2),
            "espn_draft_rank": None,
            "rookie": None,
            "age": None,
        })
    # NOTE: fetch_players.py writes the real players.json (richer schema:
    # bye weeks + ESPN draft ranks). This file is only the M0 sanity check.
    with open("players_verify_sample.json", "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2)
    print(f"  wrote players_verify_sample.json  ({len(out['players'])} players)")
    print("  (run fetch_players.py for the real players.json used by the tool)")

    hr("VERDICT")
    ok_pool = len(fa) >= 300
    ok_proj = coverage >= 0.6
    print(f"  pool >= 300 ......... {'PASS' if ok_pool else 'FAIL'}  ({len(fa)})")
    print(f"  projection coverage . {'PASS' if ok_proj else 'FAIL'}  ({coverage:.0%})")
    if ok_pool and ok_proj:
        print("\n  GREEN - proceed to Milestone 1.")
        return 0
    print("\n  NOT GREEN - see PLAN.md decision gate (per-position loop / "
          "scoringPeriodId=0 / CSV fallback).")
    return 1


if __name__ == "__main__":
    sys.exit(main())
