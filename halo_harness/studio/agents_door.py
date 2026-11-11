"""halo_harness.studio.agents_door -- the words of the sections Agents took in (Halo 3.3.16.0 R1 "Agents: one section";
R2 "the Fleet fold").

Team, Roles and Orchestra are one Studio section now, Agents (Alt+2), with three views: Cast (the lineup and its bios:
Roles' canvas), Runs (Orchestra: a goal, the lead's plan, the lanes, the report; Team's board went: a run's plan shows
who owns what) and Live (Roles Live: the session's agents as a tree). R2 folded the Fleet section in too: a machine's
agents are Agents -> Live with the fleet scope on (every machine, its sessions, their agents), its models are Local's,
pairing and the people Setup -> Machines', a mission Agents -> Runs'. The old words stay doors -- `halo studio --mode
roles|orchestra|team|fleet`, `/studio <word>`, `/roles`, a page's `?mode=<word>` (the page itself lands them:
ui/src/lib/agentsDoor.ts) -- and each answer prints the new door once:

    view_of(word)    'cast' | 'runs' | 'live' for an Agents word ('' for any other)
    door_line(word)  the one line naming the new door ('' for a word that is not an old one)
"""

from __future__ import annotations

#: The old section words and the Agents view each lands on.
DOORS = {"roles": "cast", "orchestra": "runs", "team": "runs", "fleet": "live"}
VIEWS = ("cast", "runs", "live", "workflows")  # 3.3.16.0 R3: the board of squares
TEAM_LINE = "Team's board is gone; a run's plan shows who owns what (the team file left in 3.4.0.0)"
FLEET_LINE = ("machines are Setup -> Machines (pairing, sharing, people), their models Local, a mission Agents -> Runs; "
              "halo fleet still runs the hub and the table")


def view_of(word) -> str:
    w = str(word or "").strip().lower()
    return "cast" if w == "agents" else DOORS.get(w, "")


def door_line(word) -> str:
    w = str(word or "").strip().lower()
    view = DOORS.get(w)
    if not view:
        return ""
    if w == "fleet":
        return f"Fleet is Agents -> Live now, the fleet scope on (Alt+2 in Studio; halo studio --mode agents). {FLEET_LINE}"
    line = f"{w.title()} is Agents -> {view.title()} now (Alt+2 in Studio; halo studio --mode agents)"
    return f"{line}. {TEAM_LINE}" if w == "team" else line

