"""halo_harness.studio.agents_door -- the words of the sections Agents took in (Halo 3.3.16.0 R1 "Agents: one section").

Team, Roles and Orchestra are one Studio section now, Agents (Alt+2), with three views: Cast (the lineup and its bios:
Roles' canvas), Runs (Orchestra: a goal, the lead's plan, the lanes, the report; Team's board went: a run's plan shows
who owns what) and Live (Roles Live: the session's agents as a tree). The three old words stay doors -- `halo studio
--mode roles|orchestra|team`, `/studio <word>`, `/roles`, a page's `?mode=<word>` (the page itself lands them:
ui/src/lib/agentsDoor.ts) -- and each answer prints the new door once:

    view_of(word)    'cast' | 'runs' | 'live' for an Agents word ('' for any other)
    door_line(word)  the one line naming the new door ('' for a word that is not an old one)
"""

from __future__ import annotations

#: The old section words and the Agents view each lands on.
DOORS = {"roles": "cast", "orchestra": "runs", "team": "runs"}
VIEWS = ("cast", "runs", "live")
TEAM_LINE = "Team's board is gone; a run's plan shows who owns what (halo team still runs the team file)"


def view_of(word) -> str:
    w = str(word or "").strip().lower()
    return "cast" if w == "agents" else DOORS.get(w, "")


def door_line(word) -> str:
    w = str(word or "").strip().lower()
    view = DOORS.get(w)
    if not view:
        return ""
    line = f"{w.title()} is Agents -> {view.title()} now (Alt+2 in Studio; halo studio --mode agents)"
    return f"{line}. {TEAM_LINE}" if w == "team" else line
