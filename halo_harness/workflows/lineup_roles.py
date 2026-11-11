"""halo_harness.workflows.lineup_roles -- the lineup's own roles come before a square (Halo 3.3.16.2, "from a
session's own review": a custom lineup with a `media` role still got "no square enabled" from the Workflow
tool, and the role that could read the PDF was never asked).

A role of the session's lineup covers a read (pdf, vision, audio, video) when its card or bio is media work
(the alias or role `media`, or the bio's `kind: media`: every read), or its bio's (or card's) `models.needs`
/ `models.capabilities` name it (`files` reads as pdf). The router hands a task to that role (the Agent
tool's path, `role: <alias>`) when the role covers every read the task carries and the task names no ask a
square is for (plan, review, research), unless a square is named; the receipt says
"handing the PDF to your media role: the lineup covers it".

    role_covers(team_control)                    -> [(alias, {read, ...})] (main left out)
    covering_role(gaps, team_control)            -> alias | ""
    run_role(alias, task, files, runtime=, ...)  -> square_run.Outcome
    nothing_reads(gaps, files)                   -> the one line when no role or square reads it
"""

from __future__ import annotations

from typing import Callable, Optional

READS = ("pdf", "vision", "audio", "video")
_TAG = {"pdf": "pdf", "files": "pdf", "vision": "vision", "image": "vision", "audio": "audio", "video": "video"}
_PLURAL = {"pdf": "PDFs", "vision": "images", "audio": "audio", "video": "video", "media": "media"}


def _models(d) -> dict:
    m = d.get("models") if isinstance(d, dict) else None
    return m if isinstance(m, dict) else {}


def _covers(alias: str, entry: dict, bio: Optional[dict]) -> set:
    words = {str(alias or "").lower(), str(entry.get("role") or "").lower(), str((bio or {}).get("kind") or "").lower()}
    if "media" in words:
        return set(READS) | {"media"}
    out = set()
    for src in (_models(entry), _models(bio)):
        for key in ("needs", "capabilities"):
            for tag in src.get(key) or [] if isinstance(src.get(key), list) else []:
                if _TAG.get(str(tag).strip().lower()):
                    out.add(_TAG[str(tag).strip().lower()])
    return out


def role_covers(team_control) -> list:
    """`[(alias, covers)]` for every non-main card of the lineup that covers a read, in the lineup's order."""
    if team_control is None:
        return []
    out = []
    for alias, entry in (getattr(team_control, "aliases", None) or {}).items():
        if not isinstance(entry, dict) or entry.get("role") == "main":
            continue
        try:
            bio = team_control.bio_for(alias)
        except Exception:
            bio = None
        covers = _covers(alias, entry, bio)
        if covers:
            out.append((alias, covers))
    return out


def covering_role(gaps: list, team_control) -> str:
    """The alias of the first role covering every read in `gaps` ('' when an ask is among them, no read is, or
    no role covers them all)."""
    reads = [g for g in gaps or [] if g in READS or g == "media"]
    if not reads or len(reads) != len(gaps or []):
        return ""
    return next((alias for alias, covers in role_covers(team_control) if set(reads) <= covers), "")


def nothing_reads(gaps: list, files=()) -> str:
    """(d) "no role or square reads PDFs here: `halo workflows enable media`, or give a role a model that takes
    PDFs" -- for the reads; '' when the gaps hold no read."""
    reads = [g for g in gaps or [] if g in _PLURAL]
    if not reads:
        return ""
    what = " or ".join(dict.fromkeys(_PLURAL[g] for g in reads))
    named = f" (could not read {', '.join(files)})" if files else ""
    return (f"no role or square reads {what} here{named}: `halo workflows enable media`, or give a role a model "
            f"that takes {what}")


def brief(task: str, files: list) -> str:
    return task + (f"\n\nFiles: {', '.join(files)}" if files else "")


def run_role(alias: str, task: str, files: list, *, runtime, tool_id: str, spawn: Optional[Callable] = None,
             on_child: Optional[Callable] = None):
    """The task on the lineup's role `alias`, through the Agent tool's path (its model, rules and budget)."""
    from halo_harness.agent.agent_registry import tree_for
    from halo_harness.workflows.square_run import Outcome
    if spawn is None:
        from halo_harness.agent.subagent import run_agent_call as spawn
    parent, box = runtime.parent, {}

    def _child(child) -> None:
        aid = getattr(child, "agent_id", "")
        box["row"] = lambda: (tree_for(parent).row(aid) or {}) if aid else {}
        if on_child is not None:
            on_child(child)

    tool_input = {"description": f"role {alias}"[:60], "prompt": brief(task, files), "subagent_type": "general-purpose",
                  "role": alias}
    _events, result = spawn(runtime=runtime, tool_id=tool_id, tool_input=tool_input, tool_name="Agent", on_child=_child)
    row = (box.get("row") or (lambda: {}))() or {}
    return Outcome(text=str(getattr(result, "content", "") or ""), cost_usd=float(row.get("cost_usd") or 0.0),
                   status="failed" if getattr(result, "is_error", False) else "done")
