"""halo_harness.checks.pack -- a pack's Setup check as one more row of the checks job (Halo 3.3.11.0 R3;
docs/EXTENSION_API.md "Setup blocks", docs/STUDIO-setup.md "A pack's blocks").

An enabled pack's `contributes.setup` block of kind `check` is a row shaped like checks/catalog.py's CHECKS --
`{key: "pack:<id>:<block>", title, what, cost, time, writes, default_on: False, run}` plus `pack`, `pack_name` and
`block` -- with the pack's own what / cost / time / writes lines and off by default. `rows(cwd, state_dir)` reads
them from the enabled packs and remembers them, so `checks.check(key)` and `checks.ordered(keys)` know the keys the
Check page offered; the checks job then runs one as it runs a core check (`run_one`), its frames the same frames.

`run` starts the block's command in the pack's folder (`${halo_python}` and `${CLAUDE_PLUGIN_ROOT}` put in, exec
form, no shell) with the environment a pack hook gets: Halo's environment less every provider key it holds
(`tool_child_env`), plus CLAUDE_PLUGIN_ROOT, CLAUDE_PROJECT_DIR, HALO_PACK_ID and HALO_SETUP_BLOCK. Exit 0 is green
and marks the block done in the pack's setup.json (packs/setup_state.py); its stdout lines are the row's lines; any
other exit is red, with the last stderr lines and the exit code. A command that takes longer than TIMEOUT_S is
stopped and red.
"""

from __future__ import annotations

import os
import subprocess
import threading

from halo_harness.checks.run import CheckFailed

TIMEOUT_S = 120
MAX_LINES = 40
_lock = threading.Lock()
_LIVE: "dict[str, dict]" = {}


def is_pack_key(key) -> bool:
    from halo_harness.packs.manifest_setup import split_key
    return bool(split_key(key)[0])


def _env(pack, block_id: str, cwd) -> dict:
    from halo_harness.packs.interpreter import pack_env
    from halo_harness.providers.config import tool_child_env
    env = tool_child_env(dict(os.environ))  # the provider keys Halo holds stay out, as for every pack hook
    env.update({"CLAUDE_PLUGIN_ROOT": str(pack.root), "CLAUDE_PROJECT_DIR": str(cwd or os.getcwd()),
                "HALO_PACK_ID": pack.id, "HALO_SETUP_BLOCK": block_id})
    return pack_env(pack.root, env)


def _lines(text: str) -> "list[str]":
    return [ln.rstrip() for ln in (text or "").splitlines() if ln.strip()]


def run_block(pack, e: dict, ctx) -> "list[str]":
    """Run one check block now; its stdout lines (exit 0, the block marked done) or CheckFailed."""
    from halo_harness.packs.manifest_policy import run_argv
    from halo_harness.packs.setup_state import DONE, mark
    argv = run_argv(e, pack.root)
    if not argv:
        raise CheckFailed([f"{pack.id}: setup block {e.get('id')} names no command"])
    try:
        r = subprocess.run(argv, cwd=str(pack.root), env=_env(pack, str(e.get("id")), getattr(ctx, "cwd", None)),
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=TIMEOUT_S,
                           stdin=subprocess.DEVNULL)
    except subprocess.TimeoutExpired:
        raise CheckFailed([f"no answer in {TIMEOUT_S} s: the check was stopped"])
    except OSError as ex:
        raise CheckFailed([f"the check did not start: {type(ex).__name__}: {ex}"])
    lines = _lines(r.stdout)[:MAX_LINES]
    if r.returncode != 0:
        raise CheckFailed(lines + _lines(r.stderr)[-10:] + [f"exit {r.returncode}"])
    mark(pack.id, str(e.get("id")), DONE, by="check", state_dir=getattr(ctx, "state_dir", None))
    return lines or ["exit 0"]


def _row(pack, e: dict) -> dict:
    from halo_harness.packs.manifest_setup import key_of
    return {"key": key_of(pack.id, str(e["id"])), "title": str(e.get("title") or e["id"]), "default_on": False,
            "what": str(e.get("what") or ""), "cost": str(e.get("cost") or ""), "time": str(e.get("time") or ""),
            "writes": str(e.get("writes") or ""), "pack": pack.id, "pack_name": str(pack.name or pack.id),
            "block": str(e["id"]), "run": lambda ctx, _p=pack, _e=e: run_block(_p, _e, ctx)}


def rows(cwd=None, state_dir=None, packs=None) -> "list[dict]":
    """The enabled packs' check blocks as check rows (remembered for `entry` / `known`); `packs` the active packs
    when the caller has them."""
    from halo_harness.packs.manifest_setup import setup_of
    if packs is None:
        from halo_harness.packs.registry import active
        packs = active(cwd=cwd, state_dir=state_dir)
    out = [_row(p, e) for p in packs for e in setup_of(p.manifest)
           if e.get("kind") == "check" and isinstance(e.get("id"), str)]
    with _lock:
        _LIVE.clear()
        _LIVE.update({r["key"]: r for r in out})
    return out


def entry(key: str):
    with _lock:
        return _LIVE.get(key)


def known(key) -> bool:
    return isinstance(key, str) and entry(key) is not None


def public(row: dict) -> dict:
    """The row as `GET setup/state` lists it (no `run`)."""
    return {k: v for k, v in row.items() if k != "run"}
