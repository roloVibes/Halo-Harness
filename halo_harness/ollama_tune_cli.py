"""halo_harness.ollama_tune_cli -- `halo ollama tune MODEL [--host H]
[--window N] [--remove] [--json]` (Halo 3.2.3.0 R3): makes a tuned twin of
MODEL on that host -- a derived model `<name>-halo:<tag>` that keeps every
layer on the GPU with the window calibration measured as safe (or N) as
its default, sharing the original's weights. Prints the plan line, the
streamed progress lines, and the twin's ref (`ol:<twin>@<host>`).
`--remove` deletes a twin; an original is never deleted.
Exit 0 done, 1 the host or model is missing / Ollama answered with an error / not a
twin, 2 a usage error.
"""

from __future__ import annotations

import argparse
import json
import sys


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="halo ollama tune", add_help=True,
        description="Make a tuned twin of MODEL on an Ollama host: a derived model named <name>-halo:<tag> "
                    "(FROM MODEL, PARAMETER num_ctx <the calibrated safe window>, PARAMETER num_gpu <every "
                    "layer>) that shares MODEL's weights, so Ollama keeps the whole model on the GPU at that "
                    "window. --remove deletes a twin.")
    parser.add_argument("model", help="the Ollama model to twin (with --remove: the twin to delete)")
    parser.add_argument("--host", default=None, help="a configured ollama.hosts[] name (default host otherwise)")
    parser.add_argument("--window", type=int, default=None, metavar="N",
                        help="the twin's num_ctx (default: the safe window `halo ollama calibrate` recorded)")
    parser.add_argument("--remove", action="store_true",
                        help="delete the tuned twin MODEL (an original is left alone)")
    parser.add_argument("--json", action="store_true", help="print the plan and the outcome as JSON")
    return parser


def cmd_ollama_tune(argv: list) -> int:
    try:
        args = _parser().parse_args(argv)
    except SystemExit as e:
        return int(e.code) if isinstance(e.code, int) else 2
    if args.window is not None and args.window <= 0:
        print("halo ollama tune: --window needs a positive number of tokens", file=sys.stderr)
        return 2
    if args.remove and args.window is not None:
        print("halo ollama tune: --remove takes no --window", file=sys.stderr)
        return 2
    from halo_harness.providers.ollama import resolve_ollama_host
    from halo_harness.providers.ollama_tune import TuneError, create_twin, plan_twin, remove_twin

    say = (lambda text: print(text, file=sys.stderr)) if args.json else print
    host = resolve_ollama_host(args.host)
    if host is None:
        print(f"halo ollama tune: no configured host named {args.host!r} (see `ollama.hosts` in "
              f"~/.halo/config.json, or `halo ollama discover --add`)", file=sys.stderr)
        return 1
    if args.remove:
        result = remove_twin(host, args.model)
        if args.json:
            print(json.dumps({"removed": result.ok, "twin": result.twin, "message": result.message}, indent=2))
        else:
            print(result.message, file=sys.stdout if result.ok else sys.stderr)
        return 0 if result.ok else 1
    try:
        plan = plan_twin(host, args.model, args.window)
    except TuneError as e:
        if args.json:
            print(json.dumps({"ok": False, "error": e.message, "kind": e.kind}, indent=2))
        else:
            print(f"halo ollama tune: {e.message}", file=sys.stderr)
        return 1
    say(f"plan: {plan.line}")
    progress: "list[str]" = []

    def _progress(text: str) -> None:
        progress.append(text)
        say(f"  {text}")

    result = create_twin(host, plan, on_progress=_progress)
    if args.json:
        print(json.dumps({"ok": result.ok, "plan": {"model": plan.model, "twin": plan.twin, "host": plan.host_name,
                                                    "window": plan.window, "num_gpu": plan.layers,
                                                    "modelfile": plan.modelfile, "line": plan.line},
                          "progress": progress, "message": result.message,
                          "ref": result.ref if result.ok else None}, indent=2))
        return 0 if result.ok else 1
    if not result.ok:
        print(f"halo ollama tune: {result.message}", file=sys.stderr)
        return 1
    print(result.message)
    print(result.ref)
    return 0
