"""MCP server exposing in-season ESPN Fantasy Football tools to Claude Code.

Read-only/advisory by design: every tool here recommends, none of them
submit lineup changes or waiver claims to ESPN. See espn_client.py for the
data layer these tools sit on top of.

Run directly:  venv/Scripts/python.exe -m fantasy_mcp.server
"""
from __future__ import annotations

from typing import Any, Optional

from mcp.server.fastmcp import FastMCP

from fantasy_mcp import espn_client, lineup, rest_of_season, trade, waivers

mcp = FastMCP(
    "fantasy-bot",
    instructions=(
        "Read-only bridge to the user's ESPN Fantasy Football league "
        "('B1 Boyzz', full PPR). Use these tools for in-season decisions: "
        "weekly lineup, waiver-wire targets, trade evaluation, and "
        "rest-of-season rankings. Never assume a tool here changes anything "
        "in ESPN -- these tools only recommend; the user acts manually."
    ),
)


@mcp.tool()
def get_rest_of_season_rankings(
    position: Optional[str] = None, top_n: int = 50
) -> dict[str, Any]:
    """Rest-of-season VBD rankings across rostered + available players.

    Args:
        position: Filter to one position (QB/RB/WR/TE/DST/K). Omit for the
            overall QB/RB/WR/TE board.
        top_n: Max players to return.
    """
    league = espn_client.get_league()
    players = rest_of_season.build_rankings(position=position, top_n=top_n, league=league)
    return {
        "meta": {"week": espn_client.get_current_week(league)},
        "players": players,
    }


@mcp.tool()
def get_my_roster() -> dict[str, Any]:
    """Your current roster, lineup slots, and this week's matchup."""
    league = espn_client.get_league()
    matchup = espn_client.get_my_matchup(league=league)
    my_team = espn_client.get_my_team(league)
    return {
        "team_name": my_team.team_name,
        "week": matchup["week"],
        "opponent_team_id": matchup["opponent_team_id"],
        "my_projected": matchup["my_projected"],
        "opp_projected": matchup["opp_projected"],
        "roster": matchup["my_lineup"],
    }


@mcp.tool()
def recommend_lineup(week: Optional[int] = None) -> dict[str, Any]:
    """Recommended starting lineup for a given week (defaults to the current
    week), using the league's actual roster slot requirements."""
    league = espn_client.get_league()
    matchup = espn_client.get_my_matchup(week=week, league=league)
    slot_counts = league.settings.position_slot_counts
    return lineup.recommend_lineup(matchup, slot_counts)


@mcp.tool()
def get_waiver_targets(
    position: Optional[str] = None,
    top_n: int = 15,
    compare_to_roster_player_id: Optional[int] = None,
) -> dict[str, Any]:
    """Ranked free-agent pickup candidates.

    Args:
        position: Filter to one position (QB/RB/WR/TE/DST/K).
        top_n: Max targets to return.
        compare_to_roster_player_id: Optional ESPN player id of a roster
            player you'd drop -- adds a net-value-vs-that-player figure.
    """
    league = espn_client.get_league()
    return waivers.get_waiver_targets(
        position=position,
        top_n=top_n,
        compare_to_roster_player_id=compare_to_roster_player_id,
        league=league,
    )


@mcp.tool()
def evaluate_trade(
    give_player_ids: list[int],
    get_player_ids: list[int],
    counterparty_team_id: Optional[int] = None,
) -> dict[str, Any]:
    """Evaluate a proposed trade by comparing rest-of-season value given vs.
    received.

    Args:
        give_player_ids: ESPN player ids you'd send away.
        get_player_ids: ESPN player ids you'd receive.
        counterparty_team_id: Optional ESPN team id of the other side, used
            to sanity-check that the players you'd receive are actually on
            their roster.
    """
    league = espn_client.get_league()
    return trade.evaluate_trade(
        give_player_ids=give_player_ids,
        get_player_ids=get_player_ids,
        counterparty_team_id=counterparty_team_id,
        league=league,
    )


def main():
    mcp.run()


if __name__ == "__main__":
    main()
