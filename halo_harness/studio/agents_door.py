"""halo_harness.studio.agents_door -- the words of the sections Agents took in (Halo 3.3.16.0 R1 "Agents: one section";
R2 "the Fleet fold").

Team, Roles and Orchestra are one Studio section now, Agents (Alt+2): Cast (the lineup and its bios: Roles' canvas),
Live (what runs now: the session's agents as a tree) and Workflows (the board of squares). 3.4.0.0 D "the runs fold":
the Runs view went -- a goal run is a job on Live while it runs (Run a goal on Live's bar starts one) and its report is
in History once it ended. The old words stay doors -- `halo studio --mode roles|orchestra|team`, `/studio <word>`, `/roles`, a page's `?mode=<word>` (the page itself lands them:
ui/src/lib/agentsDoor.ts) -- and each answer prints the new door once:

    view_of(word)    'cast' | 'live' for an Agents word ('' for any other; 3.4.0.0 D: Runs' words are Live's)
    door_line(word)  the one line naming the new door ('' for a word that is not an old one)
"""

from __future__ import annotations

#: The old section words and the Agents view each lands on.
DOORS = {"roles": "cast", "orchestra": "live", "team": "live"}  # 3.4.0.0 D: Runs went to Live
VIEWS = ("cast", "live", "workflows")  # 3.3.16.0 R3: the board of squares; 3.4.0.0 D: no Runs
TEAM_LINE = "Team's board is gone; a goal run on Live shows who owns what (the team file left in 3.4.0.0)"
RUNS_LINE = ("Runs is gone: a goal runs on Live (Run a goal on its bar), its report is in History once it ended; "
             "halo orchestra still runs one from a terminal")


def view_of(word) -> str:
    w = str(word or "").strip().lower()
    return "cast" if w == "agents" else DOORS.get(w, "")


def door_line(word) -> str:
    w = str(word or "").strip().lower()
    view = DOORS.get(w)
    if not view:
        return ""
    line = f"{w.title()} is Agents -> {view.title()} now (Alt+2 in Studio; halo studio --mode agents)"
    if w == "orchestra":
        return f"{line}. {RUNS_LINE}"
    return f"{line}. {TEAM_LINE}" if w == "team" else line

