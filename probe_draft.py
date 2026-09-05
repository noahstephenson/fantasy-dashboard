"""Look at what the 160 pre-draft picks actually contain."""
import json
import os

import requests
from dotenv import load_dotenv

load_dotenv()
LEAGUE_ID = os.environ["ESPN_LEAGUE_ID"]
ESPN_S2 = os.environ["ESPN_S2"]
SWID = os.environ["ESPN_SWID"]
SEASON = os.environ.get("SEASON", "2026")

base = ("https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl"
        f"/seasons/{SEASON}/segments/0/leagues/{LEAGUE_ID}")
r = requests.get(base, params={"view": "mDraftDetail"},
                 cookies={"espn_s2": ESPN_S2, "SWID": SWID},
                 headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
dd = r.json()["draftDetail"]
print("drafted:", dd.get("drafted"), " inProgress:", dd.get("inProgress"))
picks = dd.get("picks", [])
print("n picks:", len(picks))
print("\nfirst 3 picks raw:")
for p in picks[:3]:
    print(json.dumps(p, indent=2))
print("\nlast pick raw:")
print(json.dumps(picks[-1], indent=2))

# how many have a real playerId?
real = [p for p in picks if p.get("playerId", -1) and p.get("playerId", -1) > 0]
print(f"\npicks with playerId > 0: {len(real)}")
