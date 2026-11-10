"""halo_harness.local_prompt_cli -- Halo 3.3.16.1: `halo local prompt [<model ref>] [--window N] [--platform P]
[--json]`, what a model's first turn costs before you use it (agent/prompt_measure.py; docs/COMMANDS-local.md).

The composition line, the reply's room and the window it would go out at, then one row per tool: its
tokens and whether it is offered (core, the lineup's square, built-in) or left out and why (the same tool
under another name, the other shell, the window's budget -- callable by name, ToolSearch shows it).
Nothing is sent to the model; an `ol:` model's window is resolved as a call would (its catalog row, the
host, a steward profile), so the host is asked for its catalog once.
"""

from __future__ import annotations

import argparse
import json


def _default_ref() -> str:
    from halo_harness.theme import get_config_value
    try:
        return str(get_config_value("model", default="") or "")
    except Exception:
        return ""


def render(m: dict) -> str:
    from halo_harness.agent.prompt_measure import first_turn_line
    lines = [f"{m['ref']} ({m['platform']}, {'lean' if m['lean'] else 'full'} prompt)",
             first_turn_line(m),
             m["line"],
             (f"reply's room {m['reply_room']:,} · window {m['window'] or 0:,} -> sent at {m['sent_window'] or 0:,}"
              f" · prompt + room {m['total']:,}"),
             ""]
    width = max((len(r["name"]) for r in m["tools"]), default=8)
    for r in m["tools"]:
        mark = "offered " if r["offered"] else "left out"
        lines.append(f"  {r['name']:<{width}}  {r['tokens']:>5,}  {mark}  {r['why']}")
    offered = sum(r["tokens"] for r in m["tools"] if r["offered"])
    lines.append(f"  {'tools':<{width}}  {offered:>5,}  offered in all "
                 f"({sum(1 for r in m['tools'] if r['offered'])} of {len(m['tools'])})")
    return "\n".join(lines)


def cmd_prompt(argv: list) -> int:
    parser = argparse.ArgumentParser(prog="halo local prompt",
                                     description="What a model's first turn costs (nothing is sent).")
    parser.add_argument("ref", nargs="?", help="a model ref (default: your default model)")
    parser.add_argument("--window", type=int, default=None, help="measure at this window (default: the model's own)")
    parser.add_argument("--platform", choices=("win32", "linux", "darwin"), default=None,
                        help="the tools of another platform (default: this one)")
    parser.add_argument("--json", action="store_true", help="the measure as JSON")
    args = parser.parse_args(argv)
    ref = args.ref or _default_ref()
    if not ref:
        print("halo local prompt: no model named and no default model set (halo config set model <ref>)")
        return 2
    from halo_harness.agent.prompt_measure import first_turn
    try:
        m = first_turn(ref, window=args.window, platform=args.platform)
    except Exception as e:
        print(f"halo local prompt: could not measure {ref}: {e}")
        return 1
    if args.json:
        print(json.dumps(m, indent=2, default=str))
        return 0
    print(render(m))
    return 0
