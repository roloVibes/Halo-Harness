"""halo_harness.fleet.control_models -- Halo 3.3.5.0 R1: a hub's Load and
Unload of a model on a host this member serves (Studio's Local tab, Hosts
page), applied under the member's `fleet.allow_control` like a steer
(fleet/control.py: `none` refuses, `ask` puts a card in the owner's TUI, `all`
applies it). Only a host this machine serves is touched; nothing about the
server's settings changes.

    ollama_load   {host, model, num_ctx?, keep_alive?}  providers/ollama_load.load
    ollama_unload {host, model}                         providers/ollama_load.unload
"""

from __future__ import annotations

CMDS = ("ollama_load", "ollama_unload")


def describe(cmd: str, fields: dict, by: str, hub: str) -> str:
    verb = "load" if cmd == "ollama_load" else "unload"
    return f"{by} on {hub} wants to {verb} {fields.get('model') or 'a model'} on {fields.get('host') or 'this machine'}"


def run(fields: dict) -> dict:
    """The load or unload on this machine's own host; raises ValueError with the reason it cannot."""
    from halo_harness.fleet.ollama_share import served_here
    from halo_harness.providers.ollama import resolve_ollama_host
    from halo_harness.providers.ollama_load import load, unload
    name, model = str(fields.get("host") or "").strip(), str(fields.get("model") or "").strip()
    if not model:
        raise ValueError("say which model to load or unload")
    host = resolve_ollama_host(name or None)
    if host is None:
        raise ValueError(f"no Ollama host named {name!r} here")
    if not served_here(host.url):
        raise ValueError(f"{host.name} is not served by this machine")
    if fields.get("cmd") == "ollama_unload":
        return unload(host, model)
    num_ctx = fields.get("num_ctx") if isinstance(fields.get("num_ctx"), int) else None
    return load(host, model, num_ctx=num_ctx, keep_alive=fields.get("keep_alive"))
