"""tests.test_kinds -- 3.6.0.10 MW rule M2: the kinds of helper THIS session can start, as one pure list
(crew/kinds.py `kinds(agents, restriction=None)` over the agents a new session's start gives its runtime): his own
first (crew yours / the project's), then Auto's seven in the map's order while still the card, then other agents, then
the built-ins (general-purpose is the clause; one is out when its lower-cased name or its role is listed before), each
with a few words. A scratch home and folder of its own; never a model or a server.
Run: python -m tests.test_kinds
"""
from __future__ import annotations

import dataclasses
import os
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
CLEAN = ["planner", "researcher", "coder", "reviewer", "writer", "media-reader", "ops", "Judge", "Tester"]


@contextmanager
def _scratch():
    root = Path(tempfile.mkdtemp(prefix="kinds-"))
    (root / "home").mkdir()
    (root / "proj").mkdir()
    before = os.environ.get("BRIDGE_TEST_HOME")
    os.environ["BRIDGE_TEST_HOME"] = str(root / "home")
    try:
        yield root
    finally:
        if before is None:
            os.environ.pop("BRIDGE_TEST_HOME", None)
        else:
            os.environ["BRIDGE_TEST_HOME"] = before


def _his(root: Path, name: str, does: str) -> None:
    """An agent of his (crew yours), as Studio's Agents tab writes one."""
    from halo_harness.crew.store import state_dir_of
    folder = state_dir_of() / "crew" / "agents"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{name}.yaml").write_text(f"format: agent/1\nname: {name}\ndoes: {does}\nmodel: auto\nuses:\n- read\n"
                                         "careful: ask-changes\n",
                                         encoding="utf-8")


def _agents(root: Path) -> dict:
    """The agents a new session in the folder starts with (crew/session_start.py, as headless.build_session)."""
    from halo_harness.crew.session_start import new_session_state
    return new_session_state(SimpleNamespace(), cwd=root / "proj").agent_runtime.agents


def _names(rows) -> list:
    return [r["name"] for r in rows]


@test
def test_a_clean_home(ctx: Ctx):
    from halo_harness.crew.kinds import kinds
    with _scratch() as root:
        rows = kinds(_agents(root))
    ctx.check(f"a clean home lists {CLEAN}, got {_names(rows)}", _names(rows) == CLEAN)
    words = {r["name"]: r["words"] for r in rows}
    ctx.check(f"Auto's words are its routing words, then its use_for words: got {words}",
              words["planner"] == "plan, outline" and words["coder"] == "implement, fix, refactor"
              and words["media-reader"] == "image, screenshot, video, audio, pdf, transcribe"
              and words["ops"] == "deploy, release, install, ci")
    ctx.check(f"the built-ins' own words, got {words['Judge']!r} {words['Tester']!r}",
              words["Judge"] == "pass or fail a result" and words["Tester"] == "run tests, report")
    ctx.check("the parts", [r["part"] for r in rows] == ["auto"] * 7 + ["built-in"] * 2)


@test
def test_his_own_lead_and_win(ctx: Ctx):
    from halo_harness.crew.kinds import kinds
    with _scratch() as root:
        _his(root, "sorter", "Sorts the inbox by sender and date. Never deletes a message.")
        _his(root, "coder", "Writes code the way this house writes it, small commits, tests first and always.")
        rows = kinds(_agents(root))
    names = _names(rows)
    ctx.check(f"his sorter and coder lead, got {names}", set(names[:2]) == {"sorter", "coder"}
              and [r["part"] for r in rows[:2]] == ["his", "his"])
    words = {r["name"]: r["words"] for r in rows}
    ctx.check(f"his coder is listed once, got {names.count('coder')}", names.count("coder") == 1)
    ctx.check(f"then Auto's six left and the built-ins, got {names[2:]}",
              names[2:] == [n for n in CLEAN if n != "coder"])
    ctx.check(f"his words: the first sentence, got {words['sorter']!r}",
              words["sorter"] == "Sorts the inbox by sender and date")
    ctx.check(f"cut after 8 words, got {words['coder']!r}",
              words["coder"] == "Writes code the way this house writes it")


@test
def test_his_explore_drops_explore(ctx: Ctx):
    from halo_harness.crew.kinds import kinds
    with _scratch() as root:
        _his(root, "explore", "Finds where things are.")
        agents = _agents(root)
    rows = kinds(agents)
    ctx.check(f"his explore is listed and the built-in Explore is not, got {_names(rows)}",
              "explore" in _names(rows) and "Explore" not in _names(rows))
    # with no Auto seven (roles off: no map), a built-in is out by its lower-cased name, the others by their role
    plain = {n: sp for n, sp in agents.items() if sp.source != "crew:starter"}
    ctx.check(f"roles off: {_names(kinds(plain))}",
              _names(kinds(plain)) == ["explore", "Plan", "Coder", "Reviewer", "Researcher", "Judge", "Tester"])
    without = {n: sp for n, sp in plain.items() if n != "explore"}
    ctx.check(f"roles off, nothing of his: every built-in but general-purpose, got {_names(kinds(without))}",
              _names(kinds(without)) == ["Explore", "Plan", "Coder", "Reviewer", "Researcher", "Judge", "Tester"])


@test
def test_other_agents_follow_auto(ctx: Ctx):
    from halo_harness.crew.kinds import kinds
    with _scratch() as root:
        agents = dict(_agents(root))
    pack = dataclasses.replace(agents["planner"], name="tidy--sweeper", source="crew:pack", role=None,
                               description="Sweeps the build folder")
    user = dataclasses.replace(agents["planner"], name="linter", source="user", role=None, description="")
    agents.update({"tidy--sweeper": pack, "linter": user})
    rows = kinds(agents)
    ctx.check(f"a pack's agent and a Claude Code agent come after Auto's seven, before the built-ins: {_names(rows)}",
              _names(rows) == CLEAN[:7] + ["tidy--sweeper", "linter"] + CLEAN[7:]
              and [r["part"] for r in rows[7:9]] == ["other", "other"])
    ctx.check(f"no words is no words, got {rows[8]['words']!r}", rows[8]["words"] == "")


@test
def test_a_restriction_and_an_empty_list(ctx: Ctx):
    from halo_harness.crew.kinds import kinds, names
    with _scratch() as root:
        agents = _agents(root)
    ctx.check(f"a restriction {{planner}} keeps only it, got {names(kinds(agents, {'planner'}))}",
              names(kinds(agents, {"planner"})) == ["planner"])
    ctx.check("a restriction with no name it can start: none", kinds(agents, {"nobody"}) == [])
    ctx.check("no agents: none", kinds({}) == [] and kinds(None) == [])


def _rows(his: int = 0, other: int = 0) -> list:
    from halo_harness.crew.kinds import kinds
    with _scratch() as root:
        rows = kinds(_agents(root))
    mine = [{"name": f"his-{i:02d}", "words": "Sorts the inbox by sender and date", "part": "his"} for i in range(his)]
    more = [{"name": f"cc-{i:02d}", "words": f"Helper number {i}", "part": "other"} for i in range(other)]
    return mine + rows[:7] + more + rows[7:]


def _block(rows, room=None):
    from halo_harness.agent import helpers_words as W
    from halo_harness.agent.prompt_composition import tokens_of
    from halo_harness.crew.kinds import CAP, block
    room = CAP - tokens_of(W.longest_tail()) if room is None else room
    out = block(rows, W.M1, W.M2_HEAD, W.M2_END, W.M2_MORE, room)
    return out, (out or "").split("\n")[-1]


@test
def test_m7_the_block_fits_its_cap_and_gives_way_in_order(ctx: Ctx):
    """3.6.0.10 M7: frozen block + longest tail <= CAP; past it words leave (built-ins, others, Auto's seven, his
    last), then names from the end (" and {n} more"); nothing fits: None (today's line)."""
    from halo_harness.agent import helpers_words as W
    from halo_harness.agent.prompt_composition import tokens_of
    from halo_harness.crew.kinds import CAP
    room = CAP - tokens_of(W.longest_tail())
    out, line = _block(_rows())
    ctx.check(f"a clean home: every word, {tokens_of(out)} <= {room}",
              tokens_of(out) <= room and "Judge (pass or fail a result); Tester (run tests, report)." in line)
    out, line = _block(_rows(his=1))
    ctx.check(f"one of his: the built-ins' words leave first, his stay: {line}",
              "his-00 (Sorts the inbox by sender and date)" in line and "planner (plan, outline)" in line
              and "Judge (" not in line and "Tester (" not in line and tokens_of(out) <= room)
    out, line = _block(_rows(his=2, other=3))
    ctx.check(f"the others' words leave before Auto's, his last: {line}",
              "cc-00 (" not in line and "his-00 (" in line and tokens_of(out) <= room)
    out, line = _block(_rows(his=30, other=40))
    ctx.check(f"30 of his and 40 others: names only, his first, the rest counted: {line}",
              line.startswith(W.M2_HEAD + "his-00, his-01, ") and "(" not in line.split(": ", 1)[1].split(" and ")[0]
              and line.endswith(" more (a wrong name lists them all)" + W.M2_END) and tokens_of(out) <= room)
    ctx.check("M1 is always whole", out.split("\n")[0] == W.M1)
    ctx.check("M1 and one name do not fit: None (today's line)", _block(_rows(), room=tokens_of(W.M1))[0] is None)
    ctx.check("no rows: None", _block([])[0] is None)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
