"""halo_harness.tui.dialogs.agent_bio_editor -- the read-only bio view (Halo
3.1.1.0 R3: Studio is the one editor of bios; the terminal shows a bio and
opens Studio on it).

`AgentBioView` has the layout the 2.0.5 bio form had, with no inputs: the
identity, then every section's fields (bio_view_text.FIELDS, the same fields
Studio's bio form edits), each with its one plain line (field_help.py, the
lines Studio shows too), a value the bio inherits through `extends` marked as
such, and on the right the whole file as YAML. Keys:

  e    open Studio on this bio (`halo studio --edit bio:<name>`, tui/studio_open.py)
  t    Try it: the cost line first, then the bio's smoke call on a worker
  Esc  close

`/agents`, the wizard's Agents list and `/agents view <name>` open it.
"""

from __future__ import annotations

from typing import Optional

from textual.binding import Binding
from textual.containers import Horizontal, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Static

from halo_harness.tui.dialogs.bio_view_text import SECTIONS, budget_hint, duration_hint, field_rows, rule_sentence, \
    trigger_lines
from halo_harness.tui.worker_guard import guarded_worker

WHAT_SENTENCE = ("A bio describes ONE sub-agent: the model it runs on, the tools it may use, "
                 "and how it reports back. Lineups and /agent calls spawn it by name.")


def load_bio(name: str, *, cwd=None, state_dir=None) -> "tuple[dict, Optional[dict]]":
    """`(raw, parent)`: the bio's own file and, when it `extends` another, that bio resolved."""
    from halo_harness.agents_yaml import load_agent_bio_raw, resolve_agent_bio
    raw = {k: v for k, v in (load_agent_bio_raw(name, cwd=cwd, state_dir=state_dir) or {}).items() if not k.startswith("_")}
    parent = resolve_agent_bio(raw["extends"], cwd=cwd, state_dir=state_dir) if isinstance(raw.get("extends"), str) else None
    return raw, parent


class AgentBioView(ModalScreen):
    """One bio, read-only. `raw`: its file (None: read it now); `models`: the catalog (for the budget line)."""

    BINDINGS = [
        Binding("escape", "close", "Close", show=False),
        Binding("e", "edit_in_studio", "Edit in Studio", show=True),
        Binding("t", "try_it", "Try it", show=True),
    ]
    DEFAULT_CSS = """
    AgentBioView { align: center middle; }
    AgentBioView > Horizontal { width: 96%; height: 92%; border: round $primary; background: $surface; }
    AgentBioView #bio-form-pane { width: 62%; height: 100%; padding: 1 2; border-right: solid $primary-darken-1; }
    AgentBioView #bio-preview-pane { width: 38%; height: 100%; padding: 1 2; }
    AgentBioView .bio-section-title { color: $accent; text-style: bold; margin-top: 1; height: 1; }
    AgentBioView .bio-hint { color: $text-muted; }
    AgentBioView .bio-field-value { height: auto; }
    AgentBioView .wizard-extra-buttons { height: 3; margin-top: 1; }
    AgentBioView .wizard-extra-buttons Button { margin-right: 1; }
    AgentBioView #bio-preview { color: $text-muted; }
    """

    def __init__(self, name: str, raw: "Optional[dict]" = None, models: "Optional[list]" = None, *, cwd=None,
                 state_dir=None) -> None:
        super().__init__()
        self.bio_name = name  # not `self.name`: Textual's DOMNode.name is read-only
        self.cwd, self.state_dir, self.models = cwd, state_dir, list(models or [])
        loaded, self._inherited = load_bio(name, cwd=cwd, state_dir=state_dir)
        self.bio = dict(raw) if raw is not None else loaded
        if raw is not None and isinstance(raw.get("extends"), str) and self._inherited is None:
            from halo_harness.agents_yaml import resolve_agent_bio
            self._inherited = resolve_agent_bio(raw["extends"], cwd=cwd, state_dir=state_dir)

    def _value(self, section: str, key: str):
        own = self.bio.get(section) if isinstance(self.bio.get(section), dict) else {}
        if key in own:
            return own[key]
        parent = (self._inherited or {}).get(section)
        return parent.get(key) if isinstance(parent, dict) else None

    def preference(self) -> str:
        return str(self._value("models", "preference") or self._value("models", "fallback") or "").strip()

    # -- compose ---------------------------------------------------------------
    def compose(self):
        rows = field_rows(self.bio, self._inherited)
        with Horizontal():
            with VerticalScroll(id="bio-form-pane"):
                title = f"Agent bio: {self.bio_name}" + (f"  (extends {self.bio['extends']})" if self.bio.get("extends") else "")
                yield Static(title, classes="dialog-title")
                yield Static("e edit in Studio · t try it · Esc close", classes="dialog-subtitle")
                yield Static(WHAT_SENTENCE, id="bio-identity-hint", classes="bio-hint")
                for section in ("identity", *SECTIONS):
                    yield Static("Identity" if section == "identity" else section.capitalize(), classes="bio-section-title")
                    for (sec, label, value, help_line, inherited) in rows:
                        if sec == section:
                            yield from self._row(sec, label, value, help_line, inherited)
                    if section == "schedule":
                        yield Static("Triggers", classes="bio-section-title")
                        yield Static("\n".join(trigger_lines(self.bio)) or "(none)", id="bio-view-triggers",
                                     classes="bio-field-value")
                with Horizontal(classes="wizard-extra-buttons"):
                    yield Button("Edit in Studio (e)", id="bio-edit-studio", variant="primary", compact=True)
                    yield Button("Try it (t, cost first)", id="bio-try", compact=True)
                    yield Button("Close (esc)", id="bio-close", compact=True)
                yield Static("", id="bio-hint")
            with VerticalScroll(id="bio-preview-pane"):
                yield Static("The file, as YAML (edit it in Studio: e):", classes="dialog-subtitle")
                yield Static(self._yaml(), id="bio-preview")

    def _row(self, section: str, label: str, value: str, help_line: str, inherited: bool):
        slug = label.lower().replace(" ", "-").replace("(", "").replace(")", "")
        mark = "  (inherited)" if inherited else ""
        yield Static(f"{label}: {value or '(unset)'}{mark}", id=f"bio-view-{section}-{slug}", classes="bio-field-value")
        extra = ""
        if label == "Rules" and value:
            extra = "\n".join(rule_sentence(ln) for ln in (self._value("tools", "rules") or []) if str(ln).strip())
        elif label == "Timeout":
            extra = duration_hint(value)
        elif label == "Max budget (USD)":
            extra = budget_hint(value, self.preference(), self.models)
        lines = [ln for ln in (help_line if section != "identity" else "", extra) if ln]  # identity: its label says it
        if lines:
            yield Static("\n".join(lines), classes="bio-hint")

    def _yaml(self) -> str:
        import yaml
        return yaml.safe_dump(self.bio, sort_keys=False, default_flow_style=False, allow_unicode=True) or "{}\n"

    # -- actions ---------------------------------------------------------------
    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id or ""
        if bid == "bio-edit-studio":
            self.action_edit_in_studio()
        elif bid == "bio-try":
            self.action_try_it()
        elif bid == "bio-close":
            self.action_close()

    def _hint(self, text: str) -> None:
        try:
            self.query_one("#bio-hint", Static).update(text)
        except Exception:
            pass

    def action_edit_in_studio(self) -> None:
        from halo_harness.tui import studio_open
        studio_open.open_target(self, f"bio:{self.bio_name}", cwd=self.cwd, state_dir=self.state_dir, on_line=self._hint)

    def action_try_it(self) -> None:
        """The cost line first, before a token is spent; then the smoke call (the bio's acceptance prompt,
        else the fixed smoke prompt) on a worker; its one-line reply lands in the same hint."""
        from halo_harness.smoke_run import run_bio_smoke, smoke_cost_line
        pref = self.preference()
        if not pref:
            self._hint("Try it: this bio resolves no model yet -- pick a preference in Studio (e).")
            return
        acceptance_prompt = self._value("acceptance", "prompt")
        cost_line = smoke_cost_line(pref)
        try:
            hint_widget = self.query_one("#bio-hint", Static)
        except Exception:
            return
        hint_widget.update(f"Try it -- cost first: {cost_line}\nrunning the smoke call...")

        def _work() -> None:
            out = run_bio_smoke(pref, acceptance_prompt if isinstance(acceptance_prompt, str) else None)
            summary = (out.strip().splitlines() or [""])[-1][:200]
            verdict = "replied" if summary else "no output (credentials/model issue?)"
            try:
                self.app.call_from_thread(hint_widget.update,
                                          f"Try it -- cost first: {cost_line}\n{verdict}: {summary if summary else '-'}")
            except Exception:
                pass
        guarded_worker(self, _work, thread=True, name="bio-try-it", group="bio-try-it")

    def action_close(self) -> None:
        self.dismiss(None)
