"""Waiver-wire target scoring: ranks currently-available free agents by
rest-of-season VBD value, with optional context vs. a roster player you'd
drop to make room.
"""
from fantasy_mcp import espn_client, rest_of_season


def get_waiver_targets(position=None, top_n=15, compare_to_roster_player_id=None, league=None):
    league = league or espn_client.get_league()

    rankings = rest_of_season.build_rankings(position=position, top_n=1000, league=league)
    available = [p for p in rankings if p["rostered_by"] is None][:top_n]

    recent_note_by_id = {}
    for a in espn_client.get_recent_activity(size=25, league=league):
        pid = a.get("player_id")
        if pid and pid not in recent_note_by_id:
            recent_note_by_id[pid] = f"{a['action']} by {a['team']}"

    # Compare in the same units (VBD, not raw proj_pts) -- look up the drop
    # candidate's own VBD via its position's rankings rather than mixing scales.
    drop_candidate_vbd = None
    if compare_to_roster_player_id is not None:
        roster = espn_client.get_roster_dicts()
        candidate = next(
            (p for p in roster if p["id"] == compare_to_roster_player_id), None
        )
        if candidate:
            pos_rankings = rest_of_season.build_rankings(
                position=candidate["pos"], top_n=1000, league=league
            )
            match = next(
                (p for p in pos_rankings if p["id"] == compare_to_roster_player_id), None
            )
            if match:
                drop_candidate_vbd = match["vbd_value"]

    targets = []
    for p in available:
        entry = {
            "id": p["id"],
            "name": p["name"],
            "pos": p["pos"],
            "proj_value": p["vbd_value"],
            "percent_owned": p.get("percent_owned"),
            "percent_started": p.get("percent_started"),
            "recent_activity_note": recent_note_by_id.get(p["id"]),
        }
        if drop_candidate_vbd is not None:
            entry["net_value_vs_drop_candidate"] = round(
                (p.get("vbd_value") or 0) - drop_candidate_vbd, 2
            )
        targets.append(entry)

    return {"targets": targets}
