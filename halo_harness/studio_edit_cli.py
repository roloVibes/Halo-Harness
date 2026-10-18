"""halo_harness.studio_edit_cli -- what `halo agents edit`, `halo teams edit`
and `new --studio` share (Halo 3.1.1.0 R3: Studio is the one editor of bios
and lineups): open Studio on the bio or lineup (or the Studio page already
open for this home), print one line saying what happened, and the URL.
`--no-open` only prints the URL (it starts a background Studio when none
runs); `--yaml` is the terminal-only escape hatch the callers keep ($EDITOR
on the file).
"""

from __future__ import annotations

import sys
from pathlib import Path


def add_studio_flags(parser, what: str) -> None:
    parser.add_argument("--no-open", action="store_true",
                        help="print Studio's URL for this " + what + ", do not open a browser")
    parser.add_argument("--yaml", action="store_true",
                        help="open $EDITOR (or $VISUAL) on the " + what + "'s YAML file instead of Studio "
                             "(for a terminal-only box)")


def open_in_studio(kind: str, name: str, *, no_open: bool, prog: str) -> int:
    """`kind` is bio or lineup. 0 when Studio opened (or its URL printed), 1 when it did not start, 2 bad name."""
    from halo_harness.providers.config import default_state_dir
    from halo_harness.studio.edit_open import describe, open_edit
    from halo_harness.studio.edit_target import parse
    target, why = parse(f"{kind}:{name}")
    if target is None:
        print(f"{prog}: {why}", file=sys.stderr)
        return 2
    result = open_edit(target, cwd=Path.cwd(), state_dir=Path(default_state_dir()), open_browser=not no_open)
    print(describe(result))
    return 1 if result.get("how") == "failed" else 0
