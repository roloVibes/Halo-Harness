"""tests.test_review2_round5 -- pins for the vibes/review.md findings fixed
in the final round (R9/R10 slice):

  * f48  slash-command $-substitution: one pass, no re-scan of inserted
        args, single-quoted spans literal, $ARGUMENTS[N] implemented
  * f50b the Bash concurrent-batch whitelist drops env/find, and git
        branch/tag are list-form only
  * f59  resolve_role_ref: `inherit`/unresolvable values fall back to the
        session model instead of raising (the judge always said
        "confident")
  * f63  cron: dow 7 is Sunday; dom/dow OR when both restricted
  * f81  preflight: HALO_MODEL/routes.json identify the lane; no lane
        identified is a loud failure, not a vacuous PASS
  * pyflakes full-package undefined-names gate (the CI step's own check)
"""
from __future__ import annotations

import datetime
import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all
from tests.helpers.provider_env_defaults import ensure_default_provider_credentials

ensure_default_provider_credentials()

test, TESTS = new_registry()

REPO = Path(__file__).resolve().parent.parent


# ---- f48: substitution ----


@test
def test_f48_substitution_single_pass_and_quotes(ctx: Ctx):
    from halo_harness.commands.registry import substitute_arguments
    out = substitute_arguments("echo $ARGUMENTS", "a b c d $5 x")
    ctx.check("a $5 inside the user's args survives", "$5" in out)
    out2 = substitute_arguments("awk '{print $1}' $0", "file.txt")
    ctx.check("awk $1 inside single quotes stays literal", "$1" in out2 and "file.txt" in out2)
    ctx.check("$ARGUMENTS[2] implemented", substitute_arguments("run $ARGUMENTS[2] now", "a b c") == "run c now")
    ctx.check("$0/$1 still tokenize", substitute_arguments("one=$0 two=$1", "x y") == "one=x two=y")
    ctx.check("no placeholder appends ARGUMENTS", "ARGUMENTS:" in substitute_arguments("hi", "zzz"))


# ---- f50b: the concurrent-batch whitelist ----


@test
def test_f50b_bash_batch_whitelist(ctx: Ctx):
    from halo_harness.tools.bash import bash_command_is_read_only as ro
    ctx.check("env no longer batch-read-only", not ro("env"))
    ctx.check("env NAME=x cmd not batch-read-only", not ro("FOO=1 env"))
    ctx.check("find -delete not batch-read-only", not ro("find . -delete"))
    ctx.check("find -exec not batch-read-only", not ro("find . -exec rm {} +"))
    # round-6-ci-red finding 4: finding 50's first cut dropped `find`
    # ENTIRELY, not just its mutating/executing flags -- too broad (it
    # also blocked the overwhelming majority of `find` calls that only
    # ever print matches). Restored: read-only unless a mutating/
    # executing flag (`-delete`/`-exec`/... , both checked above) is
    # present.
    ctx.check("plain find (no mutating/executing flag) IS batch-read-only", ro("find . -name x"))
    ctx.check("git branch <name> not batch-read-only", not ro("git branch newb"))
    ctx.check("git branch -d not batch-read-only", not ro("git branch -d x"))
    ctx.check("git tag -d not batch-read-only", not ro("git tag -d v1"))
    ctx.check("git branch -l still batch-read-only", ro("git branch -l"))
    ctx.check("git tag (list) still batch-read-only", ro("git tag"))
    ctx.check("cat still batch-read-only", ro("cat notes.txt"))


# ---- f59: resolve_role_ref never raises on inherit/unresolvable ----


@test
def test_f59_resolve_role_ref_inherit(ctx: Ctx):
    from halo_harness.roles import resolve_role_ref

    class FakeRef:
        raw = "or:test/model"

    class FakeProfile:
        pass

    parent_ref, parent_profile = FakeRef(), FakeProfile()
    # `inherit` never resolves -> the session-model fallback path
    ref, _profile, _effort, source = resolve_role_ref(
        "judge", role_table={"judge": "inherit"}, parent_ref=parent_ref,
        parent_profile=parent_profile, state_dir=None)
    ctx.check("'inherit' falls back to the session model",
              ref is parent_ref and "session model" in source)
    # `haiku` resolves on a configured box and must simply not RAISE on
    # one where it can't (the review's env) -- assert no-raise either way
    try:
        resolve_role_ref("judge", role_table={"judge": "haiku"}, parent_ref=parent_ref,
                         parent_profile=parent_profile, state_dir=None)
        ctx.check("'haiku' never raises (resolves or falls back)", True)
    except Exception as e:
        ctx.check(f"'haiku' never raises (raised {type(e).__name__})", False)


# ---- f63: cron Sunday and dom/dow OR ----


@test
def test_f63_cron_sunday_and_day_or(ctx: Ctx):
    from halo_harness.agents_schedule import cron_next
    base = datetime.datetime(2026, 10, 8, 12, 0)  # a Thursday
    ctx.check("dow 7 == Sunday (same as 0)",
              cron_next("0 9 * * 7", now=base) == cron_next("0 9 * * 0", now=base)
              == datetime.datetime(2026, 10, 11, 9, 0))
    ctx.check("dom OR dow when both restricted",
              cron_next("0 0 1 * 1", now=datetime.datetime(2026, 10, 2, 0, 0))
              == datetime.datetime(2026, 10, 5, 0, 0))
    ctx.check("plain fields unchanged",
              cron_next("30 4 * * *", now=base) == datetime.datetime(2026, 10, 9, 4, 30))
    ctx.check("dom-only still restricts",
              cron_next("0 0 1 * *", now=datetime.datetime(2026, 10, 2, 0, 0))
              == datetime.datetime(2026, 11, 1, 0, 0))


# ---- f81: preflight lane identification ----


@test
def test_f81_preflight_lane_sources(ctx: Ctx):
    from halo_harness.preflight import _default_lane
    tmp = Path(tempfile.mkdtemp())
    old = {k: os.environ.get(k) for k in ("HALO_MODEL", "BRIDGE_MODEL", "ROLO_CLAUDE_MODEL")}
    try:
        for k in old:
            os.environ.pop(k, None)
        os.environ["HALO_MODEL"] = "or:vendor/model-x"
        ctx.check("HALO_MODEL identifies the lane", _default_lane(tmp) == "or:vendor/model-x")
        os.environ.pop("HALO_MODEL")
        (tmp / "config.json").write_text('{"model": "or:cfg/model"}', encoding="utf-8")
        ctx.check("config.json model identifies the lane", _default_lane(tmp) == "or:cfg/model")
        (tmp / "config.json").write_text('{"last_model": "or:last/model"}', encoding="utf-8")
        ctx.check("last_model identifies the lane", _default_lane(tmp) == "or:last/model")
        (tmp / "config.json").unlink()
        (tmp / "routes.json").write_text('{"model": "or:routes/model"}', encoding="utf-8")
        ctx.check("routes.json default identifies the lane", _default_lane(tmp) == "or:routes/model")
        (tmp / "routes.json").unlink()
        ctx.check("no source -> no lane (never a guess)", _default_lane(tmp) is None)
    finally:
        for k, v in old.items():
            if v is not None:
                os.environ[k] = v


# ---- the CI gate itself, pinned locally ----


@test
def test_pyflakes_no_undefined_names(ctx: Ctx):
    try:
        import pyflakes  # noqa: F401
    except ImportError:
        ctx.check("pyflakes not installed; skipping (CI runs it)", True)
        return
    proc = subprocess.run([sys.executable, "-m", "pyflakes", "halo_harness/", "bridge.py"],
                          cwd=str(REPO), capture_output=True, text=True)
    undefined = [ln for ln in proc.stdout.splitlines() if "undefined name" in ln]
    ctx.check(f"no undefined names anywhere (got {len(undefined)}): {undefined[:3]}", not undefined)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
