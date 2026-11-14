"""halo_harness.crew.map_when -- a map line's When, in words and against a task (Halo 3.6.0.0 R3, docs/CREW-sessions.md).

A line (map/1) is `{from, to, when}`; its when is `always`, `{needs: [...]}`, `{says: [words]}`, `ask` or
`main-decides` (none: main decides too). The words are the step runner's (crew/runner_when.py `decide`, which is the
router's `gaps` and `word_hit`): no third matcher.

    words(when) -> str                  "always" / "when the task needs a PDF, code" / "when the task says fix" /
                                        "only when I ask" / "main decides per task"
    fires(when, task, files, names) -> (bool, why)    for the runtime: a chain line or a route without a target;
                                        `main-decides` never fires by itself (main picks)
    rule(when) -> bool                  a line the runtime can check (always, needs, says, ask)
"""

from __future__ import annotations

NEED_WORDS = {"pdf": "a PDF", "images": "an image", "audio": "audio", "video": "video", "code": "code",
              "review": "a review", "reasoning": "reasoning", "long-text": "a long text", "tools": "tool calls"}


def words(when) -> str:
    if when in (None, "main-decides"):
        return "main decides per task"
    if when == "always":
        return "always"
    if when == "ask":
        return "only when I ask"
    if isinstance(when, dict) and isinstance(when.get("needs"), list):
        return "when the task needs " + ", ".join(NEED_WORDS.get(str(n), str(n)) for n in when["needs"])
    if isinstance(when, dict) and isinstance(when.get("says"), list):
        return "when the task says " + ", ".join(str(w) for w in when["says"])
    return str(when)


def rule(when) -> bool:
    return when not in (None, "main-decides")


def fires(when, task: str, files=(), names=()) -> "tuple[bool, str]":
    """Does the line fire for `task` (and its `files`)? `names` are the target's own names (an `ask` line fires when
    the task names one of them)."""
    if not rule(when):
        return False, "main decides per task"
    from halo_harness.crew.runner_when import decide
    ns = [str(n) for n in names if str(n).strip()]
    return decide(when, task, files, {"name": ns[0] if ns else "", "agents": ns[1:]})
