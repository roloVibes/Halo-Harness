"""halo_harness.packs.cli_policy -- `halo pack mode` and `halo pack policy` (Halo 3.3.10.0 R1; docs/COMMANDS-packs.md,
docs/EXTENSION_API.md "Policy hooks", draft).

    halo pack mode <pack> <mode> on|off [--note TEXT] [--json]
                                    turn one of the pack's modes on or off (mode.json); on arms the policies that name it
    halo pack policy status [--json]                  every pack's mode and each policy: armed, asked now, or why not
    halo pack policy arm <pack> <policy> [--json]     arm one policy (mode.json's armed list)
    halo pack policy disarm <pack> [<policy>] [--json]
                                                      disarm one, or every armed policy of the pack
    halo pack policy test <pack> <policy> <tool> '<json input>' [--budget-ms N] [--json]
                                    a verdict without a session: arms nothing, starts the policy's process for
                                    this one request, prints `deny -- fence: outside the project (12 ms)`

Every verb takes `--cwd DIR`. Exit codes: 0 done (any verdict), 1 could not (one line on stderr), 2 usage.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ACTIONS = ("status", "arm", "disarm", "test")


def _parser(verb: str) -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog=f"halo pack {verb}")
    if verb == "mode":
        p.add_argument("pack", help="the pack's id")
        p.add_argument("mode", help="one of the pack's contributes.modes ids")
        p.add_argument("switch", choices=("on", "off"), help="on: the mode is on, its policies armed; off: both undone")
        p.add_argument("--note", default="", help="a line kept in mode.json beside the mode")
    else:
        p.add_argument("action", choices=ACTIONS, help="status, arm, disarm or test")
        p.add_argument("rest", nargs="*", metavar="ARG",
                       help="arm <pack> <policy>; disarm <pack> [<policy>]; test <pack> <policy> <tool> '<json input>'")
        p.add_argument("--budget-ms", type=int, default=None, metavar="N",
                       help="test: how long to wait for the answer (default packs.policy.budget_ms, 2000)")
    p.add_argument("--cwd", default=None, metavar="DIR", help="act as if run from DIR")
    p.add_argument("--json", action="store_true", help="print JSON")
    return p


def _done(args, ok: bool, lines: "list[str]", extra=None) -> int:
    if args.json:
        print(json.dumps({"ok": ok, "lines": lines, **(extra or {})}, indent=2, ensure_ascii=False, default=str))
        return 0 if ok else 1
    stream = sys.stdout if ok else sys.stderr
    for line in lines:
        print(line if ok else f"halo pack: {line}", file=stream)
    return 0 if ok else 1


def _usage(args, text: str) -> int:
    print(f"halo pack: {text}", file=sys.stderr)
    return 2


def _test(args, cwd: Path) -> int:
    """The dry run: one request to the policy's own process, which stops after the answer."""
    from halo_harness.packs import mode_state as M
    from halo_harness.packs import policy as P
    from halo_harness.packs import state as S
    from halo_harness.packs.discover import find
    from halo_harness.packs.grants import no_pack_line
    from halo_harness.packs.registry import snapshot
    if len(args.rest) != 4:
        return _usage(args, "halo pack policy test <pack> <policy> <tool> '<json input>'")
    pack_id, policy_id, tool, raw = args.rest
    pack = find(pack_id, cwd=cwd)
    if pack is None:
        return _done(args, False, [no_pack_line(pack_id)])
    if pack.problems:
        return _done(args, False, [f"{pack.id}: pack.yaml: {line}" for line in pack.problems])
    pol = next((p for p in P.declared(pack) if p.id == policy_id), None)
    if pol is None:
        ids = ", ".join(p.id for p in P.declared(pack)) or "none"
        return _done(args, False, [f"{pack.id} declares no policy {policy_id!r} (contributes.policy: {ids})"])
    try:
        tool_input = json.loads(raw)
    except ValueError as e:
        return _done(args, False, [f"the tool input is not JSON: {e}"])
    if not isinstance(tool_input, dict):
        return _done(args, False, ["the tool input is a JSON object: '{\"file_path\": \"/tmp/x\"}'"])
    rec = M.read(pack.id)
    req = P.request(pol, tool, tool_input, cwd=cwd, session="dry-run", mode=rec["mode"])
    v = P.ask(pol, req, budget_ms=args.budget_ms, keep=False)
    lines = [v.line()]
    if v.asked and not v.error:
        lines.append(f"  rule: {v.rule or '-'}; scope: {v.scope}")
    if not v.asked:
        lines.append("  the process was not started: when.tools filters the call before it")
    if pol.modes and rec["mode"] not in pol.modes:
        lines.append(f"  a session asks it only while mode {' or '.join(pol.modes)} is on (the mode now: {rec['mode'] or 'none'})")
    snap = snapshot(cwd=cwd)
    if pack.id not in snap.order or "hooks" not in S.granted(pack.id, snap.state):
        lines.append(f"  a session asks it once the pack runs with hooks: halo pack enable {pack.id} --grant hooks")
    lines.append("  a dry run: nothing was armed; nothing enforces a verdict before 3.3.10.0 R2")
    from dataclasses import asdict
    return _done(args, True, lines, {"verdict": asdict(v)})


def cmd(verb: str, argv: list) -> int:
    from halo_harness.packs import mode_state as M
    try:
        args = _parser(verb).parse_args(argv)
    except SystemExit as e:
        return int(e.code or 0)
    cwd = Path(args.cwd).resolve() if args.cwd else Path.cwd().resolve()
    if verb == "mode":
        return _done(args, *M.set_mode(args.pack, args.mode, args.switch == "on", by="cli", note=args.note, cwd=cwd))
    if args.action == "status":
        from halo_harness.packs.policy_views import status, status_lines
        rows = status(cwd=cwd)
        if args.json:
            print(json.dumps({"packs": rows}, indent=2, ensure_ascii=False, default=str))
        else:
            print("\n".join(status_lines(rows)))
        return 0
    if args.action == "test":
        return _test(args, cwd)
    if args.action == "arm":
        if len(args.rest) != 2:
            return _usage(args, "halo pack policy arm <pack> <policy>")
        return _done(args, *M.arm(args.rest[0], args.rest[1], by="cli", cwd=cwd))
    if len(args.rest) not in (1, 2):
        return _usage(args, "halo pack policy disarm <pack> [<policy>]")
    return _done(args, *M.disarm(args.rest[0], args.rest[1] if len(args.rest) == 2 else None, by="cli", cwd=cwd))
