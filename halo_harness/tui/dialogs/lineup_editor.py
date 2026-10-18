"""halo_harness.tui.dialogs.lineup_editor -- the read-only lineup view (Halo
3.1.1.0 R3: Studio is the one editor of lineups; the terminal shows a lineup
and opens Studio on it).

`LineupView` has the layout the 2.0.5 lineup form had, with no inputs: the
assignments (one resolved line each, lineup_view_text.py), the warnings, what
each row costs, the role table the lineup resolves to, the highlighted
assignment's fields with their help lines, every top section's YAML under its
one-line meaning (field_help.py, the lines Studio shows too), and the about
text. Keys:

  e    open Studio on this lineup (`halo studio --edit lineup:<name>`)
  t    Test this model: the one-token probe on the highlighted row's model
  Esc  close

"Smoke run (cost first)" runs every member's acceptance prompt. `/teams list`,
the wizard's Team step (Enter on a lineup) and `/teams view <name>` open it.
"""

from __future__ import annotations

from typing import Optional

from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Collapsible, OptionList, Static
from textual.widgets.option_list import Option

from halo_harness.field_help import ASSIGNMENT, lineup_line
from halo_harness.teams_yaml import TOP_SECTIONS
from halo_harness.tui.dialogs.lineup_view_text import cost_lines, draft_about_text, lineup_warnings, \
    resolved_assignment_line, roles_projection, section_yaml as _yaml
from halo_harness.tui.worker_guard import guarded_worker

WHAT_SENTENCE = ("A lineup is the role table: each row picks the model (and effort) for one job. "
                 "It applies when custom roles are ON and this lineup is active.")
_ROW_FIELDS = (("role", "Role"), ("agent", "Agent"), ("as", "Alias (as)"), ("instances", "Instances"),
               ("use_for", "Use for"), ("models", "Model override"))


class LineupView(ModalScreen):
    """One lineup, read-only. `template`: its file (None: read it now); `models`: the catalog."""

    BINDINGS = [
        Binding("escape", "close", "Close", show=False),
        Binding("e", "edit_in_studio", "Edit in Studio", show=True),
        Binding("t", "test_model", "Test model", show=True),
    ]
    DEFAULT_CSS = """
    LineupView { align: center middle; }
    LineupView > Horizontal { width: 97%; height: 94%; border: round $primary; background: $surface; }
    LineupView #lineup-left-pane { width: 42%; padding: 1 2; border-right: solid $primary-darken-1; }
    LineupView #lineup-right-pane { width: 58%; padding: 1 2; }
    LineupView #lineup-assignments { height: 10; margin-top: 1; }
    LineupView #lineup-warnings { color: $warning; margin-top: 1; }
    LineupView #lineup-roles-projection { color: $text-muted; margin-top: 1; height: auto; max-height: 10; }
    LineupView .bio-section-title { color: $accent; text-style: bold; margin-top: 1; height: 1; }
    LineupView .bio-hint { color: $text-muted; }
    LineupView .wizard-extra-buttons { height: 3; margin-top: 1; }
    LineupView .wizard-extra-buttons Button { margin-right: 1; }
    """

    def __init__(self, name: str, template: "Optional[dict]" = None, models: "Optional[list]" = None, *, cwd=None,
                 state_dir=None) -> None:
        super().__init__()
        self.lineup_name = name  # not `self.name`: Textual's DOMNode.name is read-only
        if template is None:
            from halo_harness.teams_yaml import load_team_template_raw
            template = load_team_template_raw(name, cwd=cwd, state_dir=state_dir) or {}
        self.template = {k: v for k, v in dict(template).items() if not str(k).startswith("_")}
        self.models = list(models or [])
        self._models_by_ref = {m.get("ref"): m for m in self.models if isinstance(m, dict) and m.get("ref")}
        self.cwd, self.state_dir = cwd, state_dir
        self._probe_line = ""

    def _agents(self) -> "list[dict]":
        return [e for e in self.template.get("agents") or [] if isinstance(e, dict)]

    # -- compose ---------------------------------------------------------------
    def compose(self):
        with Horizontal():
            with Vertical(id="lineup-left-pane"):
                yield Static(f"Lineup: {self.lineup_name}", classes="dialog-title")
                yield Static(WHAT_SENTENCE, id="lineup-what-sentence")
                yield Static("e: edit in Studio  |  t: test the highlighted row's model  |  Esc: close",
                             classes="dialog-subtitle")
                yield OptionList(*[Option(resolved_assignment_line(e, cwd=self.cwd, state_dir=self.state_dir,
                                                                   models_by_ref=self._models_by_ref))
                                   for e in self._agents()], id="lineup-assignments")
                yield Static("\n".join(lineup_warnings(self._agents(), cwd=self.cwd, state_dir=self.state_dir)),
                             id="lineup-warnings")
                yield Static("Costs (per 1M tokens, in+out -- what each row spends when it fires):",
                             classes="dialog-subtitle")
                yield Static("", id="lineup-cost-footer")
                yield Static("Roles table (what the lineup resolves to):", classes="dialog-subtitle")
                yield Static(roles_projection(self.template, cwd=self.cwd, state_dir=self.state_dir),
                             id="lineup-roles-projection")
            with VerticalScroll(id="lineup-right-pane"):
                yield Static("Highlighted assignment", classes="bio-section-title")
                yield Static("", id="lineup-assignment-detail")
                yield Static("Sections (each as its YAML; edit them in Studio: e):", classes="bio-section-title")
                for section in TOP_SECTIONS:
                    value = self.template.get(section)
                    with Collapsible(title=f"{section}: {lineup_line(section)}", id=f"lineup-collapsible-{section}"):
                        yield Static(_yaml(value) if value else "(not set)", id=f"lineup-section-{section}")
                yield Static("How the pieces work together (about):", classes="bio-section-title")
                about = str(self.template.get("about") or "").strip()
                yield Static(about or f"(none yet; drafted from the lineup: {draft_about_text(self.template)})",
                             id="lineup-about")
                with Horizontal(classes="wizard-extra-buttons"):
                    yield Button("Edit in Studio (e)", id="lineup-edit-studio", variant="primary")
                    yield Button("Smoke run (cost first)", id="lineup-smoke")
                    yield Button("Close (esc)", id="lineup-close")
                yield Static("", id="lineup-hint")

    def on_mount(self) -> None:
        self._refresh_cost_footer()
        option_list = self.query_one("#lineup-assignments", OptionList)
        if self._agents():
            option_list.highlighted = 0
        self._show_assignment(0)
        option_list.focus()

    def _refresh_cost_footer(self) -> None:
        lines = cost_lines(self._agents(), self._models_by_ref)
        if self._probe_line:
            lines.append(f"test: {self._probe_line}")
        try:
            self.query_one("#lineup-cost-footer", Static).update("\n".join(lines) or "(no rows yet)")
        except Exception:
            pass

    def _show_assignment(self, index: "Optional[int]") -> None:
        agents = self._agents()
        if index is None or not (0 <= index < len(agents)):
            text = "(no assignments yet -- add cards in Studio: e)"
        else:
            e, lines = agents[index], []
            for key, label in _ROW_FIELDS:
                value = e.get(key)
                if isinstance(value, list):
                    value = ", ".join(str(v) for v in value)
                elif isinstance(value, dict):
                    value = value.get("preference") or _yaml(value)
                lines.append(f"{label}: {value if value not in (None, '') else '(unset)'}")
                lines.append(f"  {ASSIGNMENT.get(key, '')}")
            text = "\n".join(lines)
        try:
            self.query_one("#lineup-assignment-detail", Static).update(text)
        except Exception:
            pass

    def on_option_list_option_highlighted(self, event: OptionList.OptionHighlighted) -> None:
        if event.option_list.id == "lineup-assignments":
            self._show_assignment(event.option_list.highlighted)

    # -- actions ---------------------------------------------------------------
    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id or ""
        if bid == "lineup-edit-studio":
            self.action_edit_in_studio()
        elif bid == "lineup-smoke":
            self.action_smoke_run()
        elif bid == "lineup-close":
            self.action_close()

    def _hint(self, text: str) -> None:
        try:
            self.query_one("#lineup-hint", Static).update(text)
        except Exception:
            pass

    def action_edit_in_studio(self) -> None:
        from halo_harness.tui import studio_open
        studio_open.open_target(self, f"lineup:{self.lineup_name}", cwd=self.cwd, state_dir=self.state_dir,
                                on_line=self._hint)

    @staticmethod
    def _bio_models(agent_name) -> dict:
        from halo_harness.agents_yaml import resolve_agent_bio
        try:
            m = (resolve_agent_bio(agent_name, cwd=None, state_dir=None) or {}).get("models")
        except Exception:
            return {}
        return m if isinstance(m, dict) else {}

    def _assignment_model_ref(self, index: "Optional[int]") -> str:
        agents = self._agents()
        if index is None or not (0 <= index < len(agents)):
            return ""
        e = agents[index]
        override = e.get("models") if isinstance(e.get("models"), dict) else {}
        own = self._bio_models(e.get("agent"))
        return str(override.get("preference") or own.get("preference") or own.get("fallback") or "").strip()

    def action_test_model(self) -> None:
        """The one-token probe (model_probe.py) on the highlighted row's model, on a worker; the line
        lands in the cost footer."""
        ref = self._assignment_model_ref(self.query_one("#lineup-assignments", OptionList).highlighted)
        if not ref:
            self._probe_line = "this assignment resolves no model yet -- pick a bio with a preference first"
            self._refresh_cost_footer()
            return
        self._probe_line = f"{ref}: probing (one token, up to 20 s)..."
        self._refresh_cost_footer()

        def _work() -> None:
            from halo_harness.model_probe import probe_line, probe_model
            line = probe_line(probe_model(ref, state_dir=self.state_dir))

            def _show() -> None:
                self._probe_line = line
                self._refresh_cost_footer()
            try:
                self.app.call_from_thread(_show)
            except Exception:
                pass
        guarded_worker(self, _work, thread=True, name="lineup-probe", group="lineup-probe")

    def action_smoke_run(self) -> None:
        """Every distinct model's cost line first, before anything runs; then each member's acceptance
        prompt (what `halo doctor --teams` runs) on a worker; the result lands in the hint."""
        from halo_harness.smoke_run import smoke_cost_line
        prefs = []
        for i in range(len(self._agents())):
            ref = self._assignment_model_ref(i)
            if ref and ref not in prefs:
                prefs.append(ref)
        if not prefs:
            self._hint("Smoke run: no models resolve in this lineup yet -- pick preferences in Studio (e).")
            return
        head = "Smoke run -- cost first:\n  " + "\n  ".join(smoke_cost_line(p) for p in prefs)
        self._hint(head + f"\nrunning {len(prefs)} smoke call(s) on a worker...")
        names = [e.get("agent") for e in self._agents() if e.get("agent")]

        def _work() -> None:
            from halo_harness.agents_doctor import run_all_acceptance
            results = run_all_acceptance(names=names)
            summary = "; ".join(f"{n}: {'ok' if ok else m[:40]}" for n, ok, m in results) or "nothing ran"
            try:
                self.app.call_from_thread(self._hint, head + "\nresults: " + summary[:400])
            except Exception:
                pass
        guarded_worker(self, _work, thread=True, name="lineup-smoke", group="lineup-smoke")

    def action_close(self) -> None:
        self.dismiss(None)
