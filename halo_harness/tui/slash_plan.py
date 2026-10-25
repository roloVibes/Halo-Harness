"""halo_harness.tui.slash_plan -- `/plan [on|off|status]` (Halo 3.2.2.0 R4).

`/plan on` is Shift+Tab straight to plan mode, `/plan off` leaves it for
the mode it came from (default when there is none), `/plan` or `/plan
status` says which mode is on and where the plan file is. The mode change
goes through `Controller.set_permission_mode` exactly like Shift+Tab, so
the model is told at its next call (agent/mode_notice.py) and a pending
permission card is re-decided under the new mode.
"""

from __future__ import annotations


def _session(app):
    return getattr(getattr(app, "controller", None), "session", None)


def _current_mode(app) -> str:
    session = _session(app)
    engine = getattr(session, "permission_engine", None)
    mode = getattr(engine, "mode", None) or getattr(getattr(app, "status_bar", None), "mode", None)
    return mode or "default"


def _plan_file(app):
    engine = getattr(_session(app), "permission_engine", None)
    return getattr(engine, "plan_file", None)


def status_text(app) -> str:
    mode = _current_mode(app)
    path = _plan_file(app)
    where = f"; plan file: {path}" if path else ""
    if mode == "plan":
        return (f"Plan mode is on: reads and the web run, writes wait for the plan{where}. "
                "The model calls ExitPlanMode with the plan; /plan off or Shift+Tab leaves plan mode.")
    return f"Plan mode is off (permission mode: {mode}){where}. /plan on enters it."


def _switch(app, mode: str) -> None:
    app.controller.set_permission_mode(mode)
    try:
        app.status_bar.set_mode(mode)
    except Exception:
        pass
    reevaluate = getattr(app, "_reevaluate_pending_permission_for_mode", None)
    if callable(reevaluate):
        reevaluate(mode)


async def handle_plan(app, args: str) -> None:
    arg = (args or "").strip().lower()
    mode = _current_mode(app)
    if arg in ("", "status"):
        text = status_text(app)
    elif arg == "on":
        if mode == "plan":
            text = status_text(app)
        else:
            session = _session(app)
            if session is not None and getattr(session, "_mode_before_plan", None) is None:
                session._mode_before_plan = mode
            _switch(app, "plan")
            text = ("Plan mode on: reads and the web run, writes wait for the plan. The model is told "
                    "at its next call; /plan off or Shift+Tab leaves plan mode.")
    elif arg == "off":
        if mode != "plan":
            text = status_text(app)
        else:
            session = _session(app)
            back = getattr(session, "_mode_before_plan", None) if session is not None else None
            back = back if back and back != "plan" else "default"
            if session is not None:
                session._mode_before_plan = None
            _switch(app, back)
            text = f"Plan mode off (permission mode: {back}). The model is told to implement the plan."
    else:
        text = "Usage: /plan [on|off|status]"
    await app.transcript.add_note(text, kind="command")
