"""tests.helpers.studio_map -- Agents -> 3 · Map (Halo 3.6.0.0 R3) in headless Chrome, as a first-time user, over
tests/helpers/crew_rig.py (a scratch home, the builder's scripted model). tests/test_studio_map.py reads what it saw:

    first    from 1 · Agents, the 3 key: the switch, the starter map -- main at the left, seven boxes, a label per line in
             the lane, never over a box; no dialog, no conversation, the list drawer closed
    drag     the list drawer; a row dragged (real pointer events) over the map: the drop places say what a drop does;
             dropped on main: the When card at the line; "when the task says test", Save: the label and the receipt
    chain    coder's dot dragged onto tester: a chain line, its When card, Always; a line back would make a circle:
             the page says so in one sentence; the receipt's Undo takes the last change back
    keys     a workflow added with the keyboard (Enter on its row), under Not connected yet; its dot's list (Enter), main;
             its box opened: its steps and the link to Workflows; hover lifts its lines; a label's card takes a line out
    maps     + New map, main only; the switcher back; My sessions use this (config); Lock: no dots, no Add
    zoom     a hand zoom survives the drawer; Fit never under 75 %
    builder  "send anything touching auth to my-reviewer after the code workflow" on ship-it: ghost box and dashed line on
             the map; Apply: drawn for real; Undo: gone

    python -m tests.helpers.studio_map [DIR]     DIR: also save studio-map.png, studio-map-drag.png, studio-map-when.png
"""
from __future__ import annotations

import sys
from contextlib import contextmanager
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from tests.helpers.chrome_driver import Driver  # noqa: E402
from tests.helpers.studio_agents import key  # noqa: E402
from tests.helpers.studio_map_steps import builder, chain, drag, first, keys, maps, zoom  # noqa: E402

SHOTS: list = []


class MapDriver(Driver):
    no_chrome = {"skip": "no Chrome found"}
    width, height = 1500, 900

    @contextmanager
    def session(self, c):
        from tests.helpers.crew_rig import CrewRig
        from tests.helpers import studio_map_steps as S
        S.SHOTS[:] = self.argv[:1]
        with CrewRig() as rig:
            rig.studio()
            S.seed(rig)
            yield tuple((fn, (c, rig)) for fn in (first, drag, chain, keys, maps, zoom, builder))


__all__ = ["MapDriver", "key"]

if __name__ == "__main__":
    sys.exit(MapDriver(sys.argv[1:]).main())
