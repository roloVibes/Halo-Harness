"""halo_harness.tui.dialogs.agents_step -- Halo 2.0.5 round 2 (wizard: agent
bios and lineups), deliverable 1: the Agents step (`"agents"` in `init_
wizard.ALL_STEP_KEYS`) and deliverable 4's own `/agents`/`halo agents
--form` list+actions screen -- BOTH built on the SAME pure `bio_rows()`
helper and the SAME `AgentBioEditor` form (`agent_bio_editor.py`), never
disagreeing on what a row shows or how a save lands, same "duplicate the
chrome, share the behaviour" split `init_wizard.py`'s own `ProvidersStep`
docstring already explains for `InitTabsApp`. A NEW module (hard
constraint: `init_wizard.py` gains only the registration line).

`AgentsStep` deliberately subclasses the bare Textual `Screen`, never
`init_wizard.StepScreen` -- `init_wizard.py` imports THIS module (to
register `STEP_FACTORIES["agents"]`), so a reverse top-level `from
halo_harness.tui.dialogs.init_wizard import StepScreen` here would be a
genuine class-level circular import (not just a lazily-resolvable one,
since a `class X(StepScreen):` statement needs the real class object at
MODULE LOAD time) depending on which of the two modules happens to be
imported first. `AgentsStep` instead duplicates `StepScreen`'s own small
header/footer chrome directly and reaches `init_wizard.advance`/`go_back`/
`finish` through a LAZY, function-body-only import (safe: by the time any
action actually RUNS, both modules have finished loading) -- the exact
"duplicate the chrome" split this module's own docstring already cites.
"""

from __future__ import annotations

from typing import Optional

from textual.app import App
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen, Screen
from textual.widgets import Button, OptionList, Static
from textual.widgets.option_list import Option

from halo_harness.tui.dialogs.agent_bio_editor import AgentBioEditor


def bio_rows(*, cwd=None, state_dir=None) -> "list[dict]":
    """`[{"name", "scope", "description", "preferred_model"}, ...]`,
    name-sorted -- `scope` is the NEAREST file this name actually
    resolves to right now (`agents_yaml.find_agent_bio_path`'s own
    "project"/"user"/"template" label), never the chain `extends` might
    walk through afterward."""
    from halo_harness.agents_yaml import find_agent_bio_path, list_agent_bios, resolve_agent_bio
    rows = []
    for name in list_agent_bios(cwd=cwd, state_dir=state_dir):
        found = find_agent_bio_path(name, cwd=cwd, state_dir=state_dir)
        bio = resolve_agent_bio(name, cwd=cwd, state_dir=state_dir)
        models = (bio or {}).get("models") or {}
        rows.append({"name": name, "scope": found[1] if found else "?",
                     "description": (bio or {}).get("description") or "",
                     "preferred_model": models.get("preference") or models.get("fallback") or ""})
    return rows


def _row_label(r: dict) -> str:
    extra = f" -- {r['preferred_model']}" if r["preferred_model"] else ""
    desc = f": {r['description']}" if r["description"] else ""
    return f"{r['name']} [{r['scope']}]{desc}{extra}"


def _import_candidates(*, cwd=None) -> "list[str]":
    """Fold-in "Import from Claude Code": every discovered `.claude/
    agents/*.md` name (`config/agents_md.discover_agents`'s own "user"/
    "project:*" sources -- never a built-in/managed/plugin/cli-agents
    definition) that isn't ALREADY an agent bio name."""
    from pathlib import Path
    from halo_harness.agents_yaml import list_agent_bios
    from halo_harness.config.agents_md import discover_agents
    try:
        specs = discover_agents(Path(cwd) if cwd is not None else Path.cwd())
    except Exception:
        specs = {}
    existing = set(list_agent_bios(cwd=cwd))
    return sorted(name for name, spec in specs.items()
                  if (spec.source == "user" or spec.source.startswith("project:")) and name not in existing)


def _import_all(*, cwd=None, state_dir=None) -> "list[str]":
    """Converts every `_import_candidates` name into a user-scope bio --
    "one result line each"."""
    from halo_harness.agents_md_bridge import import_agent_bio
    from halo_harness.agents_yaml import save_agent_bio
    lines = []
    for name in _import_candidates(cwd=cwd):
        bio, problems = import_agent_bio(name, cwd=cwd)
        if bio is None:
            lines.append(f"{name}: {'; '.join(problems)}")
            continue
        ok, save_problems = save_agent_bio(name, bio, cwd=cwd, state_dir=state_dir)
        lines.append(f"{name}: imported" if ok else f"{name}: {'; '.join(save_problems)}")
    return lines or ["(nothing new to import from .claude/agents)"]


class _AgentsListMixin:
    """The list + action buttons + hint, and every action handler --
    shared verbatim by `AgentsStep` (a `StepScreen`, the wizard) and
    `AgentsListScreen` (a standalone `ModalScreen`, `/agents` and `--
    form`). Confirmed live (Textual dispatches `on_<event>` at EVERY
    class in the MRO that defines one, not just the most-derived) that
    this mixin's own `on_button_pressed` coexists safely with whatever
    the CONCRETE class's other base already handles (`StepScreen`'s own
    wiz-back/skip/next) -- see `init_wizard.py`'s `LocalModelsStep`/
    `ProvidersStep` for the same pattern this mirrors."""

    def _cwd(self):
        return None

    def _state_dir(self):
        return None

    def _models_for_picker(self) -> list:
        return []

    def _agents_list_widgets(self) -> list:
        self._rows = bio_rows(cwd=self._cwd(), state_dir=self._state_dir())
        option_list = OptionList(*[Option(_row_label(r), id=r["name"]) for r in self._rows], id="agents-list")
        return [
            option_list,
            Horizontal(Button("New", id="agents-new", variant="primary"),
                       Button("New from...", id="agents-new-from"),
                       Button("Edit", id="agents-edit"),
                       Button("Duplicate", id="agents-duplicate"),
                       Button("Delete", id="agents-delete"),
                       Button("Import", id="agents-import"),
                       classes="wizard-extra-buttons"),
            Static("", id="agents-hint"),
        ]

    def _highlighted_name(self) -> "Optional[str]":
        try:
            option_list = self.query_one("#agents-list", OptionList)
        except Exception:
            return None
        if option_list.highlighted is None:
            return None
        opt = option_list.get_option_at_index(option_list.highlighted)
        return str(opt.id) if opt.id else None

    def _refresh_list(self) -> None:
        try:
            option_list = self.query_one("#agents-list", OptionList)
        except Exception:
            return
        previous = self._highlighted_name()
        self._rows = bio_rows(cwd=self._cwd(), state_dir=self._state_dir())
        option_list.clear_options()
        for r in self._rows:
            option_list.add_option(Option(_row_label(r), id=r["name"]))
        names = [r["name"] for r in self._rows]
        if names:
            option_list.highlighted = names.index(previous) if previous in names else 0

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id or ""
        if bid == "agents-new":
            self._open_editor_for_new()
        elif bid == "agents-new-from":
            self._open_editor_for_new(extends_from=self._highlighted_name())
        elif bid == "agents-edit":
            self._open_editor_for_existing()
        elif bid == "agents-duplicate":
            self._duplicate_highlighted()
        elif bid == "agents-delete":
            self._delete_highlighted()
        elif bid == "agents-import":
            self._import()

    def _open_editor_for_new(self, *, extends_from: "Optional[str]" = None) -> None:
        import uuid
        default_name = f"{extends_from}-copy" if extends_from else f"agent-{uuid.uuid4().hex[:6]}"
        raw = {"extends": extends_from} if extends_from else {}
        self.app.push_screen(
            AgentBioEditor(default_name, raw, self._models_for_picker(), cwd=self._cwd(),
                            state_dir=self._state_dir(), is_new=True, extends_from=extends_from),
            lambda _saved: self._refresh_list())

    def _open_editor_for_existing(self) -> None:
        name = self._highlighted_name()
        if name is None:
            self._hint("Highlight a bio first.")
            return
        from halo_harness.agents_yaml import load_agent_bio_raw
        raw = load_agent_bio_raw(name, cwd=self._cwd(), state_dir=self._state_dir()) or {}
        self.app.push_screen(
            AgentBioEditor(name, raw, self._models_for_picker(), cwd=self._cwd(), state_dir=self._state_dir()),
            lambda _saved: self._refresh_list())

    def _duplicate_highlighted(self) -> None:
        name = self._highlighted_name()
        if name is None:
            self._hint("Highlight a bio first.")
            return
        from halo_harness.agents_yaml import new_agent_bio_from_template
        ok, problems = new_agent_bio_from_template(name, name, cwd=self._cwd(), state_dir=self._state_dir())
        self._hint(f"Duplicated {name!r} into user scope." if ok else "; ".join(problems))
        self._refresh_list()

    def _delete_highlighted(self) -> None:
        name = self._highlighted_name()
        if name is None:
            self._hint("Highlight a bio first.")
            return
        from halo_harness.agents_yaml import delete_agent_bio
        ok = delete_agent_bio(name, cwd=self._cwd(), state_dir=self._state_dir())
        self._hint(f"Deleted {name!r}." if ok
                    else f"Nothing to delete for {name!r} at project/user scope (a shipped bio is never "
                         f"deleted in place -- Duplicate first).")
        self._refresh_list()

    def _import(self) -> None:
        lines = _import_all(cwd=self._cwd(), state_dir=self._state_dir())
        self._hint("\n".join(lines))
        self._refresh_list()

    def _hint(self, text: str) -> None:
        try:
            self.query_one("#agents-hint", Static).update(text)
        except Exception:
            pass


class AgentsStep(_AgentsListMixin, Screen):
    """Deliverable 1: `"agents"` in `init_wizard.ALL_STEP_KEYS`, after the
    keys step/enumeration and before "roles" -- see the module docstring
    for why this duplicates `StepScreen`'s own small header/footer chrome
    rather than subclassing it."""
    BINDINGS = [
        Binding("escape", "ask_quit", "Quit setup", show=False, priority=True),
        Binding("ctrl+n", "do_next", "Next", show=False),
        Binding("ctrl+b", "do_back", "Back", show=False),
    ]
    DEFAULT_CSS = """
    AgentsStep { align: center middle; }
    AgentsStep > Vertical { width: 94%; height: 92%; border: round $primary; padding: 1 2; background: $surface; }
    AgentsStep #agents-list { height: 1fr; margin-top: 1; }
    AgentsStep .wizard-extra-buttons { height: 3; margin-top: 1; }
    AgentsStep .wizard-extra-buttons Button { margin-right: 1; }
    AgentsStep .wizard-footer { height: 3; align: right middle; margin-top: 1; }
    AgentsStep .wizard-footer Button { margin-left: 1; }
    """

    def __init__(self, state) -> None:
        super().__init__()
        self.state = state

    def _cwd(self):
        return self.state.cwd

    def _models_for_picker(self) -> list:
        # Same "this wizard run's own enumeration cache wins once it
        # exists" rule `RolesStep._controller_models`/`OrgsStep._
        # controller_models` already follow -- never re-enumerate here.
        if self.state.enumeration_done:
            return self.state.enumerated_models
        list_models = getattr(getattr(self.app, "controller", None), "list_models", None)
        try:
            return list_models() if callable(list_models) else []
        except Exception:
            return []

    def compose(self):
        with Vertical():
            yield Static(self.state.title(), classes="wizard-header")
            yield Static("Agent bios -- what each agent IS: models, tools, context, limits, output, "
                         "environment, acceptance. The next step (a lineup) assigns bios to roles.",
                         classes="dialog-title")
            for w in self._agents_list_widgets():
                yield w
            with Horizontal(classes="wizard-footer"):
                yield Button("Back", id="wiz-back", disabled=self.state.index == 0)
                yield Button("Skip", id="wiz-skip")
                last = self.state.index + 1 >= len(self.state.step_keys)
                yield Button("Finish" if last else "Next", id="wiz-next", variant="primary")

    def on_mount(self) -> None:
        try:
            self.query_one("#agents-list", OptionList).focus()
        except Exception:
            pass

    # -- the small bit of StepScreen's own chrome this step needs -- lazy
    # imports only (module docstring: never a top-level `from init_wizard
    # import ...` here).
    def on_button_pressed(self, event: Button.Pressed) -> None:  # noqa: F811 (extends the mixin's own)
        bid = event.button.id or ""
        if bid == "wiz-back":
            self.action_do_back()
        elif bid == "wiz-skip":
            from halo_harness.tui.dialogs.init_wizard import advance
            advance(self.app, self.state, skip=True)
        elif bid == "wiz-next":
            self.action_do_next()

    def action_do_next(self) -> None:
        from halo_harness.tui.dialogs.init_wizard import advance
        advance(self.app, self.state)

    def action_do_back(self) -> None:
        from halo_harness.tui.dialogs.init_wizard import go_back
        go_back(self.app, self.state)

    def action_ask_quit(self) -> None:
        from halo_harness.tui.dialogs.init_wizard import _QuitConfirm, finish

        def _after(confirmed: "Optional[bool]") -> None:
            if confirmed:
                finish(self.app, self.state)
        self.app.push_screen(_QuitConfirm(), _after)


class AgentsListScreen(_AgentsListMixin, ModalScreen):
    """Deliverable 4: `/agents new|edit|duplicate|delete` and `halo agents
    new|edit --form` open THIS standalone screen -- the SAME `_AgentsList
    Mixin` body/actions `AgentsStep` uses, in its own Esc-to-close modal
    (no wizard Back/Skip/Next chrome)."""

    BINDINGS = [Binding("escape", "cancel", "Close", show=False)]
    DEFAULT_CSS = """
    AgentsListScreen { align: center middle; }
    AgentsListScreen > Vertical { width: 90%; height: 80%; border: round $primary; background: $surface;
                                    padding: 1 2; }
    AgentsListScreen #agents-list { height: 1fr; margin-top: 1; }
    AgentsListScreen .wizard-extra-buttons { height: 3; margin-top: 1; }
    AgentsListScreen .wizard-extra-buttons Button { margin-right: 1; }
    """

    def __init__(self, *, cwd=None, state_dir=None, models: "Optional[list]" = None) -> None:
        super().__init__()
        self._cwd_value = cwd
        self._state_dir_value = state_dir
        self._models = models or []

    def _cwd(self):
        return self._cwd_value

    def _state_dir(self):
        return self._state_dir_value

    def _models_for_picker(self) -> list:
        return self._models

    def compose(self):
        with Vertical():
            yield Static("Agent bios", classes="dialog-title")
            yield Static("Enter/Edit: open  |  New/New from.../Duplicate/Delete/Import  |  Esc: close",
                         classes="dialog-subtitle")
            for w in self._agents_list_widgets():
                yield w

    def on_mount(self) -> None:
        try:
            self.query_one("#agents-list", OptionList).focus()
        except Exception:
            pass

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        self._open_editor_for_existing()

    def action_cancel(self) -> None:
        self.dismiss(None)


# Mixin method resolution needs `AgentsListScreen`'s own `on_button_pressed`
# -- inherited straight from `_AgentsListMixin` (no override here), so a
# press on "agents-new"/.../"agents-import" works identically to the step.


def run_agents_list_standalone(*, cwd=None, state_dir=None) -> None:
    """Deliverable 4: `halo agents new|edit <name> --form` with NO <name>
    at all (or a dedicated `halo agents --form` someday) opens this list
    standalone, same reasoning as `agent_bio_editor.run_agent_bio_editor_
    standalone`."""
    from halo_harness.config.paths import bridge_home
    from halo_harness.providers.model_enumeration import build_model_rows
    sd = state_dir if state_dir is not None else bridge_home()
    try:
        models = build_model_rows(sd)
    except Exception:
        models = []

    class _AgentsListApp(App):
        TITLE = "halo agents"

        def on_mount(self) -> None:
            self.push_screen(AgentsListScreen(cwd=cwd, state_dir=state_dir, models=models),
                              lambda _r: self.exit())

    _AgentsListApp().run()
