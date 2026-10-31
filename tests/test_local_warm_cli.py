"""tests.test_local_warm_cli -- Halo 3.3.7.0 R3: `halo local warm [<lineup>]` (local_warm_cli.py) over a fake Ollama
on 127.0.0.1:0 (tests/helpers/sched_rig.SchedHome) and, for the host path, R2's PeerRig:

1. the lineup's warm set: what is not resident is loaded at its lane's window (one row each, the seconds), what is
   already loaded says "already warm", a model that cannot co-reside "pivots later" with its load time; the total;
2. `--dry` loads nothing; `warm:` in the lineup file goes first; a bad `warm:` is a validator line;
3. no lineup named and none in force: the 2.0.7 form (model names) still runs;
4. host-served: the loads go through the host's `warm` operation, the second one `beside`;
5. Studio: GET local/sched (the swap preview + the Warm rows), POST local/warm, GET local/warm-set (the Hosts card).
Nothing leaves 127.0.0.1; no model is called.
Run: python -m tests.test_local_warm_cli
"""
from __future__ import annotations

import contextlib
import io
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402
from tests.helpers.sched_lineup import write  # noqa: E402
from tests.helpers.sched_rig import BIG, CODER, TINY, SchedHome, ps_row  # noqa: E402

test, TESTS = new_registry()
LANES = {"coder": f"ol:{CODER}@pc", "small": f"ol:{TINY}@pc", "reviewer": f"ol:{BIG}@pc"}


def _run(argv) -> "tuple[int, str]":
    from halo_harness.local_warm_cli import cmd_warm
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        rc = cmd_warm(argv)
    return rc, out.getvalue()


@test
def test_the_lineups_warm_set_is_loaded_and_said(ctx: Ctx):
    with SchedHome(loaded=[ps_row(TINY, 1.0)]) as h:
        h.config(model=f"ol:{CODER}@pc")
        write(h.state, "loc", LANES)
        rc, text = _run(["loc"])
        ctx.check(f"exit 0 and the warm line first, got {rc} {text!r}", rc == 0 and text.startswith(
            "warm on pc: qwen3-coder:30b (main, coder), qwen2.5:1.5b (small) -- 20.8 of 21.5 GB"))
        ctx.check("the coder loaded at its window, with its seconds",
                  "qwen3-coder:30b (main, coder): loaded in " in text and "at 32,768" in text)
        ctx.check("the helper already warm", "qwen2.5:1.5b (small): already warm" in text)
        ctx.check("the 27 B pivots later, its load time and why", "qwen3.8:27b (reviewer): pivots later (~24 s, an "
                  "estimate from the weights" in text and "does not fit beside" in text)
        ctx.check(f"the total, got {text.splitlines()[-1]!r}", text.splitlines()[-1].startswith(
            "halo local warm loc: 1 loaded in ") and text.splitlines()[-1].endswith(", 1 already warm, 1 pivot later"))
        gen = [(g["model"], (g.get("options") or {}).get("num_ctx")) for g in h.mock.generated]
        ctx.check(f"one load on the fake, at the window, got {gen}", gen == [(CODER, 32768)])
        from halo_harness.local_sched.loads import _own
        ctx.check("the load is kept for the loading tax", any(r["model"] == CODER and r["why"] == "warm"
                                                              for r in _own(h.state, None)))


@test
def test_dry_warm_list_and_the_validator(ctx: Ctx):
    from halo_harness.teams_yaml import resolve_team_template, validate_team_template
    with SchedHome() as h:
        h.config(model=f"ol:{CODER}@pc")
        write(h.state, "loc", LANES, warm=["reviewer"])
        rc, text = _run(["loc", "--dry"])
        ctx.check(f"--dry loads nothing, says what it would, got {text!r}", rc == 0 and not h.mock.generated
                  and "qwen3.8:27b (reviewer): would load at 32,768" in text)
        ctx.check("the declared warm set went first: the coder pivots", "qwen3-coder:30b (main, coder): pivots later" in text)
        t = resolve_team_template("loc")
        ctx.check(f"`warm:` survives the resolve, got {t.get('warm')}", t.get("warm") == ["reviewer"])
        bad = validate_team_template({**t, "warm": "coder"}, name="loc")
        ctx.check(f"a bad `warm:` is one line, got {bad}", any('"warm" must be a list' in p for p in bad))


@test
def test_model_names_keep_the_207_form(ctx: Ctx):
    from tests.helpers.mock_ollama import MockUpstream, send_json
    def one_shot(handler, body):
        send_json(handler, 200, {"message": {"role": "assistant", "content": "hi"}, "done": True})
    with SchedHome() as h:
        mock = MockUpstream(scenarios={"qwen3:30b": one_shot}).start()
        try:
            h.config(**{"ollama.hosts": [{"name": "box", "url": mock.base_url}]})
            rc, text = _run(["qwen3:30b", "--keep-alive", "-1"])
        finally:
            mock.stop()
        ctx.check(f"a model name warms the model (one /api/chat), got {rc} {text!r}",
                  rc == 0 and "qwen3:30b: warmed (keep_alive=-1)" in text)


@test
def test_a_host_served_warm_set_goes_through_the_host(ctx: Ctx):
    from halo_harness.local_warm_cli import warm_lineup
    from tests.helpers.host_act_rig import PeerRig
    from tests.helpers.sched_rig import rows
    from halo_harness.studio import ollama_hosts_view as V
    from tests.helpers.steward_seed import card
    with PeerRig(card=card(total_mib=32000, kv="q8_0")) as rig:
        r = rows()
        V.READERS.update(card=lambda host: card(total_mib=32000, kv="q8_0"), catalog=lambda host: {"models": list(r.values())})
        try:
            from halo_harness.theme import set_config_value
            set_config_value("model", f"ol:{CODER}@pc")
            write(rig.peer, "loc", {"small": f"ol:{SMALL_9B}@pc"})
            got = warm_lineup("loc")
        finally:
            V.READERS.clear()
            V.reset_cache()
        gen = [g["model"] for g in rig.mock.generated]
        states = [x["state"] for x in got["hosts"][0]["rows"]] if got["hosts"] else []
        ctx.check(f"both loaded through the host's warm, got {got['line']} {states} {gen}",
                  states == ["loaded", "loaded"] and gen == [CODER, SMALL_9B])
        from halo_harness.host.state import read_audit
        warms = [a for a in read_audit(rig.home) if str(a.get("path") or "").endswith("control/warm")]
        ctx.check(f"two warm requests in the host's audit, got {len(warms)}", len(warms) == 2)


SMALL_9B = "qwen3.5:9b"


@test
def test_studio_routes(ctx: Ctx):
    from halo_harness.studio.api import Request, dispatch
    with SchedHome() as h:
        h.config(model=f"ol:{CODER}@pc", team="loc")
        write(h.state, "loc", LANES)
        ask = lambda m, p, q=None, b=None: dispatch(Request(method=m, path=p, query=q or {}, body=b or {},  # noqa: E731
                                                            cwd=Path(h.root), state_dir=h.state, server=None))
        code, got = ask("GET", "local/sched", {"lineup": "loc"})
        ctx.check(f"the swap preview, got {code} {got.get('lines')}", code == 200 and got["swaps"] == 2
                  and got["lines"][-1].startswith("this lineup swaps 2x on one card ~ "))
        code, got = ask("GET", "local/warm-set", {"host": "pc"})
        ctx.check(f"the Hosts card's line for the active lineup, got {got}", code == 200 and got["line"].startswith(
            "warm on pc: qwen3-coder:30b (main, coder), qwen2.5:1.5b (small) -- 20.8 of 21.5 GB"))
        code, got = ask("POST", "local/warm", b={"lineup": "loc"})
        ctx.check(f"Warm starts, got {code} {got}", code == 200 and got["ok"])
        end = time.monotonic() + 10
        run: dict = {}
        while time.monotonic() < end:
            run = ask("GET", "local/sched", {"lineup": "loc"})[1].get("warm_run") or {}
            if run and not run.get("running"):
                break
            time.sleep(0.1)
        ctx.check(f"the Warm rows land, got {run}", run.get("line", "").startswith("halo local warm loc: 2 loaded in")
                  and any("loaded in" in x for x in run.get("rows") or []))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
