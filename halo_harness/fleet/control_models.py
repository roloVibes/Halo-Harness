"""halo_harness.fleet.control_models -- a hub's control of the models on a
host this member serves (Studio's Local tab), applied under the member's
`fleet.allow_control` like a steer (fleet/control.py: `none` refuses, `ask`
puts a card in the owner's TUI, `all` applies it). Only a host this machine
serves is touched; nothing about the server's settings changes.

    ollama_load   {host, model, num_ctx?, keep_alive?}  providers/ollama_load.load          (3.3.5.0 R1)
    ollama_unload {host, model}                         providers/ollama_load.unload        (3.3.5.0 R1)
    ollama_pull   {host, model, cancel?}                this member's own pull job (studio/local_pull_job.py);
                                                        it answers at once, its frames reach the hub with the
                                                        ledger push (fleet/control_pulls.py)  (3.3.5.0 R3)
    ollama_delete {host, model, force?}                 after this member's own uses card (studio/local_uses.py):
                                                        never while one of its sessions is on the model; with
                                                        something else using it only with force  (R3)
    ollama_copy   {host, src, dst, rename?}             providers/ollama_control.copy | rename  (R3)
    ollama_twin   {host, model, window?}                providers/ollama_tune: the tuned twin, recorded here  (R3)
"""

from __future__ import annotations

CMDS = ("ollama_load", "ollama_unload", "ollama_pull", "ollama_delete", "ollama_copy", "ollama_twin")
VERBS = {"ollama_load": "load", "ollama_unload": "unload", "ollama_pull": "pull", "ollama_delete": "delete",
         "ollama_copy": "copy", "ollama_twin": "make a tuned twin of"}


def describe(cmd: str, fields: dict, by: str, hub: str) -> str:
    verb = VERBS.get(cmd, cmd)
    if cmd == "ollama_copy" and fields.get("rename"):
        verb = "rename"
    if cmd == "ollama_pull" and fields.get("cancel"):
        verb = "stop pulling"
    what = fields.get("model") or fields.get("src") or "a model"
    to = f" to {fields['dst']}" if cmd == "ollama_copy" and fields.get("dst") else ""
    return f"{by} on {hub} wants to {verb} {what}{to} on {fields.get('host') or 'this machine'}"


def _host(fields: dict):
    from halo_harness.fleet.ollama_share import served_here
    from halo_harness.providers.ollama import resolve_ollama_host
    name = str(fields.get("host") or "").strip()
    host = resolve_ollama_host(name or None)
    if host is None:
        raise ValueError(f"no Ollama host named {name!r} here")
    if not served_here(host.url):
        raise ValueError(f"{host.name} is not served by this machine")
    return host


def _state():
    from halo_harness.config.paths import bridge_home
    return bridge_home()


def _pull(host, model: str, fields: dict) -> dict:
    from halo_harness.studio import local_pull_job as J
    if fields.get("cancel"):
        job = next((j for j in J.current()["jobs"] if not j["done"] and j["host"] == host.name and j["name"] == model), None)
        got = J.cancel(job["job"]) if job else None
        return {"ok": bool(got), "say": f"stopping the pull of {model}" if got else f"no pull of {model} runs here"}
    view = J.start(host, model, state_dir=_state())
    return {"ok": True, "job": view["job"], "say": f"pulling {model} on {host.name}", "joined": view.get("joined")}


def _delete(host, model: str, fields: dict) -> dict:
    from halo_harness.providers.ollama_control import delete
    from halo_harness.studio.local_uses import uses_of
    u = uses_of(f"ol:{model}@{host.name}")
    if u["live"]:
        raise ValueError(u["line"] + ": its sessions end first")
    if u["any"] and not fields.get("force"):
        raise ValueError(u["line"] + " (send force to delete it anyway)")
    got = delete(host, model)
    if got["ok"]:
        from halo_harness.studio.local_pull_job import after_change
        after_change()
    return got


def _copy(host, fields: dict) -> dict:
    from halo_harness.providers.ollama_control import copy, rename
    src, dst = str(fields.get("src") or "").strip(), str(fields.get("dst") or "").strip()
    return (rename if fields.get("rename") else copy)(host, src, dst)


def _twin(host, model: str, fields: dict) -> dict:
    from halo_harness.providers.ollama_tune import TuneError, create_twin, plan_twin
    window = fields.get("window") if isinstance(fields.get("window"), int) else None
    try:
        plan = plan_twin(host, model, window, state_dir=_state())
    except TuneError as e:
        raise ValueError(e.message) from None
    got = create_twin(host, plan, state_dir=_state())
    return {"ok": got.ok, "say": got.message, "twin": plan.twin, "ref": plan.ref, "line": plan.line}


def run(fields: dict) -> dict:
    """One model command on this machine's own host; raises ValueError with the reason it cannot."""
    from halo_harness.providers.ollama_load import load, unload
    cmd = fields.get("cmd")
    host = _host(fields)
    if cmd == "ollama_copy":
        return _copy(host, fields)
    model = str(fields.get("model") or "").strip()
    if not model:
        raise ValueError(f"say which model to {VERBS.get(cmd, 'use')}")
    if cmd == "ollama_pull":
        return _pull(host, model, fields)
    if cmd == "ollama_delete":
        return _delete(host, model, fields)
    if cmd == "ollama_twin":
        return _twin(host, model, fields)
    if cmd == "ollama_unload":
        return unload(host, model)
    num_ctx = fields.get("num_ctx") if isinstance(fields.get("num_ctx"), int) else None
    return load(host, model, num_ctx=num_ctx, keep_alive=fields.get("keep_alive"))
