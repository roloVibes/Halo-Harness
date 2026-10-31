"""tests.test_models_vision_cli -- Halo 3.3.6.0 R6: which models can see, on the command line and in the doctor,
over the scripted fake Ollama (tests/helpers/mock_ollama_eyes.py):

1. `halo models --vision` lists the models that can see with the truth (verified after the probe, declared from
   /api/show), and how many say nothing; `--json`;
2. `halo models show` has the vision line with its truth;
3. the search's `vision` need (`halo models browse --need vision`) reads the same fact: a declared no and an
   unknown never pass, a verified yes passes at `verified`;
4. `halo doctor --local`: a `visual` lane on a model the probe found blind is a WARN with the fix.
Run: python -m tests.test_models_vision_cli
"""
from __future__ import annotations

import contextlib
import io
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials  # noqa: E402
ensure_default_provider_credentials()

from tests.helpers.battery_rig import BatteryRig  # noqa: E402
from tests.helpers import mock_ollama_eyes as ME  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


def _rig():
    rig = BatteryRig(["bt-coder:30b"]).__enter__()
    ME.add(rig.mock, ["ey-sees:7b", "ey-blind:7b", "ey-text:7b", "ey-old:7b"])
    return rig


def _run(argv) -> "tuple[int, str]":
    from halo_harness.catalog_cli import cmd_models
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = cmd_models(argv)
    return rc, buf.getvalue()


@test
def test_halo_models_vision_and_show(ctx: Ctx):
    rig = _rig()
    try:
        rc, out = _run(["--vision"])
        ctx.check(f"exit 0, got {rc}", rc == 0)
        ctx.check(f"declared from /api/show before a probe, got {out!r}", "ol:ey-sees:7b@fake: sees (declared: /api/show capabilities)" in out)
        ctx.check("a model that says no is not listed", "ey-text:7b" not in out.replace("say nothing", ""))
        rig.probe("ey-sees:7b")
        rig.probe("ey-blind:7b")
        from halo_harness.providers import local_models_cached
        getattr(local_models_cached, "forget", lambda: None)()
        rc, out = _run(["--vision"])
        ctx.check(f"verified after the probe, got {out!r}", "ol:ey-sees:7b@fake: sees (verified: the battery's image probe" in out
                  and "ey-blind:7b@fake: sees" not in out)
        ctx.check(f"the count line names the ones that say nothing, got {out.splitlines()[-1]!r}",
                  "can see images" in out.splitlines()[-1] and "halo models probe <ref> settles it" in out.splitlines()[-1])
        rc, js = _run(["--vision", "--json"])
        got = json.loads(js)
        ctx.check(f"--json, got {sorted(got)}", sorted(got) == ["sees", "unknown"]
                  and any(r["ref"] == "ol:ey-sees:7b@fake" and r["truth"] == "verified" for r in got["sees"]))
        rc, show = _run(["show", "ol:ey-blind:7b@fake"])
        line = next((x for x in show.splitlines() if x.strip().startswith("vision:")), "")
        ctx.check(f"show has the line with its truth, got {line!r}", line.strip().startswith("vision: no, verified (the battery's image probe"))
        ctx.check("and the card's don't block", "cannot see images" in show)
    finally:
        rig.__exit__(None, None, None)


@test
def test_the_search_need_reads_the_same_fact(ctx: Ctx):
    from halo_harness.models_library.search import gate, norm_needs
    from halo_harness.models_library.truths import facts_for_row
    need = norm_needs(["vision"])
    probe_yes = {"vision": "yes", "probed_at": 1.0}
    yes, _t, lines = gate(facts_for_row({"name": "x:7b"}, {"name": "x:7b"}, probe_yes), need)
    ctx.check(f"a verified yes passes, got {lines}", yes and lines == ["vision verified"])
    strict = norm_needs(["vision=verified"])
    ctx.check("a declared yes is under a verified floor", not gate(facts_for_row(
        {"name": "x:7b", "source": "ollama", "capabilities": ["vision"]}, {"name": "x:7b"}, None), strict)[0])
    ctx.check("a declared no never passes", not gate(facts_for_row(
        {"name": "x:7b", "source": "ollama", "capabilities": ["tools"]}, {"name": "x:7b"}, None), need)[0])
    ctx.check("nothing says: no pass", not gate(facts_for_row({"name": "mystery:7b"}, {"name": "mystery:7b"}, None), need)[0])
    ctx.check("the family rule passes at expected", gate(facts_for_row({"name": "llava:13b"}, {"name": "llava:13b"}, None), need)[0])


@test
def test_doctor_warns_on_a_blind_visual_lane(ctx: Ctx):
    from halo_harness.doctor_local import format_acceptance_lines
    from halo_harness.doctor_local_roles import role_steps
    rig = _rig()
    try:
        rig.probe("ey-blind:7b")
        rig.probe("ey-sees:7b")
        steps = role_steps(rig.state, role_table={"visual": "ol:ey-blind:7b@fake", "eyes": "ol:ey-sees:7b@fake"}, main_ref="")
        lines = format_acceptance_lines(steps)
        warn = [x for x in lines if x.startswith("[WARN] role visual")]
        ctx.check(f"a WARN with the fix, got {lines}", warn and "cannot see images (verified" in warn[0]
                  and "halo models --vision" in warn[0])
        ctx.check("it does not fail the run", all(s["ok"] for s in steps))
        ctx.check(f"a lane that sees passes, got {lines}", any(x.startswith("[PASS] role eyes") for x in lines))
    finally:
        rig.__exit__(None, None, None)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
