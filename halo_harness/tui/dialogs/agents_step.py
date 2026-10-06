"""halo_harness.tui.dialogs.agents_step -- Halo 2.0.5 round 2 (wizard: agent
bios and lineups), deliverable 4's own `/agents`/`halo agents --form`
list+actions screen (`AgentsListScreen`), built on the SAME pure
`bio_rows()` helper and the SAME `AgentBioEditor` form (`agent_bio_editor.
py`) the wizard's own Team step (`tui/dialogs/team_step.py`, Halo 2.0.5
round 2c) now also reuses for its right-hand "Agents" pane -- never
disagreeing on what a row shows or how a save lands, same "duplicate the
chrome, share the behaviour" split `init_wizard.py`'s own `ProvidersStep`
docstring already explains for `InitTabsApp`.

Round 2c (`plans/briefs/2.0.5/round-2c-wizard-ux.md`, rule 11): the wizard's
OWN `AgentsStep` step class that used to live here is GONE -- the Agents
step and the "Roles and lineup" step merged into one "Team" step
(`team_step.TeamStep`), which mixes in `_AgentsListMixin` directly instead
of subclassing a step class defined in this module. `_AgentsListMixin`
itself (the list + action buttons + every handler) is UNCHANGED in
substance, now also carrying the Ctrl+N/Ctrl+D/Del chords rule 9's uniform
footer promises everywhere this mixin is used (`TeamStep`'s own Agents
pane, and this module's `AgentsListScreen`) -- round 2b's buttons-only
New/Duplicate/Delete stay exactly as they were, just no longer the only
path.
"""

from __future__ import annotations

from typing import Optional

from textual.app import App
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
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


def _cache_only_model_rows() -> "list[dict]":
    """`providers.model_enumeration.build_model_rows` against the already-
    cached catalog files -- no network, synchronous, fast (the same read
    `run_agents_list_standalone`/`run_lineup_editor_standalone` already do
    up front); `[]` on any failure, never raises."""
    from halo_harness.config.paths import bridge_home
    from halo_harness.providers.model_enumeration import build_model_rows
    try:
        return build_model_rows(bridge_home())
    except Exception:
        return []


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


#: Round 2c (rule 9, the uniform footer): Ctrl+N/Ctrl+D/Del for whatever
#: `action_agents_new`/`_duplicate`/`_delete` below mean on the host
#: screen -- a PLAIN TUPLE, not a `BINDINGS` list on the mixin itself:
#: Textual's own `DOMNode._merge_bindings` walks `cls.__mro__` but only
#: ever reads `BINDINGS` off a class that `issubclass(base, DOMNode)`
#: (confirmed against Textual 8.2.8's own source) -- a plain mixin with
#: no `DOMNode` ancestor is silently skipped, so a `BINDINGS` list
#: living HERE would never actually bind the chord (found live: Ctrl+N
#: did nothing at all). Every CONCRETE host (`team_step.TeamStep`,
#: `AgentsListScreen` below) splices this tuple into its OWN `BINDINGS`
#: instead -- the three `action_agents_*` METHODS still live on the
#: mixin and resolve normally (ordinary attribute lookup across the
#: MRO is unaffected by the DOMNode check, which is specific to this
#: one classmethod), so only the bindings themselves need repeating.
AGENTS_LIST_BINDINGS = (
    Binding("ctrl+n", "agents_new", "New", show=False, priority=True),
    Binding("ctrl+d", "agents_duplicate", "Duplicate", show=False, priority=True),
    Binding("delete", "agents_delete", "Delete", show=False, priority=True),
)


class _AgentsListMixin:
    """The list + action buttons + hint, and every action handler --
    shared verbatim by `team_step.TeamStep` (its own right-hand "Agents"
    pane) and `AgentsListScreen` (a standalone `ModalScreen`, `/agents`
    and `--form`). Confirmed live (Textual dispatches `on_<event>` at
    EVERY class in the MRO that defines one, not just the most-derived)
    that this mixin's own `on_button_pressed` coexists safely with
    whatever the CONCRETE class's OTHER base already handles (`TeamStep`'s
    own wiz-back/skip/next and Lineups-pane chords) -- see `init_wizard.
    py`'s `LocalModelsStep`/`ProvidersStep` for the same on_button_pressed-
    coexistence pattern this mirrors. See `AGENTS_LIST_BINDINGS` above for
    why the CHORDS themselves are a plain tuple a host splices in, not a
    `BINDINGS` list declared right here."""

    def action_agents_new(self) -> None:
        self._open_editor_for_new()

    def action_agents_duplicate(self) -> None:
        self._duplicate_highlighted()

    def action_agents_delete(self) -> None:
        self._delete_highlighted()

    def _cwd(self):
        return None

    def _state_dir(self):
        return None

    def _models_for_picker(self) -> list:
        return []

    def _agents_list_widgets(self) -> list:
        from halo_harness.tui.dialogs.wizard_ux import footer_hint
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
            # Rule 9: the uniform footer caption -- "choose" here means
            # Enter opens the highlighted bio (rule 2); no Ctrl+S of its
            # own (a save happens inside the bio editor this opens).
            Static(footer_hint(new=True, delete=True, save=False), classes="bio-hint"),
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

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        """Bug sweep (round 2b, owner feedback: "you highlight a row, then
        Tab down to a button and press ... edit this"), rule (a): Enter on
        a highlighted bio opens it -- the buttons stay, but are never the
        ONLY path. Lives on the mixin (was `AgentsListScreen`-only) so
        every host of `_AgentsListMixin` -- `AgentsListScreen` and the
        wizard's own Team step (`team_step.TeamStep`'s Agents pane) --
        gets the exact same behaviour as `/agents`/`--form`."""
        if event.option_list.id == "agents-list":
            self._open_editor_for_existing()

    def _after_bio_saved(self, saved: "Optional[str]") -> None:
        """Rule 8: "Save shows a one-line toast" -- the bio editor itself
        dismisses the instant Save succeeds, so the toast lands here, on
        the list screen the user actually returns to."""
        self._refresh_list()
        if saved:
            from halo_harness.tui.dialogs.wizard_ux import toast
            try:
                toast(self.query_one("#agents-hint", Static), f"Saved {saved!r}.")
            except Exception:
                pass

    def _open_editor_for_new(self, *, extends_from: "Optional[str]" = None) -> None:
        import uuid
        default_name = f"{extends_from}-copy" if extends_from else f"agent-{uuid.uuid4().hex[:6]}"
        raw = {"extends": extends_from} if extends_from else {}
        self.app.push_screen(
            AgentBioEditor(default_name, raw, self._models_for_picker(), cwd=self._cwd(),
                            state_dir=self._state_dir(), is_new=True, extends_from=extends_from),
            self._after_bio_saved)

    def _open_editor_for_existing(self) -> None:
        name = self._highlighted_name()
        if name is None:
            self._hint("Highlight a bio first.")
            return
        from halo_harness.agents_yaml import load_agent_bio_raw
        raw = load_agent_bio_raw(name, cwd=self._cwd(), state_dir=self._state_dir()) or {}
        self.app.push_screen(
            AgentBioEditor(name, raw, self._models_for_picker(), cwd=self._cwd(), state_dir=self._state_dir()),
            self._after_bio_saved)

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


class AgentsListScreen(_AgentsListMixin, ModalScreen):
    """Deliverable 4: `/agents new|edit|duplicate|delete` and `halo agents
    new|edit --form` open THIS standalone screen -- the SAME `_AgentsList
    Mixin` body/actions `team_step.TeamStep`'s own Agents pane uses, in
    its own Esc-to-close modal (no wizard Back/Skip/Next chrome)."""

    BINDINGS = [Binding("escape", "cancel", "Close", show=False), *AGENTS_LIST_BINDINGS]
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

    def action_cancel(self) -> None:
        self.dismiss(None)


# Mixin method resolution needs `AgentsListScreen`'s own `on_button_pressed`
# AND `on_option_list_option_selected` -- both inherited straight from
# `_AgentsListMixin` (no override here), so a press on "agents-new"/.../
# "agents-import", or Enter on a highlighted row, works identically to
# the wizard step.


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
