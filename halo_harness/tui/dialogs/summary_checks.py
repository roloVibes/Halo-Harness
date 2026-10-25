"""halo_harness.tui.dialogs.summary_checks -- the wizard Summary's checks
(Halo 3.2.2.0 R2): the five rows of start/checks.py, each its title and
then its what / cost / time line in muted text; Space toggles a row
(docs/WIZARD.md rule 2), the defaults are the list's (doctor, catalog and
hello on; the gym and the guided first run off). Under them, the models the
gym would run on (the default model and the start lineup's models; local
ones ticked, a cloud one says the gym does not run it).

Finish runs the ticked checks in order, in a thread worker, and prints each
one's title and result lines in the Summary; then Finish (again) closes
setup. With nothing ticked, or only the guided first run, Finish closes at
once. The guided first run row IS the hand-off: it sets `state.run_start`
and `halo init` runs `halo start` after the wizard has closed (it needs the
terminal); Esc while the checks run closes setup with no hand-off
(`state.checks_cancel`). A /setup Summary (no `offer_start`) shows the first four rows.

`SummaryChecks` is the SummaryStep's half that holds this: `check_widgets()`,
`ticked()`, `begin()` (False when nothing runs in the Summary) and the
worker. The results land in `state.check_results` ([(key, ok, lines)]),
`state.doctor_lines` and `state.pong_ok` (False only when hello ran and
failed), which `init_cli` reads back.
"""

from __future__ import annotations

from halo_harness.start import checks as C

LIST_ID = "wiz-summary-checks"
GYM_ID = "wiz-summary-gym-models"
TEXT_ID = "wiz-summary-text"
HINT = "Checks (Space ticks a row; Finish runs the ticked ones in order, then Finish again closes setup):"


def ctx_for(state) -> "C.CheckCtx":
    from halo_harness.start import fake
    picked = getattr(state, "gym_models", None)  # None until Finish: the candidates price the gym row
    return C.CheckCtx(cwd=state.cwd, model=state.final_model or _config_model(), no_live=state.no_live,
                      fake=fake.enabled(), gym_models=list(picked) if picked is not None else None)


def _config_model() -> str:
    from halo_harness.start.provider import default_model
    return default_model()


def rows_for(state) -> "list[dict]":
    return [c for c in C.CHECKS if c["key"] != "start" or state.offer_start]




class SummaryChecks:
    """Mixed into SummaryStep (it has `state`, `app`, `query_one`)."""

    _phase = "pick"  # pick -> running -> done

    def check_widgets(self) -> list:
        from textual.widgets import SelectionList, Static
        from textual.widgets.selection_list import Selection
        from halo_harness.tui.dialogs.check_rows import CheckRows
        ctx = ctx_for(self.state)
        rows = [(c["key"], c["title"], C.detail_line(c, ctx), c["default_on"]) for c in rows_for(self.state)]
        widgets = [Static(HINT, classes="dialog-subtitle"), CheckRows(rows, id=LIST_ID)]
        from halo_harness.start.checks_run import gym_candidates, gym_model_cost, is_local
        models = gym_candidates(ctx)
        if models:
            picks = [Selection(f"{m}  ({gym_model_cost(m)})", m, is_local(m)) for m in models]
            widgets.append(Static("The gym's models (Space ticks one):", classes="wiz-summary-muted"))
            widgets.append(SelectionList(*picks, id=GYM_ID))
        else:
            widgets.append(Static("The gym's models: none to pick yet (no default model, no pinned lineup model).",
                                  classes="wiz-summary-muted"))
        return widgets

    def ticked(self) -> "list[str]":
        try:
            return C.ordered(self.query_one(f"#{LIST_ID}").selected)
        except Exception:
            return []

    def _gym_ticked(self) -> "list[str]":
        from textual.widgets import SelectionList
        try:
            return list(self.query_one(f"#{GYM_ID}", SelectionList).selected)
        except Exception:
            return []

    def begin(self) -> bool:
        """Finish pressed while picking: True when checks now run in the Summary (Finish waits for them)."""
        keys = self.ticked()
        self.state.check_keys = tuple(keys)
        self.state.run_start = bool(self.state.offer_start and "start" in keys)
        self.state.gym_models = self._gym_ticked()
        here = [k for k in keys if k != "start"]
        if not here:
            return False
        self._phase = "running"
        self._lock_controls(True)
        from halo_harness.tui.worker_guard import guarded_worker
        guarded_worker(self, lambda: self._run_worker(here), thread=True, name="wiz-summary-checks")
        return True

    def _lock_controls(self, running: bool) -> None:
        from textual.widgets import Button
        for wid in (LIST_ID, GYM_ID):
            try:
                self.query_one(f"#{wid}").disabled = running
            except Exception:
                pass
        try:
            button = self.query_one("#wiz-next", Button)
            button.disabled = running
            button.label = "Running checks..." if running else "Finish"
            if not running:
                button.focus()
        except Exception:
            pass

    def _run_worker(self, keys: "list[str]") -> None:
        ctx = ctx_for(self.state)
        done: "list[str]" = []

        def each(key, ok, lines) -> None:
            c = C.check(key)
            if ok is None:
                done.append(f"{c['title']}: running...")
            else:
                mark = "[OK]" if ok else "[!!]"
                done[-1] = f"{c['title']}: {mark}"
                done.extend(f"   {line}" for line in lines)
            self._post("\n".join(done))
        results = C.run_many(keys, ctx, on_each=each, stop=lambda: bool(getattr(self.state, "checks_cancel", False)))
        self.state.check_results = results
        for key, ok, lines in results:
            if key == "doctor":
                self.state.doctor_lines = list(lines)
            if key == "hello" and not ok:
                self.state.pong_ok = False
        tail = self.summary_text()
        end = "Done. Finish closes setup" + (" and starts the guided first run." if self.state.run_start else ".")
        self._post("\n".join(done) + "\n\n" + tail + "\n\n" + end, finished=True)

    def _post(self, text: str, finished: bool = False) -> None:
        try:
            self.app.call_from_thread(self._show, text, finished)
        except Exception:  # Finish or Esc came first and the app has ended; the state holds the results
            pass

    def _show(self, text: str, finished: bool) -> None:
        from rich.text import Text
        from textual.widgets import Static
        try:
            self.query_one(f"#{TEXT_ID}", Static).update(Text(text))  # a Text: "[OK]" is never read as markup
        except Exception:
            pass
        if finished:
            self._phase = "done"
            self._lock_controls(False)

    def on_unmount(self) -> None:
        """Setup closed while they ran (Esc): the checks still to come do not start, and the guided first run is
        not handed off (`init_cli` reads `checks_cancel`)."""
        if self._phase == "running":
            self.state.checks_cancel = True

    def summary_text(self) -> str:
        """`init_cli._step_summary`'s lines (what was set up and written, the PATH line), plus the enumeration."""
        import io
        from rich.console import Console
        from halo_harness.init_cli import _step_summary
        stream = io.StringIO()
        console = Console(file=stream, width=100)
        state = self.state
        _step_summary(console, state.written, state.pong_ok, state.doctor_lines, no_live=state.no_live,
                      configured_this_run=state.configured_this_run, final_model=state.final_model)
        text = stream.getvalue().rstrip()
        if state.enumeration_done:
            selectable = [m for m in state.enumerated_models if isinstance(m, dict) and m.get("ref")]
            groups = {m.get("group") or m.get("provider") for m in selectable}
            text += f"\n\nModel enumeration: {len(selectable)} model(s) across {len(groups)} provider group(s)."
            not_reachable = [ln for ln in state.enumeration_lines if "not reachable" in ln]
            if not_reachable:
                text += "\n  not reachable: " + "; ".join(not_reachable)
        return text
