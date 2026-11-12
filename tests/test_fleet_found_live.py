"""tests.test_fleet_found_live -- Halo 3.4.0.1 "Found live": the fleet pack's planning words a two-machine run showed
wrong (defects 14, 16, 19). No model, no hub: the planner's code (mission_assign) and the capability card.

14: a member joined with no halo session open was "offline", and the plan said "nobody in the fleet has gpu" while
    `halo fleet who 4090` ranked it first. Now the plan names it: it has gpu but is offline, open a session there.
16: a part sent to a harness in permission mode `default` ran as a print-mode worker where every ask was refused;
    nothing said so at planning time. Now the card carries the mode a part runs in, and the plan says it per part.
19: the hub's own card from an older Halo's cache showed (halo 3.3.16.3, "age unknown") with no word that it refreshes.
Run: python -m tests.test_fleet_found_live
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tests.helpers import fleet_pack as _fleet_pack  # noqa: E402  (the fleet pack on, its modules by their old names)
_fleet_pack.on()

from tests.helpers.provider_env_defaults import ensure_scoped_state_dir_once  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

ensure_scoped_state_dir_once()
test, TESTS = new_registry()
GPU = {"gpu": [{"name": "NVIDIA GeForce RTX 4090", "vram_gb": 22.5}]}


def _entry(name: str, hid: str, *, gpu: bool = False, nmap: bool = False, mode: str = "auto", online: bool = True) -> dict:
    cat = {"harness": {"id": hid, "name": name, "permission_mode": mode}, "hardware": GPU if gpu else {},
           "clis": {"nmap": "7.95"} if nmap else {}, "mcp": [], "skills": [], "craft_apps": []}
    return {"harness": hid, "name": name, "online": online, "local": False, "catalog": cat}


@test
def test_a_need_only_an_away_member_has_names_it(ctx: Ctx):
    from halo_harness.fleet.mission_assign import assign
    kali = _entry("kali@kali", "k", nmap=True)
    pc = _entry("rolo@roundBoy", "p", gpu=True, online=False)
    part = assign({"id": "2", "needs": ["gpu"]}, [kali], [], {}, [pc])
    ctx.check(f"not 'nobody in the fleet': who has it, offline, and what brings it back, got {part['unassignable']!r}",
              part["unassignable"] == "nobody online has gpu; rolo@roundBoy has it but is offline (no halo session open "
                                     "there): open one, then plan again" and part["harness"] is None)
    none = assign({"id": "3", "needs": ["metasploit"]}, [kali], [], {}, [pc])
    ctx.check(f"a need nobody has, online or not, keeps its words, got {none['unassignable']!r}",
              none["unassignable"] == "nobody in the fleet has metasploit")


@test
def test_the_plan_says_a_part_runs_where_asks_are_refused(ctx: Ctx):
    from halo_harness.fleet.mission_assign import assign
    from halo_harness.fleet.mission_plan import finalize
    kali = _entry("kali@kali", "k", nmap=True, mode="default")
    pc = _entry("rolo@roundBoy", "p", gpu=True, mode="auto")
    parts = [{"id": "1", "title": "nmap", "needs": ["nmap"], "depends_on": [], "claims": [], "kind": "files"},
             {"id": "2", "title": "gpu", "needs": ["gpu"], "depends_on": [], "claims": [], "kind": "files"}]
    parts, notes = finalize(parts, [], [kali, pc], [], {})
    said = [n for n in notes if n.startswith("part 1: ")]
    ctx.check(f"part 1 on kali@kali (mode default): the plan says asks are refused there and what lets them through, got {said}",
              len(said) == 1 and "kali@kali runs mission parts in permission mode default" in said[0]
              and "refused" in said[0] and "Bash(nmap:*)" in said[0] and "permission_mode auto" in said[0])
    ctx.check("part 2 on an auto harness: no such note", not [n for n in notes if n.startswith("part 2: ")])
    old = _entry("old@box", "o", nmap=True)
    old["catalog"]["harness"].pop("permission_mode")
    ctx.check("a card from an older Halo (no mode on it): nothing guessed",
              assign({"id": "1", "needs": ["nmap"]}, [old], [], {})["mode_note"] == "")


@test
def test_the_card_carries_the_mode_and_an_older_halos_card_is_stale(ctx: Ctx):
    from halo_harness.ext import core
    from halo_harness.fleet import capabilities as caps
    from halo_harness.fleet.hub_capabilities import entry, local_catalog
    from halo_harness.theme import set_config_value
    set_config_value("permission_mode", "default")
    ctx.check(f"a part runs in config.json's mode, got {caps.part_mode(Path.cwd())!r}", caps.part_mode(Path.cwd()) == "default")
    now = time.time()
    old = {"harness": {"id": "x", "name": "kali@kali", "version": "3.3.16.3"}, "at": now - 60, "hash": "h"}
    mine = {"harness": {"id": "x", "name": "kali@kali", "version": core.version()}, "at": now - 60, "hash": "h"}
    ctx.check("a card an older Halo made is stale; this Halo's fresh one is not", caps.stale(old, now) and not caps.stale(mine, now))
    home = Path(caps._home(None))
    caps.save(old, home)
    seen = []
    caps.refresh_in_background, saved = (lambda h=None, on_done=None: seen.append(h) or True), caps.refresh_in_background
    try:
        got = local_catalog(home)
    finally:
        caps.refresh_in_background = saved
    row = entry({"id": "x", "name": "kali@kali", "local": True, "online": True}, got)
    ctx.check(f"the hub shows the old card, says it refreshes, and asked for a new one, got {row.get('note')!r} {len(seen)}",
              row.get("note", "").startswith("refreshing:") and len(seen) == 1)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="fleet found-live tests"))
