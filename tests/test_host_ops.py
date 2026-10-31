"""tests.test_host_ops -- Halo 3.3.7.0 R2 deliverable 2: the typed vocabulary (host/ops.py, ops_control.py,
ops_jobs.py, ops_manage.py, routes_act.py) on a fake Ollama (tests/helpers/host_act_rig.py):

1. every op's dry preview: {would, writes, takes, cost}, nothing landed (no load, no pull, no delete, no change row);
2. apply: warm / pin (keep_alive -1 on the wire) / unload / pivot (one event each), a profile field landed with its
   scope and a change row, delete and retire after the uses card, revert puts the change back;
3. the stated ops (KV type, flash attention, restart, env) call nothing and carry the OS line, applied: false;
4. the job ops answer {job} and stream `job` frames; `GET job/<id>` catches up;
5. one audit line per request {at, peer, op, params, evidence, dry, landed, change_id?, job?};
6. a missing grant is 403 naming it; an unknown op is 404 naming the vocabulary; bad params are 422.
Run: python -m tests.test_host_ops
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.host_act_rig import BIG, CODER, SMALL, ActRig  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
EV = {"finding": "window-small-0b27aa", "lines": ["limit=16386 prompt=41104"]}
PARAMS = {"warm": {"model": SMALL}, "pin": {"model": SMALL}, "unload": {"model": SMALL},
          "pivot": {"from": SMALL, "to": SMALL}, "set_num_ctx": {"model": BIG, "value": 16384},
          "set_num_predict": {"model": BIG, "value": 2048}, "set_keep_alive": {"model": BIG, "value": "30m"},
          "set_tools_max": {"model": BIG, "value": 8}, "set_kv_cache_type": {"value": "q8_0"},
          "set_flash_attn": {"on": True}, "rerun_battery": {"model": SMALL}, "bench": {"model": SMALL},
          "verify_twin": {"model": SMALL}, "pull": {"model": "new-model:7b"}, "delete": {"model": SMALL},
          "retire": {"model": SMALL}, "restart_ollama": {}, "set_env": {"key": "OLLAMA_NUM_PARALLEL", "value": "2"},
          "revert": {"change": "ch-none"}}


def _writes(rig) -> dict:
    from halo_harness.ollama_steward import changes
    return {"generated": len(rig.mock.generated), "pulled": len(rig.mock.pulled), "deleted": len(rig.mock.deleted),
            "changes": changes.path(rig.home).exists()}


@test
def test_every_op_previews_and_lands_nothing(ctx: Ctx):
    from halo_harness.host.ops import table
    with ActRig(grants=("manage",)) as rig:
        ctx.check("every op of the table has preview params here", set(PARAMS) == set(table()))
        before = _writes(rig)
        for name, op in table().items():
            status, got = rig.act(op.grant, name, PARAMS[name], dry=True)
            shape = all(k in got for k in ("would", "writes", "takes", "cost")) and got.get("dry") is True
            ctx.check(f"{name}: a dry preview {{would, writes, takes, cost}}, got {status} {sorted(got)}",
                      status == 200 and shape)
        ctx.check(f"nothing landed, got {_writes(rig)}", _writes(rig) == before)
        status, got = rig.act("control", "set_num_ctx", PARAMS["set_num_ctx"], dry=True)
        ctx.check(f"the profile preview names the field, the scope and the verify, got {got['would']}",
                  "num_ctx unset -> 16,384 on pc|qwen3.8:27b (kept)" in got["would"][0] and "measure the next 5" in got["would"][1])


@test
def test_apply_loads_fields_deletes_and_revert(ctx: Ctx):
    from halo_harness.ollama_steward import changes
    from halo_harness.ollama_steward.profiles import all_profiles
    with ActRig(grants=("manage",)) as rig:
        status, got = rig.act("control", "warm", {"model": SMALL, "num_ctx": 8192, "keep_alive": "10m"})
        sent = rig.mock.generated[-1] if rig.mock.generated else {}
        ctx.check(f"warm: loaded at 8192, keep_alive honoured and reported, got {status} {got}", status == 200
                  and got["ok"] and sent.get("options") == {"num_ctx": 8192} and sent.get("keep_alive") == "10m"
                  and got["keep_alive"] == "10m")
        status, got = rig.act("control", "pin", {"model": SMALL, "num_ctx": 8192})
        ctx.check(f"pin: keep_alive -1 on the wire, got {rig.mock.generated[-1]}", status == 200
                  and rig.mock.generated[-1]["keep_alive"] == -1)
        n = len(rig.mock.generated)
        status, got = rig.act("control", "pivot", {"from": SMALL, "to": BIG, "num_ctx": 8192})
        pair = rig.mock.generated[n:]
        ctx.check(f"pivot: unload A then load B, got {status} {pair}", status == 200 and len(pair) == 2
                  and pair[0]["model"] == SMALL and pair[0]["keep_alive"] in (0, "0") and pair[1]["model"] == BIG)
        status, got = rig.act("control", "unload", {"model": BIG})
        ctx.check("unload", status == 200 and rig.mock.generated[-1]["keep_alive"] in (0, "0"))
        status, got = rig.act("control", "set_num_ctx", {"model": BIG, "value": 16384}, evidence=EV, why="the log says so")
        key = "pc|qwen3.8:27b"
        row = next((r for r in changes.read(rig.home) if r["id"] == got.get("change_id")), {})
        ctx.check(f"set_num_ctx: the profile, a change row with the steward's scope, got {status} {got}", status == 200
                  and all_profiles().get(key, {}).get("num_ctx") == 16384 and row.get("scope") == "until-restart"
                  and row.get("by") == "carol@peer via host" and "the log says so" in row.get("why", ""))
        status, got2 = rig.act("manage", "revert", {"change": got["change_id"]})
        ctx.check(f"revert puts it back, got {status} {got2}", status == 200 and "took num_ctx" in got2["say"]
                  and "num_ctx" not in all_profiles().get(key, {}))
        status, got = rig.act("manage", "delete", {"model": SMALL})
        ctx.check(f"delete: the model goes, got {status} {got}", status == 200 and SMALL in str(rig.mock.deleted))
        from halo_harness.theme import set_config_value
        set_config_value("compactionModel", f"ol:{CODER}@pc")
        status, got = rig.act("manage", "delete", {"model": CODER})
        ctx.check(f"delete of a model a role names: refused with the uses line, got {status} {got}", status == 422
                  and "force: true" in got["error"])
        status, got = rig.act("manage", "retire", {"model": CODER, "force": True, "why": "never used"})
        ctx.check(f"retire with force: deleted, the shelf line, got {status} {got}", status == 200 and "retired" in got["say"])


@test
def test_stated_ops_call_nothing_and_carry_the_line(ctx: Ctx):
    with ActRig(grants=("manage",)) as rig:
        rig.mock.clear()
        for grant, name, params, word in (("control", "set_kv_cache_type", {"value": "q8_0"}, "OLLAMA_KV_CACHE_TYPE"),
                                          ("control", "set_flash_attn", {"on": True}, "OLLAMA_FLASH_ATTENTION"),
                                          ("manage", "set_env", {"key": "OLLAMA_NUM_PARALLEL", "value": "2"},
                                           "OLLAMA_NUM_PARALLEL"),
                                          ("manage", "restart_ollama", {}, "")):
            status, got = rig.act(grant, name, params)
            ctx.check(f"{name}: applied false, stated, the OS's set / revert / restart, got {status} {got}", status == 200
                      and got["applied"] is False and got["stated"] is True and got["os"] in ("windows", "linux", "macos")
                      and word in got["set"] + got["line"] and got["restart"])
        posts = [r for r in rig.mock.requests if r.get("method") == "POST"]
        ctx.check(f"no POST reached the server, got {posts}", posts == [])
        status, got = rig.act("control", "set_kv_cache_type", {"value": "q2"})
        ctx.check(f"a KV type it does not know: 422, got {status} {got}", status == 422 and "q8_0" in got["error"])
        status, got = rig.act("manage", "set_env", {"key": "PATH", "value": "x"})
        ctx.check(f"set_env takes OLLAMA_* only, got {status}", status == 422 and "OLLAMA_" in got["error"])


@test
def test_job_ops_frames_and_catch_up(ctx: Ctx):
    from tests.helpers.mock_ollama_pull import HF_SHOW
    with ActRig(grants=("manage",)) as rig:
        rig.mock.pullable["new-model:7b"] = HF_SHOW
        s = rig.client().stream()
        status, got = rig.act("manage", "pull", {"model": "new-model:7b"})
        ctx.check(f"pull: a job, got {status} {got}", status == 200 and got["job"].startswith("pull-"))
        job = rig.wait_job(got["job"])
        ctx.check(f"GET job/<id> catches up: done, ok, the lines, got {job}", job.get("done") and job.get("ok")
                  and any("success" in x or "pulling" in x for x in job.get("lines") or []))
        frames = []
        end = time.monotonic() + 5
        while time.monotonic() < end and not any(f.get("type") == "job" and (f.get("data") or {}).get("done") for f in frames):
            frames += s.read(timeout=0.5)
        s.close()
        jobs = [f for f in frames if f.get("type") == "job"]
        ctx.check(f"job frames on the stream, the last one done, got {len(jobs)}", len(jobs) >= 2 and jobs[-1]["data"]["done"])
        status, got = rig.act("control", "rerun_battery", {"model": SMALL})
        job = rig.wait_job(got["job"])
        ctx.check(f"rerun_battery: a job that ends, got {job.get('say')}", status == 200 and job.get("done") is True)
        status, got = rig.act("control", "verify_twin", {"model": SMALL})
        job = rig.wait_job(got["job"])
        ctx.check(f"verify_twin: a job that ends with the twin's line, got {job.get('say')}", status == 200 and job.get("done"))


@test
def test_the_audit_line_and_the_refusals(ctx: Ctx):
    from halo_harness.host.state import read_audit
    with ActRig(grants=("control",)) as rig:
        status, got = rig.act("control", "set_num_ctx", {"model": BIG, "value": 16384}, evidence=EV)
        end, rows = time.monotonic() + 3, []
        while time.monotonic() < end and not rows:  # the line is written as the answer goes out
            rows = [a for a in read_audit(rig.home) if a.get("op") == "set_num_ctx"]
            time.sleep(0.05)
        row = rows[-1] if rows else {}
        ctx.check(f"the audit line: peer, op, params, evidence, dry, landed, change_id, got {row}", row["peer"] == "carol@peer"
                  and row["params"] == {"model": BIG, "value": 16384} and row["evidence"] == EV and row["dry"] is False
                  and row["landed"] is True and row["change_id"] == got["change_id"] and row["fix"] is True)
        status, got = rig.act("manage", "pull", {"model": "x"})
        ctx.check(f"a missing grant names it, got {status} {got}", status == 403 and "`manage` grant" in got["error"])
        status, got = rig.act("control", "explode", {})
        ctx.check(f"an unknown op names the vocabulary, got {status} {got}", status == 404 and "warm" in got["error"])
        status, got = rig.act("control", "pull", {"model": "x"})
        ctx.check(f"an op under the wrong grant says where it is, got {got}", status == 404 and "POST manage/pull" in got["error"])
        status, got = rig.act("control", "warm", {"model": 7, "colour": "red"})
        ctx.check(f"bad params: 422 naming them, got {status} {got}", status == 422 and "model" in got["error"]
                  and "colour" in got["error"])


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
