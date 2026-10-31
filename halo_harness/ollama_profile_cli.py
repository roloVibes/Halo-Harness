"""halo_harness.ollama_profile_cli -- `halo ollama profile ...` (Halo 3.3.7.0 R3): the steward profiles by hand, a
lane's own included (plans/local-model-fit-brief.md D1 6).

    profile [list] [--host H] [--json]                          every profile (`<host>|<model>[|<role>]`)
    profile set <host> <model> <field> <value> [--role R]       one field; `--role` writes the lane's own key
    profile unset <host> <model> <field> [--role R]             the field removed (the key goes when empty)

The fields: num_ctx, num_predict, keep_alive, tools_max, host_for, compact_at (ollama_steward/profiles.CHANGEABLE).
A call on that host and model reads the lane's key first, then `<host>|<model>` (field by field). A set goes
through agent_proposals.land_user (checked like any change you apply; one row in changes.jsonl, so
`halo local revert <id>` puts it back). Halo-side only: nothing on the server changes.
"""

from __future__ import annotations

import argparse
import json
import sys

INTS = ("num_ctx", "num_predict", "tools_max")


def _value(field: str, raw: str):
    if field in INTS:
        return int(raw)
    if field == "compact_at":
        return float(raw)
    if field == "keep_alive":
        try:
            return int(raw)
        except ValueError:
            return raw
    return raw


def _key(args) -> str:
    from halo_harness.ollama_steward.profiles import key_for
    return key_for(args.host, args.model, args.role)


def cmd_ollama_profile(argv: list) -> int:
    from halo_harness.ollama_steward.profiles import CHANGEABLE, all_profiles, split_role
    parser = argparse.ArgumentParser(prog="halo ollama profile", add_help=True,
                                     description="The steward profiles: one per host and model, a lane's own with "
                                                 "--role. Halo-side only.")
    sub = parser.add_subparsers(dest="what")
    lp = sub.add_parser("list", help="every profile")
    for p in (parser, lp):
        p.add_argument("--host", dest="only_host", default=None, help="only this host")
        p.add_argument("--json", action="store_true", help="print JSON")
    for verb in ("set", "unset"):
        sp = sub.add_parser(verb, help=f"{verb} one field of one profile")
        sp.add_argument("host")
        sp.add_argument("model")
        sp.add_argument("field", choices=CHANGEABLE)
        if verb == "set":
            sp.add_argument("value")
        sp.add_argument("--role", default=None, help="the lane's own key (<host>|<model>|<role>)")
    args = parser.parse_args(argv)
    if args.what in ("set", "unset"):
        from halo_harness.config.paths import bridge_home
        from halo_harness.ollama_steward.agent_proposals import land_user
        try:
            to = _value(args.field, args.value) if args.what == "set" else None
        except ValueError:
            print(f"halo ollama profile: {args.field} takes a number, not {args.value!r}", file=sys.stderr)
            return 2
        got = land_user(bridge_home(), {"key": _key(args), "field": args.field, "to": to}, by="user",
                        why="halo ollama profile " + args.what)
        print(got["line"], file=sys.stdout if got.get("ok") else sys.stderr)
        return 0 if got.get("ok") else 1
    rows = {k: v for k, v in sorted(all_profiles().items())
            if not getattr(args, "only_host", None) or split_role(k)[0] == args.only_host}
    if getattr(args, "json", False):
        print(json.dumps(rows, indent=2, default=str))
        return 0
    if not rows:
        print("no profiles: the steward writes them as it learns, or halo ollama profile set ...")
    for k, v in rows.items():
        host, model, role = split_role(k)
        fields = ", ".join(f"{f} {v[f]}" for f in CHANGEABLE if f in v)
        print(f"{host}|{model}" + (f" (the {role} lane)" if role else "") + f": {fields or 'no fields'} "
              f"(by {v.get('by') or 'you'})")
    return 0
