"""halo_harness.ollama_steward.cli_steward_chat -- `halo ollama steward chat | candidates` (Halo 3.3.7.0 R5;
cli_steward.cmd_ollama_steward sends these two here; docs/COMMANDS-ollama-steward-chat.md).

    halo ollama steward chat "<question>" [--bigger] [--yes] [--json]
        one turn of the steward's chat: the steward's own model reads the job's context and the hosts' findings, may
        use its tools (the reads; a Halo-side change citing a finding; an adviser suggestion), and answers; the answer
        and its cost ("local, 4 s" / "$0.0012") are printed, a button's command beside it. --bigger asks the session's
        main model once with the same context: its cost is said first and, in a terminal, asked (--yes: no question)
    halo ollama steward candidates [--host H] [--json]
        the models that could run the steward here, best first, each with why (fits beside the main model, its size,
        tool calls verified); a known-good small model to download when nothing installed fits (never downloaded here)
Writes only what a tool lands (a profile field, a role) and the chat's log (<state>/ollama/steward-chat.jsonl).
"""

from __future__ import annotations

import argparse
import json
import sys


def _state():
    from halo_harness.config.paths import bridge_home
    return bridge_home()


def _tty() -> bool:
    try:
        return bool(sys.stdin and sys.stdin.isatty() and sys.stdout and sys.stdout.isatty())
    except (AttributeError, ValueError):
        return False


def cmd_chat(argv: list) -> int:
    from halo_harness.ollama_steward.chat import ask, bigger_cost
    p = argparse.ArgumentParser(prog="halo ollama steward chat", description="One turn of the steward's chat.")
    p.add_argument("question", help="what to ask the steward (quote it)")
    p.add_argument("--bigger", action="store_true", help="ask the session's main model once instead (its cost said first)")
    p.add_argument("--yes", action="store_true", help="with --bigger: do not ask before the call")
    p.add_argument("--json", action="store_true", help="print JSON")
    args = p.parse_args(argv)
    state = _state()
    if args.bigger:
        c = bigger_cost(state, args.question)
        if not c["model"]:
            print(f"halo ollama steward chat: {c['line']}", file=sys.stderr)
            return 1
        if not args.json:
            print(c["line"])
        if not (args.yes or args.json) and _tty():
            try:
                if input("Ask it? [y/N] ").strip().lower() not in ("y", "yes"):
                    return 1
            except (EOFError, KeyboardInterrupt):
                return 1
    got = ask(state, args.question, bigger=args.bigger)
    if args.json:
        print(json.dumps(got, indent=2, default=str))
        return 0 if got["model"] else 1
    for t in got["tools"]:
        print(f"  [{t['tool']}] {t['text'].splitlines()[0] if t['text'] else ''}")
    print(got["answer"])
    for b in got["buttons"]:
        print(f"  {b['label']}: {b['cli']}")
    if got["model"]:
        print(f"({got['model']}: {got['cost']}" + (f"; left out: {', '.join(got['left_out'])}" if got["left_out"] else "")
              + ")")
    return 0 if got["model"] else 1


def cmd_candidates(argv: list) -> int:
    from halo_harness.ollama_steward.agent import choose_model
    from halo_harness.ollama_steward.candidates import candidates, line
    p = argparse.ArgumentParser(prog="halo ollama steward candidates",
                                description="The models that could run the steward here, best first, each with why.")
    p.add_argument("--host", default=None, help="only this host (its name here)")
    p.add_argument("--json", action="store_true", help="print JSON")
    args = p.parse_args(argv)
    state = _state()
    cands = candidates(state, args.host)
    model, why = choose_model(state_dir=state)
    if args.json:
        print(json.dumps({"candidates": cands, "chosen": model, "why": why}, indent=2, default=str))
        return 0
    print(line(cands))
    for c in cands:
        mark = "*" if model and c["ref"] == model else "-"
        print(f"  {mark} {c['model']}: {c['why']}" + ("" if c["installed"] else f" (halo models pull "
                                                       f"{c['model'][3:].rsplit('@', 1)[0]} --host {c['host']})"))
    print(f"the steward runs on: {model or 'nothing'} ({why})")
    return 0
