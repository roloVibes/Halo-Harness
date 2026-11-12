"""tests.test_fleet_mission_needs -- Halo 3.4.1.1 defect 42 (the fleet pack's fleet/mission_assign.py): the lead gave a
part `needs: ["os:linux", "shell"]`; no card lists "shell", so the part was unassignable ("nobody in the fleet has
shell") though the goal named kali@kali, the only harness, which has a shell and every CLI. Now a bare need no card's
vocabulary knows is dropped (said in the plan's notes), a real capability nobody has still makes the part
unassignable, and a harness the part or the goal names wins. Run: python -m tests.test_fleet_mission_needs
"""
from __future__ import annotations
from tests.helpers import fleet_pack as _fleet_pack  # noqa: E402  (the fleet pack on, its modules by their old names)
_fleet_pack.on()

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_scoped_state_dir_once  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

ensure_scoped_state_dir_once()
test, TESTS = new_registry()


def _entry(name: str, hid: str, os_: str, clis: dict, gpu: str = "") -> dict:
    hw = {"os": os_, "distro": os_, "gpu": [{"name": gpu}] if gpu else []}
    return {"name": name, "harness": hid, "catalog": {"harness": {}, "hardware": hw, "clis": clis, "mcp": [], "skills": []}}


KALI = _entry("kali@kali", "h-kali", "linux", {"nmap": "installed", "bash": "installed"})
PC = _entry("you@tower", "h-pc", "windows", {"nmap": False}, gpu="NVIDIA GeForce RTX 4090")


@test
def test_an_unknown_need_is_dropped_not_unassignable(ctx: Ctx):
    from halo_harness.fleet.mission_assign import assign
    goal = "One part, on kali@kali: run the shell command uname -s and write its output into uname.txt"
    part = assign({"id": "1", "title": "uname", "brief": "run uname -s", "needs": ["os:linux", "shell"]}, [KALI], [], {}, (), goal)
    ctx.check(f"placed on kali@kali, not unassignable: {part.get('harness_name')} {part.get('unassignable')!r}",
              part["harness"] == "h-kali" and not part["unassignable"])
    ctx.check(f"the word no card knows is dropped and said: {part['needs']} {part['dropped_needs']}",
              part["needs"] == ["os:linux"] and part["dropped_needs"] == ["shell"])


@test
def test_a_real_capability_nobody_has_still_stops_the_part(ctx: Ctx):
    from halo_harness.fleet.mission_assign import assign, vocab_problems
    for need in ("gpu", "cli:zzz", "4090", "metasploit"):
        part = assign({"id": "1", "title": "x", "brief": "x", "needs": [need]}, [KALI], [], {}, [PC])
        ctx.check(f"{need}: with no harness named, kept and unassignable: {part['needs']} {part.get('unassignable')!r}",
                  part["needs"] == [need] and part["dropped_needs"] == [] and bool(part["unassignable"]))
    probs = vocab_problems([{"id": "1", "needs": ["shell", "gpu"]}, {"id": "2", "title": "on kali@kali", "needs": ["shell"]}],
                           [KALI], [PC])
    ctx.check(f"the lead's first answer goes back for a word no card knows, unless the owner named the harness: {probs}",
              len(probs) == 1 and probs[0].startswith("part 1: no harness lists shell"))


@test
def test_the_lead_is_asked_again_once(ctx: Ctx):
    import json as J
    from halo_harness.fleet import mission as M
    from halo_harness.fleet import mission_plan as P
    from halo_harness.fleet import mission_store as S
    from tests.helpers.mission_seed import FakeLead
    home = Path(__import__("tempfile").mkdtemp(prefix="needs42-"))
    mid = M.new_id()
    S.create(home, M.new_doc(mid=mid, goal="Report the kernel name", hub={"id": "h-kali", "name": "kali@kali"}, repo=None))
    one = lambda needs: J.dumps({"parts": [{"id": "1", "title": "uname", "brief": "uname -s into uname.txt", "kind": "files",
                                           "harness": "kali@kali", "needs": needs, "outputs": ["uname.txt"]}], "merge_order": ["1"]})
    lead = FakeLead(one(["os:linux", "shell"]), one(["os:linux"]))
    plan = P.plan(home, mid, [KALI], call_model=lead)
    ctx.check(f"asked twice, the second prompt names the word: {len(lead.prompts)}",
              len(lead.prompts) == 2 and "no harness lists shell" in lead.prompts[1])
    ctx.check(f"the part placed: {plan['parts'][0].get('harness_name')} {plan['parts'][0].get('unassignable')!r}",
              plan["parts"][0]["harness"] == "h-kali" and not plan["parts"][0]["unassignable"])


@test
def test_a_harness_the_goal_or_the_part_names_wins(ctx: Ctx):
    from halo_harness.fleet.mission_assign import assign
    both = [PC, KALI]
    part = assign({"id": "1", "title": "scan", "brief": "nmap localhost", "needs": [], "harness": "you@tower"},
                  both, ["you@tower"], {}, (), "Run nmap on kali@kali and keep the report")
    ctx.check(f"the goal names kali@kali: over the lead's pick and prefer: {part['harness_name']} {part['reason']!r}",
              part["harness"] == "h-kali" and part["pinned"] and part["reason"].startswith("the goal names kali@kali"))
    part = assign({"id": "2", "title": "On you@tower: list the files", "brief": "ls", "needs": []}, both, [], {}, (),
                  "Two parts: one on kali@kali, one on you@tower")
    ctx.check(f"a part's own words name its harness first: {part['harness_name']}", part["harness"] == "h-pc")
    part = assign({"id": "3", "title": "anything", "brief": "x", "needs": []}, both, [], {}, (), "kali@kali or you@tower")
    ctx.check(f"a goal naming two picks neither by name: {part['reason']!r}", not part["reason"].startswith("the goal names"))


@test
def test_the_plan_notes_say_what_was_dropped(ctx: Ctx):
    from halo_harness.fleet.mission_plan import finalize
    parts, notes = finalize([{"id": "1", "title": "uname", "brief": "uname -s", "needs": ["shell"], "depends_on": []}],
                            ["1"], [KALI], [], {}, (), "on kali@kali")
    ctx.check(f"a note per dropped need: {notes}", any("dropped the need shell" in n for n in notes))
    src = (Path(_fleet_pack.PACK) / "fleet" / "mission_attention.py").read_text(encoding="utf-8")
    ctx.check("the Attention row counts parts in words (1 part, 2 parts)", "part{'' if len(parts) == 1 else 's'}" in src)


@test
def test_the_plan_reads_the_mode_and_the_ask_wait_now(ctx: Ctx):
    """3.4.1.1 defect 40: the first plan after an update said the old note (the cached card the background refresh had
    not replaced), and after `halo config set fleet.mission.ask_wait_min 1` the next plan still said 30 min."""
    import json as J
    import tempfile
    import time
    from halo_harness import __version__
    from halo_harness.fleet import capabilities as caps
    from halo_harness.fleet.hub_capabilities import local_catalog
    from halo_harness.fleet.mission_assign import mode_note
    home = Path(tempfile.mkdtemp(prefix="needs40-"))
    (home / "config.json").write_text(J.dumps({"permission_mode": "default", "fleet": {"mission": {"ask_wait_min": 1}}}),
                                      encoding="utf-8")
    card = {"harness": {"id": "h-kali", "name": "kali@kali", "version": __version__, "permission_mode": "auto"},
            "at": time.time(), "hash": "old", "mcp": [], "clis": {}}
    caps.save(card, home)
    got = (local_catalog(home) or {}).get("harness") or {}
    ctx.check(f"the mode and the wait are read now, over the cached card's: {got}",
              got.get("permission_mode") == "default" and got.get("mission_ask_wait_min") == 1.0)
    note = mode_note({"name": "kali@kali", "catalog": {"harness": got}})
    ctx.check(f"so the plan's note says 1 min: {note!r}", "for up to 1 min" in note)
    # 3.4.1.1 defect 43: a worker wrote its output with `cmd | head -1 > artifacts/1/x.txt`, which asks: two cards for
    # a one-command part. The part's brief says to run the command alone and write the file with Write.
    ctx.check(f"the note says it is the Write tool that needs no ask: {note!r}",
              "with the Write tool needs no ask" in note and "a shell redirect there asks" in note)
    from halo_harness.fleet.mission_outcome import write_line
    src = (Path(_fleet_pack.PACK) / "fleet" / "mission_worker_run.py").read_text(encoding="utf-8")
    said = write_line("2")
    ctx.check(f"a files part's brief says Write, never a shell redirect: {said!r}",
              "Write each output file with the Write tool" in said and "artifacts/2/" in said
              and "never with a shell redirect" in said and "+ write_line(n)" in src)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
