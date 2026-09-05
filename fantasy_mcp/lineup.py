"""Weekly lineup optimizer.

A greedy heuristic (most-constrained slots first, then flex, then bench) --
consistent with the project's existing heuristic style (build_board.py's
scoreBoard/needMultiplier recommender), not a full ILP optimizer. Good
enough for "who should I start" advice; not claimed to be provably optimal
in every edge case (e.g. it doesn't model bye-week bench depth beyond the
single week being recommended).
"""

FLEX_ELIGIBLE = {"RB", "WR", "TE"}


def _slot_kind(slot_name):
    """Map an ESPN lineup-slot key to the set of positions eligible for it,
    or None if it isn't a starting slot at all (bench/IR).

    Careful: "D/ST" is a single fixed position (defense/special teams), not
    a flex slot -- despite containing a "/" like a real flex slot
    ("RB/WR/TE") does. Check it explicitly before the generic flex check.
    """
    if slot_name in ("BE", "IR"):
        return None
    if slot_name == "D/ST":
        return {"DST"}
    if "/" in slot_name:
        return FLEX_ELIGIBLE
    return {slot_name}


def recommend_lineup(matchup, slot_counts):
    """matchup: espn_client.get_my_matchup()'s return dict.
    slot_counts: league.settings.position_slot_counts (includes BE/IR, which
    are skipped here since they're not starting slots)."""
    players = matchup["my_lineup"]
    pool = {p["id"]: p for p in players if p["id"] is not None}

    required = []  # (slot_label, eligible_positions)
    for slot, count in slot_counts.items():
        eligible = _slot_kind(slot)
        if eligible is None:
            continue
        for _ in range(count):
            required.append((slot, eligible))

    # Fill single-position slots (most constrained) before flex slots.
    required.sort(key=lambda r: len(r[1]))

    used = set()
    starters = []
    for slot_label, eligible in required:
        candidates = [p for p in pool.values()
                      if p["id"] not in used and p["pos"] in eligible]
        if not candidates:
            starters.append({"slot": slot_label, "player": None})
            continue
        best = max(candidates, key=lambda p: p.get("proj_week_pts") or 0)
        used.add(best["id"])
        starters.append({"slot": slot_label, "player": best})

    bench = [p for p in pool.values() if p["id"] not in used]
    bench.sort(key=lambda p: p.get("proj_week_pts") or 0, reverse=True)

    current_slot_by_id = {p["id"]: p.get("lineup_slot") for p in players}
    reasoning = []
    for s in starters:
        p = s["player"]
        if not p:
            reasoning.append(f"No eligible healthy roster player found for {s['slot']}.")
            continue
        currently_benched = current_slot_by_id.get(p["id"]) in ("BE", "IR", None)
        if currently_benched:
            reasoning.append(
                f"Start {p['name']} ({p['pos']}) in {s['slot']} -- "
                f"{p.get('proj_week_pts') or 0:.1f} proj pts, currently on bench."
            )

    projected_total = round(
        sum((s["player"].get("proj_week_pts") or 0) for s in starters if s["player"]), 2
    )

    return {
        "week": matchup["week"],
        "recommended_starters": starters,
        "bench": bench,
        "reasoning": reasoning,
        "projected_total": projected_total,
    }
