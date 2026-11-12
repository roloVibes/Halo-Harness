"""halo_harness.fleet.mission_outcome -- whether a mission part that ran to its end
did its work (3.4.0.1 "Found live", defect 15).

A part's session ending without an error says only that the process exited. The
part is `done` when its hand-back says so and the outputs the plan named are in
the mission folder; otherwise it ends `failed` with the reason:

- the hand-back's last `Outcome:` line (the brief asks for `Outcome: done` or
  `Outcome: blocked -- <why>`) says anything but done, or, with no such line, the
  hand-back says the part "is blocked" / "is not done";
- a files part's named outputs (`artifacts/<n>/...`) are missing.

The worker applies it before it writes `result.json`, and the hub applies it
again when it reads a result (a member on an older Halo still says `done`).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable, Optional

OUTCOME_LINE = ("Its last line is `Outcome: done` when this part's work is done, or `Outcome: blocked -- <why>` "
                "when it is not (a command was refused, a tool is missing, an output could not be made).")


def write_line(n: str) -> str:
    """3.4.1.1 (43): how a files part leaves its outputs. A shell redirect into `artifacts/<n>/` asks where the
    machine's permission mode asks (two cards for a one-command part); the Write tool there does not."""
    return (f" Write each output file with the Write tool (it needs no ask in artifacts/{n}/); run a command on its own "
            "and put what it printed into the file with Write, never with a shell redirect (> or tee), which asks first "
            "where this machine's permission mode asks.")
_LINE = re.compile(r"^[\s>*_`#-]*outcome[\s*_`]*:[\s*_`]*(.+?)\s*$", re.I)
_DONE = re.compile(r"^(done|finished|complete|completed|ok)\b[\s.!*_`]*$", re.I)
_SAID = re.compile(r"\b(?:the |this )?(?:part|task|work)\s+(?:is|was)\s+(?:blocked|not done|not finished|incomplete)\b", re.I)


def cut(text: str, n: int) -> str:
    """`text` whole when it fits, else cut at a word with "..." (3.4.1.0 R5, defect 37: a reason ended mid-word)."""
    text = " ".join(str(text or "").split())
    if len(text) <= n:
        return text
    return text[:n - 3].rsplit(" ", 1)[0].rstrip(" ,;:-") + "..."


def said(text: str) -> Optional[str]:
    """Why the hand-back says the part is not done, or None when it does not say so."""
    lines = [x for x in str(text or "").splitlines() if x.strip()]
    for line in reversed(lines):
        m = _LINE.match(line)
        if m:
            word = m.group(1).strip().strip("*_`").strip()
            return None if _DONE.match(word) else f"its hand-back says: {cut(word, 300)}"
    m = _SAID.search(str(text or ""))
    return f"its hand-back says: {m.group(0).strip()}" if m else None


def missing(folder: Optional[Path], outputs: Iterable[str], kind: str) -> list:
    """The named outputs of a files part that are not in the mission folder."""
    if folder is None or kind == "repo":
        return []
    return [o for o in outputs or [] if o and not (Path(folder) / o).is_file()]


def verdict(text: str, folder: Optional[Path], outputs: Iterable[str], kind: str) -> Optional[str]:
    """None when the part's work is done; otherwise the one-line reason it is not."""
    if kind == "orchestra":  # the run's own verdict (its checks) already decided
        return None
    gone = missing(folder, outputs, kind)
    why = said(text)
    if gone:
        return cut("not done: the outputs the plan named are missing: " + ", ".join(gone[:5])
                   + (f" ({why})" if why else ""), 500)
    return cut(f"not done: {why}", 500) if why else None


def on_hub(home, mid: str, pid: str, res: dict) -> dict:
    """The hub's check of a member's `done` result: the same verdict on the hub's copy of the folder."""
    if res.get("state") != "done":
        return res
    from . import mission_store as S
    from .mission_plan import load_plan
    part = next((p for p in (load_plan(home, mid) or {}).get("parts") or [] if str(p.get("id")) == str(pid)), None)
    if part is None:
        return res
    folder = S.folder(home, mid)
    text = S.read_text(folder, f"parts/{pid}/handback.md") or ""
    why = verdict(text, folder, part.get("outputs") or [], str(part.get("kind") or "files"))
    return {**res, "state": "failed", "ok": False, "error": why} if why else res
