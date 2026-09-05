"""Rest-of-season rankings: reuses value_model.py's VBD/tiering math against
a live player pool (every rostered player + available free agents) instead
of the static draft-day players.json snapshot.

Does NOT rewrite value_model.py's math -- it's pure stdlib and already
position-agnostic. This module just supplies a differently-sourced player
list and a swappable points figure.
"""
import value_model as vm  # tool/value_model.py, importable via fantasy_mcp/__init__'s sys.path fix

from fantasy_mcp import espn_client


def default_value_fn(player_dict):
    """The points figure VBD is computed against. Currently a passthrough of
    ESPN's season-total projection -- the same field fetch_players.py has
    always used.

    OPEN QUESTION (see plan file): unconfirmed whether projected_total_points
    is already a rest-of-season figure or a static preseason total that
    never updates. Resolve in Week 2+ by comparing a player's value here
    before/after Week 1 games are final: if it dropped by roughly a week's
    worth of points, it's already ROS-correct and this function stays as-is.
    If it stayed flat, replace this function's body with a sum of remaining-
    week projections instead -- nothing else in this module (or its callers)
    needs to change.
    """
    return player_dict["proj_pts"]


def build_live_player_pool(free_agent_size=250, league=None):
    """Every rostered player + available free agents, as value_model-shaped
    dicts, each tagged with which team (if any) currently rosters them."""
    league = league or espn_client.get_league()

    players = []
    seen_ids = set()

    for team_id, p in espn_client.get_all_rostered_players(league):
        d = espn_client.player_to_dict(p)
        if d["id"] in seen_ids:
            continue
        seen_ids.add(d["id"])
        d["rostered_by"] = espn_client.get_team_by_id(team_id, league).team_name
        players.append(d)

    for p in espn_client.get_free_agents(size=free_agent_size, league=league):
        d = espn_client.player_to_dict(p)
        if d["id"] in seen_ids:
            continue
        seen_ids.add(d["id"])
        d["rostered_by"] = None
        players.append(d)

    for d in players:
        d["proj_pts"] = default_value_fn(d)

    return players


def build_rankings(position=None, top_n=50, league=None):
    """VBD-ranked players, optionally filtered to one position. Reuses
    value_model.py's replacement-level + tiering functions verbatim."""
    players = build_live_player_pool(league=league)
    pos_map = vm.by_position(players)

    for pos in vm.POSITIONS:
        pp = pos_map[pos]
        if not pp:
            continue
        repl_pts = vm.replacement_pts(pos, pp)
        for p in pp:
            p["raw_vbd"] = vm.raw_vbd(p["proj_pts"], repl_pts)
        pp.sort(key=lambda x: x["raw_vbd"], reverse=True)
        vm.assign_tiers(pos, pp)

    if position:
        pool = pos_map.get(espn_client.norm_pos(position.upper()), [])
    else:
        pool = [p for pos in vm.BOARD_POSITIONS for p in pos_map[pos]]
        pool.sort(key=lambda x: x.get("raw_vbd", 0), reverse=True)

    out = []
    for p in pool[:top_n]:
        out.append({
            "id": p["id"],
            "name": p["name"],
            "pos": p["pos"],
            "team": p["pro_team"],
            "tier": p.get("tier_label"),
            "vbd_value": p.get("raw_vbd"),
            "rostered_by": p["rostered_by"],
            "percent_owned": p.get("percent_owned"),
            "percent_started": p.get("percent_started"),
            "injury_status": p.get("injury_status"),
        })
    return out
