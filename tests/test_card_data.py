"""tests.test_card_data -- the report card's data: a session's or a goal run's record read for the card (halo_harness/
live/card_data.py and card_run.py, card_facts.py, card_timeline.py beside it; 3.6.0.3 moved them out of the modules named
for replays -- live/replay_file.py, replay_run.py, replay_facts.py, compare.py, compare_text.py, timeline.py -- with no
change of behaviour). The time axis' marks and bands, a goal run's lead model, a sub-agent's cost once, the record's
figures and a cost Halo cannot price; every name that moved is the same object through its old module until the batch
that deletes it, and the card's own files import it from here. Run: python -m tests.test_card_data
"""
from __future__ import annotations

import ast
import contextlib
import json
import os
import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tests.helpers.compare_seed import RUN, SID_B, TR, seed_b, seed_run  # noqa: E402
from tests.helpers.replay_seed import SID, T0, seed  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


@contextlib.contextmanager
def _home():
    saved = {k: os.environ.get(k) for k in ("BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR")}
    with tempfile.TemporaryDirectory(prefix="halo-card-") as d:
        os.environ["BRIDGE_TEST_HOME"] = d
        os.environ.pop("BRIDGE_STATE_DIR", None)
        try:
            from halo_harness.config.paths import bridge_home
            yield bridge_home()
        finally:
            for k, v in saved.items():
                os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)


def _hist(state: Path) -> dict:
    from halo_harness.live import history
    return history.read(seed(state))


@contextlib.contextmanager
def _run():
    saved = {k: os.environ.get(k) for k in ("BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR")}
    with tempfile.TemporaryDirectory(prefix="halo-run-time-") as d:
        os.environ["BRIDGE_TEST_HOME"] = d
        os.environ.pop("BRIDGE_STATE_DIR", None)
        try:
            from halo_harness.config.paths import bridge_home
            state, repo = bridge_home(), Path(d) / "repo"
            run_dir = seed_run(repo)
            lane = run_dir / "lanes" / "1.json"
            lane.write_text(json.dumps(dict(json.loads(lane.read_text(encoding="utf-8")), ended=TR + 70)), encoding="utf-8")
            yield state, repo
        finally:
            for k, v in saved.items():
                os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)


@contextlib.contextmanager
def _compare_home(priced: bool = False):
    saved = {k: os.environ.get(k) for k in ("BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR")}
    cwd = os.getcwd()
    with tempfile.TemporaryDirectory(prefix="halo-compare-") as d:
        os.environ["BRIDGE_TEST_HOME"] = d
        os.environ.pop("BRIDGE_STATE_DIR", None)
        try:
            from halo_harness.config.paths import bridge_home
            state = bridge_home()
            seed(state)
            seed_b(state, priced=priced)
            repo = state.parent / "repo"
            seed_run(repo)
            yield state, repo
        finally:
            os.chdir(cwd)
            for k, v in saved.items():
                os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)


def _cmp(state, repo, a, b, **kw) -> dict:
    """Two records side by side: card_data.resolve reads each; compare.compare (Compare's rows, which leave with Compare
    in Z4 batch 5) puts them side by side. This test is mixed like ruling (4)'s: batch 5 splits it."""
    from halo_harness.live import card_data, compare
    pa = card_data.resolve(state, a, cwd=repo)
    return compare.compare(pa, pa if a == b else card_data.resolve(state, b, cwd=repo), same=a == b, **kw)


def _rows(got: dict) -> dict:
    return {r["key"]: r for r in got["rows"]}


@test
def test_timeline_marks_and_bands(ctx: Ctx):
    from halo_harness.live import card_timeline
    with _home() as state:
        h = _hist(state)
        marks = card_timeline.marks(h)
        kinds = [m["kind"] for m in marks]
        ctx.check(f"a spawn per sub-agent, the scout's hand-back, the ask, the fixer's failure, the finishes: {kinds}",
                  kinds.count("spawn") == 2 and "handoff" in kinds and "ask" in kinds and "fail" in kinds and "finish" in kinds)
        ctx.check("in time order", [m["t"] for m in marks] == sorted(m["t"] for m in marks))
        ctx.check("a spawn names its parent and its task", any(m["kind"] == "spawn" and m["to"] == "main" and "find the bug" in m["text"] for m in marks))
        asks = [(round(m["t"] - T0), m["text"]) for m in marks if m["kind"] == "ask"]
        ctx.check(f"the permission card from the turn's record (its words, how it was answered) and the question, got {asks}",
                  asks[0] == (20, "Bash: rm -rf build (answered allow after 6 s)") and asks[1][0] == 70 and asks[1][1].startswith("may I push?"))
        main = [(round(x["t"] - T0), x["state"]) for x in h["states"] if x["agent_id"] == "main"]
        ctx.check(f"main waits on the owner from the card to the answer, and through the question, got {main}",
                  (20, "waiting") in main and (26, "running") in main and (70, "waiting") in main and (80, "running") in main)
        bands = card_timeline.bands(h)
        phases = {b["phase"] for b in bands}
        ctx.check(f"the bands carry the phase words, got {phases}", {"tool", "waiting", "thinking"} <= phases and phases <= set(card_timeline.PHASES))
        ctx.check("they tile the session without overlap", all(a["t1"] <= b["t0"] + 1e-6 for a, b in zip(bands, bands[1:])))
        ctx.check("each agent's own cost over time", {c["agent_id"] for c in h["agent_costs"]} == {"main", "scout1"})


@test
def test_a_role_word_is_never_named_as_the_model(ctx: Ctx):
    """3.4.1.1 defect 59: a goal run with `lead: main` (the lead role) read "MODELS USED ... main: 2 % of cost" and the
    lead's box MODEL main. The lead's model is its own session's record's, else said as not recorded."""
    from halo_harness.live import card_run
    with _run() as (state, repo):
        run_dir = repo / ".halo" / "orchestra" / RUN
        goal = json.loads((run_dir / "goal.json").read_text(encoding="utf-8"))
        (run_dir / "goal.json").write_text(json.dumps(dict(goal, lead="main", worker="subagent")), encoding="utf-8")
        p = card_run.build_run(state, run_dir)
        ctx.check(f"no session on disk: the lead's model is not recorded, never `main`: {p['agents'][0]['model']} {p['facts']['model_cost']}",
                  p["agents"][0]["model"] is None and "main" not in p["facts"]["model_cost"]
                  and card_run.LEAD_UNKNOWN in p["facts"]["model_cost"])
        split = json.loads((run_dir / "split.json").read_text(encoding="utf-8"))
        (run_dir / "split.json").write_text(json.dumps(dict(split, lead_sessions=["leadsess0001"])), encoding="utf-8")
        sess = state / "sessions" / "repo" / "leadsess0001.jsonl"
        sess.parent.mkdir(parents=True, exist_ok=True)
        sess.write_text(json.dumps({"type": "meta", "ts": TR, "model": "or:deepseek/deepseek-v4.1-flash"}) + "\n", encoding="utf-8")
        p = card_run.build_run(state, run_dir)
        ctx.check(f"its session's record names it: {p['agents'][0]['model']} {sorted(p['facts']['model_cost'])}",
                  p["agents"][0]["model"] == "or:deepseek/deepseek-v4.1-flash" and "or:deepseek/deepseek-v4.1-flash" in p["facts"]["model_cost"])


@test
def test_a_sub_agents_cost_counts_once(ctx: Ctx):
    from halo_harness.live import history
    with _home() as state:
        h = history.read(seed_b(state))
        ctx.check(f"main's $0.004 and the reviewer's $0.008, its rolled-up total not again: {h['cost_usd']}", abs(h["cost_usd"] - 0.012) < 1e-9)
        main = next(a for a in h["agents"] if a["agent_id"] == "main")
        ctx.check(f"main's own cost is its own calls: {main['cost_usd']}", abs(main["cost_usd"] - 0.004) < 1e-9)
        ctx.check(f"the running total ends at the session's: {h['costs'][-1]}", abs(h["costs"][-1]["usd"] - 0.012) < 1e-9)


@test
def test_the_records_figures(ctx: Ctx):
    from halo_harness.live import card_facts, history
    with _home() as state:
        f = card_facts.session_facts(seed_b(state))
        ctx.check(f"cost from the transcripts, each call once: {f['cost_usd']}", abs(f["cost_usd"] - 0.012) < 1e-9)
        ctx.check(f"the unpriced call's model is unknown, not $0: {f['cost_unknown']}", f["cost_unknown"] == ["or:mock/free"])
        ctx.check(f"tokens in and out (main's two calls + the reviewer's): {f['tokens']}", f["tokens"] == {"in": 4000, "out": 800})
        ctx.check(f"each model's cost: {f['model_cost']}", f["model_cost"] == {"or:mock/glm-5.3": 0.012})
        ctx.check(f"the retries and the steer: {f['retries']} {f['steers']}", f["retries"] == 1 and len(f["steers"]) == 1)
        priced = card_facts.session_facts(seed_b(state, priced=True))
        ctx.check("a call priced at $0 is known", priced["cost_unknown"] == [] and abs(priced["cost_usd"] - 0.012) < 1e-9)
        ctx.check("the session file is found by id", history.find(state, SID_B) is not None)


@test
def test_a_cost_halo_cannot_price_is_never_marked(ctx: Ctx):
    with _compare_home() as (state, repo):
        r = _rows(_cmp(state, repo, SID, SID_B))
        ctx.check(f"B's priced part with a +, never $0: {r['cost']['b']}", r["cost"]["b"]["text"] == "$0.0120+" and r["cost"]["b"]["unknown"])
        ctx.check("the better cost is not marked where a side is unknown", r["cost"]["better"] is None and r["cost"]["word"] == "unknown")
    with _compare_home(priced=True) as (state, repo):
        r = _rows(_cmp(state, repo, SID, SID_B))
        ctx.check(f"once every call is priced it is compared: {r['cost']}", r["cost"]["better"] == "b" and r["cost"]["word"] == "cheaper")
    from halo_harness.live.card_data import cells
    c = cells({"cost_usd": 0.0, "cost_known": False, "cost_unknown": ["or:x/free"], "models": []})["cost"]
    ctx.check(f"nothing priced: unknown, not $0: {c}", c["text"].startswith("unknown") and "$0" not in c["text"] and c["value"] is None)


def _defined(path: Path) -> list:
    """The names a module defines at its top level (functions, classes, assignments), never what it imports."""
    out = []
    for node in ast.parse(path.read_text(encoding="utf-8")).body:
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            out.append(node.name)
        elif isinstance(node, ast.Assign):
            out += [t.id for t in node.targets if isinstance(t, ast.Name)]
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            out.append(node.target.id)
    return out


def _imports(path: Path) -> list:
    """(module, name) for every import of a file, at any depth (a function-local one too)."""
    out = []
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.ImportFrom) and node.module:
            out += [(node.module, a.name) for a in node.names]
        elif isinstance(node, ast.Import):
            out += [(a.name, "") for a in node.names]
    return out


LIVE = ROOT / "halo_harness" / "live"
#: old module -> (its new home, the names that moved; None = the whole module moved)
MOVES = {"replay_file": ("card_data", ("FORMAT", "VERSION", "AGENT_KEYS", "ReplayError", "plan_of", "includes", "build")),
         "compare": ("card_data", ("PHASE", "CompareError", "resolve", "lanes")),
         "compare_text": ("card_data", ("money", "secs", "kilo", "bare", "_pct", "cells")),
         "replay_run": ("card_run", None), "replay_facts": ("card_facts", None), "timeline": ("card_timeline", None)}
OLD = set(MOVES) | {"replay_private", "replay_cut", "clip_chrome"}
#: the file code that does not move (it leaves in Z4 batch 5, Z13): the one place a kept file may still name it
FILE_CODE = {("halo_harness/live/report_card.py", "replay_file"), ("halo_harness/live/card_data.py", "replay_file")}


@test
def test_every_moved_name_is_the_same_object_through_its_old_module(ctx: Ctx):
    """3.6.0.3 (R-B6, Z5): the card's data left its replay names as a pure move; each old module re-exports what moved
    (the private names too) until the batch that deletes it; the payload's value "halo-replay" stays."""
    import importlib
    for old, (new, names) in MOVES.items():
        a, b = importlib.import_module(f"halo_harness.live.{old}"), importlib.import_module(f"halo_harness.live.{new}")
        for name in names if names is not None else _defined(LIVE / f"{new}.py"):
            ctx.check(f"{old}.{name} is {new}.{name}", hasattr(b, name) and getattr(a, name, None) is getattr(b, name))
    from halo_harness.live import card_data
    ctx.check(f"the payload's format stays, got {card_data.FORMAT!r}", card_data.FORMAT == "halo-replay" and card_data.VERSION == 1)
    for rel in ("card_data.py", "card_run.py", "card_facts.py", "card_timeline.py"):
        lines = len((LIVE / rel).read_text(encoding="utf-8").splitlines())
        ctx.check(f"live/{rel} is at most 400 lines, got {lines}", lines <= 400)


@test
def test_the_cards_files_import_no_moved_name_from_an_old_module(ctx: Ctx):
    """3.6.0.3 (R-B6): the report card (report_card*.py, `halo report`, Studio's live_recording_api) reads its data from
    card_data and the card_* files; the new modules import no old one but resolve's file branch (replay_file's
    path_for, load, SUFFIX: file code, a named exception until Z4 batch 5)."""
    files = ("halo_harness/live/report_card.py", "halo_harness/live/report_card_text.py",
             "halo_harness/live/report_card_sections.py", "halo_harness/report_cli.py",
             "halo_harness/studio/live_recording_api.py", "halo_harness/live/card_data.py", "halo_harness/live/card_run.py",
             "halo_harness/live/card_facts.py", "halo_harness/live/card_timeline.py")
    for rel in files:
        bad = []
        for mod, name in _imports(ROOT / rel):
            old = mod.rsplit(".", 1)[-1] if mod.startswith("halo_harness.live.") else name if mod == "halo_harness.live" else ""
            if old in OLD and (rel, old) not in FILE_CODE:
                bad.append(f"{mod}:{name}")
        ctx.check(f"{rel} imports no moved name from an old module, got {bad}", not bad)
    src = (ROOT / "halo_harness" / "live" / "report_card.py").read_text(encoding="utf-8")
    ctx.check("report_card.py still names replay_file only for path_for and SUFFIX (file code, Z13)",
              set(re.findall(r"replay_file\.(\w+)", src)) <= {"path_for", "SUFFIX"})


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
