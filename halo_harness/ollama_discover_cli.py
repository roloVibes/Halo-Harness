"""halo_harness.ollama_discover_cli -- `halo ollama discover [--lan] [--add
[NAME,NAME]] [--calibrate] [--twins | --no-twins] [--json] [--timeout S]`
(Halo 3.2.3.0 R2; the tuned-twins question after `--calibrate`: R3): the
Ollama servers on this machine (and, with `--lan`, on the network), one
line each with the models it serves; `--add` writes the new ones as
`ollama.hosts` entries; `--calibrate` then measures each of their models.
Exit 0 when a server was found, 1 when none was, 2 on a usage error.
"""

from __future__ import annotations

import argparse
import json
import sys


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="halo ollama discover", add_help=True,
        description="Find the Ollama servers on this machine (OLLAMA_HOST, loopback on ollama.discover.ports, "
                    "this machine's LAN address, Docker, WSL) and, with --lan, on the network; list each "
                    "one's models; add the new ones to ollama.hosts; measure their windows.")
    parser.add_argument("--lan", action="store_true",
                        help="also scan the network: this machine's /24 plus ollama.discover.subnets (about 10 s)")
    parser.add_argument("--add", nargs="?", const="", default=None, metavar="NAME,NAME",
                        help="write the new servers as ollama.hosts entries (all of them, or the named ones)")
    parser.add_argument("--calibrate", action="store_true",
                        help="after --add, measure every model of the hosts added (and of the named configured "
                             "ones): one progress line per model, recorded in ~/.halo/ollama-fit.json")
    parser.add_argument("--twins", action="store_true",
                        help="after --calibrate, make a tuned twin of every model that fits without asking")
    parser.add_argument("--no-twins", action="store_true",
                        help="after --calibrate, skip the tuned-twins question")
    parser.add_argument("--json", action="store_true", help="print the servers and the measurements as JSON")
    parser.add_argument("--timeout", type=float, default=None, metavar="S",
                        help="the calibration's per-step budget in seconds (default: the calibration's own)")
    return parser


def cmd_ollama_discover(argv: list) -> int:
    try:
        args = _parser().parse_args(argv)
    except SystemExit as e:
        return int(e.code) if isinstance(e.code, int) else 2
    if args.timeout is not None and args.timeout <= 0:
        print("halo ollama discover: --timeout needs a positive number of seconds", file=sys.stderr)
        return 2
    if args.twins and args.no_twins:
        print("halo ollama discover: --twins and --no-twins are each other's opposite; pass one", file=sys.stderr)
        return 2
    from halo_harness.providers.ollama_discover import add_hosts, discover
    from halo_harness.providers.ollama_discover_hosts import format_row

    say = (lambda text: print(text, file=sys.stderr)) if args.json else print
    rows = discover("all" if args.lan else "local", on_progress=say)
    if not args.json:
        for row in rows:
            print(format_row(row))
        for note in rows.notes:
            print(f"note: {note}")
        if not rows:
            print("No Ollama server found" + (" on this machine or the network." if args.lan else
                                               " on this machine (--lan also scans the network)."))
    names = [n.strip() for n in args.add.split(",") if n.strip()] if args.add else None
    added_lines: "list[str]" = []
    added_hosts: "list[str]" = []
    if args.add is not None and rows:
        from halo_harness.theme import get_config_value
        before = {str(h.get("name")) for h in (get_config_value("ollama.hosts", default=None) or [])
                  if isinstance(h, dict)}
        added_lines = add_hosts(rows, names)
        after = [str(h.get("name")) for h in (get_config_value("ollama.hosts", default=None) or [])
                 if isinstance(h, dict)]
        added_hosts = [n for n in after if n not in before]
        if not args.json:
            for line in added_lines or ["nothing new to add: every server found is already in ollama.hosts"]:
                print(line)
    measurements: "list[dict]" = []
    if args.calibrate:
        from halo_harness.providers.ollama import resolve_ollama_host
        from halo_harness.providers.ollama_discover import url_key
        from halo_harness.providers.ollama_discover_measure import measure_hosts
        wanted = {n.lower() for n in names or []}
        by_host: dict = {}
        for name in added_hosts + [r.name for r in rows if r.configured and r.name.lower() in wanted]:
            host = resolve_ollama_host(name)
            match = [r for r in rows if host is not None and url_key(r.url) == url_key(host.url)]
            # the default host `add_hosts` keeps for a bare ol:<model> is not one the user picked
            if match and name not in by_host and (not match[0].configured or name.lower() in wanted):
                by_host[name] = match[0].models
        if not by_host:
            say("nothing to calibrate: --calibrate measures the hosts --add adds (or names)")
        else:
            measurements = measure_hosts(list(by_host), models_by_host=by_host, timeout=args.timeout, on_line=say)
    twins = _offer_twins(args, measurements, say)
    if args.json:
        print(json.dumps({"servers": [r.as_dict() for r in rows], "notes": rows.notes, "added": added_lines,
                          "measurements": measurements, "twins": twins}, indent=2))
    return 0 if rows else 1


def _ask(question: str) -> bool:
    """Enter (or y) = yes, n = no; stdin that is not a terminal answers no."""
    try:
        if not sys.stdin.isatty():
            print(f"{question} -- not asked (stdin is not a terminal); --twins makes them")
            return False
        return input(f"{question} ").strip().lower() not in ("n", "no")
    except (EOFError, OSError, ValueError):
        return False


def _offer_twins(args, measurements: "list[dict]", say) -> "list[dict]":
    """Halo 3.2.3.0 R3: after the measurements, "make tuned twins of the
    models that fit? (Enter / n)" -- `--twins` answers yes, `--no-twins`
    (and `--json` without `--twins`) skips it; one line per twin made."""
    from halo_harness.providers.ollama_tune_offer import TWIN_QUESTION, make_twins, twin_candidates
    if args.twins and not args.calibrate:
        say("no twins: --twins follows the measurements of --calibrate (or run `halo ollama tune MODEL`)")
        return []
    if args.no_twins or not twin_candidates(measurements):
        return []
    if not args.twins and (args.json or not _ask(TWIN_QUESTION)):
        return []
    return make_twins(measurements, on_line=say)
