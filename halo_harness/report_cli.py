"""halo_harness.report_cli -- `halo report <session|run> [--json]` (Halo 3.4.1.0 R3 "Time"): a finished run's report
card, rendered from its record with no model call (live/report_card.py).

    halo report <ref> [--json]     ref: a session id of this machine, then a goal run id of the repo you are in -- or
                                   session:<id> / run:<id>

It prints the Markdown (the same text Studio's report card copies); `--json` prints the card's data. 3.6.0.3 B (Z13): a
saved file of the old playback gets the one retired line (cli_commands.REPLAY_LEFT) and exit 2.
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
    ap.add_argument("ref", help="a session id, or a goal run id of this repo")
    ap.add_argument("--json", action="store_true", help="the card's data instead of the Markdown")
    args = ap.parse_args(sys.argv[1:] if argv is None else argv)
    from halo_harness.config.paths import bridge_home
    from halo_harness.live import card_data, report_card
    from halo_harness.live.report_card_text import markdown
    try:
        p = report_card.resolve(bridge_home(), args.ref, cwd=Path.cwd())
    except report_card.OldFile as e:  # 3.6.0.3 B (Z13): the one retired line, word for word
        print(str(e), file=sys.stderr)
        return 2
    except card_data.CompareError as e:
        print(f"halo report: {e}", file=sys.stderr)
        return 2
    c = report_card.card(p, args.ref)
    text = json.dumps(c, indent=2, ensure_ascii=False) if args.json else markdown(c)
    try:
        sys.stdout.write(text if text.endswith("\n") else text + "\n")
    except UnicodeEncodeError:  # a console that cannot show every character: the same text, escaped
        sys.stdout.write(text.encode(sys.stdout.encoding or "ascii", "replace").decode(sys.stdout.encoding or "ascii") + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(cmd_report())
