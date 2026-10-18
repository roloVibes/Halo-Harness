"""halo_harness.tui.dialogs.teams_list -- `/teams list`:
every lineup with its scope, the active one marked (Halo 2.0.5 round 2; moved
out of lineup_editor.py in 3.1.1.0 R3, when Studio became the one editor of
lineups).

Enter (or View) opens the read-only `LineupView`; Edit in Studio opens Studio
on the highlighted lineup (`halo studio --edit lineup:<name>`); New writes a
starter lineup and opens Studio on it; Activate makes it the active team.
"""

from __future__ import annotations

from typing import Optional

from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, OptionList, Static
from textual.widgets.option_list import Option


def team_rows(*, cwd=None, state_dir=None) -> "list[dict]":
    """`[{"name", "scope", "description", "active", "roles"}, ...]`, the list screen's rows."""
    from halo_harness.teams_yaml import ensure_builtin_team_templates, find_team_template_path, \
        list_team_templates, resolve_team_template
    from halo_harness.theme import get_config_value
    ensure_builtin_team_templates(state_dir=state_dir)
    active = get_config_value("team", default=None)
    rows = []
    for name in list_team_templates(cwd=cwd, state_dir=state_dir):
        found = find_team_template_path(name, cwd=cwd, state_dir=state_dir)
        template = resolve_team_template(name, cwd=cwd, state_dir=state_dir) or {}
        roles = template.get("roles") or {}
        n_roles = len(roles) if isinstance(roles, dict) else len(template.get("agents") or [])
        rows.append({"name": name, "scope": found[1] if found else "?",
                     "description": template.get("description") or "", "active": name == active,
                     "roles": n_roles})
    return rows


def _team_row_label(r: dict) -> str:
    marker = " [active]" if r["active"] else ""
    desc = f": {r['description']}" if r["description"] else ""
    return f"{r['name']} [{r['scope']}]{marker}{desc}"


class TeamsListScreen(ModalScreen):
    BINDINGS = [Binding("escape", "cancel", "Close", show=False),
                Binding("e", "edit_in_studio", "Edit in Studio", show=True)]
    DEFAULT_CSS = """
    TeamsListScreen { align: center middle; }
    TeamsListScreen > Vertical { width: 90%; height: 80%; border: round $primary; background: $surface;
                                   padding: 1 2; }
    TeamsListScreen #teams-list { height: 1fr; margin-top: 1; }
    TeamsListScreen .wizard-extra-buttons { height: 3; margin-top: 1; }
    TeamsListScreen .wizard-extra-buttons Button { margin-right: 1; }
    """

    def __init__(self, *, cwd=None, state_dir=None, models: "Optional[list]" = None) -> None:
        super().__init__()
        self.cwd, self.state_dir, self.models = cwd, state_dir, (models or [])

    def compose(self):
        with Vertical():
            yield Static("Team templates (lineups)", classes="dialog-title")
            yield Static("Enter/View: show  |  e: edit in Studio  |  New/Activate  |  Esc: close",
                         classes="dialog-subtitle")
            self._rows = team_rows(cwd=self.cwd, state_dir=self.state_dir)
            yield OptionList(*[Option(_team_row_label(r), id=r["name"]) for r in self._rows], id="teams-list")
            with Horizontal(classes="wizard-extra-buttons"):
                yield Button("View", id="teams-view")
                yield Button("Edit in Studio", id="teams-edit", variant="primary")
                yield Button("New", id="teams-new")
                yield Button("Activate", id="teams-activate")
            yield Static("", id="teams-hint")

    def on_mount(self) -> None:
        try:
            self.query_one("#teams-list", OptionList).focus()
        except Exception:
            pass

    def _highlighted_name(self) -> "Optional[str]":
        try:
            option_list = self.query_one("#teams-list", OptionList)
        except Exception:
            return None
        if option_list.highlighted is None:
            return None
        opt = option_list.get_option_at_index(option_list.highlighted)
        return str(opt.id) if opt.id else None

    def _refresh(self) -> None:
        try:
            option_list = self.query_one("#teams-list", OptionList)
        except Exception:
            return
        previous = self._highlighted_name()
        self._rows = team_rows(cwd=self.cwd, state_dir=self.state_dir)
        option_list.clear_options()
        for r in self._rows:
            option_list.add_option(Option(_team_row_label(r), id=r["name"]))
        names = [r["name"] for r in self._rows]
        if names:
            option_list.highlighted = names.index(previous) if previous in names else 0

    def _hint(self, text: str) -> None:
        try:
            self.query_one("#teams-hint", Static).update(text)
        except Exception:
            pass

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        self._open_view()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id or ""
        if bid == "teams-view":
            self._open_view()
        elif bid == "teams-edit":
            self.action_edit_in_studio()
        elif bid == "teams-new":
            self._new_in_studio()
        elif bid == "teams-activate":
            self._activate_highlighted()

    def _open_view(self) -> None:
        name = self._highlighted_name()
        if name is None:
            self._hint("Highlight a lineup first.")
            return
        from halo_harness.tui.dialogs.lineup_editor import LineupView
        self.app.push_screen(LineupView(name, None, self.models, cwd=self.cwd, state_dir=self.state_dir),
                             lambda _r: self._refresh())

    def action_edit_in_studio(self) -> None:
        name = self._highlighted_name()
        if name is None:
            self._hint("Highlight a lineup first.")
            return
        from halo_harness.tui import studio_open
        studio_open.open_target(self, f"lineup:{name}", cwd=self.cwd, state_dir=self.state_dir, on_line=self._hint)

    def _new_in_studio(self) -> None:
        from halo_harness.tui import studio_open
        name, problems = studio_open.new_lineup(cwd=self.cwd, state_dir=self.state_dir)
        if not name:
            self._hint("; ".join(problems))
            return
        self._refresh()
        studio_open.open_target(self, f"lineup:{name}", cwd=self.cwd, state_dir=self.state_dir, on_line=self._hint)

    def _activate_highlighted(self) -> None:
        name = self._highlighted_name()
        if name is None:
            self._hint("Highlight a lineup first.")
            return
        from halo_harness.teams_yaml import resolve_team_template, validate_team_template
        template = resolve_team_template(name, cwd=self.cwd, state_dir=self.state_dir)
        problems = validate_team_template(template or {}, name=name, cwd=self.cwd, state_dir=self.state_dir)
        if problems:
            self._hint("; ".join(problems))
            return
        from halo_harness.theme import set_config_value
        set_config_value("team", name)
        self._hint(f"Active team: {name!r}.")
        self._refresh()

    def action_cancel(self) -> None:
        self.dismiss(None)

