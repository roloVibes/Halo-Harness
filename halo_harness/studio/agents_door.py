"""halo_harness.studio.agents_door -- the words of the sections Agents took in (Halo 3.3.16.0 R1 "Agents: one section";
R2 "the Fleet fold").

Team, Roles and Orchestra are one Studio section now, Agents (Alt+2): Cast (the lineup and its bios: Roles' canvas),
Live (what runs now: the session's agents as a tree) and Workflows (the board of squares). R2 folded the Fleet section
in too: a machine's agents are Agents -> Live with the fleet scope on, its models are Local's, pairing and the people
Setup -> Machines'. 3.4.0.0 D "the runs fold": the Runs view went -- a goal run is a job on Live while it runs (Run a
goal on Live's bar starts one) and its report is in History once it ended; a mission's panel is on Live too. The old
words stay doors -- `halo studio --mode
roles|orchestra|team|fleet`, `/studio <word>`, `/roles`, a page's `?mode=<word>` (the page itself lands them:
ui/src/lib/agentsDoor.ts) -- and each answer prints the new door once:

    view_of(word)    'cast' | 'live' for an Agents word ('' for any other; 3.4.0.0 D: Runs' words are Live's)
    door_line(word)  the one line naming the new door ('' for a word that is not an old one)
"""

from __future__ import annotations

#: The old section words and the Agents view each lands on.
DOORS = {"roles": "cast", "orchestra": "live", "team": "live", "fleet": "live"}  # 3.4.0.0 D: Runs went to Live
VIEWS = ("cast", "live", "workflows")  # 3.3.16.0 R3: the board of squares; 3.4.0.0 D: no Runs
TEAM_LINE = "Team's board is gone; a goal run on Live shows who owns what (the team file left in 3.4.0.0)"
RUNS_LINE = ("Runs is gone: a goal runs on Live (Run a goal on its bar), its report is in History once it ended; "
             "halo orchestra still runs one from a terminal")
FLEET_LINE = ("machines are Setup -> Machines (pairing, sharing, people), their models Local, a mission's panel Live; "
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
        from halo_harness.packs import fleet_door
        if fleet_door.running() is None:  # 3.4.0.1 (live check, defect 29): no Setup -> Machines to point at
            return f"Fleet is Agents -> Live now (Alt+2 in Studio); the fleet itself is a pack: {fleet_door.line()}"
        return f"Fleet is Agents -> Live now, the fleet scope on (Alt+2 in Studio; halo studio --mode agents). {FLEET_LINE}"
    line = f"{w.title()} is Agents -> {view.title()} now (Alt+2 in Studio; halo studio --mode agents)"
    if w == "orchestra":
        return f"{line}. {RUNS_LINE}"
    return f"{line}. {TEAM_LINE}" if w == "team" else line

