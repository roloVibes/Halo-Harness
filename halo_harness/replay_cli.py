"""halo_harness.replay_cli -- `halo replay`: the CLI face of
`replay.py` (Halo 2.0.6 round 4: session replay for model swaps).

    halo replay <session-id> --model <ref> [--turn N] [--json] [--timeout S]

Forks the session, truncates the fork to just before turn N's user node,
re-sends that turn's own prompt against the swapped model through plain
print mode (same cwd/tools/hooks as any `halo -p`), and prints the
side-by-side outcome. The original session file is never appended to.
"""

from __future__ import annotations

import argparse
import sys
from typing import Optional


def cmd_replay(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="halo replay",
        description="Replay one turn of a recorded session against a different model "
                    "and compare the outcomes side by side.")
    parser.add_argument("session_id", help="the recorded session to replay (a session id; "
                                           "`halo sessions`/`/resume` lists them)")
    parser.add_argument("--model", required=True,
                        help="the swapped model to replay against (any route/ref form)")
    parser.add_argument("--turn", type=int, default=None,
                        help="which real user turn to replay, 1-based (default: 1 -- the task, fresh)")
    parser.add_argument("--max-turns", type=int, default=10,
                        help="the replay run's own turn cap (default 10)")
    parser.add_argument("--timeout", type=float, default=600.0,
                        help="hard wall-clock cap for the replay run, seconds (default 600)")
    parser.add_argument("--json", action="store_true", help="machine-readable report")
    parser.add_argument("--cwd", default=None, help="the session's project directory (default: here)")
    args = parser.parse_args(argv)

    from pathlib import Path
    from halo_harness.replay import format_report, replay_session
    cwd = Path(args.cwd) if args.cwd else Path.cwd()
    report = replay_session(cwd, args.session_id, model=args.model, turn=args.turn,
                            max_turns=args.max_turns, timeout=args.timeout)
    if args.json:
        import json
        print(json.dumps(report, indent=2))
    else:
        print(format_report(report))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    sys.exit(cmd_replay())
