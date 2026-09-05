"""Milestone 1: value model -> tiers.txt + tiers.html

Pure standard library (json, math, datetime, html). No pip installs.

Run from tool/:
    venv/Scripts/python.exe value_model.py

Reads:  players.json  (Milestone 0 output)
Writes: tiers.txt, tiers.html
"""

import json
import math
import datetime
import html
import os

# --------------------------------------------------------------------------
# Retunable constants (exactly per SPEC.md)
# --------------------------------------------------------------------------
import sys as _sys  # noqa: E402
# Override league size from the command line: `python value_model.py 12`
TEAMS = int(_sys.argv[1]) if len(_sys.argv) > 1 and _sys.argv[1].isdigit() else 10
STARTERS = {"QB": 1, "RB": 2, "WR": 2, "TE": 1, "DST": 1, "K": 1}  # plus 1 FLEX
FLEX_SPLIT = {"RB": 0.40, "WR": 0.50, "TE": 0.10}
REPLACEMENT_BUFFER = {"QB": 2, "RB": 0, "WR": 0, "TE": 0, "DST": 1, "K": 1}
POS_MAX = {"QB": 4, "RB": 8, "WR": 8, "TE": 3, "DST": 3, "K": 3}

# Tiering is relative: within a position's "startable range" (roughly how many
# get drafted as startable assets), a new tier begins when the VBD drop to the
# next player exceeds TIER_FACTOR x the average consecutive gap in that range.
# Retunable. Higher factor => fewer, coarser tiers.
TIER_FACTOR = 2.2
TIER_MIN_GAP = 5.0          # absolute floor so bottom-of-pool noise isn't a tier
TIER_MAX = 9                # merge anything beyond this into the last tier
TIER_RANGE = {"QB": 18, "RB": 30, "WR": 40, "TE": 16, "DST": 14, "K": 14}

POSITIONS = ["QB", "RB", "WR", "TE", "DST", "K"]
# K and D/ST are ranked but kept OFF the overall board - with only ~11 of each
# drafted, their top options show inflated VBD next to real skill players.
# The draft tool surfaces them from round 12+.
BOARD_POSITIONS = ["QB", "RB", "WR", "TE"]
LATE_POSITIONS = ["DST", "K"]

HERE = os.path.dirname(os.path.abspath(__file__))
PLAYERS_PATH = os.path.join(HERE, "players.json")
TXT_PATH = os.path.join(HERE, "tiers.txt")
HTML_PATH = os.path.join(HERE, "tiers.html")


# --------------------------------------------------------------------------
# Core logic
# --------------------------------------------------------------------------
def replacement_rank(pos):
    """1-indexed rank within a position whose proj_pts becomes 'replacement'."""
    return (
        STARTERS[pos] * TEAMS
        + round(FLEX_SPLIT.get(pos, 0) * TEAMS)
        + REPLACEMENT_BUFFER[pos]
    )


def _assert_replacement_ranks():
    expected = {"QB": 12, "RB": 24, "WR": 25, "TE": 11, "DST": 11, "K": 11}
    for pos, want in expected.items():
        got = replacement_rank(pos)
        assert got == want, f"replacement_rank({pos}) = {got}, expected {want}"


def by_position(players):
    """dict pos -> players list sorted by proj_pts desc."""
    out = {pos: [] for pos in POSITIONS}
    for p in players:
        if p["pos"] in out:
            out[p["pos"]].append(p)
    for pos in out:
        out[pos].sort(key=lambda x: x["proj_pts"], reverse=True)
    return out


def replacement_pts(pos, pos_players):
    """proj_pts of the player at the replacement rank (clamp to last player)."""
    rank = replacement_rank(pos)
    idx = min(rank - 1, len(pos_players) - 1)
    return pos_players[idx]["proj_pts"]


def raw_vbd(proj_pts, repl_pts):
    return round(proj_pts - repl_pts, 2)


def tier_threshold(pos, pos_players):
    """Relative gap that starts a new tier: TIER_FACTOR x average consecutive
    gap across this position's startable range."""
    rng = pos_players[: TIER_RANGE.get(pos, 20)]
    if len(rng) < 3:
        return TIER_MIN_GAP
    spread = rng[0]["raw_vbd"] - rng[-1]["raw_vbd"]
    avg_gap = spread / (len(rng) - 1)
    return max(TIER_MIN_GAP, TIER_FACTOR * avg_gap)


def assign_tiers(pos, pos_players):
    """Walk down by raw_vbd desc; new tier when the drop exceeds a relative
    threshold. Tiers past TIER_MAX are merged into the last one.

    Mutates each player dict (needs 'raw_vbd' set); adds 'tier' and 'tier_label'.
    """
    thr = tier_threshold(pos, pos_players)
    tier = 1
    prev_vbd = None
    for p in pos_players:
        if prev_vbd is not None and (prev_vbd - p["raw_vbd"]) > thr:
            tier = min(tier + 1, TIER_MAX)
        p["tier"] = tier
        p["tier_label"] = f"{pos}{tier}"
        prev_vbd = p["raw_vbd"]
    return tier  # highest tier number = tier count


def build_model():
    with open(PLAYERS_PATH, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    players = data["players"]

    _assert_replacement_ranks()

    pos_map = by_position(players)
    repl_pts = {}
    tier_counts = {}
    for pos in POSITIONS:
        pp = pos_map[pos]
        rp = replacement_pts(pos, pp)
        repl_pts[pos] = rp
        for p in pp:
            p["raw_vbd"] = raw_vbd(p["proj_pts"], rp)
        # already sorted by proj_pts desc; that is also raw_vbd desc (monotonic)
        pp.sort(key=lambda x: x["raw_vbd"], reverse=True)
        tier_counts[pos] = assign_tiers(pos, pp)

    overall = [p for pos in BOARD_POSITIONS for p in pos_map[pos]]
    overall.sort(key=lambda x: x["raw_vbd"], reverse=True)
    late = [p for pos in LATE_POSITIONS for p in pos_map[pos]]
    late.sort(key=lambda x: x["raw_vbd"], reverse=True)

    return {
        "meta": data.get("meta", {}),
        "players": players,
        "pos_map": pos_map,
        "repl_pts": repl_pts,
        "tier_counts": tier_counts,
        "overall": overall,
        "late": late,
    }


# --------------------------------------------------------------------------
# Formatting helpers
# --------------------------------------------------------------------------
def bye_str(bye):
    return "-" if bye is None else str(bye)


def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat()


def clip(s, width):
    s = str(s)
    return s if len(s) <= width else s[: width - 1] + "…"


# --------------------------------------------------------------------------
# tiers.txt
# --------------------------------------------------------------------------
def write_txt(model):
    ts = now_iso()
    lines = []
    lines.append("=" * 78)
    lines.append("B1 BOYZZ DRAFT BOARD  --  VBD / TIERS  (Milestone 1 fallback sheet)")
    lines.append("Full PPR  |  10 teams  |  2026 season")
    lines.append("=" * 78)
    lines.append("")
    lines.append("REPLACEMENT LEVELS (derived from this player pool):")
    for pos in POSITIONS:
        rank = replacement_rank(pos)
        lines.append(
            f"  {pos:<3}  replacement={pos}{rank:<3}  repl_pts={model['repl_pts'][pos]:6.1f}"
        )
    lines.append("")
    lines.append("FLEX split assumption: 40% RB / 50% WR / 10% TE")
    lines.append("Null bye weeks shown as '-'.  proj = full-PPR season projection.")
    lines.append(f"Generated: {ts}")
    lines.append("")

    # ---- overall board ----
    lines.append("-" * 78)
    lines.append("OVERALL BOARD (by VBD)   -- QB/RB/WR/TE only, top 200")
    lines.append("(K and D/ST are ranked separately below -- do not draft before round 12)")
    lines.append("-" * 78)
    hdr = f"{'#':>3}  {'name':<22} {'pos':<3} {'tm':<3} {'bye':>3} {'proj':>6} {'vbd':>7} {'tier':<5}"
    lines.append(hdr)
    lines.append("-" * len(hdr))
    for i, p in enumerate(model["overall"][:200], start=1):
        lines.append(
            f"{i:>3}  {clip(p['name'], 22):<22} {p['pos']:<3} {p['pro_team']:<3} "
            f"{bye_str(p['bye']):>3} {p['proj_pts']:>6.1f} {p['raw_vbd']:>7.2f} {p['tier_label']:<5}"
        )
    lines.append("")

    # ---- kickers & defenses (late) ----
    lines.append("-" * 78)
    lines.append("KICKERS & DEFENSES  --  draft round 12+ only")
    lines.append("-" * 78)
    lhdr = f"{'#':>3}  {'name':<22} {'pos':<3} {'tm':<3} {'bye':>3} {'proj':>6} {'vbd':>7} {'tier':<5}"
    lines.append(lhdr)
    lines.append("-" * len(lhdr))
    for i, p in enumerate(model["late"][:20], start=1):
        lines.append(
            f"{i:>3}  {clip(p['name'], 22):<22} {p['pos']:<3} {p['pro_team']:<3} "
            f"{bye_str(p['bye']):>3} {p['proj_pts']:>6.1f} {p['raw_vbd']:>7.2f} {p['tier_label']:<5}"
        )
    lines.append("")

    # ---- by position ----
    lines.append("-" * 78)
    lines.append("BY POSITION")
    lines.append("-" * 78)
    for pos in POSITIONS:
        pp = model["pos_map"][pos]
        rank = replacement_rank(pos)
        lines.append("")
        lines.append(
            f"### {pos}  (replacement {pos}{rank} = {model['repl_pts'][pos]:.1f} pts, "
            f"{model['tier_counts'][pos]} tiers)"
        )
        phdr = f"{'#':>3}  {'name':<22} {'tm':<3} {'bye':>3} {'proj':>6} {'vbd':>7}"
        lines.append(phdr)
        lines.append("-" * len(phdr))
        cur_tier = None
        for j, p in enumerate(pp, start=1):
            if p["tier"] != cur_tier:
                cur_tier = p["tier"]
                lines.append(f"---- TIER {cur_tier} ----")
            lines.append(
                f"{j:>3}  {clip(p['name'], 22):<22} {p['pro_team']:<3} "
                f"{bye_str(p['bye']):>3} {p['proj_pts']:>6.1f} {p['raw_vbd']:>7.2f}"
            )

    with open(TXT_PATH, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")


# --------------------------------------------------------------------------
# tiers.html
# --------------------------------------------------------------------------
def _row(cells, tag="td"):
    return "<tr>" + "".join(f"<{tag}>{c}</{tag}>" for c in cells) + "</tr>"


def write_html(model):
    ts = now_iso()
    e = html.escape

    css = """
:root { color-scheme: light dark; }
body { font-family: -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif;
       margin: 1.2rem; background: #ffffff; color: #111111; line-height: 1.35; }
h1 { font-size: 1.3rem; margin: 0 0 .3rem; }
h2 { font-size: 1.05rem; margin: 1.6rem 0 .4rem; border-bottom: 2px solid #888; padding-bottom: .2rem; }
.meta { background: #f2f2f2; border: 1px solid #ccc; padding: .7rem .9rem; border-radius: 6px;
        font-size: .85rem; max-width: 640px; }
.meta code { background: #e4e4e4; padding: 0 .25rem; border-radius: 3px; }
table { border-collapse: collapse; margin: .4rem 0 1rem; font-size: .82rem; }
th, td { border: 1px solid #ccc; padding: .18rem .5rem; text-align: left; white-space: nowrap; }
th { background: #e8e8e8; position: sticky; top: 0; cursor: pointer; }
td.num, th.num { text-align: right; }
tr.tierbreak td { background: #d8d8d8; font-weight: bold; letter-spacing: .04em; }
.pos-QB { color: #7b241c; } .pos-RB { color: #1e5631; }
.pos-WR { color: #1a3c6e; } .pos-TE { color: #6b4c00; }
.pos-DST { color: #4a235a; } .pos-K { color: #555; }
details { margin: .3rem 0; }
summary { cursor: pointer; font-weight: bold; padding: .2rem 0; }
""".strip()

    sort_js = """
document.querySelectorAll('table.sortable').forEach(function(t){
  t.querySelectorAll('th').forEach(function(th, idx){
    th.addEventListener('click', function(){
      var tb = t.tBodies[0];
      var rows = Array.prototype.slice.call(tb.querySelectorAll('tr:not(.tierbreak)'));
      var asc = th.dataset.asc !== 'true';
      th.dataset.asc = asc;
      rows.sort(function(a, b){
        var x = a.cells[idx].textContent.trim();
        var y = b.cells[idx].textContent.trim();
        var nx = parseFloat(x), ny = parseFloat(y);
        if (!isNaN(nx) && !isNaN(ny)) return asc ? nx - ny : ny - nx;
        return asc ? x.localeCompare(y) : y.localeCompare(x);
      });
      rows.forEach(function(r){ tb.appendChild(r); });
    });
  });
});
""".strip()

    out = []
    out.append("<!doctype html><html><head><meta charset='utf-8'>")
    out.append("<meta name='viewport' content='width=device-width, initial-scale=1'>")
    out.append("<title>B1 Boyzz VBD / Tiers</title>")
    out.append(f"<style>{css}</style></head><body>")
    out.append("<h1>B1 Boyzz Draft Board &mdash; VBD / Tiers</h1>")
    out.append("<p>Full PPR &nbsp;|&nbsp; 10 teams &nbsp;|&nbsp; 2026 season &nbsp;|&nbsp; Milestone 1 fallback sheet</p>")

    # meta block
    out.append("<div class='meta'><strong>Replacement levels</strong> (derived from this pool):<br>")
    for pos in POSITIONS:
        rank = replacement_rank(pos)
        out.append(
            f"&nbsp;&nbsp;<code>{pos}</code> replacement={pos}{rank} "
            f"repl_pts={model['repl_pts'][pos]:.1f}<br>"
        )
    out.append("<br>FLEX split assumption: <strong>40% RB / 50% WR / 10% TE</strong><br>")
    out.append("Null bye weeks shown as &lsquo;&ndash;&rsquo;. proj = full-PPR season projection.<br>")
    out.append(f"Generated (UTC): <code>{e(ts)}</code></div>")

    # ---- overall ----
    out.append("<h2>Overall board (by VBD) &mdash; QB/RB/WR/TE, top 200</h2>")
    out.append("<p style='font-size:.8rem;color:#666'>K and D/ST ranked separately "
               "below &mdash; do not draft before round 12.</p>")
    out.append("<table class='sortable'><thead>")
    out.append(
        "<tr><th class='num'>#</th><th>Name</th><th>Pos</th><th>Team</th>"
        "<th class='num'>Bye</th><th class='num'>Proj</th><th class='num'>VBD</th><th>Tier</th></tr>"
    )
    out.append("</thead><tbody>")
    for i, p in enumerate(model["overall"][:200], start=1):
        out.append(
            "<tr>"
            f"<td class='num'>{i}</td>"
            f"<td>{e(p['name'])}</td>"
            f"<td class='pos-{p['pos']}'>{p['pos']}</td>"
            f"<td>{e(p['pro_team'])}</td>"
            f"<td class='num'>{e(bye_str(p['bye']))}</td>"
            f"<td class='num'>{p['proj_pts']:.1f}</td>"
            f"<td class='num'>{p['raw_vbd']:.2f}</td>"
            f"<td>{p['tier_label']}</td>"
            "</tr>"
        )
    out.append("</tbody></table>")

    # ---- kickers & defenses ----
    out.append("<h2>Kickers &amp; Defenses &mdash; draft round 12+ only</h2>")
    out.append("<table><thead><tr><th class='num'>#</th><th>Name</th><th>Pos</th>"
               "<th>Team</th><th class='num'>Bye</th><th class='num'>Proj</th>"
               "<th class='num'>VBD</th><th>Tier</th></tr></thead><tbody>")
    for i, p in enumerate(model["late"][:20], start=1):
        out.append(
            "<tr>"
            f"<td class='num'>{i}</td>"
            f"<td>{e(p['name'])}</td>"
            f"<td class='pos-{p['pos']}'>{p['pos']}</td>"
            f"<td>{e(p['pro_team'])}</td>"
            f"<td class='num'>{e(bye_str(p['bye']))}</td>"
            f"<td class='num'>{p['proj_pts']:.1f}</td>"
            f"<td class='num'>{p['raw_vbd']:.2f}</td>"
            f"<td>{p['tier_label']}</td>"
            "</tr>"
        )
    out.append("</tbody></table>")

    # ---- by position ----
    out.append("<h2>By position</h2>")
    for pos in POSITIONS:
        pp = model["pos_map"][pos]
        rank = replacement_rank(pos)
        out.append("<details open><summary>"
                   f"{pos} &mdash; replacement {pos}{rank} = {model['repl_pts'][pos]:.1f} pts, "
                   f"{model['tier_counts'][pos]} tiers</summary>")
        out.append("<table><thead>"
                   "<tr><th class='num'>#</th><th>Name</th><th>Team</th>"
                   "<th class='num'>Bye</th><th class='num'>Proj</th><th class='num'>VBD</th></tr>"
                   "</thead><tbody>")
        cur_tier = None
        for j, p in enumerate(pp, start=1):
            if p["tier"] != cur_tier:
                cur_tier = p["tier"]
                out.append(f"<tr class='tierbreak'><td colspan='6'>TIER {cur_tier}</td></tr>")
            out.append(
                "<tr>"
                f"<td class='num'>{j}</td>"
                f"<td>{e(p['name'])}</td>"
                f"<td>{e(p['pro_team'])}</td>"
                f"<td class='num'>{e(bye_str(p['bye']))}</td>"
                f"<td class='num'>{p['proj_pts']:.1f}</td>"
                f"<td class='num'>{p['raw_vbd']:.2f}</td>"
                "</tr>"
            )
        out.append("</tbody></table></details>")

    out.append(f"<script>{sort_js}</script>")
    out.append("</body></html>")

    with open(HTML_PATH, "w", encoding="utf-8") as fh:
        fh.write("".join(out))


# --------------------------------------------------------------------------
# stdout summary
# --------------------------------------------------------------------------
def print_summary(model):
    print("=" * 64)
    print("VALUE MODEL SUMMARY")
    print("=" * 64)
    print("Replacement level per position:")
    for pos in POSITIONS:
        rank = replacement_rank(pos)
        print(
            f"  {pos:<3}  rank={pos}{rank:<4}  repl_pts={model['repl_pts'][pos]:7.2f}  "
            f"(pool has {len(model['pos_map'][pos])} at {pos})"
        )
    print()
    print("Tier counts per position:")
    for pos in POSITIONS:
        print(f"  {pos:<3}  {model['tier_counts'][pos]} tiers")
    print()
    print("Top 15 overall by VBD:")
    print(f"  {'#':>2}  {'name':<24} {'pos':<4} {'proj':>7} {'vbd':>8}  tier")
    for i, p in enumerate(model["overall"][:15], start=1):
        print(
            f"  {i:>2}  {clip(p['name'], 24):<24} {p['pos']:<4} "
            f"{p['proj_pts']:>7.1f} {p['raw_vbd']:>8.2f}  {p['tier_label']}"
        )
    print()
    print(f"Wrote: {TXT_PATH}")
    print(f"Wrote: {HTML_PATH}")


def main():
    model = build_model()
    write_txt(model)
    write_html(model)
    print_summary(model)


if __name__ == "__main__":
    main()
