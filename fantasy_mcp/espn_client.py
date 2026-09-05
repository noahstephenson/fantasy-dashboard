"""Live ESPN data access layer for the in-season MCP tools.

Pure data access only -- no valuation math lives here (see rest_of_season.py
for VBD/tiering, lineup.py/waivers.py/trade.py for tool logic). Reuses the
exact auth pattern already proven in fetch_players.py: python-dotenv loads
tool/.env, espn_api.football.League handles the authenticated session.

No function in this module ever calls a mutating ESPN endpoint -- the whole
MCP bridge is read-only/advisory by design.
"""
import os

from dotenv import load_dotenv
from espn_api.football import League

load_dotenv()

LEAGUE_ID = os.environ["ESPN_LEAGUE_ID"]
ESPN_S2 = os.environ["ESPN_S2"]
SWID = os.environ["ESPN_SWID"]
SEASON = int(os.environ.get("SEASON", "2026"))

# Same normalization fetch_players.py applies to espn_api's "D/ST" position.
POS_NORM = {"D/ST": "DST"}

_league = None
_my_team_id = None


def norm_pos(pos):
    return POS_NORM.get(pos, pos)


def get_league(force_refresh=False):
    """Module-level League singleton -- MCP tool calls are request/response,
    so avoid re-authenticating with ESPN on every call. Pass
    force_refresh=True to re-pull live state mid-session."""
    global _league, _my_team_id
    if _league is None:
        _league = League(league_id=int(LEAGUE_ID), year=SEASON,
                          espn_s2=ESPN_S2, swid=SWID)
        _my_team_id = _resolve_my_team_id(_league)
    elif force_refresh:
        _league.refresh()
    return _league


def _resolve_my_team_id(league):
    """Match ESPN_SWID (from .env) against each team's owners to auto-detect
    the user's own team -- confirmed working against the live league, no
    extra config needed."""
    for team in league.teams:
        for owner in (getattr(team, "owners", None) or []):
            if owner.get("id") == SWID:
                return team.team_id
    raise RuntimeError(
        "Could not resolve your team: no team owner in this league matched "
        "ESPN_SWID from tool/.env"
    )


def get_my_team_id():
    get_league()
    return _my_team_id


def get_team_by_id(team_id, league=None):
    league = league or get_league()
    for team in league.teams:
        if team.team_id == team_id:
            return team
    raise RuntimeError(f"team_id {team_id} not found in league.teams")


def get_my_team(league=None):
    return get_team_by_id(get_my_team_id(), league)


def player_to_dict(p, week=None):
    """Convert an espn_api Player/BoxPlayer into the plain-dict shape
    value_model.py's VBD/tiering functions expect (id/name/pos/pro_team/
    proj_pts), plus extra live fields the MCP tools use directly."""
    return {
        "id": getattr(p, "playerId", None),
        "name": getattr(p, "name", None),
        "pos": norm_pos(getattr(p, "position", "")),
        "pro_team": getattr(p, "proTeam", None),
        "bye": None,  # draft-time players.json backfills this; live pull doesn't need it
        "proj_pts": round(getattr(p, "projected_total_points", 0) or 0, 2),
        "proj_week_pts": (
            round(getattr(p, "projected_points", 0) or 0, 2) if week is not None else None
        ),
        "lineup_slot": getattr(p, "lineupSlot", None),
        "injury_status": getattr(p, "injuryStatus", None),
        "percent_owned": getattr(p, "percent_owned", None),
        "percent_started": getattr(p, "percent_started", None),
        "total_points": getattr(p, "total_points", None),
    }


def get_current_week(league=None):
    league = league or get_league()
    return league.current_week


def get_roster_dicts(team=None):
    team = team or get_my_team()
    return [player_to_dict(p) for p in team.roster]


def _team_id_of(box_side):
    """box_scores' home_team/away_team have varied across espn_api versions
    between raw team_id ints and Team objects -- handle both."""
    return getattr(box_side, "team_id", box_side)


def get_my_matchup(week=None, league=None):
    """This week's (or a given week's) box score involving the user's team,
    with full per-player weekly projections for both lineups."""
    league = league or get_league()
    week = week or get_current_week(league)
    my_id = get_my_team_id()
    for box in league.box_scores(week=week):
        home_id = _team_id_of(box.home_team)
        away_id = _team_id_of(box.away_team)
        if my_id not in (home_id, away_id):
            continue
        is_home = home_id == my_id
        return {
            "week": week,
            "opponent_team_id": away_id if is_home else home_id,
            "my_score": box.home_score if is_home else box.away_score,
            "opp_score": box.away_score if is_home else box.home_score,
            "my_projected": box.home_projected if is_home else box.away_projected,
            "opp_projected": box.away_projected if is_home else box.home_projected,
            "my_lineup": [
                player_to_dict(p, week=week)
                for p in (box.home_lineup if is_home else box.away_lineup)
            ],
            "opp_lineup": [
                player_to_dict(p, week=week)
                for p in (box.away_lineup if is_home else box.home_lineup)
            ],
        }
    raise RuntimeError(f"No box score found for week {week} involving your team")


def get_free_agents(size=200, position=None, league=None):
    league = league or get_league()
    if position:
        return league.free_agents(size=size, position=position)
    return league.free_agents(size=size)


def get_all_rostered_players(league=None):
    """(team_id, Player) pairs for every rostered player league-wide."""
    league = league or get_league()
    return [(team.team_id, p) for team in league.teams for p in team.roster]


def get_recent_activity(size=25, league=None):
    league = league or get_league()
    out = []
    for a in league.recent_activity(size=size):
        for team, action, player, bid in a.actions:
            out.append({
                "date": getattr(a, "date", None),
                "team": getattr(team, "team_name", str(team)),
                "action": action,
                "player": getattr(player, "name", str(player)),
                "player_id": getattr(player, "playerId", None),
                "bid": bid,
            })
    return out


def get_standings(league=None):
    league = league or get_league()
    return [
        {"team_id": t.team_id, "team_name": t.team_name, "wins": t.wins,
         "losses": t.losses, "points_for": t.points_for}
        for t in league.standings()
    ]
