"""Manual smoke test for the fantasy_mcp package -- calls the underlying
Python functions directly (no MCP transport involved), same lightweight,
framework-free style as verify_data.py.

Run from tool/:
    venv/Scripts/python.exe verify_mcp.py
"""
import sys

from fantasy_mcp import espn_client, lineup, rest_of_season, trade, waivers

PASS = "PASS"
FAIL = "FAIL"
_failures = []


def check(label, condition, detail=""):
    status = PASS if condition else FAIL
    print(f"  [{status}] {label}" + (f"  ({detail})" if detail else ""))
    if not condition:
        _failures.append(label)


def main():
    print("=" * 70)
    print("fantasy_mcp smoke test")
    print("=" * 70)

    league = espn_client.get_league()
    print(f"\nLeague: {league.settings.name if hasattr(league, 'settings') else league}")

    # -- my team resolution --------------------------------------------
    my_team = espn_client.get_my_team(league)
    print(f"\nMy team: {my_team.team_name} (team_id={my_team.team_id})")
    check("my team resolves", my_team is not None)
    check("roster has players", len(my_team.roster) > 0, f"{len(my_team.roster)} players")

    # -- roster dicts -----------------------------------------------------
    roster = espn_client.get_roster_dicts(my_team)
    print(f"\nRoster ({len(roster)} players):")
    for p in roster[:5]:
        print(f"    {p['name']:<24} {p['pos']:<4} slot={p['lineup_slot']}")
    check("roster dicts non-empty", len(roster) > 0)

    # -- current week / matchup -------------------------------------------
    week = espn_client.get_current_week(league)
    print(f"\nCurrent week: {week}")
    matchup = espn_client.get_my_matchup(league=league)
    check("matchup found", matchup is not None)
    check("matchup lineup non-empty", len(matchup["my_lineup"]) > 0,
          f"{len(matchup['my_lineup'])} players")

    # -- lineup recommendation --------------------------------------------
    slot_counts = league.settings.position_slot_counts
    rec = lineup.recommend_lineup(matchup, slot_counts)
    starting_slots = sum(v for k, v in slot_counts.items() if k not in ("BE", "IR"))
    check(
        "lineup covers all starting slots",
        len(rec["recommended_starters"]) == starting_slots,
        f"{len(rec['recommended_starters'])}/{starting_slots}",
    )
    print(f"\nRecommended lineup (week {rec['week']}, "
          f"projected {rec['projected_total']} pts):")
    for s in rec["recommended_starters"]:
        name = s["player"]["name"] if s["player"] else "-- NONE ELIGIBLE --"
        print(f"    {s['slot']:<10} {name}")
    if rec["reasoning"]:
        print("  Reasoning:")
        for r in rec["reasoning"]:
            print(f"    - {r}")

    # -- rest-of-season rankings -------------------------------------------
    rankings = rest_of_season.build_rankings(top_n=15, league=league)
    check("rankings non-empty", len(rankings) > 0)
    vbds = [p["vbd_value"] for p in rankings if p["vbd_value"] is not None]
    check("rankings sorted by vbd desc", vbds == sorted(vbds, reverse=True))
    print(f"\nTop {len(rankings)} rest-of-season rankings:")
    for i, p in enumerate(rankings, 1):
        owner = p["rostered_by"] or "FA"
        print(f"    {i:>2}. {p['name']:<24} {p['pos']:<4} vbd={p['vbd_value']:>7.2f} "
              f"tier={p['tier']:<5} owner={owner}")

    # -- waiver targets ----------------------------------------------------
    wt = waivers.get_waiver_targets(top_n=10, league=league)
    check("waiver targets returned", len(wt["targets"]) > 0)
    print(f"\nTop waiver targets ({len(wt['targets'])}):")
    for t in wt["targets"][:5]:
        print(f"    {t['name']:<24} {t['pos']:<4} value={t['proj_value']:>7.2f}")

    # -- trade evaluation (self-test: trade a player for themselves) -------
    if roster:
        pid = roster[0]["id"]
        result = trade.evaluate_trade([pid], [pid], league=league)
        check("trade eval: same player nets ~0", abs(result["net_value"]) < 0.01,
              f"net_value={result['net_value']}")

    print("\n" + "=" * 70)
    if _failures:
        print(f"RESULT: FAIL ({len(_failures)} check(s) failed)")
        for f in _failures:
            print(f"  - {f}")
        sys.exit(1)
    print("RESULT: PASS (all checks passed)")


if __name__ == "__main__":
    main()
