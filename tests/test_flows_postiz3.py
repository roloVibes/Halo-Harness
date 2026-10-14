"""tests.test_flows_postiz3 -- the watch poller, `halo flow posts|metrics`,
`halo postiz doctor` and the `every` validation (Halo 3.0.4.0 round R4).
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_scoped_state_dir_once

ensure_scoped_state_dir_once()

from tests.helpers import fake_postiz  # noqa: E402
from tests.helpers.fake_comfy import FakeComfy  # noqa: E402
from tests.helpers.fake_flow import FakeOrg, make_adapters  # noqa: E402
from tests.helpers.postiz_rig import (  # noqa: E402
    COPY4, FOUR, KEY, _cli, _fake, _go, _project, no_secret as _no_secret, spec_with as _spec)
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


@test
def test_watch_polls_on_the_interval(ctx: Ctx):
    from halo_harness.flows.postiz import PostizCli
    from halo_harness.flows.watch import watch_metrics
    d, log = _fake()
    with fake_postiz.put_on_path(d, key=KEY):
        run_dir, report = _go(_spec(True, every="2h"), platforms="x,tiktok", project="postiz-watch")
        before = len(_project(run_dir).metrics())
        slept, said = [], []
        t = [__import__("time").time()]

        def sleep(s):
            slept.append(s)
            t[0] += s
        polls = watch_metrics(run_dir, sleep=sleep, clock=lambda: t[0], say=said.append, max_polls=2, slice_s=3600)
        ctx.check(f"two polls, each after two hours of sleeping, got {polls} {slept}", polls == 2 and sum(slept) == 4 * 3600)
        ctx.check("each poll sampled both posts", len(_project(run_dir).metrics()) == before + 4 and "poll 2: 2 samples" in said)
        (run_dir / "stop.json").write_text(json.dumps({"reason": "enough"}), encoding="utf-8")
        said.clear()
        ctx.check("halo flow stop ends the watch", watch_metrics(run_dir, sleep=sleep, clock=lambda: t[0], say=said.append) == 0
                  and "metrics polling stopped" in said)
        (run_dir / "stop.json").unlink()
        t[0] += 8 * 86400
        ctx.check("past the step's days there is nothing to poll", watch_metrics(run_dir, sleep=sleep, clock=lambda: t[0], say=said.append) == 0)
    dry, _rep = _go(_spec(False), project="postiz-watch-dry")
    said = []
    ctx.check("dry-run posts have no metrics to poll", watch_metrics(dry, say=said.append) == 0 and said == ["dry run: no metrics to poll"])


@test
def test_cli_commands_and_doctor(ctx: Ctx):
    run_dir, _report = _go(_spec(False), platforms="x", project="postiz-cli")
    code, out, _ = _cli("flow", "posts", run_dir.name)
    ctx.check(f"posts on a dry run, got {out}", code == 0 and out.startswith("x: dry run;"))
    code, out, _ = _cli("flow", "metrics", run_dir.name)
    ctx.check(f"metrics on a dry run, got {out}", code == 0 and "dry run: no metrics" in out)
    ctx.check("an unknown run is an error", _cli("flow", "posts", "no-such-run")[0] == 2 and _cli("flow", "metrics", "nope")[0] == 2)
    with tempfile.TemporaryDirectory() as empty, fake_postiz.put_on_path(empty, exclusive=True):
        code, out, _ = _cli("postiz", "doctor")
        ctx.check(f"doctor without the CLI says so and exits 1, got {out}", code == 1 and "postiz CLI: not installed (npm i -g postiz)" in out
                  and "credentials: none" in out)
        code2, out2, err2 = _cli("flow", "metrics", run_dir.name)
        ctx.check("metrics on a dry run needs no CLI", code2 == 0)
    d, log = _fake(integrations=[{"id": "int-yt", "identifier": "youtube", "name": "Halo Channel", "disabled": False},
                                 {"id": "int-x", "identifier": "x", "name": "@halo", "disabled": True}])
    with fake_postiz.put_on_path(d, key=KEY, POSTIZ_API_URL="https://api.example"):
        code, out, _ = _cli("postiz", "doctor")
    ctx.check(f"doctor lists ids and platforms and never the key, got {out}", code == 0 and "credentials: found via POSTIZ_API_KEY" in out
              and "int-yt  youtube" in out and "(disabled)" in out and "platforms: youtube ok, instagram missing, x missing, tiktok missing" in out
              and KEY not in out and "api url: https://api.example" in out)
    with fake_postiz.put_on_path(d):
        code, out, _ = _cli("postiz", "doctor")
    ctx.check("the fake without a key: credentials none (or the real credentials file), exit follows", ("credentials: none" in out) == (code == 1))
    ctx.check("halo postiz with no subcommand prints usage", _cli("postiz")[0] == 0 and _cli("postiz", "bogus")[0] == 2)


@test
def test_validate_every_and_flow_help(ctx: Ctx):
    from halo_harness.flows.spec import validate_flow
    spec = _spec(False, every="soon")
    lines = validate_flow(spec)
    ctx.check(f"a bad every is an error line, got {lines}", any("every is a duration like 30m, 6h or 1d" in l for l in lines))
    ctx.check("6h and 90m validate", not [l for l in validate_flow(_spec(False, every="90m")) if "every" in l])
    code, out, _ = _cli("flow", "help")
    ctx.check("flow help lists posts and metrics", "halo flow posts <run>" in out and "halo flow metrics <run>" in out)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="flow postiz cli tests"))
