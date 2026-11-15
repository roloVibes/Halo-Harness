"""halo_harness.studio.agents_door -- the words of the sections Agents took in (Halo 3.3.16.0 R1 "Agents: one section";
3.6.0.0 R5: three tabs).

Agents (Alt+2) has three tabs: 1 · Agents (`crew`), 2 · Workflows (`workflows`), 3 · Map (`map`: who main hands work
to and when, lit while a session runs, History and goal runs in its drawer). The old words stay doors -- `halo studio
--mode roles|orchestra|team`, `/studio <word>`, `/roles`, a page's `?mode=<word>` (the page itself lands them:
ui/src/lib/agentsDoor.ts) -- and each answer prints the new door once:

    view_of(word)    the tab an Agents word lands on ('' for any other word)
    door_line(word)  the one line naming the new door ('' for a word that is not an old one)
"""

from __future__ import annotations

#: The old section words and the Agents tab each lands on (3.6.0.0 R5: every one on the Map).
DOORS = {"roles": "map", "orchestra": "map", "team": "map"}
VIEWS = ("crew", "workflows", "map")
#: The views before 3.6.0.0 R5 and where they land.
OLD_VIEWS = {"cast": "map", "live": "map", "runs": "map", "roles": "map", "team": "map", "orchestra": "map", "flows": "workflows"}
LINEUP_LINE = "lineups are gone: halo maps use <name> picks the map your sessions run on"
RUNS_LINE = "a goal runs from the Map's bar (Run a goal); halo orchestra still runs one from a terminal"


def view_of(word) -> str:
    w = str(word or "").strip().lower()
    return "map" if w == "agents" else DOORS.get(w, "")


def tab_of(view) -> str:
    """A view word of any age as the tab it is now ('' for none)."""
    v = str(view or "").strip().lower()
    return v if v in VIEWS else OLD_VIEWS.get(v, "")


def door_line(word) -> str:
    w = str(word or "").strip().lower()
    if not DOORS.get(w):
        return ""
    line = f"{w.title()} is Agents -> 3 · Map now (Alt+2 in Studio; halo studio --mode agents)"
    return f"{line}; {RUNS_LINE}" if w == "orchestra" else f"{line}; {LINEUP_LINE}"
