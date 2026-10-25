"""halo_harness.agent.mode_notice -- Halo 3.2.2.0 R4: the model always knows
its permission mode.

Every way into plan mode -- the EnterPlanMode tool, Shift+Tab, `/plan on`,
config or `--permission-mode plan` at startup -- ends with the same
PLAN_MODE_NOTE (with the plan file's path) in the conversation before the
next model call; every way out (Shift+Tab, `/plan off`, the plan card's
approve) ends with PLAN_OFF_NOTE. The mode is read off
`permission_engine.mode` before each model call and compared with the one
the model was last told (`Session._mode_told`), so a change made from any
thread or any surface is caught at the next call without each surface
having to say so itself.

Each turn also carries one line naming the current mode (`mode_line`), in
the same user-role snapshot as the turn's prompt.
"""

from __future__ import annotations

from typing import Optional

from halo_harness.agent.planmode import PLAN_MODE_NOTE, ensure_plan_file

PLAN_OFF_NOTE = "Plan mode is off: implement the plan."

_MODE_WORDS = {
    "plan": "read-only; call ExitPlanMode with the plan",
    "default": "edits and commands ask first",
    "acceptEdits": "edits in the working directory run without asking; commands ask first",
    "auto": "every call runs except the user's own deny and ask rules",
    "bypassPermissions": "every call runs",
    "dontAsk": "only calls the user's rules allow run; the rest are refused",
}


def mode_line(mode: str) -> str:
    """One line: `permission mode: plan (read-only; call ExitPlanMode with the plan)`."""
    words = _MODE_WORDS.get(mode)
    return f"permission mode: {mode}" + (f" ({words})" if words else "")


def plan_mode_note(plan_path) -> str:
    """PLAN_MODE_NOTE with the plan file's path, the text EnterPlanMode gives."""
    return f"{PLAN_MODE_NOTE}\n\nPlan file: {plan_path}"


def _ensure_plan_path(session):
    engine = session.permission_engine
    settings = getattr(getattr(session, "session_context", None), "settings", None)
    path = ensure_plan_file(session.cwd, settings, existing=engine.plan_file)
    engine.set_plan_file(path)
    return path


def told_plan(session) -> None:
    """EnterPlanMode already logged the note itself: record that it was told."""
    session._mode_told = "plan"


def sync(session, *, turn_start: bool = False) -> Optional[str]:
    """Before a model call: log the plan-mode note on entry, PLAN_OFF_NOTE on
    exit, and (at a turn's start, or with a change) the one-line mode.
    Returns the text logged, or None when nothing was."""
    engine = getattr(session, "permission_engine", None)
    if engine is None:
        return None
    mode = getattr(engine, "mode", None) or "default"
    told = getattr(session, "_mode_told", None)
    blocks = []
    if mode != told:
        if mode == "plan":
            if told not in (None, "plan") and getattr(session, "_mode_before_plan", None) is None:
                session._mode_before_plan = told
            try:
                path = _ensure_plan_path(session)
            except Exception:  # an unwritable plans dir: the note still goes out, without a path
                path = engine.plan_file
            blocks.append(plan_mode_note(path) if path is not None else PLAN_MODE_NOTE)
        elif told == "plan":
            blocks.append(PLAN_OFF_NOTE)
        session._mode_told = mode
    if blocks or turn_start:
        blocks.append(mode_line(mode))
    if not blocks:
        return None
    text = "\n\n".join(blocks)
    session.log.append_snapshot([{"type": "text", "text": text}], kind="permission_mode")
    return text
