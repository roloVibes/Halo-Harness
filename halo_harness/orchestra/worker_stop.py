"""halo_harness.orchestra.worker_stop -- the worker's `STOP: <reason>` line (Halo 3.3.15.0).

A worker ends its reply with `STOP: <reason>` when the goal's STOP WHEN applies to its job (orchestra/workers.py
`worker_prompt`); the run reads it with `stop_line` and fails the lane. A reason that only says the condition did
not apply ("STOP: none", "STOP: not applicable -- the unit is written", "STOP: n/a") is no stop at all: a worker that
answered "did STOP apply? no" killed its lane and every lane that depended on it (rolo, Kali, 2026-11-09, finding
f-20261109-9f7492). A bare `STOP:` still means "the worker stopped".
"""

from __future__ import annotations

from typing import Optional

NO_STOP = ("none", "nothing", "not applicable", "does not apply", "doesn't apply", "not needed", "no stop",
           "not triggered", "did not apply", "didn't apply")
NO_STOP_ALONE = ("no", "na", "n/a")  # only as the whole reason: "STOP: no provider configured" is a real stop


def stop_line(text: str) -> Optional[str]:
    """The first real `STOP: <reason>` line of `text`, or None."""
    for line in str(text or "").splitlines():
        if line.strip().upper().startswith("STOP:"):
            reason = line.strip()[5:].strip()
            if is_no_stop(reason):
                continue
            return reason or "the worker stopped"
    return None


def is_no_stop(reason: str) -> bool:
    """True when `reason` only says the stop condition did not apply (a NO_STOP word, alone or followed by a
    separator: "none", "none -- my unit is written", "not applicable (job complete)"; never "nonexistent file")."""
    low = reason.lower().strip().strip(".!")
    if low in NO_STOP_ALONE:
        return True
    for word in NO_STOP:
        if low == word or (low.startswith(word) and not low[len(word):len(word) + 1].isalnum()):
            return True
    return False


__all__ = ["NO_STOP", "NO_STOP_ALONE", "is_no_stop", "stop_line"]
