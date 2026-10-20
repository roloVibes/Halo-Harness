"""halo_harness.remote.print_handle -- the `SessionHandle` for `halo -p`
(incl. `--bg` runs): print mode has no `Controller`, so this wraps the bare
`Session` plus the stream-json input queue `headless.run_print_mode` already
owns (`_TurnLineQueue`; items are `{"text", "images"}`).

* submit: a steer while a turn runs, else a queued next turn. A single-prompt
  text run has no input queue (the process ends with its one turn); only a
  steer is possible there.
* events: `tee(stream)` wraps the turn's event generator, so the sink still
  sees every event and the hub gets a copy.
* answers go to the same session waiters the Controller path uses (a print
  session is not `interactive`, so permission cards normally never appear;
  the waiters answer if a sub-agent or hook ever raises one).
"""

from __future__ import annotations

from typing import Iterator, Optional

from halo_harness.remote.base import HandleError, _BaseHandle, _short


class PrintModeHandle(_BaseHandle):
    kind = "print"

    def __init__(self, session, cwd, *, input_queue=None, registry=None, facade=None,
                 state_dir=None, routes: Optional[dict] = None, settings=None,
                 disable_slash_commands: bool = False) -> None:
        super().__init__(session, cwd)
        self.input_queue = input_queue
        self.registry = registry
        self.facade = facade
        self.state_dir = state_dir
        self.routes = routes or {}
        self.settings = settings
        self.disable_slash_commands = disable_slash_commands

    def tee(self, stream) -> Iterator:
        """Yield every event of `stream` unchanged, publishing a copy."""
        try:
            for ev in stream:
                self.hub.publish(ev)
                yield ev
        finally:
            close = getattr(stream, "close", None)
            if callable(close):
                close()

    def fleet_shutdown(self, text: str) -> None:
        """3.0.5.0: the current turn ends at its next tool boundary
        (agent/agent_inbox.py) and no further turn is read: the run returns."""
        from halo_harness import events
        self.hub.publish(events.system_note(f"(remote) {text}"))
        queue_ = self.input_queue
        if queue_ is not None:
            (getattr(queue_, "put_urgent", None) or queue_.put)(None)

    def _add_rule(self, rule: str, scope: str):
        if scope == "session":
            self.session.permission_engine.add_session_allow_rule(rule)
            return None
        from halo_harness.permissions import add_allow_rule
        return add_allow_rule(rule, scope, cwd=self.cwd)

    def submit(self, text: str, *, images: Optional[list] = None) -> dict:
        text = (text or "").strip()
        if not text:
            raise HandleError("empty prompt")
        if self.session.busy and self.session.steer(text):
            return {"steered": True, "queued": False}
        if self.input_queue is None:
            raise HandleError("this print-mode run takes one prompt and has no input queue "
                              "(start it with --input-format stream-json to send more turns)")
        self.input_queue.put({"text": text, "images": images or None})
        return {"steered": False, "queued": True}

    def set_mode(self, mode: str) -> dict:
        self._check_mode(mode)
        self.session.permission_engine.mode = mode
        self.hub.publish(self.session.status_event())
        return {"mode": mode}

    def set_model(self, ref: str) -> dict:
        from halo_harness.controller import _default_model_resolver, _not_configured_message
        if not ref:
            raise HandleError("model ref required")
        if self.session.busy:
            raise HandleError("a turn is running; change the model between turns")
        try:
            mref, profile, creds = _default_model_resolver(
                ref, state_dir=self.state_dir, routes=self.routes, settings=self.settings)
        except Exception as e:
            raise HandleError(f"{e}")
        if creds is None:
            raise HandleError(_not_configured_message(mref))
        self.session.set_model(mref, profile, creds)
        self.hub.publish(self.session.status_event())
        return {"model": ref, "queued": False}

    def set_effort(self, level: str) -> dict:
        self._check_effort(level)
        text = self.run_slash("effort", level)
        return {"effort": getattr(self.session, "effort", level), "message": text}

    def run_slash(self, name: str, args: str = "") -> str:
        from halo_harness.headless import _maybe_run_slash_command
        name = (name or "").lstrip("/").strip()
        if not name:
            raise HandleError("slash command name required")
        if self.registry is None or self.facade is None:
            raise HandleError("no command registry in this run")
        final_prompt, direct = _maybe_run_slash_command(
            f"/{name} {args or ''}".strip(), registry=self.registry, facade=self.facade,
            disable_slash_commands=self.disable_slash_commands)
        if direct is not None:
            return direct
        if final_prompt:
            self.submit(final_prompt)
            return f"(sent as a prompt: {_short(final_prompt)})"
        return f"Unknown command: /{name}"
