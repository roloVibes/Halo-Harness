"""halo_harness.packs.cli_bundle -- the bundle verbs of `halo pack` (Halo 3.3.7.0 R5; docs/COMMANDS-packs.md "Bundles").

    halo pack verdict <bundle> [--host H] [--json]     the honest verdict, before anything downloads: ready / needs N
                                                       downloads (each tag, its size, its fit, the minutes, and the
                                                       pull lines) / won't work, with the ways out, each a number
    halo pack on <bundle> [--host H] [--json]          turn it on: a ready bundle is installed and enabled, its
                                                       reservation claimed (the paired halo host when one serves the
                                                       card), the reserved model's keep_alive -1 (kept until off)
    halo pack off <bundle> [--json]                    the claim released, the keep_alive put back, the pack disabled
    halo pack list --bundles [--host H] [--json]       every bundle here and shipped, on or off, with its verdict line

Exit codes: 0 done, 1 could not (the reason printed), 2 usage. Nothing downloads: the verdict's download lines are
printed for you to run (or the Pack Manager's one button).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

VERBS = ("verdict", "on", "off")


def _parser(verb: str) -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog=f"halo pack {verb}")
    if verb != "list":
        p.add_argument("bundle", help="a bundle's id (halo pack list --bundles)")
    if verb == "list":
        p.add_argument("--bundles", action="store_true", help="the bundles, each with its verdict line")
    if verb != "off":
        p.add_argument("--host", default=None, help="the Ollama host to judge (its name here; the default one)")
    p.add_argument("--cwd", default=None, metavar="DIR", help="act as if run from DIR")
    p.add_argument("--json", action="store_true", help="print JSON")
    return p


def _state():
    from halo_harness.config.paths import bridge_home
    return bridge_home()


def verdict_lines(v: dict) -> list:
    out = [f"{v['bundle']} on {v['host'] or 'this machine'}: {v['state']}", f"  {v.get('main_says') or v['says']}"]
    for p in v.get("parts") or []:  # 3.3.8.0 R4: its other reservations, each where it is held
        out.append(f"  + {p['says']} [{p['state']}]")
    if v.get("schedule"):
        out.append(f"  schedule: {v['schedule']['line']}")
    if v.get("priority") and v.get("priority") != "normal":
        out.append(f"  priority {v['priority']}: when two claims collide the lower one is pre-empted and told")
    for n in v.get("notices") or []:
        out.append(f"  ! {n['line']} (at {n.get('when') or '?'})")
    if v.get("claims_line"):
        out.append(f"  {v['claims_line']}")
    out += [f"  {'!' if o['kind'] == 'warn' else '-'} {o['says']}" for o in v.get("options") or []]
    if v.get("button"):
        out.append(f"  {v['button']['label']}: " + " && ".join(
            f"halo models pull {t} --host {v['host']} && halo models probe {t} --host {v['host']}" for t in v["button"]["tags"]))
    for c in v.get("voice_downloads") or []:  # 3.3.9.0 R1: a speech model comes from the hub, on this machine
        out.append(f"  speech model: {c}")
    return out


def with_notices(v: dict) -> dict:
    """3.3.8.0 R4: a pre-emption its owner is told of (claims_file.notice, the last day)."""
    import time
    from halo_harness.local_sched import claims_file as CF
    rows = CF.notices(CF.local_file(_state()), v.get("bundle"))
    v["notices"] = [{**n, "when": time.strftime("%H:%M", time.localtime(float(n.get("at") or 0)))} for n in rows]
    return v


def _verdict(args, cwd) -> int:
    from halo_harness.local_sched.bundle_parts import verdict  # 3.3.8.0 R4: every reservation where it is held
    from halo_harness.packs.bundles import find
    e = find(args.bundle, cwd=cwd)
    if e is None or e["block"] is None:
        print(f"halo pack: no bundle {args.bundle!r} here (halo pack list --bundles)", file=sys.stderr)
        return 1
    v = with_notices(verdict(e["block"], args.host, state_dir=_state()))
    print(json.dumps(v, indent=2, default=str) if args.json else "\n".join(verdict_lines(v)))
    return 0


def _list(args, cwd) -> int:
    from halo_harness.local_sched.bundle_parts import verdict
    from halo_harness.local_sched.reserve import claims
    from halo_harness.packs.bundles import listing
    on = {c["bundle"] for c in claims(None, state_dir=_state())}
    rows = []
    for e in listing(cwd=cwd):
        v = verdict(e["block"], args.host, state_dir=_state()) if e["block"] else {"state": "unknown", "says": ""}
        rows.append({"id": e["id"], "name": e["name"], "scope": e["scope"], "on": e["id"] in on, "state": v["state"],
                     "says": v["says"], "problems": e["problems"]})
    if args.json:
        print(json.dumps({"bundles": rows}, indent=2))
        return 0
    if not rows:
        print("no bundles here")
    for r in rows:
        print(f"[{'x' if r['on'] else ' '}] {r['id']:<14} {r['state']:<9} {r['says']}")
    return 0


def _onoff(verb: str, args, cwd) -> int:
    from halo_harness.local_sched.reserve_act import claim, release
    if verb == "on":
        ok, lines, v = claim(args.bundle, host=args.host, holder="keep", cwd=cwd)
        if ok and not args.json:
            lines.append(f"held until: halo pack off {args.bundle}")
    else:
        ok, lines = release(args.bundle, cwd=cwd)
        v = None
    if args.json:
        print(json.dumps({"ok": ok, "lines": lines, **({"verdict": v} if v else {})}, indent=2, default=str))
        return 0 if ok else 1
    print("\n".join(lines), file=sys.stdout if ok else sys.stderr)
    return 0 if ok else 1


def cmd(verb: str, argv: list) -> int:
    try:
        args = _parser(verb).parse_args(argv)
    except SystemExit as e:
        return int(e.code or 0)
    cwd = Path(args.cwd).resolve() if args.cwd else Path.cwd().resolve()
    if verb == "verdict":
        return _verdict(args, cwd)
    if verb == "list":
        return _list(args, cwd)
    return _onoff(verb, args, cwd)
