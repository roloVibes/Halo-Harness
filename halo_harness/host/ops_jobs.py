"""halo_harness.host.ops_jobs -- the stated and job-shaped `control` operations (Halo 3.3.7.0 R2; host/ops.py).

    set_kv_cache_type {value} | set_flash_attn {on}   stated: the exact line for the host's OS
                                                    (ollama_steward/tune_lines.env_lines), `applied: false`; nothing
                                                    is called and nothing changes
    rerun_battery {model, force?}                   providers/capability_battery.run on the host, as a job
    bench {model, quick?}                           providers/local_bench.bench (its busy wait reads the host's ledger)
    verify_twin {model, window?}                    providers/ollama_twin_verify.verify
"""

from __future__ import annotations

from halo_harness.host.ops import HOST, MODEL, PORT, Op
from halo_harness.host.ops_control import KV_TYPES, LOCAL_TIME, _takes_load

# ---- stated: the host says the line, never runs it ------------------------------------------------

def stated_answer(ctx, env_key: str, value: str) -> dict:
    from halo_harness.ollama_steward.tune_lines import server_block
    os_name = ctx.os_name()
    block = server_block("env", env_key, value, os_name)
    one = block.get(os_name) if os_name else next(iter(block.values()))
    line = (f"{env_key}={value} on {ctx.host.name} is a server setting the host states and never applies: run "
            f"`{one['set']}` there, then {one['restart']}; `{one['revert']}` puts it back")
    return {"ok": True, "applied": False, "stated": True, "os": os_name, "set": one["set"], "revert": one["revert"],
            "restart": one["restart"], "lines": block, "line": line, "say": line}


def _stated_preview(ctx, env_key: str, value: str) -> dict:
    got = stated_answer(ctx, env_key, value)
    return {"would": [got["line"]], "writes": ["nothing: a stated action (applied: false)"],
            "takes": "the restart's time, when you run it", "cost": "local: a restart unloads every model", **got}


def _kv(p) -> str:
    v = str(p["value"]).lower()
    if v not in KV_TYPES:
        raise ValueError(f"value: {', '.join(KV_TYPES)} (not {p['value']!r})")
    return v


def _fa(p) -> str:
    return "1" if p["on"] else "0"


def _job(name: str, params: dict, preview, run, help_: str) -> Op:
    return Op(name, "control", {"host": HOST, "port": PORT, "model": MODEL, **params}, preview,
              lambda ctx, p: {"ok": True, "run": lambda on: run(ctx, p, on), "say": preview(ctx, p)["takes"]},
              job=True, help=help_)


def _battery_prev(ctx, p):
    from halo_harness.providers.capability_battery import cost_line
    return {"would": [f"run the capability battery on {p['model']} ({ctx.host.name})"],
            "writes": ["<state>/ollama-capabilities.json: the verified profile"], "takes": cost_line(p["model"], ctx.host.name),
            "cost": LOCAL_TIME + "; the card is busy while it runs"}


def _battery(ctx, p, on):
    from halo_harness.providers.capability_battery import run
    return run(ctx.host, p["model"], card=ctx.view.host_card(ctx.host), on_status=on, state_dir=ctx.home,
               force=p.get("force") is True)


def _bench_prev(ctx, p):
    from halo_harness.providers.local_bench import estimate
    from halo_harness.providers.local_bench_runs import busy
    _m, line = estimate(ctx.host, p["model"], card=ctx.view.host_card(ctx.host), state_dir=ctx.home,
                        quick=p.get("quick") is True)
    out = {"would": [f"bench {p['model']} on {ctx.host.name}" + (" (quick)" if p.get("quick") else "")],
           "writes": ["the speed card in the host's fit store"], "takes": line, "cost": LOCAL_TIME}
    why = busy(ctx.home, ctx.host.name)
    if why:
        out["busy"] = why
    return out


def _bench(ctx, p, on):
    from halo_harness.providers.local_bench import bench
    return bench(ctx.host, p["model"], quick=p.get("quick") is True, card=ctx.view.host_card(ctx.host),
                 state_dir=ctx.home, on_line=lambda s: on({"say": s}), check_busy=False)


def _twin_prev(ctx, p):
    return {"would": [f"load the twin {p['model']} at its window, read /api/ps and the log, time one warm call"],
            "writes": ["the twin's verify record in the tune store"], "takes": _takes_load(ctx, p["model"]),
            "cost": LOCAL_TIME}


def _twin(ctx, p, on):
    from halo_harness.providers.ollama_twin_verify import verify
    on({"say": f"verifying the twin {p['model']}"})
    got = verify(ctx.host, p["model"], p.get("window"), state_dir=ctx.home)
    return {**got, "ok": got.get("state") == "verified", "say": got.get("line")}


TABLE = [
    Op("set_kv_cache_type", "control", {"host": HOST, "port": PORT, "value": ("str", True, "f16, q8_0 or q4_0")},
       lambda ctx, p: _stated_preview(ctx, "OLLAMA_KV_CACHE_TYPE", _kv(p)),
       lambda ctx, p: stated_answer(ctx, "OLLAMA_KV_CACHE_TYPE", _kv(p)), stated=True,
       help="the server's KV cache type (stated: the line, never applied)"),
    Op("set_flash_attn", "control", {"host": HOST, "port": PORT, "on": ("bool", True, "true or false")},
       lambda ctx, p: _stated_preview(ctx, "OLLAMA_FLASH_ATTENTION", _fa(p)),
       lambda ctx, p: stated_answer(ctx, "OLLAMA_FLASH_ATTENTION", _fa(p)), stated=True,
       help="the server's flash attention (stated)"),
    _job("rerun_battery", {"force": ("bool", False, "run it even when the profile is fresh")}, _battery_prev, _battery,
         "the capability battery, on the host"),
    _job("bench", {"quick": ("bool", False, "the ceiling window only")}, _bench_prev, _bench, "the bench, on the host"),
    _job("verify_twin", {"window": ("int", False, "the twin's window")}, _twin_prev, _twin, "verify a tuned twin"),
]
