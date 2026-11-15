"""halo_harness.crew_cli_parts -- what `halo agents` and `halo workflows` share (Halo 3.6.0.0 R5): list a kind's files
nearest first, show one, make one of yours from a starter (or a blank one), open one to edit (your $VISUAL / $EDITOR on
your file, else Studio's tab on it), and wait for a Try it run to end.

Every file is in ~/.halo/crew/<kind>s/ (yours) or a trusted project's .halo/crew/<kind>s/; the starters ship read-only
(halo_harness/templates/crew/). Nothing here writes anything but the one file of yours a `new` asks for.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

TABS = {"agent": "1 · Agents", "workflow": "2 · Workflows", "map": "3 · Map"}


def print_list(kind: str, cwd: Path, extra=None) -> int:
    from halo_harness.crew import store
    rows = store.rows(kind, cwd=cwd)
    if not rows:
        print(f"no {kind}s (the starters ship with Halo: check the install)")
        return 0
    seen = set()
    for r in rows:
        shadowed = r["name"] in seen
        seen.add(r["name"])
        what = str(r.get("does") or r.get("for") or "").strip().replace("\n", " ")
        bad = f"  problem: {r['_problems'][0]}" if r.get("_problems") else ""
        more = f"  {extra(r)}" if extra else ""
        print(f"  {r['name']:<22} {r['_scope']:<8}{' (shadowed)' if shadowed else ''} {what[:70]}{more}{bad}")
    return 0


def show(kind: str, name: str, cwd: Path) -> int:
    from halo_harness.crew import store
    got = store.load(kind, name, cwd=cwd)
    if got is None:
        print(f"halo {kind}s show: no {kind} named {name!r} (halo {kind}s list)", file=sys.stderr)
        return 1
    print(f"# {got['_path']} ({got['_scope']})")
    print(store.dump(store.clean(got)).rstrip())
    used = store.used_by(name, cwd=cwd) if kind == "agent" else store.maps_with(name, cwd=cwd)
    if used:
        print(f"# used by: {', '.join(used)}")
    return 0


def new(kind: str, name: str, start: "str | None", cwd: Path, blank: dict) -> int:
    from halo_harness.crew import store
    from halo_harness.crew.formats import name_problem
    bad = name_problem(name)
    if bad:
        print(f"halo {kind}s new: {bad}", file=sys.stderr)
        return 2
    if store.find(kind, name, cwd=cwd, scope="yours"):
        print(f"halo {kind}s new: you have a {kind} named {name} already (halo {kind}s edit {name})", file=sys.stderr)
        return 1
    if start:
        got = store.load(kind, start, cwd=cwd)
        if got is None:
            print(f"halo {kind}s new: no {kind} named {start!r} to start from (halo {kind}s list)", file=sys.stderr)
            return 1
        raw = {**store.clean(got), "name": name}
    else:
        raw = {**blank, "name": name}
    path = store.path_for(kind, name)
    store.write_text(path, store.dump(raw))
    print(f"wrote {path}" + (f" (from {start})" if start else "") + f"; halo {kind}s edit {name} opens it")
    return 0


def edit(kind: str, name: str, cwd: Path) -> int:
    from halo_harness.crew import store
    found = store.find(kind, name, cwd=cwd)
    if found is None:
        print(f"halo {kind}s edit: no {kind} named {name!r} (halo {kind}s list)", file=sys.stderr)
        return 1
    path, scope = found
    editor = os.environ.get("VISUAL") or os.environ.get("EDITOR")
    if scope != "starter" and editor and sys.stdin.isatty():
        return subprocess.call([*editor.split(), str(path)])
    if scope == "starter":
        print(f"{name} is a starter (read-only): halo {kind}s new my-{name} --from {name} makes yours")
    print(f"opening Studio on it: halo studio --edit {kind}:{name} (Agents -> {TABS[kind]})")
    from halo_harness.studio_edit_cli import open_in_studio
    return open_in_studio(kind, name, no_open=False, prog=f"halo {kind}s edit")


def wait_try(rec: dict, state_dir=None, poll: float = 0.5) -> dict:
    """Wait for a Try it run to end; its record."""
    from halo_harness.crew import trial
    tid = rec.get("id")
    while True:
        got = trial.get(str(tid), state_dir) or rec
        if got.get("state") not in ("running", "stopping"):
            return got
        time.sleep(poll)


def say_try(rec: dict) -> int:
    cost = rec.get("cost_usd")
    money = f", ${cost:.4f}" if isinstance(cost, (int, float)) else ""
    print(f"Try it {rec.get('state')}: {rec.get('agent')}{money} on {rec.get('model') or 'each agent its own model'}")
    for s in rec.get("steps") or []:
        print(f"  step {s.get('n', '?')}: {s.get('name', '')} -- {s.get('state', '')}")
    text = str(rec.get("reply") or rec.get("error") or "").strip()
    if text:
        print(text)
    return 0 if rec.get("state") == "done" else 1
