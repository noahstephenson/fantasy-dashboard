"""Trade evaluation: compares aggregate rest-of-season value given vs.
received, using the same VBD figure as the rankings/waiver tools.
"""
from collections import defaultdict

from fantasy_mcp import espn_client, rest_of_season


def evaluate_trade(give_player_ids, get_player_ids, counterparty_team_id=None, league=None):
    league = league or espn_client.get_league()
    pool = {p["id"]: p for p in rest_of_season.build_live_player_pool(league=league)}

    def summarize(ids):
        total = 0.0
        per_pos = defaultdict(float)
        missing = []
        for pid in ids:
            p = pool.get(pid)
            if p is None:
                missing.append(pid)
                continue
            total += p["proj_pts"]
            per_pos[p["pos"]] += p["proj_pts"]
        return total, dict(per_pos), missing

    value_given, given_by_pos, missing_give = summarize(give_player_ids)
    value_received, received_by_pos, missing_get = summarize(get_player_ids)
    net_value = round(value_received - value_given, 2)

    per_position_impact = {
        pos: round(received_by_pos.get(pos, 0) - given_by_pos.get(pos, 0), 2)
        for pos in set(given_by_pos) | set(received_by_pos)
    }

    caveats = [
        "Compares season-total ESPN projections, not adjusted for playoff "
        "schedule, injury risk, or how well a player fits your specific "
        "roster needs beyond raw projected points.",
    ]
    if missing_give or missing_get:
        caveats.append(
            f"Could not find player(s) in the live pool -- "
            f"give={missing_give} get={missing_get}"
        )
    if counterparty_team_id is not None:
        roster_ids = {p.playerId for p in espn_client.get_team_by_id(counterparty_team_id, league).roster}
        not_on_roster = [pid for pid in get_player_ids if pid not in roster_ids]
        if not_on_roster:
            caveats.append(
                f"Player(s) {not_on_roster} are not currently on team "
                f"{counterparty_team_id}'s roster -- double-check the trade details."
            )

    if net_value > 5:
        verdict = "Favorable for you"
    elif net_value < -5:
        verdict = "Unfavorable for you"
    else:
        verdict = "Roughly even"

    return {
        "value_given": round(value_given, 2),
        "value_received": round(value_received, 2),
        "net_value": net_value,
        "per_position_impact": per_position_impact,
        "verdict": verdict,
        "caveats": caveats,
    }
