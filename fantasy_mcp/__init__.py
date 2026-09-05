"""In-season MCP bridge for the B1 Boyzz ESPN Fantasy Football league.

This package is additive to the draft-time pipeline (fetch_players.py,
value_model.py) — it does not modify or depend on being run after them.
It talks to ESPN live via espn_api for roster/matchup/waiver/transaction
data, reuses value_model.py's VBD/tiering math for rankings, and exposes
everything to Claude as read-only MCP tools (see server.py).
"""
import os
import sys

# value_model.py lives one directory up (tool/), not inside this package.
# Add it to sys.path so `import value_model` works regardless of the
# server's working directory (it's launched via `python -m fantasy_mcp.server`).
_TOOL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _TOOL_DIR not in sys.path:
    sys.path.insert(0, _TOOL_DIR)
