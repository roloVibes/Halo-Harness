"""tests.test_replay_clip_pillow -- a replay clip with and without Pillow (Halo 3.4.1.0 R6; split from
tests/test_replay_file.py for the 250-line cap). The CI runners had no Pillow and the clip's PLAN answered 422 there:
saying what a clip will write needs no imaging library, only the encode does. Pillow is hidden for a block
(tests/helpers/no_pillow.py), so a box that has it proves both paths:

1. live/replay_clip.py: `encoder()` says Pillow is missing with the install line, `plan()` still plans, `clip()` refuses
   in that one line before it films or writes anything; with Pillow there the encoder can write;
2. `halo replay clip`: `--dry-run` plans and says what to install (exit 0); the clip itself is that line, exit 2,
   nothing written;
3. Studio's `GET replays/<id>/clip` answers 200 with `pillow` / `needs` (never a 422 for a plan); `POST` is 422 with
   the line and writes nothing.
Run: python -m tests.test_replay_clip_pillow
"""
from __future__ import annotations

import contextlib
import io
import os
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.no_pillow import has_pillow, no_pillow  # noqa: E402
from tests.helpers.replay_seed import SID, T0, seed  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
INSTALL = 'uv tool install "halo-harness[images]"'


@contextlib.contextmanager
def _saved():
    """A scratch home with the seeded session saved as a replay file: (state, its id)."""
    saved = {k: os.environ.get(k) for k in ("BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR")}
    with tempfile.TemporaryDirectory(prefix="halo-clip-pil-") as d:
        os.environ["BRIDGE_TEST_HOME"] = d
        os.environ.pop("BRIDGE_STATE_DIR", None)
        try:
            from halo_harness.config.paths import bridge_home
            from halo_harness.live import replay_file as RF
            state = bridge_home()
            seed(state)
            yield state, RF.save(state, RF.build(state, SID)).name[:-len(RF.SUFFIX)]
        finally:
            for k, v in saved.items():
                os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)


def _err(fn):
    try:
        fn()
    except Exception as e:
        return e
    return None


@test
def test_the_plan_needs_no_pillow_and_the_encode_says_so(ctx: Ctx):
    from halo_harness.live import replay_clip as C
    with _saved() as (state, rid):
        with no_pillow():
            enc = C.encoder()
            ctx.check(f"the encoder says Pillow is missing, with the install line, got {enc}",
                      enc["pillow"] is False and "needs Pillow" in enc["needs"] and INSTALL in enc["needs"])
            ctx.check("the plan still says the frames", C.plan({"started": T0, "ended": T0 + 600}, 60, 120, 4)["frames"] == 76)
            filmed: list = []
            err = _err(lambda: C.clip(state, rid, 0, 100, 16, frames=lambda t: filmed.append(t) or []))
            ctx.check(f"the encode refuses in that line before filming or writing, got {err!r}",
                      isinstance(err, C.ClipError) and "needs Pillow" in str(err) and not filmed
                      and not (state / "replays" / "clips").exists())
        ctx.check(f"Pillow back as it was here ({has_pillow()}): the encoder says so", C.encoder()["pillow"] is has_pillow())


def _cli(argv: list) -> "tuple[int, str]":
    from halo_harness.replay_cli import cmd_replay
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
        try:
            code = cmd_replay(argv)
        except SystemExit as e:
            code = e.code
    return int(code or 0), out.getvalue()


@test
def test_halo_replay_clip_without_pillow(ctx: Ctx):
    with _saved() as (state, rid), no_pillow():
        code, text = _cli(["clip", rid, "--from", "0:10", "--to", "90", "--speed", "4", "--dry-run"])
        ctx.check(f"--dry-run plans and says what to install: {text!r}",
                  code == 0 and "1200 px" in text and "from 10 s to 90 s" in text and "needs Pillow" in text and INSTALL in text)
        code, text = _cli(["clip", rid, "--from", "0:10", "--to", "90", "--speed", "4"])
        ctx.check(f"the clip itself is that line, exit 2, nothing written: {text!r}",
                  code == 2 and "needs Pillow" in text and not (state / "replays" / "clips").exists())


@test
def test_studio_plans_a_clip_without_pillow(ctx: Ctx):
    from halo_harness.studio.replays_api import dispatch_replays
    with _saved() as (state, rid):
        server = SimpleNamespace(server_address=("127.0.0.1", 1), token="t", cwd=state, state_dir=state)

        def call(method, path, query=None, body=None):
            return dispatch_replays(SimpleNamespace(method=method, path=path, query=query or {}, body=body, state_dir=state,
                                                    cwd=state, server=server, params={}))
        code, plan = call("GET", f"replays/{rid}/clip", {"from": "0", "to": "100", "speed": "16"})
        ctx.check(f"with Pillow as it is here ({has_pillow()}): the plan says whether Export can encode, got {code}",
                  code == 200 and plan["pillow"] is has_pillow() and plan["path"].endswith((".webp", ".gif")))
        with no_pillow():
            code, plan = call("GET", f"replays/{rid}/clip", {"from": "0", "to": "100", "speed": "16"})
            ctx.check(f"no Pillow: still a plan, with what to install: {code} {plan.get('needs')!r}",
                      code == 200 and plan["frames"] == 33 and plan["width"] == 1200 and plan["pillow"] is False
                      and INSTALL in plan["needs"])
            code, got = call("POST", f"replays/{rid}/clip", body={"from": 0, "to": 100, "speed": 16})
            ctx.check(f"no Pillow: Export says what it needs and writes nothing: {code} {got}",
                      code == 422 and "needs Pillow" in got["error"] and not (state / "replays" / "clips").exists())


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="replay clip pillow"))
