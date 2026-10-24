"""tests.test_isolation_secrets -- Halo 3.1.8.0 R5: `secrets: broker` (isolation/secrets.py, brokers/): refs read
at spawn by a fake `op` on the rig's temp PATH into the worker's environment only (never the argv, a file, the
lane record or what the runner keeps of the reply), the worker's tool children never see them unless
`pass_to_tools` names them, a ref that cannot be read stops the lane with one line naming the ref, the `env`
broker, and `halo secrets check` printing names and ok only. The values are made up. No model is called.

Run: python -m tests.test_isolation_secrets
"""
from __future__ import annotations

import contextlib
import io
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.isolation_rig import IsoEnv, Recorder, run_with_lane
from tests.helpers.runner import Ctx, new_registry, print_results, run_all

test, TESTS = new_registry()
_SERVICE = "made-up-service-value-31415"
_ROUTER = "made-up-router-value-27182"
_VALUES = {"op://vault/service/credential": _SERVICE, "op://vault/router/credential": _ROUTER}


def _coder(e, refs=None, **extra):
    e.lineup("crew", {"agents": [{"agent": "boss", "role": "main"}, {"agent": "coder", "role": "subagent"}]})
    e.bio("boss", {})
    e.bio("coder", {"secrets": {"broker": "1password", "account": "team-acct"},
                    "environment": {"secrets": refs if refs is not None else [
                        {"env": "SERVICE_TOKEN", "ref": "op://vault/service/credential"},
                        {"env": "OPENROUTER_API_KEY", "ref": "op://vault/router/credential"}], **extra}})


def _spawn(run_dir, lane, runner):
    from halo_harness.orchestra.adapters import spawn_worker
    return spawn_worker("or:cheap/model", run_dir=run_dir, runner=runner)(lane)


def _files_holding(roots, value: str) -> list:
    hits = []
    for root in roots:
        for p in Path(root).rglob("*"):
            if p.is_file() and ".git" not in p.parts:
                try:
                    if value in p.read_text(encoding="utf-8", errors="replace"):
                        hits.append(str(p))
                except OSError:
                    pass
    return hits


@test
def test_refs_are_read_into_the_worker_env_only(ctx: Ctx):
    with IsoEnv() as e:
        e.fake_op(_VALUES)
        _coder(e)
        repo, run_dir, lane = run_with_lane(lineup="crew", bio="coder")
        rec = Recorder()
        result = _spawn(run_dir, lane, rec)
        env, argv = rec.calls[0]["env"], rec.calls[0]["argv"]
        ctx.check("each ref's value is in the worker's env under its name",
                  env.get("SERVICE_TOKEN") == _SERVICE and env.get("OPENROUTER_API_KEY") == _ROUTER)
        ctx.check(f"the names join the run's strip list, got {env.get('HALO_SECRET_KEYS')}",
                  env.get("HALO_SECRET_KEYS") == "OPENROUTER_API_KEY,SERVICE_TOKEN" and "HALO_SECRET_PASS" not in env)
        calls = e.op_calls()
        ctx.check(f"`op read <ref> --account <account>` per ref, got {calls}",
                  ["read", "op://vault/service/credential", "--account", "team-acct"] in calls and len(calls) == 2)
        ctx.check("no value in the worker's argv", not any(v in a for a in argv for v in (_SERVICE, _ROUTER)))
        data = lane.data()
        ctx.check(f"the lane records a count, never a value, got {data.get('secrets')}",
                  data.get("secrets", {}).get("refs") == 2 and data["secrets"].get("broker") == "1password")
        ctx.check("and the line", "secrets: 1password (2 refs)" in data.get("opt_ins", []))
        hits = _files_holding([e.state, repo], _SERVICE) + _files_holding([e.state, repo], _ROUTER)
        ctx.check(f"no file under the home or the repo (run folder included) holds a value, got {hits}", not hits)
        ctx.check("the worker ran", result.get("ok") is True)


@test
def test_what_the_runner_keeps_of_the_reply_is_scrubbed(ctx: Ctx):
    with IsoEnv() as e:
        e.fake_op(_VALUES)
        _coder(e)
        _repo, run_dir, lane = run_with_lane(lineup="crew", bio="coder")
        result = _spawn(run_dir, lane, Recorder(text=f"I printed {_SERVICE} by mistake"))
        ctx.check(f"the value is replaced, got {result.get('text')!r}",
                  result["text"] == "I printed <redacted> by mistake")


@test
def test_tool_children_never_see_the_keys_unless_pass_to_tools_names_them(ctx: Ctx):
    from halo_harness.providers.config import tool_child_env
    with IsoEnv() as e:
        env = {"SERVICE_TOKEN": _SERVICE, "OPENROUTER_API_KEY": _ROUTER, "PLAIN": "x",
               "HALO_SECRET_KEYS": "OPENROUTER_API_KEY,SERVICE_TOKEN"}
        out = tool_child_env(env, env_file_path=e.root / "no-env-file")
        ctx.check("both broker keys are stripped", "SERVICE_TOKEN" not in out and "OPENROUTER_API_KEY" not in out)
        ctx.check("the rest is kept", out.get("PLAIN") == "x")
        out = tool_child_env(dict(env, HALO_SECRET_PASS="SERVICE_TOKEN,OPENROUTER_API_KEY"),
                             env_file_path=e.root / "no-env-file")
        ctx.check("pass_to_tools lets a key through", out.get("SERVICE_TOKEN") == _SERVICE)
        ctx.check("a harness provider key never reaches a tool child", "OPENROUTER_API_KEY" not in out)
        e.fake_op(_VALUES)
        _coder(e, pass_to_tools=["SERVICE_TOKEN"])
        _repo, run_dir, lane = run_with_lane(lineup="crew", bio="coder")
        rec = Recorder()
        _spawn(run_dir, lane, rec)
        ctx.check("the bio's pass_to_tools rides in the worker's env", rec.calls[0]["env"].get("HALO_SECRET_PASS") == "SERVICE_TOKEN")


@test
def test_a_ref_that_cannot_be_read_stops_the_lane_naming_the_ref(ctx: Ctx):
    with IsoEnv() as e:
        e.fake_op({"op://vault/service/credential": _SERVICE})
        _coder(e)
        _repo, run_dir, lane = run_with_lane(lineup="crew", bio="coder")
        rec = Recorder()
        result = _spawn(run_dir, lane, rec)
        ctx.check(f"one line naming the ref, got {result}",
                  result == {"ok": False, "error": "secrets: could not read op://vault/router/credential (op exited 1)"})
        ctx.check("no worker started", not rec.calls)
    with IsoEnv() as e:
        _coder(e)
        _repo, run_dir, lane = run_with_lane(lineup="crew", bio="coder")
        result = _spawn(run_dir, lane, Recorder())
        ctx.check(f"no op on PATH is one line, got {result}", result.get("error") == "secrets: 1password asked, no `op` on PATH")


@test
def test_the_env_broker_reads_an_env_ref(ctx: Ctx):
    with IsoEnv() as e:
        e.lineup("crew", {"agents": [{"agent": "coder", "role": "main"}], "secrets": {"broker": "env"}})
        e.bio("coder", {"environment": {"secrets": [{"env": "SERVICE_TOKEN", "ref": "ENV:SOURCE_VALUE_FOR_TEST"}]}})
        os.environ["SOURCE_VALUE_FOR_TEST"] = _SERVICE
        try:
            _repo, run_dir, lane = run_with_lane(lineup="crew", bio="coder")
            rec = Recorder()
            _spawn(run_dir, lane, rec)
        finally:
            os.environ.pop("SOURCE_VALUE_FOR_TEST", None)
        ctx.check("the lineup's broker reads the bio's ENV: ref", rec.calls[0]["env"].get("SERVICE_TOKEN") == _SERVICE)
        ctx.check("the line names the broker", "secrets: env (1 ref)" in lane.data().get("opt_ins", []))
        from halo_harness.isolation.brokers import BrokerError, load
        try:
            load("env").read("ENV:NOT_SET_ANYWHERE_FOR_TEST", environ={})
            line = None
        except BrokerError as err:
            line = str(err)
        ctx.check(f"an unset key is one line, got {line!r}", line == "secrets: ENV:NOT_SET_ANYWHERE_FOR_TEST is not set in this environment")


@test
def test_halo_secrets_check_prints_names_and_ok_only(ctx: Ctx):
    from halo_harness.isolation.secrets import cmd_secrets
    with IsoEnv() as e:
        e.fake_op(_VALUES)
        _coder(e)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = cmd_secrets(["check", "--bio", "coder"], which=e.which)
        text = out.getvalue()
        ctx.check(f"the broker and each name with ok, rc 0, got {text!r}", rc == 0 and "broker 1password (op on PATH)" in text
                  and "  SERVICE_TOKEN: ok" in text and "  OPENROUTER_API_KEY: ok" in text)
        ctx.check("never a value", _SERVICE not in text and _ROUTER not in text)
        e.fake_op({"op://vault/service/credential": _SERVICE})
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = cmd_secrets(["check", "--lineup", "crew"], which=e.which)
        text = out.getvalue()
        ctx.check(f"a ref that cannot be read: its name and the ref, rc 1, got {text!r}", rc == 1
                  and "OPENROUTER_API_KEY: could not read op://vault/router/credential (op exited 1)" in text)
        ctx.check("still never a value", _SERVICE not in text)


@test
def test_the_bio_and_lineup_declarations_are_validated(ctx: Ctx):
    from halo_harness.isolation.spec import bio_problems, secrets_problems
    ctx.check("a known broker is fine", not secrets_problems({"broker": "1password", "account": "a"}))
    ctx.check("an unknown broker is one line", secrets_problems({"broker": "vault"})
              == ['"secrets.broker" \'vault\' is not one of 1password, env'])
    ctx.check("environment.secrets needs env and ref", bio_problems({"environment": {"secrets": [{"env": "X"}]}})
              == ['"environment.secrets" must be a list of {env: <KEY>, ref: <broker ref>}'])
    with IsoEnv() as e:
        from halo_harness.agents_yaml import validate_agent_bio
        ok = validate_agent_bio({"secrets": {"broker": "env"}, "environment": {"secrets": [{"env": "A", "ref": "ENV:B"}],
                                                                              "pass_to_tools": ["A"]}})
        ctx.check(f"a bio with all three is valid, got {ok}", not ok)
        from halo_harness.schemas.check import check
        from halo_harness.schemas.yaml_files import bio
        ctx.check("the bio schema knows isolation and secrets", not check({"isolation": "container",
                                                                            "secrets": {"broker": "env"}}, bio()))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
