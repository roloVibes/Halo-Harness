"""halo_harness.pool_cli -- `halo pool ...` (Halo 3.3.8.0 R1; docs/COMMANDS-pool.md, docs/POOL.md).

    halo pool members [--json]
    halo pool add <name> <host[:port]> [--weight W] [--vram GB] [--json]
    halo pool remove <name> [--json]
    halo pool recommend [--batch] [--json]
    halo pool verdict <model> [--json]
    halo pool scan [--port N] [--subnet CIDR ...] [--no-own-subnet] [--json]      (pool_scan_cli.py)
    halo pool preflight <model> | rpc <member> on|off|status | status | stop       (pool_run_cli.py, 3.3.8.0 R3)

The pool is a set of paired hosts whose GPU memory serves one model together over llama.cpp RPC. These verbs read and
recommend: nothing here launches rpc-server or llama-server (pool_run_cli.py and `halo local serve --pool` do); the
only network traffic is `scan` (which you run) and the host-card reads Halo already does. Exit codes: 0 done, 1
could not (the reason on stderr), 2 usage.
"""

from __future__ import annotations

import argparse
import sys

from halo_harness.remote import cli_common as C

VERBS = ("members", "add", "remove", "recommend", "verdict", "scan", "preflight", "rpc", "status", "stop")
USAGE = """usage: halo pool members [--json]
       halo pool add <name> <host[:port]> [--weight W] [--vram GB] [--json]
       halo pool remove <name> [--json]
       halo pool recommend [--batch] [--json]
       halo pool verdict <model> [--json]
       halo pool scan [--port N] [--subnet CIDR ...] [--no-own-subnet] [--json]
       halo pool preflight <model> [--window N] [--allow-wifi] [--json]
       halo pool rpc <member> on | off | status [--json]     halo pool status [--json]     halo pool stop [--json]
       halo local serve --pool <model> [--window N] [--allow-wifi] [--keep] [--json]

  members    the members, each one's GPU, free / total VRAM (from its host card), link and RTT, and the tensor split
  add        a member: a paired host's name, `local`, or a worker's host[:port] running rpc-server (port 50052)
  remove     take a member out of pool.json
  recommend  what fits the pool (the fewest active parameters first), then what one node holds; --batch shows the
             batch-only models
  verdict    one catalog model's fit on the pool, every number said, and the preview before any download
  scan       probe the RPC port on this machine's /24 (and pool.scan_subnets) and on every member: candidates, RTT
  preflight  every check before a launch: the fit read now, each rpc-server, the link, the builds, the GGUF, the window
  rpc        a member's rpc-server through its halo host (control grant there); status reads it
  status     the running pool: health, degraded (a worker down), the claim on each member
  stop       stop the pool: llama-server stopped, the claims released, the pivoted-out models back (said)"""


def _parser(verb: str, description: str) -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog=f"halo pool {verb}", description=description)
    p.add_argument("--json", action="store_true", help="print the result as JSON")
    return p


def members_view(state_dir=None) -> dict:
    from halo_harness.local_pool.budget import budgets, split_from, tensor_split
    from halo_harness.local_pool.members import check, load, path, rpc_port
    rows = budgets(state_dir=state_dir)
    split = tensor_split(rows)
    counted = [r for r in rows if isinstance(r.get("free_gb"), (int, float)) and r["free_gb"] > 0]
    for r in rows:
        r["share"] = split[counted.index(r)] if r in counted and split else None
        r["share_word"] = f"{r['share']:.2f}" if r["share"] is not None else ""  # the head's own rounding
    free = round(sum(r["free_gb"] for r in counted), 1)
    total = round(sum(float(r.get("total_gb") or 0) for r in counted), 1)
    head = (f"{len(rows)} member{'' if len(rows) == 1 else 's'}, {len(counted)} with VRAM read: {free:.1f} GB free of "
            f"{total:.1f} GB" + (f"; split {' / '.join(f'{w:.2f}' for w in split)} (from {split_from(rows)})" if split else ""))
    return {"members": rows, "split": split, "split_from": split_from(rows) if split else "", "free_gb": free,
            "total_gb": total, "head": head if rows else "no members yet: halo pool add <name> <host[:port]>",
            "problems": check(load(state_dir)) + _reserved(), "file": str(path(state_dir)), "rpc_port": rpc_port()}


def _reserved() -> list:
    """The name `pool` is reserved for the pool's own huggingface.local_servers entry: one line when yours has it."""
    from halo_harness.local_pool.entry import clash
    line = clash()
    return [line] if line else []


def cmd_members(argv: list) -> int:
    p = _parser("members", "The pool's members: GPU, free / total VRAM, link, RTT, the tensor split.")
    a, rc = C.parse(p, argv)
    if a is None:
        return rc
    v = members_view()
    if a.json:
        C.emit_json({"ok": True, **v})
        return 0
    print(v["head"])
    for r in v["members"]:
        share = f" -- share {r['share']:.2f}" if r.get("share") is not None else ""
        print(f"  {r['line']}; RTT {r['rtt_word']}{share} -- the link from {r.get('spoke') or 'nothing yet'}")
    for line in v["problems"]:
        print(f"  ! {line}")
    return 0


def cmd_add(argv: list) -> int:
    p = _parser("add", "Add a member: a paired host's name, `local`, or the host[:port] of a worker running rpc-server.")
    p.add_argument("name", help="the member's name (letters, digits, '.', '-', '_')")
    p.add_argument("target", help="a paired host's name, `local`, or host[:port] (the port defaults to pool.rpc_port)")
    p.add_argument("--weight", type=float, default=None, help="its tensor-split weight (every member's weight set: the "
                                                               "split follows them instead of free VRAM)")
    p.add_argument("--vram", type=float, default=None, help="the VRAM in GB to count for a worker whose card no halo "
                                                             "host reads (the verdict says it is as you stated it)")
    a, rc = C.parse(p, argv)
    if a is None:
        return rc
    from halo_harness.local_pool.members import add
    ok, lines, rows = add(a.name, a.target, weight=a.weight, vram_gb=a.vram)
    if a.json:
        C.emit_json({"ok": ok, "lines": lines, "members": rows})
        return 0 if ok else 1
    for line in lines:
        print(line, file=sys.stdout if ok else sys.stderr)
    return 0 if ok else 1


def cmd_remove(argv: list) -> int:
    p = _parser("remove", "Take a member out of the pool (pool.json); nothing on that machine changes.")
    p.add_argument("name", help="the member's name")
    a, rc = C.parse(p, argv)
    if a is None:
        return rc
    from halo_harness.local_pool.members import remove
    ok, lines, rows = remove(a.name)
    if a.json:
        C.emit_json({"ok": ok, "lines": lines, "members": rows})
        return 0 if ok else 1
    for line in lines:
        print(line, file=sys.stdout if ok else sys.stderr)
    return 0 if ok else 1


def _verdict_lines(v: dict) -> list:
    tags = f" [{', '.join(v['tags'])}]" if v.get("tags") else ""
    rank = f"{v['rank']}. " if v.get("rank") else "-  "
    out = [f"{rank}{v['display']}{tags}: {v['verdict']}"]
    out += [f"     {x}" for x in v["lines"][1:]]
    out.append(f"     preview: {v['preview']}")
    return out


def cmd_recommend(argv: list) -> int:
    p = _parser("recommend", "What fits the pool, the fewest active parameters first; then what one node holds.")
    p.add_argument("--batch", action="store_true", help="show the batch-only models too (always tagged batch-only)")
    a, rc = C.parse(p, argv)
    if a is None:
        return rc
    from halo_harness.local_pool.budget import budgets
    from halo_harness.local_pool.recommend import recommend
    rec = recommend(budgets(), allow_batch=a.batch)
    if a.json:
        C.emit_json({"ok": True, **rec})
        return 0
    print(rec["head"])
    for v in rec["rows"] + rec["others"]:
        for line in _verdict_lines(v):
            print(line)
    for h in rec["hidden"]:
        print(f"-  {h['line']}")
    return 0


def cmd_verdict(argv: list) -> int:
    p = _parser("verdict", "One catalog model's fit on the pool and its preview before any download.")
    p.add_argument("model", help="a pool catalog model: its name, display name or repo")
    a, rc = C.parse(p, argv)
    if a is None:
        return rc
    from halo_harness.local_pool.budget import budgets
    from halo_harness.local_pool.catalog import names
    from halo_harness.local_pool.recommend import verdict
    v = verdict(a.model, budgets())
    if v is None:
        return C.fail(a.json, "unknown_model", f"halo pool verdict: {a.model!r} is not in the pool catalog "
                                               f"({', '.join(names())})")
    if a.json:
        C.emit_json({"ok": True, **v})
        return 0
    for line in _verdict_lines(v):
        print(line)
    return 0


def cmd_pool(argv: list) -> int:
    if not argv or argv[0] in ("-h", "--help"):
        print(USAGE)
        return 0 if argv else 2
    verb, rest = argv[0], argv[1:]
    if verb == "scan":
        from halo_harness.pool_scan_cli import cmd_scan
        return cmd_scan(rest)
    if verb in ("preflight", "rpc", "status", "stop"):  # 3.3.8.0 R3
        from halo_harness.pool_run_cli import VERBS as RUN
        return RUN[verb](rest)
    fn = {"members": cmd_members, "add": cmd_add, "remove": cmd_remove, "recommend": cmd_recommend,
          "verdict": cmd_verdict}.get(verb)
    if fn is None:
        print(USAGE, file=sys.stderr)
        return 2
    return fn(rest)
