"""tests.test_card_data -- the report card's data: a session's or a goal run's record read for the card (halo_harness/
live/card_data.py and card_run.py, card_facts.py, card_timeline.py beside it; 3.6.0.3 moved them out of the modules named
for replays -- live/replay_file.py, replay_run.py, replay_facts.py, compare.py, compare_text.py, timeline.py -- with no
change of behaviour). The time axis' marks and bands, a goal run's lead model, a sub-agent's cost once, the record's
figures and a cost Halo cannot price; the card's own files import it from here. 3.6.0.3 B (file 06): the old modules
left, and the asserts of their mixed tests on build / find / build_run moved here (a session's and a goal run's record,
no key, no home path, no names in what build returns). Run: python -m tests.test_card_data
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
from tests.helpers.replay_seed import FAKE_KEY, SID, T0, seed  # noqa: E402
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


def _cost_cell(state, repo, ref: str) -> dict:
    """One run's cost cell, as the card shows it (card_data.cells of card_facts.figures of the resolved record)."""
    from halo_harness.live import card_data, card_facts
    return card_data.cells(card_facts.figures(card_data.resolve(state, ref, cwd=repo)))["cost"]


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
    """3.6.0.3 B (file 06) split it from Compare: the run's own cost cell stays (the card shows it); which of two runs
    was cheaper (Compare's rows, `better` and `word`) left with Compare."""
    with _compare_home() as (state, repo):
        b = _cost_cell(state, repo, SID_B)
        ctx.check(f"B's priced part with a +, never $0: {b}", b["text"] == "$0.0120+" and b["unknown"])
    with _compare_home(priced=True) as (state, repo):
        b = _cost_cell(state, repo, SID_B)
        ctx.check(f"once every call is priced it is known: {b}", b["text"] == "$0.0120" and not b.get("unknown")
                  and abs(b["value"] - 0.012) < 1e-9)
    from halo_harness.live.card_data import cells
    c = cells({"cost_usd": 0.0, "cost_known": False, "cost_unknown": ["or:x/free"], "models": []})["cost"]
    ctx.check(f"nothing priced: unknown, not $0: {c}", c["text"].startswith("unknown") and "$0" not in c["text"] and c["value"] is None)


@test
def test_a_goal_runs_cells_name_each_models_share_and_its_wall_time(ctx: Ctx):
    """3.6.0.3 B (file 10): the asserts the deleted test_replay_compare::test_rows_name_the_better_figure_with_a_word
    made on code that stays (card_data.cells), with the same seed and the same texts, without Compare."""
    from halo_harness.live import card_data, card_facts
    with _compare_home() as (state, repo):
        b = card_data.cells(card_facts.figures(card_data.resolve(state, f"run:{RUN}", cwd=repo)))
        a = card_data.cells(card_facts.figures(card_data.resolve(state, f"session:{SID}", cwd=repo)))
        ctx.check(f"each model's share of cost and time: {b['models']['text']}",
                  b["models"]["text"].startswith("glm-5.3: 60 % of cost, 35 % of time"))
        ctx.check(f"the goal run's wall time in words: {b['wall']}", b["wall"]["text"] == "1 min 30 s" and b["wall"]["value"] == 90)
        ctx.check(f"tokens not recorded: unknown on both, said: {a['tokens']} {b['tokens']}",
                  all(x["tokens"].get("unknown") and x["tokens"]["value"] is None and x["tokens"]["text"] == "unknown" for x in (a, b)))


@test
def test_a_goal_runs_lanes_are_its_agents_with_their_phases(ctx: Ctx):
    """3.6.0.3 B (file 10): card_data.lanes() as the deleted Compare test pinned it: each agent a lane in its block,
    and a lane carries its phase segments."""
    from halo_harness.live import card_data
    with _compare_home() as (state, repo):
        got = card_data.lanes(card_data.resolve(state, f"run:{RUN}", cwd=repo))
        lanes = {(x["agent_id"], x["block"]) for x in got}
        ctx.check(f"each agent a lane in its block: {lanes}", lanes == {("lead", "goal run"), ("lane-1", "goal run"), ("lane-2", "goal run")})
        ctx.check("a lane carries its phase segments", any(s["phase"] == "writing" for x in got for s in x["segs"]))


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
#: the modules of the old playback the card's data moved out of (3.6.0.3 R-B6); file 06 deleted them
OLD = {"replay_file", "compare", "compare_text", "replay_run", "replay_facts", "timeline", "replay_private", "replay_cut",
       "clip_chrome"}


@test
def test_the_payload_format_stays_and_each_file_is_small(ctx: Ctx):
    """3.6.0.3 (R-B6, Z5): the payload's "format" value stays as it is; each of the card's data files stays under 400
    lines. (File 02's identity checks through the old modules left with those modules in file 06.)"""
    from halo_harness.live import card_data
    ctx.check(f"the payload's format stays, got {card_data.FORMAT!r}", card_data.FORMAT == "halo-replay" and card_data.VERSION == 1)
    for rel in ("card_data.py", "card_run.py", "card_facts.py", "card_timeline.py"):
        lines = len((LIVE / rel).read_text(encoding="utf-8").splitlines())
        ctx.check(f"live/{rel} is at most 400 lines, got {lines}", lines <= 400)


@test
def test_the_cards_files_import_no_moved_name_from_an_old_module(ctx: Ctx):
    """3.6.0.3 (R-B6): the report card (report_card*.py, `halo report`, Studio's live_recording_api) reads its data from
    card_data and the card_* files; none of them imports an old module (3.6.0.3 B file 06: resolve's file branch left)."""
    files = ("halo_harness/live/report_card.py", "halo_harness/live/report_card_text.py",
             "halo_harness/live/report_card_sections.py", "halo_harness/report_cli.py",
             "halo_harness/studio/live_recording_api.py", "halo_harness/live/card_data.py", "halo_harness/live/card_run.py",
             "halo_harness/live/card_facts.py", "halo_harness/live/card_timeline.py")
    for rel in files:
        bad = []
        for mod, name in _imports(ROOT / rel):
            old = mod.rsplit(".", 1)[-1] if mod.startswith("halo_harness.live.") else name if mod == "halo_harness.live" else ""
            if old in OLD:
                bad.append(f"{mod}:{name}")
        ctx.check(f"{rel} imports no moved name from an old module, got {bad}", not bad)
    for rel in ("report_card.py", "card_data.py"):
        src = (LIVE / rel).read_text(encoding="utf-8")
        ctx.check(f"live/{rel} names no replay_file (the file code left, Z13)", not re.findall(r"replay_file", src))


# 3.6.0.3 B (file 06, its rulings): the mixed tests of the old file code are SPLIT, not deleted -- every assert on
# build, find and build_run stays here, checked on the built payload itself; what saved, loaded or listed a file left.

@test
def test_a_sessions_record_for_the_card(ctx: Ctx):
    """From test_replay_file's round trip: build() reads a session as one payload with its agents, marks, bands and the
    lines that say what it holds."""
    from halo_harness.live import card_data
    with _home() as state:
        seed(state)
        p = card_data.build(state, SID, lineup="none-such")
        ctx.check("three agents, marks and bands", len(p["agents"]) == 3 and p["marks"] and p["bands"])
        ctx.check("it says what it holds", any("not included" in line for line in p["includes"]))


@test
def test_a_seeded_key_never_reaches_the_built_record(ctx: Ctx):
    """From test_replay_file: build alone redacts (title, task, hand-back); no working directory or project path."""
    from halo_harness.live import card_data
    with _home() as state:
        seed(state)
        built = json.dumps(card_data.build(state, SID))
        ctx.check("no key in the record", FAKE_KEY not in built and FAKE_KEY[9:] not in built and "zq" * 14 not in built)
        ctx.check("where it stood, the redactor's mark", "<redacted>" in built)
        ctx.check("no working directory or path", "secret-project" not in built and '"cwd"' not in built)


@test
def test_a_goal_runs_record_for_the_card(ctx: Ctx):
    """From test_replay_run: a goal run is found by id in its repo and read as the same payload a session is."""
    from halo_harness.live import card_run
    with _home() as state:
        repo = state.parent / "repo"
        run_dir = seed_run(repo)
        ctx.check("found by id in the repo", card_run.find(repo, RUN) == run_dir and card_run.find(repo, "nope") is None)
        p = card_run.build_run(state, run_dir)
        ctx.check(f"kind run: {p['kind']}", p["kind"] == "run")
        ctx.check(f"the lead and its two lanes as agents: {[a['agent_id'] for a in p['agents']]}",
                  [a["agent_id"] for a in p["agents"]] == ["lead", "lane-1", "lane-2"] and p["agents"][1]["parent"] == "lead")
        ctx.check(f"lane 1 done, lane 2 failed: {[a['state'] for a in p['agents']]}", [a["state"] for a in p["agents"]] == ["done", "done", "failed"])
        kinds = [(m["kind"], round(m["t"] - TR)) for m in p["marks"]]
        ctx.check(f"the plan review, two spawns, two hand-offs, the failure and the finishes: {kinds}",
                  ("ask", 8) in kinds and kinds.count(("spawn", 10)) == 2 and ("handoff", 40) in kinds and ("fail", 50) in kinds and ("finish", 90) in kinds)
        ctx.check("each lane's states from its record", any(s["agent_id"] == "lane-1" and s["activity"] == "typing" for s in p["states"]))
        ctx.check(f"the bands: {sorted({b['phase'] for b in p['bands']})}", {"writing"} <= {b["phase"] for b in p["bands"]})
        f = p["facts"]
        ctx.check(f"its figures from the report and the lanes: {f}", f["cost_usd"] == 0.05 and f["how"] == "finished" and f["ok"] is True
                  and f["retries"] == 1 and f["model_cost"] == {"or:mock/lead": 0.01, "or:mock/glm-5.3": 0.03, "or:mock/worker": 0.01})
        ctx.check("its tokens are unknown (no lane session on this disk), never 0", f["tokens"] is None)


@test
def test_a_seeded_key_never_reaches_a_goal_runs_record(ctx: Ctx):
    """From test_replay_run: the goal and a lane's title held a key; the built record holds none, nor the repo's path."""
    from halo_harness.live import card_run
    with _home() as state:
        run_dir = seed_run(state.parent / "repo")
        built = json.dumps(card_run.build_run(state, run_dir))
        ctx.check("no key in the record (the goal and a lane's title held one)", FAKE_KEY not in built and FAKE_KEY[9:] not in built)
        ctx.check("where it stood, the redactor's mark", "<redacted>" in built)
        ctx.check("no repo path, worktree or branch", "secret-project" not in built and '"cwd"' not in built and "worker-1" not in built)


@test
def test_a_goal_runs_lane_ends_when_it_merged(ctx: Ctx):
    """From test_replay_run_time (3.4.1.1 defect 60; its route left with the old playback): the record gives each lane's
    states and the run's costs at their own times -- lane 1 written at +70 ends when it merged (+80)."""
    from halo_harness.live import card_run
    with _run() as (state, repo):
        p = card_run.build_run(state, card_run.find(repo, RUN))
        lane1 = next(a for a in p["agents"] if a["agent_id"] == "lane-1")
        ctx.check(f"lane 1 ends when it merged (+80), not when its piece was written (+70): {lane1['ended'] - TR}",
                  round(lane1["ended"] - TR) == 80)
        ends = {s["agent_id"]: round(s["t"] - TR) for s in p["states"] if s["state"] == "done"}
        ctx.check(f"its done state is at +80: {ends}", ends.get("lane-1") == 80)
        costs = [(round(c["t"] - TR), c["usd"]) for c in p["costs"]]
        ctx.check(f"its costs come at each end (the record's only times for them): {costs}", costs and costs[-1] == (90, 0.05))


@contextlib.contextmanager
def _private_home(where=None):
    """A scratch home in `where` with a made-up account (tests/test_privacy_scrub.py's names) in its environment."""
    from tests.test_privacy_scrub import MACHINE, NIX_HOME, USER, WIN_HOME
    env = {"USERPROFILE": WIN_HOME, "HOME": NIX_HOME, "USERNAME": USER, "USER": USER, "LOGNAME": USER, "COMPUTERNAME": MACHINE}
    saved = {k: os.environ.get(k) for k in ("BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR") + tuple(env)}
    with tempfile.TemporaryDirectory(prefix="halo-private-", dir=where) as d:
        os.environ["BRIDGE_TEST_HOME"] = d
        os.environ.pop("BRIDGE_STATE_DIR", None)
        os.environ.update(env)
        try:
            from halo_harness.config.paths import bridge_home
            yield bridge_home()
        finally:
            for k, v in saved.items():
                os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)


def _private(ctx: Ctx, where=None, label: str = "") -> None:
    """From test_replay_private (3.4.1.1 defect 56): a seeded home path, user name, machine name and key never reach the
    BUILT record; a path inside the project reads project-relative, any other under the home as ~/..."""
    from halo_harness.live import card_data
    from tests.test_privacy_scrub import MACHINE, NIX_HOME, USER, WIN_HOME
    with _private_home(where) as state:
        sub = seed(state).parent / SID / "subagents"
        proj = str(state.parent / "work" / "secret-project")  # the session's cwd (seed's meta)
        (Path(proj) / ".git").mkdir(parents=True, exist_ok=True)  # its own repo, wherever the scratch home lies
        said = f"read {WIN_HOME}\\Documents\\plan.md and {NIX_HOME}/notes, as {USER} on {MACHINE} {FAKE_KEY}"
        task = f"count lines of {proj}{os.sep}a.txt; {said}"
        for name in ("agent-scout1.meta.json", "agent-scout1.jsonl"):  # the task: the meta's and the first user line
            rows = [json.loads(x) for x in (sub / name).read_text(encoding="utf-8").splitlines() if x.strip()]
            rows[0].update({"description": task} if name.endswith(".meta.json") else {"content": task})
            (sub / name).write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
        p = card_data.build(state, SID)
        raw = json.dumps(p)
        for bad in (FAKE_KEY, USER, USER[:6], MACHINE, "Users\\\\" + USER, "/home/" + USER, proj,
                    proj.replace("\\", "\\\\"), str(state.parent).replace("\\", "\\\\"), "secret-project"):
            ctx.check(f"{label}{bad[:40]!r} is not in the built record", bad not in raw)
        got = next(a["task"] for a in p["agents"] if a["agent_id"] == "scout1")
        want = "count lines of a.txt; read ~/Documents/plan.md and ~/notes, as <user> on <machine>"
        # the task is an excerpt (200 characters of the model's words, live/history.py): how much of `want` it holds
        # depends on how long the scratch home's path was; it is `want` or a cut of it ending in "..."
        cut = got[:-3] if got.endswith("...") else None
        ctx.check(f"{label}the task (the model's words) reads project-relative, ~ and no names, got {got!r}",
                  got.startswith(want) or (cut is not None and (want.startswith(cut) or (
                      cut.endswith(("<user>", "<machine>")) and want.startswith(cut.rsplit(" ", 1)[0] + " ")))))
        ctx.check("the includes line says the limit",
                  any("relative to the project" in x and "where you typed it" in x for x in p["includes"]))


@test
def test_a_seeded_home_path_user_name_and_key_never_reach_the_built_record(ctx: Ctx):
    _private(ctx)


@test
def test_the_scratch_home_inside_a_repo_and_under_an_8_3_spelling(ctx: Ctx):
    """3.4.1.2: the gate puts TEMP under the real home (and a run may put it inside the project): the redaction does not
    depend on where the scratch home lies, nor on a short (8.3) spelling of its folder."""
    inside = ROOT / ".prepush" / "card-private-inside"
    inside.mkdir(parents=True, exist_ok=True)
    try:
        _private(ctx, str(inside), "inside the working tree: ")
    finally:
        import shutil
        shutil.rmtree(inside, ignore_errors=True)
    long_dir = Path(tempfile.mkdtemp(prefix="halo private long folder name "))
    try:
        short = str(long_dir)
        if os.name == "nt":
            import ctypes
            buf = ctypes.create_unicode_buffer(1024)
            if ctypes.windll.kernel32.GetShortPathNameW(str(long_dir), buf, 1024):
                short = buf.value
        _private(ctx, short, f"under {'an 8.3 spelling' if short != str(long_dir) else 'a long folder name'}: ")
    finally:
        import shutil
        shutil.rmtree(long_dir, ignore_errors=True)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
