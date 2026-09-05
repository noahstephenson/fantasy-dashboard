"""Milestone 0 output - build players.json per SPEC.md.

Projections: espn-api's League.free_agents() - its stat parsing is the proven
path (verify_data.py run 1 produced a consensus-sane board from it).
Bye week + ESPN STANDARD draft rank: raw kona_player_info call, joined by id.

projected_total_points is ESPN's precomputed full-PPR season projection.

Run:  venv/Scripts/python.exe fetch_players.py
"""
import json
import os
from collections import Counter
from datetime import datetime, timezone

import requests
from dotenv import load_dotenv
from espn_api.football import League

load_dotenv()

LEAGUE_ID = os.environ["ESPN_LEAGUE_ID"]
ESPN_S2 = os.environ["ESPN_S2"]
SWID = os.environ["ESPN_SWID"]
SEASON = int(os.environ.get("SEASON", "2026"))
POOL_SIZE = 400

COOKIES = {"espn_s2": ESPN_S2, "SWID": SWID}
UA = {"User-Agent": "Mozilla/5.0"}
POS_NORM = {"D/ST": "DST"}
PRO_TEAM = {
    0: "FA", 1: "ATL", 2: "BUF", 3: "CHI", 4: "CIN", 5: "CLE", 6: "DAL",
    7: "DEN", 8: "DET", 9: "GB", 10: "TEN", 11: "IND", 12: "KC", 13: "LV",
    14: "LAR", 15: "MIA", 16: "MIN", 17: "NE", 18: "NO", 19: "NYG", 20: "NYJ",
    21: "PHI", 22: "ARI", 23: "PIT", 24: "LAC", 25: "SF", 26: "SEA", 27: "TB",
    28: "WSH", 29: "CAR", 30: "JAX", 33: "BAL", 34: "HOU",
}


def raw_meta_by_id():
    """id -> {bye, rank, pro_team, rookie} from the raw player endpoint."""
    base = ("https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl"
            f"/seasons/{SEASON}/segments/0/leagues/{LEAGUE_ID}")
    season_ep = ("https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl"
                 f"/seasons/{SEASON}")

    byes = {}
    sr = requests.get(season_ep, params={"view": "proTeamSchedules_wl"},
                      cookies=COOKIES, headers=UA, timeout=20)
    if sr.ok:
        for t in sr.json().get("settings", {}).get("proTeams", []):
            if t.get("byeWeek"):
                byes[t["id"]] = t["byeWeek"]

    filt = {"players": {
        "filterStatus": {"value": ["FREEAGENT", "WAIVERS", "ONTEAM"]},
        "limit": 700,
        "sortDraftRanks": {"sortPriority": 1, "sortAsc": True,
                           "value": "STANDARD"}}}
    r = requests.get(base, params={"view": "kona_player_info"},
                     cookies=COOKIES,
                     headers={**UA, "x-fantasy-filter": json.dumps(filt)},
                     timeout=30)
    r.raise_for_status()
    out = {}
    for entry in r.json()["players"]:
        p = entry.get("player", entry)
        pid = p.get("id")
        pro_id = p.get("proTeamId", 0)
        ranks = p.get("draftRanksByRankType", {}).get("STANDARD", {})
        rookie = None
        if p.get("rookieSeasonId"):
            rookie = p.get("rookieSeasonId") == SEASON
        out[pid] = {
            "bye": byes.get(pro_id),
            "espn_draft_rank": ranks.get("rank"),
            "pro_team": PRO_TEAM.get(pro_id, str(pro_id)),
            "rookie": rookie,
        }
    return out


def main():
    league = League(league_id=int(LEAGUE_ID), year=SEASON,
                    espn_s2=ESPN_S2, swid=SWID)
    fa = league.free_agents(size=POOL_SIZE)
    print(f"free_agents pool: {len(fa)}")

    meta = raw_meta_by_id()
    print(f"raw meta rows:    {len(meta)}")

    players = []
    for p in fa:
        pos = POS_NORM.get(getattr(p, "position", ""), getattr(p, "position", ""))
        if pos not in {"QB", "RB", "WR", "TE", "K", "DST"}:
            continue
        m = meta.get(p.playerId, {})
        players.append({
            "id": p.playerId,
            "name": p.name,
            "pos": pos,
            "pro_team": m.get("pro_team") or getattr(p, "proTeam", None),
            "bye": m.get("bye"),
            "proj_pts": round(p.projected_total_points or 0, 2),
            "espn_draft_rank": m.get("espn_draft_rank"),
            "rookie": m.get("rookie"),
            "age": None,
        })

    players.sort(key=lambda x: -(x["proj_pts"] or 0))
    cov = sum(1 for x in players if (x["proj_pts"] or 0) > 0) / max(len(players), 1)
    with_bye = sum(1 for x in players if x["bye"])
    with_rank = sum(1 for x in players if x["espn_draft_rank"])

    out = {
        "meta": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "season": SEASON,
            "scoring": "full_ppr",
            "source": "espn_free_agents+kona_meta",
            "pool_size": len(players),
            "projection_coverage": round(cov, 3),
        },
        "players": players,
    }
    with open("players.json", "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2)

    print(f"\nwrote players.json: {len(players)} players")
    print(f"  projection coverage: {cov:.0%}")
    print(f"  with bye week:       {with_bye}/{len(players)}")
    print(f"  with ESPN rank:      {with_rank}/{len(players)}")
    print(f"  positions:           {dict(Counter(x['pos'] for x in players))}")
    print("\n  top 15 by projection:")
    for i, x in enumerate(players[:15], 1):
        print(f"   {i:>2}. {x['name']:<24} {x['pos']:<4} {x['pro_team'] or '-':<4} "
              f"bye {str(x['bye'] or '-'):<3} proj {x['proj_pts']:>7.1f} "
              f"rank {x['espn_draft_rank']}")


if __name__ == "__main__":
    main()
