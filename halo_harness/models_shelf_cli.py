"""halo_harness.models_shelf_cli -- Halo 3.3.6.0 R4: the model shelf from the terminal (models_library/shelf.py;
catalog_cli.cmd_models dispatches the verbs):

    halo models retire <model> [--host H] [--why TEXT] [--force]
        the uses card first (a live session on it waits; a use asks unless --force), then the delete
        (halo models rm's path) and one shelf line with how to get it back
    halo models shelf [--host H] [--json]
        every installed model's last use, size and whether a role picked it, then the retired ones
    halo models shelf --repull <model> [--host H]
        pull a retired model back (a fitted twin prints its recipe)
"""

from __future__ import annotations

import argparse
import json
import sys
import time


def _host(name):
    from halo_harness.providers.ollama import resolve_ollama_host
    return resolve_ollama_host(name or None)


def _retire(argv: list) -> int:
    from halo_harness.config.paths import bridge_home
    from halo_harness.models_library.shelf import retire
    p = argparse.ArgumentParser(prog="halo models retire", description="Delete a model from an Ollama host and keep a "
                                "note on the shelf so it comes back with one command (halo models shelf --repull).")
    p.add_argument("model")
    p.add_argument("--host", default=None)
    p.add_argument("--why", default="")
    p.add_argument("--force", action="store_true")
    a = p.parse_args(argv)
    host = _host(a.host)
    if host is None:
        print(f"halo models retire: no Ollama host named {a.host!r}", file=sys.stderr)
        return 1
    from halo_harness.providers.local_models_cached import cached_catalog
    from halo_harness.providers.model_card import _row_for
    got = retire(host, a.model, state_dir=bridge_home(), why=a.why, force=a.force, row=_row_for(cached_catalog(host), a.model))
    if not got.get("ok"):
        print(f"halo models retire: {got.get('say')}", file=sys.stderr)
        if got.get("status") == 422:
            print(f"retire it anyway: halo models retire {a.model} --host {host.name} --force", file=sys.stderr)
        return 1
    print(got["say"])
    return 0


def _day(t) -> str:
    return time.strftime("%Y-%m-%d", time.localtime(t)) if t else "never"


def _list(a) -> int:
    from halo_harness.config.paths import bridge_home
    from halo_harness.models_library.shelf import facts, shelf
    state = bridge_home()
    host = _host(a.host)
    rows = []
    if host is not None:
        try:
            from halo_harness.providers.ollama import get_catalog
            rows = (get_catalog(host) or {}).get("models") or []
        except Exception:
            rows = []
    got = facts(state, host, rows) if host is not None else {}
    retired = shelf(state, a.host)
    if a.json:
        print(json.dumps({"installed": got, "shelf": retired}, indent=2, default=str))
        return 0
    if host is not None:
        print(f"installed on {host.name}:")
        for m, f in sorted(got.items(), key=lambda kv: (kv[1].get("last_used") or 0)):
            size = f"{f['size'] / 1e9:.1f} GB" if f.get("size") else "?"
            print(f"  {m}: last used {_day(f.get('last_used'))}, {size}, "
                  f"{'picked by a role' if f.get('picked') else 'no role picked it'}" + (f" -- {f['hint']}" if f.get("hint") else ""))
    print("on the shelf (retired):" if retired else "the shelf is empty: nothing retired")
    for r in retired:
        print(f"  {r['model']} from {r.get('host')} on {str(r.get('retired_at'))[:10]} ({r.get('why')}): {r.get('repull')}")
    return 0


def _repull(a) -> int:
    from halo_harness.config.paths import bridge_home
    from halo_harness.models_library.shelf import mark_repulled, shelf
    state = bridge_home()
    hit = next((r for r in shelf(state, a.host) if r.get("model") == a.repull), None)
    if hit is None:
        print(f"halo models shelf: {a.repull} is not on the shelf", file=sys.stderr)
        return 1
    if not str(hit.get("repull")).startswith("ollama pull "):
        print(f"{a.repull} was a fitted twin: re-make it with {hit['repull']}")
        return 0
    host = _host(a.host or hit.get("host"))
    if host is None:
        print(f"halo models shelf: no Ollama host named {hit.get('host')!r}", file=sys.stderr)
        return 1
    from halo_harness.models_control_cli import cmd_models_control
    rc = cmd_models_control("pull", [a.repull, "--host", host.name])
    if rc == 0:
        mark_repulled(state, host.name, a.repull)
    return rc


def cmd_models_shelf(verb: str, argv: list) -> int:
    if verb == "retire":
        return _retire(argv)
    p = argparse.ArgumentParser(prog="halo models shelf", description="The installed models' last use and size, and "
                                "the retired ones with how to get each back.")
    p.add_argument("--host", default=None)
    p.add_argument("--repull", default=None, metavar="MODEL")
    p.add_argument("--json", action="store_true")
    a = p.parse_args(argv)
    return _repull(a) if a.repull else _list(a)
