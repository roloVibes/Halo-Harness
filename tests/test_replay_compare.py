"""tests.test_replay_compare -- Halo 3.4.1.0 R2 "Time": compare two runs (live/compare.py, compare_text.py): the rows
from two seeded records with the better figure named by a word, a cost Halo cannot price never marked, "what
differed" in three plain lines, a run compared with itself before / after its steer, a file saved before R2, `halo
replay compare` and Studio's `GET replays/compare` (a mission is compared from its report).

Seeds: tests/helpers/replay_seed.py (session A: 100 s, $0.03, a failed sub-agent, two asks) and
tests/helpers/compare_seed.py (session B: 60 s, $0.012 + an unpriced call, glm-5.3, a steer at +30 s; a goal run:
90 s, $0.05, glm-5.3 for lane 1). Run: python -m tests.test_replay_compare
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.compare_seed import RUN, SID_B, seed_b, seed_run  # noqa: E402
from tests.helpers.replay_seed import SID, seed  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


@contextlib.contextmanager
def _home(priced: bool = False):
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
    from halo_harness.live import compare
    pa = compare.resolve(state, a, cwd=repo)
    return compare.compare(pa, pa if a == b else compare.resolve(state, b, cwd=repo), same=a == b, **kw)


def _rows(got: dict) -> dict:
    return {r["key"]: r for r in got["rows"]}


@test
def test_rows_name_the_better_figure_with_a_word(ctx: Ctx):
    with _home() as (state, repo):
        got = _cmp(state, repo, f"session:{SID}", f"run:{RUN}")
        r = _rows(got)
        ctx.check(f"the rows in order: {[x['key'] for x in got['rows']]}",
                  [x["key"] for x in got["rows"]] == ["ended", "wall", "cost", "tokens", "models", "agents", "asks", "failures", "retries"])
        ctx.check(f"cost: A $0.0300 cheaper than B $0.0500: {r['cost']}", r["cost"]["better"] == "a" and r["cost"]["word"] == "cheaper"
                  and r["cost"]["a"]["text"] == "$0.0300" and r["cost"]["b"]["text"] == "$0.0500")
        ctx.check(f"wall time: B faster (1 min 30 s): {r['wall']['b']}", r["wall"]["better"] == "b" and r["wall"]["word"] == "faster" and r["wall"]["b"]["text"] == "1 min 30 s")
        ctx.check("asks: B fewer (one plan review against a card and a question)", r["asks"]["better"] == "b" and r["asks"]["a"]["value"] == 2 and r["asks"]["b"]["value"] == 1)
        ctx.check("failures: the same (one each), said", r["failures"]["better"] == "same" and r["failures"]["word"] == "same")
        ctx.check("retries: A fewer (B's lane sent back once)", r["retries"]["better"] == "a" and r["retries"]["b"]["value"] == 1)
        ctx.check("models and agents are not better or worse", r["models"]["better"] is None and r["agents"]["better"] is None)
        ctx.check(f"each model's share of cost and time: {r['models']['b']['text']}", r["models"]["b"]["text"].startswith("glm-5.3: 60 % of cost, 35 % of time"))
        ctx.check("tokens unknown on both: not compared, said", r["tokens"]["better"] is None and r["tokens"]["word"] == "unknown")
        ctx.check(f"the time axis spans the longer run: {got['axis']}", got["axis"]["secs"] == 100)
        lanes = {(l["agent_id"], l["block"]) for l in got["b"]["lanes"]}
        ctx.check(f"each agent a lane in its block: {lanes}", lanes == {("lead", "goal run"), ("lane-1", "goal run"), ("lane-2", "goal run")})
        ctx.check("a lane carries its phase segments", any(s["phase"] == "writing" for l in got["b"]["lanes"] for s in l["segs"]))


@test
def test_a_cost_halo_cannot_price_is_never_marked(ctx: Ctx):
    with _home() as (state, repo):
        r = _rows(_cmp(state, repo, SID, SID_B))
        ctx.check(f"B's priced part with a +, never $0: {r['cost']['b']}", r["cost"]["b"]["text"] == "$0.0120+" and r["cost"]["b"]["unknown"])
        ctx.check("the better cost is not marked where a side is unknown", r["cost"]["better"] is None and r["cost"]["word"] == "unknown")
    with _home(priced=True) as (state, repo):
        r = _rows(_cmp(state, repo, SID, SID_B))
        ctx.check(f"once every call is priced it is compared: {r['cost']}", r["cost"]["better"] == "b" and r["cost"]["word"] == "cheaper")
    from halo_harness.live.compare_text import cells
    c = cells({"cost_usd": 0.0, "cost_known": False, "cost_unknown": ["or:x/free"], "models": []})["cost"]
    ctx.check(f"nothing priced: unknown, not $0: {c}", c["text"].startswith("unknown") and "$0" not in c["text"] and c["value"] is None)


@test
def test_what_differed_in_three_plain_lines(ctx: Ctx):
    with _home() as (state, repo):
        got = _cmp(state, repo, SID, RUN)
        lines = got["differed"]
        ctx.check(f"three lines: {lines}", len(lines) == 3 and all(isinstance(x, str) and x.endswith(".") for x in lines))
        ctx.check("the cost difference in words", any("A cost 40 % less ($0.0300 against $0.0500)" in x for x in lines))
        ctx.check("the model only B used, with its share", any(x.startswith("B used glm-5.3 (60 % of its cost)") for x in lines))
        same = _cmp(state, repo, f"file:{_saved(state, repo)}", f"run:{RUN}")["differed"]
        ctx.check(f"a run against its own saved file: the same figures, still three lines: {same}",
                  len(same) == 3 and same[0].startswith("The same for both:"))


def _saved(state, repo) -> str:
    from halo_harness.live import replay_file as RF
    from halo_harness.live import replay_run
    return RF.save(state, replay_run.build_run(state, replay_run.find(repo, RUN))).name[: -len(RF.SUFFIX)]


@test
def test_a_run_compared_with_itself_before_and_after_its_steer(ctx: Ctx):
    with _home() as (state, repo):
        got = _cmp(state, repo, SID_B, SID_B)
        r = _rows(got)
        ctx.check(f"split at its steer (+30 s): {got['split']}", got["split"] == 30)
        ctx.check(f"A is before, B from it on: {got['a']['title']!r} / {got['b']['title']!r}",
                  "before 30 s" in got["a"]["title"] and "from 30 s on" in got["b"]["title"] and got["a"]["figures"]["window"] == [0, 30])
        ctx.check("a shorter stretch is not 'faster'", r["wall"]["better"] is None and r["wall"]["word"] == "")
        ctx.check(f"the unpriced call fell before: A {r['cost']['a']['text']}, B {r['cost']['b']['text']}",
                  r["cost"]["a"]["text"] == "$0.0120+" and r["cost"]["b"]["text"] == "$0.0000" and r["cost"]["better"] is None)
        ctx.check("the reviewer was spawned before the steer", r["agents"]["a"]["value"] == 1 and r["agents"]["b"]["value"] == 0)
        moved = _cmp(state, repo, SID_B, SID_B, split=10)
        ctx.check(f"split where asked: {moved['split']}", moved["split"] == 10 and moved["b"]["figures"]["window"] == [10, 60])


@test
def test_a_file_saved_before_r2_still_compares(ctx: Ctx):
    from halo_harness.live import compare
    from halo_harness.live import replay_file as RF
    with _home() as (state, repo):
        p = RF.build(state, SID)
        p.pop("facts")
        p["id"] = "r1-file"
        RF.save(state, p)
        got = compare.compare(compare.resolve(state, "file:r1-file"), compare.resolve(state, SID, cwd=repo))
        r = _rows(got)
        ctx.check(f"its cost from the file, each model's from its agents: {r['models']['a']['text']}",
                  r["cost"]["a"]["text"] == "$0.0300" and r["models"]["a"]["text"].startswith("lead: 67 % of cost"))
        ctx.check("retries and tokens it never held are unknown", r["retries"]["a"]["text"] == "unknown" and r["tokens"]["a"]["text"] == "unknown")


def _cli(argv: list, cwd: Path) -> "tuple[int, str]":
    from halo_harness.replay_cli import cmd_replay
    out = io.StringIO()
    os.chdir(cwd)
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
        try:
            code = cmd_replay(argv)
        except SystemExit as e:
            code = e.code
    return int(code or 0), out.getvalue()


@test
def test_halo_replay_compare(ctx: Ctx):
    with _home() as (state, repo):
        code, text = _cli(["compare", SID, RUN], repo)
        ctx.check(f"two columns of rows, the word, what differed: {text!r}", code == 0 and "A: session" in text and "B: run" in text
                  and "[A cheaper]" in text and "What differed:" in text and text.count("\n  - ") == 3)
        code, text = _cli(["compare", SID_B, SID_B, "--split", "0:20", "--json"], repo)
        got = json.loads(text)
        ctx.check("--json: the rows as data, split where asked", code == 0 and got["split"] == 20 and len(got["rows"]) == 9 and len(got["differed"]) == 3)
        code, text = _cli(["save", RUN, "--dry-run"], repo)
        ctx.check(f"save takes a goal run id: {text!r}", code == 0 and f"The replay of {RUN} holds:" in text and "Would write" in text)
        code, text = _cli(["compare", "nope", SID], repo)
        ctx.check(f"an unknown run: one line, exit 2: {text!r}", code == 2 and "'nope' is not a session" in text)


@test
def test_studio_compare_route(ctx: Ctx):
    from halo_harness.studio.replays_api import dispatch_replays
    with _home() as (state, repo):
        def call(query):
            req = SimpleNamespace(method="GET", path="replays/compare", query=query, body=None, state_dir=state, cwd=repo, server=None, params={})
            return dispatch_replays(req)
        code, got = call({"a": f"session:{SID}", "b": f"run:{RUN}"})
        ctx.check(f"the comparison: {code}", code == 200 and got["a"]["kind"] == "session" and got["b"]["kind"] == "run" and len(got["differed"]) == 3)
        code, got = call({"a": f"session:{SID_B}", "b": f"session:{SID_B}", "split": "20"})
        ctx.check("one ref twice: before / after", code == 200 and got["split"] == 20)
        code, got = call({"a": "mission:m-1", "b": f"session:{SID}"})
        ctx.check(f"a mission is compared from its report: {got}", code == 422 and "from its report" in got["error"])
        ctx.check("one ref only: 422", call({"a": f"session:{SID}"})[0] == 422)
        ctx.check("an unknown ref: 404", call({"a": "session:nope", "b": f"session:{SID}"})[0] == 404)
        ctx.check("nothing written", not (state / "replays").exists())


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="replay compare"))
