"""tests.test_dialect -- Halo 3.3.6.0 R4 deliverable 2, the dialect record (providers/dialect.py, dialect_refine.py,
dialect_apply.py; stored at ollama.profiles["<host>|<model>"]["dialect"]) on a fixture home and profile:

1. the record from a battery profile: a weak system role -> user-turn, fences -> strip, thinking -> native and a
   reserve of at least 300, the reserve from the probes' longest answer, a printed end token -> a stop quirk,
   no tool calling -> tools_max 0, a JSON failure -> two repair attempts; each field's `from`;
2. the ledger's rules: a cut rate over 10 % of the last 20 calls raises the reserve one step, a loop seen turns the
   guard on; per ollama.steward.apply (auto writes `from: ledger`, review leaves a proposal, off nothing);
3. your edit always wins (marked `user`; the ledger never overwrites it); reset puts it back;
4. the applied body: stop quirks, the reserve floor, thinking off; the loop guard alone;
5. `halo models dialect` (--set, --reset, --json) and the Studio routes (GET / POST local/host/<n>/dialect,
   GET local/host/<n>/measured), a value that does not fit its field -> 422.
Run: python -m tests.test_dialect
"""
from __future__ import annotations

import sys
import time
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.logs_rig import LogsHome  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402
from tests.test_measured import BOX, _seed, profile  # noqa: E402

test, TESTS = new_registry()


def _ev(content: str, n: int = 60) -> dict:
    return {"content": content, "thinking": "", "tool_calls": [], "done_reason": "stop", "eval_count": n}


def _api(h, method, path, body=None, query=None):
    from halo_harness.studio.api import Request, dispatch
    return dispatch(Request(method=method, path=path, query=query or {}, body=body or {}, cwd=h.root, state_dir=h.state,
                            server=None))


@test
def test_the_record_from_a_profile(ctx: Ctx):
    from halo_harness.providers.dialect import from_profile, record
    with LogsHome(hosts=[BOX]) as h:
        p = profile("mute:24b", tools="no", output="prose", evidence={"json": _ev("{...}<|im_end|>", 700),
                                                                      "system": _ev("4", 3)})
        _seed(h.state, p)
        rec = record("box", "mute:24b", state_dir=h.state)
        ctx.check(f"weak system role -> user-turn (battery), got {rec['instruction_placement']} {rec['from']}",
                  rec["instruction_placement"] == "user-turn" and rec["from"]["instruction_placement"] == "battery")
        ctx.check(f"the reserve from the longest answer (700 x 2 -> 2048), got {rec['reply_reserve']}",
                  rec["reply_reserve"] == 2048)
        ctx.check(f"a printed end token is a stop quirk, got {rec['stop_quirks']}", rec["stop_quirks"] == ["<|im_end|>"]
                  and rec["from"]["stop_quirks"] == "battery")
        ctx.check(f"no tool calling -> tools_max 0, got {rec['tools_max']}", rec["tools_max"] == 0)
        ctx.check(f"a JSON failure -> two repair attempts, got {rec['json_repair']}", rec["json_repair"] == {"on": True, "attempts": 2})
        ctx.check(f"thinking -> native, got {rec['thinking']}", rec["thinking"] == "native" and rec["from"]["thinking"] == "battery")
        thinker, _src = from_profile(profile("t:27b", evidence={"json": _ev("x", 40)}))
        ctx.check(f"a thinking model's reserve is at least 300 (one step: 512), got {thinker['reply_reserve']}",
                  thinker["reply_reserve"] == 512)
        plain, src = from_profile(None)
        ctx.check(f"no profile: the defaults, from default, got {plain['instruction_placement']} {src['reply_reserve']}",
                  plain["instruction_placement"] == "system" and src["reply_reserve"] == "default"
                  and plain["loop_guard"] == {"on": False, "window": 40})


def _calls(h, model: str, n: int, cut: int = 0, loop: bool = False):
    now = time.time()
    for i in range(n):
        h.call(BOX, model, now - 200 + i, eval_tok_s=100.0, eval_count=100, kind="turn",
               done_reason="length" if i < cut else "stop", loop=loop and i == n - 1)


@test
def test_the_ledger_refines_it_per_the_apply_modes(ctx: Ctx):
    from halo_harness.providers.dialect import record, set_fields
    from halo_harness.providers.dialect_refine import refine
    from halo_harness.theme import set_config_value
    with LogsHome(hosts=[BOX]) as h:
        _seed(h.state, profile("cut:9b", reasoning="none", evidence={"json": _ev("x", 200)}))
        _calls(h, "cut:9b", 20, cut=3, loop=True)
        before = record("box", "cut:9b", state_dir=h.state)
        lines = refine("box", "cut:9b", state_dir=h.state, force=True)
        after = record("box", "cut:9b", state_dir=h.state)
        ctx.check(f"3 of 20 cut (15 %): the reserve one step up, got {before['reply_reserve']} -> {after['reply_reserve']}",
                  before["reply_reserve"] == 512 and after["reply_reserve"] == 1024 and after["from"]["reply_reserve"] == "ledger")
        ctx.check(f"a loop seen turns the guard on, got {after['loop_guard']}", after["loop_guard"]["on"] is True
                  and after["from"]["loop_guard"] == "ledger")
        ctx.check(f"each change said in one line, got {lines}", len(lines) == 2 and "3 of its last 20 replies were cut" in lines[0])
        ctx.check("refined at most once a minute", refine("box", "cut:9b", state_dir=h.state) == [])
        set_fields("box", "cut:9b", {"reply_reserve": 768}, by="user")
        _calls(h, "cut:9b", 20, cut=10)
        refine("box", "cut:9b", state_dir=h.state, force=True)
        mine = record("box", "cut:9b", state_dir=h.state)
        ctx.check(f"your edit wins: the ledger never raises a reserve you set, got {mine['reply_reserve']} {mine['from']}",
                  mine["reply_reserve"] == 768 and mine["from"]["reply_reserve"] == "user")
        _seed(h.state, profile("rev:9b", reasoning="none", evidence={"json": _ev("x", 200)}))
        _calls(h, "rev:9b", 20, cut=5)
        set_config_value("ollama.steward.apply", "review")
        said = refine("box", "rev:9b", state_dir=h.state, force=True)
        from halo_harness.ollama_steward.steward import read_journal
        props = [r for r in read_journal(h.state) if r.get("kind") == "proposal" and r.get("field") == "dialect"]
        ctx.check(f"review: a proposal, the record unchanged, got {said} {len(props)}",
                  "proposed" in said[0] and len(props) == 1 and record("box", "rev:9b", state_dir=h.state)["reply_reserve"] == 512
                  and props[0]["to"]["reply_reserve"] == 1024)
        set_config_value("ollama.steward.apply", "off")
        ctx.check("off: nothing", refine("box", "rev:9b", state_dir=h.state, force=True) == [])


@test
def test_the_applied_body_and_the_loop_guard(ctx: Ctx):
    from halo_harness.providers.dialect import set_fields
    from halo_harness.providers.dialect_apply import LoopGuard, apply_body, repair_attempts, strips
    with LogsHome(hosts=[BOX]) as h:
        _seed(h.state, profile("b:9b", reasoning="none", evidence={"json": _ev("ok<|eot_id|>", 900)}))
        set_fields("box", "b:9b", {"thinking": "off", "json_repair": {"on": False, "attempts": 1}, "strip_fences": False},
                   by="user")
        from halo_harness.model import parse_model_ref
        s = SimpleNamespace(model_ref=parse_model_ref("ol:b:9b@box"), state_dir=h.state, turn_count=1, settings=None,
                            route=SimpleNamespace(dialect="ollama"))
        body = apply_body(s, {"model": "b:9b", "options": {"num_ctx": 32768, "num_predict": 1024, "stop": ["</x>"]}})
        ctx.check(f"stop quirks added, the battery's reserve (2048) as a floor, think false, got {body}",
                  body["options"]["stop"] == ["</x>", "<|eot_id|>"] and body["options"]["num_predict"] == 2048
                  and body["think"] is False)
        kept = apply_body(s, {"model": "b:9b", "think": True, "options": {"num_predict": 4096}})
        ctx.check("a think the request set stays; a larger reserve stays", kept["think"] is True
                  and kept["options"]["num_predict"] == 4096)
        ctx.check("repair off -> 0 attempts; strip_fences off", repair_attempts(s) == 0 and strips(s) is False)
        cloud = SimpleNamespace(model_ref=parse_model_ref("or:anthropic/claude-haiku-4.5"), state_dir=h.state,
                                turn_count=1, settings=None)
        ctx.check("a cloud model's body is untouched", apply_body(cloud, {"max_tokens": 10}) == {"max_tokens": 10})
    g, words = LoopGuard(40), " ".join(f"w{i}" for i in range(40)) + " "
    got = None
    text = "Intro. " + words * 4
    for i in range(0, len(text), 25):
        got = g.feed(text[i:i + 25]) or got
        if got:
            break
    ctx.check(f"the same 40-token span three times stops it, the text cut after the first span, got {got} "
              f"{text[:g.cut_at][-12:]!r}", got == "stop" and g.cut_at is not None and "w39" in text[:g.cut_at])
    watch = LoopGuard(40, stop=False)
    ctx.check("a guard that is off only marks it", watch.feed(text) == "seen")
    ctx.check("ordinary prose never trips it", LoopGuard(40).feed(" ".join(f"t{i}" for i in range(600))) is None)


@test
def test_the_cli_and_the_studio_routes(ctx: Ctx):
    import json
    from halo_harness.catalog_cli import cmd_models
    with LogsHome(hosts=[BOX]) as h:
        _seed(h.state, profile("c:30b", evidence={"json": _ev("x", 100)}))
        code, text = h.cli(cmd_models, "dialect", "ol:c:30b@box")
        ctx.check(f"each field with its from, got {code} {text!r}", code == 0 and "instructions go in: user-turn (battery)" in text
                  and "loop guard: off, 40 tokens (default)" in text)
        code, text = h.cli(cmd_models, "dialect", "c:30b", "--host", "box", "--set", "reply_reserve=4096", "--set",
                           "loop_guard=on:60", "--set", "stop_quirks=<|end|>")
        ctx.check(f"--set marks them yours, got {code} {text!r}", code == 0 and "reply reserve (tokens): 4,096 (you" not in text
                  and "reply reserve (tokens): 4,096 (user)" in text and "loop guard: on, 60 tokens (user)" in text)
        code, text = h.cli(cmd_models, "dialect", "c:30b", "--host", "box", "--set", "thinking=sometimes")
        ctx.check(f"a value that does not fit: exit 2, the field's help, got {code} {text!r}", code == 2 and "thinking:" in text)
        code, text = h.cli(cmd_models, "dialect", "c:30b", "--host", "box", "--reset", "reply_reserve", "--json")
        rec = json.loads(text[text.index("{"):])
        ctx.check(f"--reset FIELD: the battery's again, the rest still yours, got {rec['from']}",
                  rec["from"]["reply_reserve"] == "battery" and rec["from"]["loop_guard"] == "user")
        code, got = _api(h, "GET", "local/host/box/dialect", query={"model": "c:30b"})
        ctx.check(f"GET dialect: the record, the view, the cli, got {code}", code == 200 and got["record"]["loop_guard"]["window"] == 60
                  and any(f["field"] == "tools_max" for f in got["view"]["fields"]) and got["cli"].startswith("halo models dialect"))
        code, got = _api(h, "POST", "local/host/box/dialect", body={"model": "c:30b", "set": {"instruction_placement": "system"}})
        ctx.check(f"POST set: yours, the cli line, got {code} {got.get('cli')}", code == 200
                  and got["record"]["instruction_placement"] == "system" and got["record"]["from"]["instruction_placement"] == "user"
                  and "--set instruction_placement=system" in got["cli"])
        code, got = _api(h, "POST", "local/host/box/dialect", body={"model": "c:30b", "set": {"reply_reserve": -3}})
        ctx.check(f"a bad value: 422 with the problem, got {code}", code == 422 and "reply_reserve" in got["error"])
        code, got = _api(h, "POST", "local/host/box/dialect", body={"model": "c:30b", "reset": ""})
        ctx.check(f"reset every field, got {got['record']['from']}", code == 200 and "user" not in got["record"]["from"].values())
        code, got = _api(h, "GET", "local/host/box/measured", query={"model": "c:30b"})
        ctx.check(f"GET measured, got {code} {got.get('lines')}", code == 200 and got["cli"] == "halo models measured c:30b --host box"
                  and any("187.5 tok/s" in x for x in got["lines"]))
        ctx.check("an unknown host: 404", _api(h, "GET", "local/host/nope/dialect", query={"model": "x"})[0] == 404)
        ctx.check("no model: 422", _api(h, "GET", "local/host/box/dialect")[0] == 422)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
