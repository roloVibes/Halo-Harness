"""halo_harness.report_cli -- `halo report <session|run|file> [--json]` (Halo 3.4.1.0 R3 "Time"): a finished run's
report card, rendered from its record with no model call (live/report_card.py; docs/REPLAY.md "The report card").

    halo report <ref> [--json]     ref: a session id of this machine, a goal run id of the repo you are in, a
                                   `.halo-replay` file (a path or a saved id) -- or session:<id> / run:<id> / file:<id>

It prints the Markdown (the same text Studio's report card copies); `--json` prints the card's data. A file made on
another machine gives the same card. A mission's report is the fleet pack's (`halo fleet mission report`).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional


def cmd_report(argv: Optional[list] = None) -> int:
    ap = argparse.ArgumentParser(prog="halo report", description="A finished run's report card, from its record (no model call): "
                                 "the story, where the time and the money went, what failed, what waited on you, the files.")
    ap.add_argument("ref", help="a session id, a goal run id of this repo, or a .halo-replay (path or saved id)")
    ap.add_argument("--json", action="store_true", help="the card's data instead of the Markdown")
    args = ap.parse_args(sys.argv[1:] if argv is None else argv)
    from halo_harness.config.paths import bridge_home
    from halo_harness.live import compare, report_card
    from halo_harness.live.report_card_text import markdown
    try:
        p, from_file = report_card.resolve(bridge_home(), args.ref, cwd=Path.cwd())
    except compare.CompareError as e:
        print(f"halo report: {e}", file=sys.stderr)
        return 2
    c = report_card.card(p, args.ref, from_file)
    text = json.dumps(c, indent=2, ensure_ascii=False) if args.json else markdown(c)
    try:
        sys.stdout.write(text if text.endswith("\n") else text + "\n")
    except UnicodeEncodeError:  # a console that cannot show every character: the same text, escaped
        sys.stdout.write(text.encode(sys.stdout.encoding or "ascii", "replace").decode(sys.stdout.encoding or "ascii") + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(cmd_report())
