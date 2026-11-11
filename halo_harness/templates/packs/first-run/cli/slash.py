"""The first-run pack's `/start` (`contributes.slash`): in a session it shows the guided first run's card -- what it
does, the models, the cost, the time, what it writes -- and how to run it (`halo start` in a terminal, or Run on the
First run panel in Studio's Agents section). `/start --explain` is the same card. The run itself drives an Orchestra
run step by step, so it runs in a terminal of its own or in Studio, never inside this session's turn.
"""

from __future__ import annotations

import contextlib
import io


def run(args_text: str, facade) -> str:
    from .start import cmd_start
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
        cmd_start(["--explain"])
    text = out.getvalue().rstrip()
    return (text + "\n\nRun it: `halo start` in a terminal, or Run on the First run panel in Studio (Agents).").strip()
