"""halo_harness.host.ops_manage -- the `manage` operations (Halo 3.3.7.0 R2; host/ops.py has the registry). `manage`
holds `control`'s operations too; `admin` is its own grant, and its operations are not part of this version.

    pull {model}                       providers/ollama_control.pull, as a job (its status lines are `job` frames)
    delete {model, force?}             after the uses card (studio/local_uses.uses_of): a live session on the model is
                                       refused with the line; a role, lineup or profile naming it too, unless force
    retire {model, why?, force?}       models_library/shelf.retire (the delete, a note left, the re-pull line)
    restart_ollama {} | set_env {key, value}   stated: the exact line for the host's OS, applied: false
    revert {change}                    ollama_steward/changes.revert: the change put back (`GET changes` lists them)
"""

from __future__ import annotations

import re

from halo_harness.host.ops import HOST, MODEL, PORT, Op
from halo_harness.host.ops_control import LOCAL_TIME

_ENV = re.compile(r"^OLLAMA_[A-Z0-9_]{1,40}$")


def _pull_prev(ctx, p):
    return {"would": [f"pull {p['model']} onto {ctx.host.name}"], "writes": ["Ollama's own blob store: the layers it "
            "does not have yet"], "takes": "the download's time (the job's frames say how far)",
            "cost": "local: time and disk; a download from the registry"}


def _pull(ctx, p, on):
    from halo_harness.providers.ollama_control import pull

    def status(d: dict) -> None:
        total, done = d.get("total"), d.get("completed")
        say = str(d.get("status") or "")
        if isinstance(total, int) and total and isinstance(done, int):
            say += f" ({100 * done // total} %)"
        on({"say": say, "step": done, "of": total})
    got = pull(ctx.host, p["model"], on_status=status)
    ctx.forget_card()
    return got


def _uses(ctx, model: str) -> dict:
    from halo_harness.studio.local_uses import uses_of
    return uses_of(f"ol:{model}@{ctx.host.name}", state_dir=ctx.home)


def _refusal(u: dict, force: bool) -> str:
    if u.get("live"):
        return u["line"] + ": the delete waits until they end or move to another model"
    if u.get("any") and not force:
        return u["line"] + " (send force: true to delete it anyway)"
    return ""


def p_delete(ctx, p):
    u = _uses(ctx, p["model"])
    out = {"would": [f"delete {p['model']} from {ctx.host.name}"], "writes": ["Ollama's own blob store: the layers no "
           "other model shares"], "takes": "~1 s", "cost": "local: the download to get it back", "uses": u}
    why = _refusal(u, p.get("force") is True)
    if why:
        out["breach"] = why
    return out


def a_delete(ctx, p):
    from halo_harness.providers.ollama_control import delete
    from halo_harness.providers.ollama_tune_store import forget_twin
    why = _refusal(_uses(ctx, p["model"]), p.get("force") is True)
    if why:
        return {"ok": False, "status": 409 if "waits" in why else 422, "say": why, "breach": True}
    got = delete(ctx.host, p["model"])
    if got.get("ok"):
        forget_twin(ctx.home, host_url=ctx.host.url, twin=p["model"])
        ctx.forget_card()
        ctx.publish("event", {"kind": "deleted", "model": p["model"], "say": got.get("say")})
    return got


def p_retire(ctx, p):
    out = p_delete(ctx, p)
    out["would"] = [f"retire {p['model']} from {ctx.host.name}: the delete, a note on the shelf, the re-pull line"]
    out["writes"].append("<state>/ollama/shelf.jsonl: one line")
    return out


def a_retire(ctx, p):
    from halo_harness.models_library.shelf import retire
    got = retire(ctx.host, p["model"], state_dir=ctx.home, why=ctx.why or str(p.get("why") or ""),
                 force=p.get("force") is True)
    if got.get("ok"):
        ctx.forget_card()
        ctx.publish("event", {"kind": "retired", "model": p["model"], "say": got.get("say")})
    return got


def _restart(ctx, _p) -> dict:
    from halo_harness.ollama_steward.tune_lines import OSES, RESTART
    os_name = ctx.os_name()
    lines = {o: RESTART[o] for o in ([os_name] if os_name else OSES)}
    one = lines.get(os_name) if os_name else next(iter(lines.values()))
    line = (f"restarting Ollama on {ctx.host.name} is a server action the host states and never runs: {one} "
            "(every loaded model unloads)")
    return {"ok": True, "applied": False, "stated": True, "os": os_name, "set": one, "revert": "", "restart": one,
            "lines": lines, "line": line, "say": line}


def _env_value(p) -> "tuple[str, str]":
    key = str(p["key"]).strip().upper()
    if not _ENV.match(key):
        raise ValueError(f"key: an OLLAMA_* name (not {p['key']!r})")
    return key, str(p["value"])


def _stated_env(ctx, p) -> dict:
    from halo_harness.host.ops_jobs import stated_answer
    return stated_answer(ctx, *_env_value(p))


def _stated_prev(fn):
    def preview(ctx, p):
        got = fn(ctx, p)
        return {"would": [got["line"]], "writes": ["nothing: a stated action (applied: false)"],
                "takes": "the restart's time, when you run it", "cost": "local: a restart unloads every model", **got}
    return preview


def p_revert(ctx, p):
    from halo_harness.ollama_steward.changes import in_force, line_of
    row = next((r for r in in_force(ctx.home) if r.get("id") == p["change"]), None)
    out = {"would": [f"put back {line_of(row)}" if row else f"nothing: no change in force with the id {p['change']}"],
           "writes": ["config.json: the field's value before", "<state>/ollama/changes.jsonl: a revert line"],
           "takes": "~0 s", "cost": "local: nothing"}
    if row is None:
        out["breach"] = f"no change in force with the id {p['change']} (GET changes lists them)"
    return out


def a_revert(ctx, p):
    from halo_harness.ollama_steward.changes import revert
    prev = p_revert(ctx, p)
    if prev.get("breach"):
        return {"ok": False, "status": 404, "say": prev["breach"]}
    lines = revert(ctx.home, p["change"], f"reverted by {ctx.peer} through the host" + (f": {ctx.why}" if ctx.why else ""))
    ctx.publish("event", {"kind": "reverted", "change": p["change"], "say": lines[0] if lines else ""})
    return {"ok": True, "say": "; ".join(lines), "lines": lines, "change_id": p["change"]}


MODEL_P = {"host": HOST, "port": PORT, "model": MODEL}
FORCE = ("bool", False, "delete it even when a role, lineup or profile names it")
TABLE = [
    Op("pull", "manage", MODEL_P, _pull_prev, lambda ctx, p: {"ok": True, "run": lambda on: _pull(ctx, p, on),
                                                               "say": f"pulling {p['model']}"},
       job=True, help="pull a model onto the host"),
    Op("delete", "manage", {**MODEL_P, "force": FORCE}, p_delete, a_delete, help="delete a model (the uses card first)"),
    Op("retire", "manage", {**MODEL_P, "force": FORCE, "why": ("str", False, "the note on the shelf")}, p_retire,
       a_retire, help="retire a model: the delete, a note, the re-pull line"),
    Op("restart_ollama", "manage", {"host": HOST, "port": PORT}, _stated_prev(_restart), _restart, stated=True,
       help="restart the Ollama server (stated: the line, never run)"),
    Op("set_env", "manage", {"host": HOST, "port": PORT, "key": ("str", True, "an OLLAMA_* variable"),
                             "value": ("any", True, "its value")}, _stated_prev(_stated_env), _stated_env, stated=True,
       help="set an Ollama environment variable (stated)"),
    Op("revert", "manage", {"change": ("str", True, "the change id (GET changes)")}, p_revert, a_revert,
       help="put a change back"),
]
