"""Milestone 4 (STRETCH, untested against a live draft) - ESPN live pick poller.

Polls the raw mDraftDetail endpoint every few seconds and writes tool/live_picks.json:
  {"updated": "<iso>", "drafted": <bool>, "in_progress": <bool>,
   "picks": [{"overall": int, "round": int, "round_pick": int,
              "team_id": int, "player_id": int, "player_name": str}]}
Only picks with player_id > 0 are included (the endpoint pre-populates 160
placeholder slots with player_id -1 before/at the start of the draft).

The draft board does NOT depend on this. It is a convenience: if it proves it
surfaces picks within ~10s during a live ESPN mock, the board can read
live_picks.json to pre-fill the drafted list. Manual click-off always wins.

Usage:
  venv/Scripts/python.exe poll.py               # poll this league
  venv/Scripts/python.exe poll.py --league 111  # poll a different id (e.g. a mock)
  venv/Scripts/python.exe poll.py --once        # single fetch, print, exit (test)
"""
import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone

import requests
from dotenv import load_dotenv

load_dotenv()

S2 = os.environ["ESPN_S2"]
SWID = os.environ["ESPN_SWID"]
SEASON = os.environ.get("SEASON", "2026")
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "live_picks.json")
INTERVAL = 5  # seconds

# playerId -> name, built once from the same pool the board uses
def load_names():
    try:
        with open(os.path.join(HERE, "players.json"), encoding="utf-8") as fh:
            return {p["id"]: p["name"] for p in json.load(fh)["players"]}
    except Exception:  # noqa: BLE001
        return {}


def fetch(league_id, names):
    url = ("https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl"
           f"/seasons/{SEASON}/segments/0/leagues/{league_id}")
    r = requests.get(url, params={"view": "mDraftDetail"},
                     cookies={"espn_s2": S2, "SWID": SWID},
                     headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
    r.raise_for_status()
    dd = r.json().get("draftDetail", {})
    picks = []
    for p in dd.get("picks", []):
        pid = p.get("playerId", -1)
        if not pid or pid <= 0:
            continue
        picks.append({
            "overall": p.get("overallPickNumber"),
            "round": p.get("roundId"),
            "round_pick": p.get("roundPickNumber"),
            "team_id": p.get("teamId"),
            "player_id": pid,
            "player_name": names.get(pid, f"#{pid}"),
        })
    return {
        "updated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "drafted": bool(dd.get("drafted")),
        "in_progress": bool(dd.get("inProgress")),
        "picks": picks,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--league", default=os.environ["ESPN_LEAGUE_ID"])
    ap.add_argument("--once", action="store_true")
    args = ap.parse_args()
    names = load_names()

    if args.once:
        data = fetch(args.league, names)
        print(json.dumps(data, indent=2)[:2000])
        print(f"\n{len(data['picks'])} real picks; drafted={data['drafted']} "
              f"in_progress={data['in_progress']}")
        return

    print(f"polling league {args.league} every {INTERVAL}s -> {OUT}  (Ctrl+C to stop)")
    last = -1
    while True:
        try:
            data = fetch(args.league, names)
            with open(OUT, "w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=2)
            n = len(data["picks"])
            if n != last:
                newest = data["picks"][-1]["player_name"] if data["picks"] else "-"
                print(f"[{data['updated']}] {n} picks  latest: {newest}")
                last = n
            if data["drafted"]:
                print("draft complete flag set - stopping")
                return
        except KeyboardInterrupt:
            print("\nstopped")
            return
        except Exception as e:  # noqa: BLE001
            print(f"  poll error: {e!r}")
        time.sleep(INTERVAL)


if __name__ == "__main__":
    sys.exit(main())
