"""halo_harness.tui.dialogs.init_wizard -- Halo 2.0.2 round 7: ONE Textual
app for the whole interactive `halo init` (and `halo setup`/`/setup`),
replacing the old tabs-app-then-plain-console-steps flow (owner 2026-10-03:
"I have to press esc then it exits then brings up the next section ...
there should be a button you select to move it forward"). Every step is a
plain `Screen` pushed onto the SAME app's screen stack (`push_screen`/
`pop_screen`) -- nothing ever tears down the terminal driver between
steps, and Back genuinely returns to the previous step's own widget state
(Textual suspends, never destroys, a screen under a newer one).

Steps, in order (`ALL_STEP_KEYS`): providers, local_models, default_model,
permission_mode, theme, team, orgs, linux_fixes, summary --
`full_step_keys()` drops `linux_fixes` when there is nothing for it to
offer (brief item 1). A
SHORTER run (`halo setup`, `/setup roles`) uses a SUBSET of this same list
via `build_truncated_state`/`first_step_screen` -- the exact same Screen
classes serve both, which is also what `/setup` (pushed onto a live
`BridgeApp`) and the standalone `halo init`/`halo setup` wizard share.

Halo 2.0.5 round 2c (`plans/briefs/2.0.5/round-2c-wizard-ux.md`, the wizard
interaction model, `docs/WIZARD.md`): a FIRST screen, before "providers",
offers Quick/Full setup (`tui/dialogs/setup_mode.SetupModeStep`, pushed
only by a genuine standalone `halo init` with no `--step` -- see
`WizardState.offer_quick_full`); every step now shows a step rail (current
highlighted, done ticked -- `tui/dialogs/step_rail.py`) and Ctrl+Left/
Ctrl+Right walk Back/Next from anywhere; rule 11 merged the round-2/2b
"Agents" step and "Roles and lineup" step into ONE "Team" step
(`tui/dialogs/team_step.TeamStep`) -- `STEP_FACTORIES["team"]` is the real
entry, `"agents"`/`"roles"` stay registered as plain aliases pointing at
the SAME factory (`--step agents`/`--step roles`, and the pre-existing
`/setup roles`/`halo setup roles` step_keys literal, all still land there
with zero other code changes needed).

Hosting: `run_init_wizard()` builds a standalone `InitWizardApp` (same
reason `init_tabs.py`'s `InitTabsApp`/`init_picker.py`'s pickers are
standalone -- a bare CLI command has no host screen stack); `tui/slash.
py`'s `/setup` instead pushes the first step straight onto the live
`BridgeApp` (the SAME pattern `RolesEditor`/`OrgEditor` already use) --
every step screen is host-agnostic (it only ever calls `self.app.
push_screen`/`pop_screen`, never anything App-subclass-specific), so the
exact same classes work either way.

The "Providers" step duplicates (deliberately, not by subclassing)
`init_tabs.py`'s `InitTabsApp` tab composition/workers -- both call the
SAME Textual-free `init_providers.py` functions, so the two can never
disagree on BEHAVIOUR, only on the chrome around it (a Screen's own
Back/Skip/Next footer here vs. that module's standalone Esc-to-finish).
`init_tabs.py` itself is left untouched -- its own large pilot-test block
in test_tui.py keeps passing unchanged.
"""

from __future__ import annotations

import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen, Screen
from textual.widgets import Button, Input, Static, TabbedContent, TabPane

from halo_harness.init_providers import TAB_LABEL, TAB_PROVIDERS, tab_credential_state
from halo_harness.tui.dialogs.step_rail import STEP_RAIL_BINDINGS, StepRailMixin
from halo_harness.tui.dialogs.wizard_ux import focus_first, mark_checked, one_sentence

# Halo 2.0.5 round 2c (rule 11): "agents" and "roles" MERGE into one
# "team" step -- STILL right after the keys step/enumeration (every
# earlier step already is) and before "orgs" (which the lineup's own
# `org:` section can feed, same as before). `full_step_keys()`'s only
# other caller in test_tui.py resolves by KEY name, unaffected either
# way; `_resolve_start_index` keeps "agents"/"roles" working as `--step`
# aliases even though neither is in this tuple any more (see its own
# alias map).
ALL_STEP_KEYS = ("providers", "local_models", "default_model", "permission_mode", "theme", "team",
                 "orgs", "linux_fixes", "summary")
STEP_TITLES = {
    "providers": "Providers", "local_models": "Local models", "default_model": "Default model",
    "permission_mode": "Permission mode", "theme": "Theme",
    "team": "Team", "orgs": "Organizations",
    "linux_fixes": "Linux fixes", "summary": "Summary",
    # Round 2c: "agents"/"roles" are no longer real keys in `ALL_STEP_
    # KEYS` (`_STEP_KEY_ALIASES` is `_resolve_start_index`'s OWN alias
    # map, for a `--step` value checked against a real `step_keys`
    # tuple) -- but `setup_cli.py`/`tui/slash.py` and several pre-
    # existing tests still build a `WizardState`/push a step with the
    # LITERAL `step_keys=("agents",)`/`("roles",)`, and `WizardState.
    # title()`/`TeamStep`'s own rail both index this dict BY THAT SAME
    # literal key -- missing either one here is a real `KeyError` in
    # production (`/setup roles`), not just a test gap.
    "agents": "Team", "roles": "Team",
}
# `--step agents`/`--step roles` (and the pre-existing `step_keys=
# ("agents",)`/`("roles",)` literals in `setup_cli.py`/`tui/slash.py`)
# keep landing on the Team step -- `STEP_FACTORIES["agents"/"roles"]` are
# registered as plain aliases of `STEP_FACTORIES["team"]` below; this map
# is ONLY for `_resolve_start_index`, which checks membership in the
# ACTUAL `step_keys` tuple a run is using (now spelled "team" there).
_STEP_KEY_ALIASES = {"agents": "team", "roles": "team"}


@dataclass
class WizardState:
    """Shared, mutable, cross-step data -- passed BY REFERENCE to every
    step screen's constructor, so step N+1 can read what step N decided
    and the Summary step can read everything. The `configured_this_run`/
    `written`/`doctor_lines`/`picked_per_provider`/`team_warnings`/
    `catalog_notes` names deliberately mirror `init_tabs.InitTabsApp`'s
    own result attributes -- `init_cli.py` reads this object back the
    same way it used to read that app."""
    cwd: Path
    step_keys: tuple = ALL_STEP_KEYS
    index: int = 0
    team: Optional[str] = None
    no_live: bool = False
    on_finish: "Optional[Callable[[object], None]]" = None
    pushed: int = 0  # screens THIS wizard has pushed -- popped this many times to fully exit

    configured_this_run: list = field(default_factory=list)
    written: list = field(default_factory=list)
    doctor_lines: list = field(default_factory=list)
    picked_per_provider: dict = field(default_factory=dict)
    team_warnings: list = field(default_factory=list)
    catalog_notes: dict = field(default_factory=dict)
    final_model: str = ""
    permission_mode: str = ""
    theme_name: str = ""
    default_org: str = ""
    pong_ok: bool = True

    # Halo 2.0.5 round 2c (deliverable 5, rule 5): `offer_quick_full` --
    # set only by `run_init_wizard()` for a genuine fresh `halo init` with
    # no `--step` (never by a truncated `/setup`/`halo setup` entry,
    # which starts mid-flow on purpose and has no use for this gate) --
    # tells `InitWizardApp.on_mount` to push `setup_mode.SetupModeStep`
    # FIRST instead of the real step 1. `quick_setup`: which the owner
    # picked there, read back by the Summary step to say so (rule 5:
    # "the Summary says what it chose").
    offer_quick_full: bool = False
    quick_setup: bool = False

    # Halo 2.0.4 round 4 (deliverable 1): the merged model list from ONE
    # live, off-thread enumeration run right after the Providers step's
    # own Next (`ProvidersStep._run_enumeration_then_advance`) -- the
    # SAME shape `Controller.list_models()` returns (`providers.
    # model_enumeration.build_model_rows`), cached here for the rest of
    # THIS wizard run and reused by the roles step, the org step and the
    # summary, so a standalone `halo init` (no live Controller/session of
    # its own at all) still has a real, grouped, gym-scored model list to
    # show -- fixing the owner's own report ("the available models are
    # not listed when you select edit a role"), which traced to exactly
    # that: the Roles step's own `_controller_models` (now `team_step.
    # TeamStep`'s) reading `self.app.controller`,
    # always `None` on the standalone wizard app. `enumeration_done`
    # distinguishes "ran, found nothing" (still prefer this -- possibly
    # empty -- list) from "never ran this wizard run yet" (fall back to
    # the live `Controller.list_models()` when one is hosting this
    # screen, e.g. `/setup roles` with no Providers step in its own
    # truncated `step_keys`). `enumeration_lines`: one "<label>: <status>"
    # string per provider, in finish order, for the Summary step.
    enumerated_models: list = field(default_factory=list)
    enumeration_done: bool = False
    enumeration_lines: list = field(default_factory=list)

    def title(self) -> str:
        key = self.step_keys[self.index]
        return f"Step {self.index + 1} of {len(self.step_keys)}: {STEP_TITLES[key]}"


def linux_fixes_needed() -> bool:
    """Whether the Linux-fixes step has anything to offer right now --
    the SAME two checks `init_cli.py::_step_linux_fixes` itself makes,
    pure (no console I/O) so the wizard can decide whether to include
    this step in `step_keys` at all before anything is ever drawn."""
    if sys.platform == "win32":
        return False
    if not shutil.which("rg"):
        return True
    from halo_harness.linux_fixes import local_bin_on_noninteractive_path
    return not local_bin_on_noninteractive_path()


def full_step_keys() -> tuple:
    keys = list(ALL_STEP_KEYS)
    if not linux_fixes_needed():
        keys.remove("linux_fixes")
    return tuple(keys)


STEP_FACTORIES: dict = {}  # name -> callable(state) -> Screen, filled once every class below exists


def _build_step(state: WizardState, key: str) -> Screen:
    return STEP_FACTORIES[key](state)


def advance(app, state: WizardState, *, skip: bool = False) -> None:
    """Next/Skip -- both move forward; a step's own `commit()` (called by
    `StepScreen.action_do_next` BEFORE this, never by Skip) is what
    actually applies a choice, so `skip=True` reaching here with nothing
    committed is exactly "leave config untouched"."""
    if state.index + 1 >= len(state.step_keys):
        finish(app, state)
        return
    state.index += 1
    screen = _build_step(state, state.step_keys[state.index])
    state.pushed += 1
    app.push_screen(screen)


def go_back(app, state: WizardState) -> None:
    if state.index <= 0:
        return
    state.index -= 1
    state.pushed -= 1
    app.pop_screen()


def finish(app, state: WizardState) -> None:
    for _ in range(state.pushed):
        app.pop_screen()
    state.pushed = 0
    if state.on_finish is not None:
        state.on_finish(app)


class _QuitConfirm(ModalScreen):
    """Esc on any step: "Quit setup? What you saved so far stays." --
    "so far" is literal: every step only persists from inside `commit()`,
    called on Next, so whatever earlier steps already committed survives
    a quit here untouched."""
    BINDINGS = [Binding("escape", "no", "No", show=False), Binding("n", "no", "No", show=False),
                Binding("y", "yes", "Yes", show=False)]
    DEFAULT_CSS = """
    _QuitConfirm { align: center middle; }
    _QuitConfirm > Vertical { width: 64; height: auto; border: round $primary; background: $surface; padding: 1 2; }
    _QuitConfirm Horizontal { height: 3; align: right middle; margin-top: 1; }
    _QuitConfirm Button { margin-left: 1; }
    """

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static("Quit setup? What you saved so far stays. [y/N]", classes="dialog-title")
            with Horizontal():
                yield Button("No", id="confirm-no")
                yield Button("Yes, quit", id="confirm-yes", variant="error")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "confirm-yes")

    def action_yes(self) -> None:
        self.dismiss(True)

    def action_no(self) -> None:
        self.dismiss(False)


class _EnumeratingScreen(ModalScreen):
    """Halo 2.0.4 round 4 (deliverable 1): shown the moment Next leaves
    the Providers step -- one line per provider, appended as each one's
    own live probe answers (`ProvidersStep._enumeration_worker`'s
    `progress_cb`, via `call_from_thread`), never blocking the UI thread
    itself (the probing runs in `providers.model_enumeration.
    enumerate_live`'s own background threads). No bindings of its own:
    this is a brief, non-interactive wait, not a dialog the user drives --
    it pops itself once every provider has answered or the shared
    deadline passes, whichever comes first (see that function's own
    bounded-timeout docstring)."""
    DEFAULT_CSS = """
    _EnumeratingScreen { align: center middle; }
    _EnumeratingScreen > Vertical { width: 70%; height: auto; max-height: 80%; border: round $primary;
                                     background: $surface; padding: 1 2; }
    _EnumeratingScreen #wiz-enum-lines { height: auto; max-height: 20; margin-top: 1; }
    """

    def __init__(self) -> None:
        super().__init__()
        self._lines: list = []

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static("Checking which models you can reach, with the keys just entered...",
                         classes="dialog-title")
            yield Static("", id="wiz-enum-lines")

    def append_line(self, text: str) -> None:
        self._lines.append(text)
        try:
            self.query_one("#wiz-enum-lines", Static).update("\n".join(self._lines))
        except Exception:
            pass


class StepScreen(StepRailMixin, Screen):
    """Shared chrome every wizard step uses: a "Step N of M" header, the
    step rail (rule 4), the step's own `body()` widgets, and a Back/Skip/
    Next(/Finish) footer. Concrete steps override `body()` (what to show)
    and `commit()` (what Next actually applies) -- navigation and Esc-to-
    quit live here once. Round 2c: Ctrl+Left/Ctrl+Right (`StepRailMixin`,
    spliced in from `STEP_RAIL_BINDINGS` -- see that constant's own
    comment for why a mixin's `BINDINGS` alone would never actually
    bind) replace the old Ctrl+N/Ctrl+B -- freed for rule 9's "new/
    duplicate/delete" everywhere (`team_step.py`'s own module docstring)."""
    BINDINGS = [Binding("escape", "ask_quit", "Quit setup", show=False, priority=True), *STEP_RAIL_BINDINGS]
    DEFAULT_CSS = """
    StepScreen { align: center middle; }
    StepScreen > Vertical { width: 94%; height: 92%; border: round $primary; padding: 1 2; background: $surface; }
    .wizard-header { color: $text-muted; margin-bottom: 1; }
    .wizard-rail { margin-bottom: 1; }
    .wizard-footer { height: 3; align: right middle; margin-top: 1; }
    .wizard-footer Button { margin-left: 1; }
    """

    def __init__(self, state: WizardState) -> None:
        super().__init__()
        self.state = state

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static(self.state.title(), classes="wizard-header")
            yield Static(self.rail_text(self.state.step_keys, self.state.index, STEP_TITLES),
                         classes="wizard-rail", id="wizard-rail")
            for widget in self.body():
                yield widget
            with Horizontal(classes="wizard-footer"):
                yield Button("Back", id="wiz-back", disabled=self.state.index == 0)
                yield Button("Skip", id="wiz-skip")
                last = self.state.index + 1 >= len(self.state.step_keys)
                yield Button("Finish" if last else "Next", id="wiz-next", variant="primary")

    def body(self) -> list:
        return []

    def commit(self) -> None:
        """Override: apply/persist this step's own choice. Called by
        `action_do_next` only -- never by Skip or Back."""
        return None

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id or ""
        if bid == "wiz-back":
            self.action_do_back()
        elif bid == "wiz-skip":
            self.action_do_skip()
        elif bid == "wiz-next":
            self.action_do_next()

    def action_do_next(self) -> None:
        self.commit()
        advance(self.app, self.state)

    def action_do_skip(self) -> None:
        advance(self.app, self.state, skip=True)

    def action_do_back(self) -> None:
        go_back(self.app, self.state)

    def action_ask_quit(self) -> None:
        def _after(confirmed: "Optional[bool]") -> None:
            if confirmed:
                finish(self.app, self.state)
        self.app.push_screen(_QuitConfirm(), _after)


# ---------------------------------------------------------------------------
# Step: Providers -- see this module's own docstring for why this
# deliberately duplicates (rather than subclasses) `init_tabs.InitTabsApp`.
# ---------------------------------------------------------------------------

def _pv_pane_id(provider: str) -> str:
    return f"wiz-pane-{provider}"


def _pv_status_text(provider: str, *, state: Optional[dict] = None) -> str:
    state = state if state is not None else tab_credential_state(provider)
    if state["configured"]:
        return f"picked up from {state['source']}: {state['masked']}"
    if state.get("known_host"):
        return f"host picked up from {state['source']}: {state['known_host']} -- token still needed"
    return "not set up"


class ProvidersStep(StepScreen):
    BINDINGS = [
        Binding("shift+tab", "prev_tab", "Previous provider", priority=True, show=False),
        Binding("up", "focus_prev_field", "Up", show=False),
        Binding("down", "focus_next_field", "Down", show=False),
    ]
    DEFAULT_CSS = """
    ProvidersStep .tab-status { margin-top: 1; color: $text-muted; }
    ProvidersStep .tab-reach { margin-top: 1; }
    ProvidersStep .tab-help { margin-top: 1; color: $text-muted; }
    ProvidersStep Input { margin-top: 1; }
    ProvidersStep TabPane Button { margin-top: 1; }
    """

    def __init__(self, state: WizardState) -> None:
        super().__init__(state)
        self._team_cfg, self._team_cfg_pending = self._load_team_cfg_fast()
        self._state_cache: "dict[str, dict]" = {
            p: tab_credential_state(p, team_cfg=self._team_cfg) for p in TAB_PROVIDERS
            if p not in ("claude", "codex")
        }
        self._state_cache["claude"] = {"configured": False, "source": None, "masked": None,
                                        "known_host": None, "fields": []}
        self._state_cache["codex"] = {"configured": False, "source": None, "masked": None,
                                        "known_host": None, "fields": []}

    def _load_team_cfg_fast(self):
        from halo_harness.team_config import load_team_config, team_config_path
        try:
            source = team_config_path(self.state.cwd, team_flag=self.state.team)
        except Exception:
            return None, False
        if source and (source.startswith("http://") or source.startswith("https://")):
            return None, True
        cfg, warnings = load_team_config(self.state.cwd, team_flag=self.state.team)
        self.state.team_warnings.extend(warnings)
        return cfg, False

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static(self.state.title(), classes="wizard-header")
            yield Static("Set up providers below, then Next.", classes="dialog-title")
            with TabbedContent(initial=_pv_pane_id(TAB_PROVIDERS[0])):
                for provider in TAB_PROVIDERS:
                    with TabPane(TAB_LABEL[provider], id=_pv_pane_id(provider)):
                        yield from self._tab_widgets(provider)
            with Horizontal(classes="wizard-footer"):
                yield Button("Back", id="wiz-back", disabled=self.state.index == 0)
                yield Button("Skip", id="wiz-skip")
                last = self.state.index + 1 >= len(self.state.step_keys)
                yield Button("Finish" if last else "Next", id="wiz-next", variant="primary")

    def _tab_widgets(self, provider: str):
        state = self._state_cache[provider]
        if provider in ("ollama", "huggingface"):
            # Round 5b part 2 (brief item 5, "the wizard detects before
            # it asks"): opens with a placeholder; `on_mount`'s own
            # worker (off the UI thread, short-timeout probes only --
            # see `providers.local_models.detection_summary_lines`'s own
            # docstring) fills it in later. A slow/never-finishing probe
            # just leaves this line as-is -- the tab is fully usable
            # (every field/button below renders immediately) either way.
            yield Static("detecting what's already on this machine…", id=f"wiz-{provider}-detect",
                        classes="tab-help")
        status_text = "checking…" if provider in ("claude", "codex") else _pv_status_text(provider, state=state)
        yield Static(status_text, id=f"wiz-{provider}-status", classes="tab-status")
        for f in state["fields"]:
            prefill = state.get("known_host") or "" if f["name"] == "host" else ""
            yield Input(value=prefill, placeholder=f["label"], password=f["secret"],
                        id=f"wiz-{provider}-field-{f['name']}")
        if provider == "claude":
            yield Static("Uses your existing `claude` login as-is -- nothing is stored here.", classes="tab-help")
        if provider == "codex":
            yield Static("Uses your existing `codex` ChatGPT login as-is -- nothing is stored here; an "
                         "API-key login belongs on the OpenAI API (key) tab instead.", classes="tab-help")
        if provider == "settings_sources":
            yield Static("What halo found in Claude Code's and Codex's own settings/instruction files, "
                         "merged into one view (`/settings`, `halo doctor`). Pick which one wins when they "
                         "disagree and halo's own config doesn't already decide it.", classes="tab-help")
        if provider == "ollama":
            yield Static("Leave every field blank and Save to register the local daemon at its default "
                         "address; fill in a URL to add a LAN or cloud host instead. Running local servers "
                         "are found automatically by /local, not here.", classes="tab-help")
        if provider == "huggingface":
            yield Static("Each of these is independent and optional: paste HF_TOKEN for the router, add one "
                         "dedicated endpoint (name + URL [+ token]), or add one local server (URL [+ key]). "
                         "A local server on a default port (llama.cpp, vLLM, LM Studio, ...) is found "
                         "automatically by /local with none of this.", classes="tab-help")
        if provider == "openai":
            yield Static("Paste OPENAI_API_KEY to use the real OpenAI API directly (oai: models) -- "
                         "separate from a Codex subscription login.", classes="tab-help")
        if provider == "typesafe":
            yield Static("Stores TYPESAFE_API_KEY only -- for a later feature, no routed models yet.",
                         classes="tab-help")
        if provider == "experiential":
            yield Static("Paste EXPLABS_API_KEY (the inference key, prefix xpl_) to use the Experiential "
                         "Labs gateway (xp: models) -- its catalog, credits balance and model prices come "
                         "from this same key; the separate provisioning key is never asked for here.",
                         classes="tab-help")
        label = "Check login" if provider in ("claude", "codex") else "Save"
        yield Button(label, id=f"wiz-{provider}-save", variant="primary")
        reach = "reachability: skipped (--no-live)" if self.state.no_live else "reachability: checking…"
        yield Static(reach, id=f"wiz-{provider}-reach", classes="tab-reach")

    def on_mount(self) -> None:
        if self._team_cfg_pending:
            self.run_worker(self._team_cfg_worker, thread=True, name="wiz-init-team-config")
        self.run_worker(self._claude_state_worker, thread=True, name="wiz-init-tab-claude-state")
        self.run_worker(self._codex_state_worker, thread=True, name="wiz-init-tab-codex-state")
        if self.state.no_live:
            return
        for provider in TAB_PROVIDERS:
            if provider not in ("claude", "codex") and self._state_cache[provider]["configured"]:
                self.run_worker(lambda p=provider: self._probe_worker(p), thread=True, name=f"wiz-init-probe-{provider}")
        if "ollama" in TAB_PROVIDERS or "huggingface" in TAB_PROVIDERS:
            self.run_worker(self._detect_local_worker, thread=True, name="wiz-init-detect-local")

    def _detect_local_worker(self) -> None:
        from halo_harness.providers.local_models import detection_summary_lines
        try:
            lines = detection_summary_lines()
        except Exception:
            lines = []
        text = "\n".join(lines) if lines else "nothing detected on this machine yet (no Ollama daemon, no " \
                                               "local server, no cached model files)."
        self.app.call_from_thread(self._apply_detect_text, text)

    def _apply_detect_text(self, text: str) -> None:
        for provider in ("ollama", "huggingface"):
            try:
                self.query_one(f"#wiz-{provider}-detect", Static).update(text)
            except Exception:
                pass

    def _team_cfg_worker(self) -> None:
        from halo_harness.team_config import load_team_config
        cfg, warnings = load_team_config(self.state.cwd, team_flag=self.state.team)
        self.app.call_from_thread(self._apply_team_cfg, cfg, warnings)

    def _apply_team_cfg(self, cfg, warnings: list) -> None:
        self._team_cfg = cfg
        self.state.team_warnings.extend(warnings)
        if not cfg or "databricks" in self.state.configured_this_run:
            return
        state = tab_credential_state("databricks", team_cfg=self._team_cfg)
        self._state_cache["databricks"] = state
        if state["configured"] or not state.get("known_host"):
            return
        try:
            self.query_one("#wiz-databricks-status", Static).update(_pv_status_text("databricks", state=state))
            host_input = self.query_one("#wiz-databricks-field-host", Input)
            if not host_input.value:
                host_input.value = state["known_host"]
        except Exception:
            pass

    def _claude_state_worker(self) -> None:
        from halo_harness.providers.cc_models import refresh_cached_claude_auth_status
        refresh_cached_claude_auth_status()
        state = tab_credential_state("claude", team_cfg=self._team_cfg)
        from halo_harness.providers.reachability import reachability_tag
        reach_text = f"reachability: {reachability_tag('claude', detected=state['configured'])}"
        self.app.call_from_thread(self._apply_claude_state, state, reach_text)

    def _apply_claude_state(self, state: dict, reach_text: str) -> None:
        self._state_cache["claude"] = state
        try:
            self.query_one("#wiz-claude-status", Static).update(_pv_status_text("claude", state=state))
        except Exception:
            pass
        if not self.state.no_live:
            try:
                self.query_one("#wiz-claude-reach", Static).update(reach_text)
            except Exception:
                pass

    def _codex_state_worker(self) -> None:
        """The `codex` tab's own counterpart of `_claude_state_worker` --
        same reasoning, substituting `codex_models`."""
        from halo_harness.providers.codex_models import refresh_cached_codex_auth_status
        refresh_cached_codex_auth_status()
        state = tab_credential_state("codex", team_cfg=self._team_cfg)
        from halo_harness.providers.reachability import reachability_tag
        reach_text = f"reachability: {reachability_tag('codex', detected=state['configured'])}"
        self.app.call_from_thread(self._apply_codex_state, state, reach_text)

    def _apply_codex_state(self, state: dict, reach_text: str) -> None:
        self._state_cache["codex"] = state
        try:
            self.query_one("#wiz-codex-status", Static).update(_pv_status_text("codex", state=state))
        except Exception:
            pass
        if not self.state.no_live:
            try:
                self.query_one("#wiz-codex-reach", Static).update(reach_text)
            except Exception:
                pass

    def action_prev_tab(self) -> None:
        tabs = self.query_one(TabbedContent)
        tab_ids = [_pv_pane_id(p) for p in TAB_PROVIDERS]
        try:
            idx = tab_ids.index(tabs.active)
        except ValueError:
            idx = 0
        tabs.active = tab_ids[(idx - 1) % len(tab_ids)]

    def action_focus_prev_field(self) -> None:
        self.focus_previous()

    def action_focus_next_field(self) -> None:
        self.focus_next()

    def on_input_changed(self, event: Input.Changed) -> None:
        field_id = event.input.id or ""
        if "-field-" not in field_id:
            return
        provider = field_id[len("wiz-"):].split("-field-", 1)[0]
        state = self._state_cache[provider]
        if state["configured"]:
            return
        try:
            status = self.query_one(f"#wiz-{provider}-status", Static)
        except Exception:
            return
        any_value = any((self._field_value(provider, f["name"]) or "").strip() for f in state["fields"])
        status.update("value entered -- Enter (or Save) stores it" if any_value
                      else _pv_status_text(provider, state=state))

    def _field_value(self, provider: str, name: str) -> str:
        try:
            return self.query_one(f"#wiz-{provider}-field-{name}", Input).value
        except Exception:
            return ""

    def on_input_submitted(self, event: Input.Submitted) -> None:
        field_id = event.input.id or ""
        if "-field-" in field_id:
            self._save(field_id[len("wiz-"):].split("-field-", 1)[0])

    def on_button_pressed(self, event: Button.Pressed) -> None:
        # Textual invokes EVERY `on_button_pressed` found across the whole
        # class hierarchy, not just the most-derived one (`MessagePump.
        # _on_message`'s own `_get_dispatch_methods`) -- `StepScreen.
        # on_button_pressed` ALREADY handles wiz-back/skip/next on its
        # own, independently of this override, so repeating any of those
        # three ids here would fire `action_do_next`/etc. TWICE per
        # press. This handler must only ever recognize ids `StepScreen`
        # does not already know about.
        bid = event.button.id or ""
        if bid.endswith("-save"):
            self._save(bid[len("wiz-"):-len("-save")])

    def _collect_values(self, provider: str) -> dict:
        state = self._state_cache[provider]
        return {f["name"]: self._field_value(provider, f["name"]) for f in state["fields"]}

    def _save(self, provider: str) -> None:
        if provider == "claude":
            self.run_worker(self._save_claude_worker, thread=True, name="wiz-save-claude")
            return
        if provider == "codex":
            self.run_worker(self._save_codex_worker, thread=True, name="wiz-save-codex")
            return
        from halo_harness.init_providers import save_tab_credentials
        values = self._collect_values(provider)
        ok, message = save_tab_credentials(provider, values, team_cfg=self._team_cfg)
        try:
            status = self.query_one(f"#wiz-{provider}-status", Static)
        except Exception:
            return
        if not ok:
            status.update(f"not set up ({message})")
            return
        from halo_harness.providers.enablement import enable_if_was_explicitly_disabled
        enable_if_was_explicitly_disabled(provider)
        if provider not in self.state.configured_this_run:
            self.state.configured_this_run.append(provider)
        state = tab_credential_state(provider, team_cfg=self._team_cfg)
        self._state_cache[provider] = state
        status.update(_pv_status_text(provider, state=state))
        if self.state.no_live:
            try:
                self.query_one(f"#wiz-{provider}-reach", Static).update("reachability: skipped (--no-live)")
            except Exception:
                pass
            return
        try:
            self.query_one(f"#wiz-{provider}-reach", Static).update("reachability: checking…")
        except Exception:
            pass
        self.run_worker(lambda: self._finish_tab_worker(provider), thread=True, name=f"wiz-finish-tab-{provider}")

    def _save_claude_worker(self) -> None:
        from halo_harness.providers.cc_models import refresh_cached_claude_auth_status
        from halo_harness.init_providers import save_tab_credentials, tab_credential_state
        refresh_cached_claude_auth_status()
        ok, message = save_tab_credentials("claude", {}, team_cfg=self._team_cfg)
        state = tab_credential_state("claude", team_cfg=self._team_cfg) if ok else None
        self.app.call_from_thread(self._apply_claude_save, ok, message, state)

    def _apply_claude_save(self, ok: bool, message: str, state: Optional[dict]) -> None:
        try:
            status = self.query_one("#wiz-claude-status", Static)
        except Exception:
            return
        if not ok:
            status.update(f"not set up ({message})")
            return
        from halo_harness.providers.enablement import enable_if_was_explicitly_disabled
        enable_if_was_explicitly_disabled("claude")
        if "claude" not in self.state.configured_this_run:
            self.state.configured_this_run.append("claude")
        self._state_cache["claude"] = state
        status.update(_pv_status_text("claude", state=state))
        if self.state.no_live:
            try:
                self.query_one("#wiz-claude-reach", Static).update("reachability: skipped (--no-live)")
            except Exception:
                pass
            return
        try:
            self.query_one("#wiz-claude-reach", Static).update("reachability: checking…")
        except Exception:
            pass
        self.run_worker(lambda: self._finish_tab_worker("claude"), thread=True, name="wiz-finish-tab-claude")

    def _save_codex_worker(self) -> None:
        """The `codex` tab's own counterpart of `_save_claude_worker` --
        same reasoning, substituting `codex_models`."""
        from halo_harness.providers.codex_models import refresh_cached_codex_auth_status
        from halo_harness.init_providers import save_tab_credentials, tab_credential_state
        refresh_cached_codex_auth_status()
        ok, message = save_tab_credentials("codex", {}, team_cfg=self._team_cfg)
        state = tab_credential_state("codex", team_cfg=self._team_cfg) if ok else None
        self.app.call_from_thread(self._apply_codex_save, ok, message, state)

    def _apply_codex_save(self, ok: bool, message: str, state: Optional[dict]) -> None:
        try:
            status = self.query_one("#wiz-codex-status", Static)
        except Exception:
            return
        if not ok:
            status.update(f"not set up ({message})")
            return
        from halo_harness.providers.enablement import enable_if_was_explicitly_disabled
        enable_if_was_explicitly_disabled("codex")
        if "codex" not in self.state.configured_this_run:
            self.state.configured_this_run.append("codex")
        self._state_cache["codex"] = state
        status.update(_pv_status_text("codex", state=state))
        if self.state.no_live:
            try:
                self.query_one("#wiz-codex-reach", Static).update("reachability: skipped (--no-live)")
            except Exception:
                pass
            return
        try:
            self.query_one("#wiz-codex-reach", Static).update("reachability: checking…")
        except Exception:
            pass
        self.run_worker(lambda: self._finish_tab_worker("codex"), thread=True, name="wiz-finish-tab-codex")

    def _probe_worker(self, provider: str) -> None:
        from halo_harness.providers.reachability import reachability_tag
        tag = reachability_tag(provider)
        self.app.call_from_thread(self._apply_reach, provider, tag)

    def _finish_tab_worker(self, provider: str) -> None:
        from halo_harness.init_providers import refresh_tab_catalog
        from halo_harness.providers.reachability import reachability_tag
        tag = reachability_tag(provider)
        self.app.call_from_thread(self._apply_reach, provider, tag)
        _ok, note = refresh_tab_catalog(provider)
        if note:
            self.state.catalog_notes[provider] = note

    def _apply_reach(self, provider: str, tag: str) -> None:
        try:
            self.query_one(f"#wiz-{provider}-reach", Static).update(f"reachability: {tag}")
        except Exception:
            pass

    # Halo 2.0.4 round 4 (deliverable 1, owner report 2026-10-05: "an enum
    # of what models you can reach should occur after you set the keys"):
    # Next leaving this step runs ONE live, off-thread enumeration of
    # every provider `/model` knows, with the credentials just typed into
    # every tab (saved via that tab's own Save press, or not) merged over
    # the saved config -- cached on `self.state` for the rest of this
    # wizard run (`WizardState.enumerated_models`'s own docstring) and
    # reused by the Roles step, the Orgs step and the Summary step. Skip
    # (inherited `action_do_skip`, untouched) never enumerates.
    def action_do_next(self) -> None:
        self.commit()
        if self.state.no_live:
            # `--no-live` already skips every OTHER live probe on this
            # step ("reachability: skipped (--no-live)") -- the
            # enumeration's own cache-only `build_model_rows` read still
            # runs (no network of its own, same contract `DefaultModelStep`
            # already follows regardless of `no_live`), just with no live
            # refresh first, so the roles/org steps still see whatever is
            # already cached on disk instead of staying permanently empty
            # under `--no-live`.
            from halo_harness.config.paths import bridge_home
            from halo_harness.providers.model_enumeration import build_model_rows
            try:
                self.state.enumerated_models = build_model_rows(bridge_home(), env=self._collect_env_overlay())
            except Exception:
                self.state.enumerated_models = []
            self.state.enumeration_done = True
            advance(self.app, self.state)
            return
        overlay = self._collect_env_overlay()
        screen = _EnumeratingScreen()
        self.app.push_screen(screen)
        self.run_worker(lambda: self._enumeration_worker(overlay, screen), thread=True,
                         name="wiz-enumerate-models", group="wiz-enumerate-models")

    def _collect_env_overlay(self) -> dict:
        """`dict(os.environ)` plus whatever's CURRENTLY TYPED (saved via
        that tab's own Save press, or not) into every single-key provider
        tab's own field, plus Databricks' host+token and Hugging Face's
        router token -- never written to disk, never assigned to `os.
        environ` itself (an already-SAVED value is in `os.environ`
        already, via `save_tab_credentials`; this only adds what a Save
        press hasn't reached yet). Ollama's own "add a host" fields are
        deliberately NOT covered here -- unlike every other tab, Ollama
        persists each host to `ollama.hosts` immediately on its own Save
        press, so `providers.local_models.build_local_view` already sees
        it with no overlay needed; a host typed but never saved at all is
        the one gap this leaves (documented, not a silent miss)."""
        import os
        from halo_harness.init_providers import _TAB_KEY_ENV
        overlay = dict(os.environ)
        for provider, key_env in _TAB_KEY_ENV.items():
            value = (self._collect_values(provider).get("key") or "").strip()
            if value:
                overlay[key_env] = value
        dbx = self._collect_values("databricks")
        if (dbx.get("host") or "").strip():
            overlay["DATABRICKS_HOST"] = dbx["host"].strip()
        if (dbx.get("token") or "").strip():
            overlay["DATABRICKS_TOKEN"] = dbx["token"].strip()
        hf_token = (self._collect_values("huggingface").get("token") or "").strip()
        if hf_token:
            overlay["HF_TOKEN"] = hf_token
        return overlay

    def _enumeration_worker(self, overlay: dict, screen: "_EnumeratingScreen") -> None:
        from halo_harness.config.paths import bridge_home
        from halo_harness.providers.model_enumeration import enumerate_live

        def _progress(label: str, status: str) -> None:
            line = f"{label}: {status}"
            self.state.enumeration_lines.append(line)
            self.app.call_from_thread(screen.append_line, line)

        try:
            rows = enumerate_live(bridge_home(), env=overlay, progress_cb=_progress)
        except Exception as e:
            rows = []
            _progress("enumeration", f"failed ({type(e).__name__})")
        self.app.call_from_thread(self._finish_enumeration, rows)

    def _finish_enumeration(self, rows: list) -> None:
        self.state.enumerated_models = rows
        self.state.enumeration_done = True
        self.app.pop_screen()  # the _EnumeratingScreen pushed by action_do_next
        advance(self.app, self.state)


STEP_FACTORIES["providers"] = ProvidersStep


# ---------------------------------------------------------------------------
# Step: Local models -- Halo 2.0.3 round 5c (brief item 1): "the wizard
# gets a 'Local models' step (detects Ollama and running servers, scans
# the default caches, offers 'add a folder', and asks which runtime to
# prefer for files that are not served yet)". The detection summary reuses
# `providers.local_models.detection_summary_lines` verbatim (round 5b part
# 2's own text, already covering Ollama/running-servers/caches) -- this
# step adds ONLY the two things that summary can't do by itself: adding a
# `huggingface.model_dirs` folder, and the preferred-runtime choice.
# ---------------------------------------------------------------------------

class LocalModelsStep(StepScreen):
    DEFAULT_CSS = """
    LocalModelsStep #wiz-local-detect { margin-top: 1; color: $text-muted; }
    LocalModelsStep #wiz-local-dirs { margin-top: 1; }
    LocalModelsStep #wiz-local-runtime-status { margin-top: 1; color: $text-muted; }
    LocalModelsStep .wizard-extra-buttons { height: 3; margin-top: 1; }
    LocalModelsStep .wizard-extra-buttons Button { margin-right: 1; }
    """

    def _dirs_text(self) -> str:
        from halo_harness.providers.local_model_dirs import resolve_model_dirs
        dirs = resolve_model_dirs()
        return ("Folders scanned for .gguf/safetensors/MLX models: " + ", ".join(str(d) for d in dirs)) if dirs \
            else "No folders added yet (huggingface.model_dirs is empty)."

    def _runtime_status_text(self) -> str:
        from halo_harness.theme import get_config_value
        preferred = get_config_value("huggingface.preferred_runtime", default=None)
        return f"Preferred runtime: {preferred}" if preferred else "Preferred runtime: not set (Halo picks " \
            "llama-server for GGUF, mlx_lm for safetensors on Apple Silicon, either way)."

    def body(self) -> list:
        return [
            Static("Folders Halo scans for .gguf files and safetensors/MLX model folders, on top of the "
                   "Hugging Face Hub cache, LM Studio's own folder, and Ollama's own store.",
                   classes="dialog-title"),
            Static("detecting what's already on this machine…", id="wiz-local-detect", classes="tab-help"),
            Static(self._dirs_text(), id="wiz-local-dirs"),
            Input(placeholder="/path/to/a/models/folder", id="wiz-local-folder-input"),
            Button("Add folder", id="wiz-local-folder-add"),
            Static("Preferred runtime for a file `halo local serve` isn't told --runtime for explicitly:",
                   classes="tab-help"),
            Horizontal(Button("llama-server (GGUF)", id="wiz-local-runtime-llama"),
                       Button("mlx_lm (Apple Silicon)", id="wiz-local-runtime-mlx"),
                       classes="wizard-extra-buttons"),
            Static(self._runtime_status_text(), id="wiz-local-runtime-status"),
        ]

    def on_mount(self) -> None:
        self.run_worker(self._detect_worker, thread=True, name="wiz-local-detect")

    def _detect_worker(self) -> None:
        from halo_harness.providers.local_models import detection_summary_lines
        try:
            lines = detection_summary_lines()
        except Exception:
            lines = []
        text = "\n".join(lines) if lines else "nothing detected on this machine yet (no Ollama daemon, no " \
                                               "local server, no cached model files)."
        self.app.call_from_thread(self._apply_detect_text, text)

    def _apply_detect_text(self, text: str) -> None:
        try:
            self.query_one("#wiz-local-detect", Static).update(text)
        except Exception:
            pass

    def on_button_pressed(self, event: Button.Pressed) -> None:
        # See ProvidersStep.on_button_pressed's own comment -- must never
        # re-handle wiz-back/skip/next (StepScreen already does).
        bid = event.button.id or ""
        if bid == "wiz-local-folder-add":
            self._add_folder()
        elif bid == "wiz-local-runtime-llama":
            self._set_preferred_runtime("llama-server")
        elif bid == "wiz-local-runtime-mlx":
            self._set_preferred_runtime("mlx_lm")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "wiz-local-folder-input":
            self._add_folder()

    def _add_folder(self) -> None:
        from halo_harness.providers.local_model_dirs import add_model_dir
        try:
            field = self.query_one("#wiz-local-folder-input", Input)
            dirs_static = self.query_one("#wiz-local-dirs", Static)
        except Exception:
            return
        path = field.value.strip()
        if not path:
            return
        ok, message = add_model_dir(path)
        if ok:
            field.value = ""
        dirs_static.update(self._dirs_text() + f"\n({message})")

    def _set_preferred_runtime(self, runtime: str) -> None:
        from halo_harness.theme import set_config_value
        set_config_value("huggingface.preferred_runtime", runtime)
        try:
            self.query_one("#wiz-local-runtime-status", Static).update(self._runtime_status_text())
        except Exception:
            pass


STEP_FACTORIES["local_models"] = LocalModelsStep


# ---------------------------------------------------------------------------
# Step: Default model -- "the picker the console step used, now a list in
# the wizard" (brief item 1). Entries span EVERY currently-configured
# provider (`init_providers.configured_providers`), read fresh each time
# this step is built -- it always reflects whatever the Providers step
# just did, with no separate per-provider bookkeeping needed.
# ---------------------------------------------------------------------------

class DefaultModelStep(StepScreen):
    DEFAULT_CSS = "DefaultModelStep OptionList { height: 1fr; margin-top: 1; }"

    def __init__(self, state: WizardState) -> None:
        super().__init__(state)
        self._entries: "list[dict]" = []

    def body(self) -> list:
        from halo_harness.config.paths import bridge_home
        from halo_harness.init_providers import configured_providers, model_entries_for_provider
        from halo_harness.model_display import ROW_HEADER
        from textual.widgets import OptionList

        state_dir = bridge_home()
        entries: "list[dict]" = []
        for provider in configured_providers():
            for e in model_entries_for_provider(provider, state_dir):
                entries.append({**e, "group": e.get("group") or provider})
        self._entries = entries
        from halo_harness.theme import get_config_value
        current = get_config_value("model", default=None)
        widgets = [Static(one_sentence("Default model", current if isinstance(current, str) else None,
                                        hint="Highlight one below, Enter to change."),
                           id="wiz-default-model-sentence", classes="dialog-title"),
                   Static("Pick a default model across every configured provider -- Next keeps the "
                          "current default if you don't pick one.", classes="dialog-subtitle")]
        if not entries:
            widgets.append(Static("No model catalog is cached yet -- Next keeps the current default.",
                                   classes="tab-help"))
            return widgets
        widgets += [Static(ROW_HEADER, classes="dialog-subtitle"), OptionList(id="wiz-model-list")]
        return widgets

    def on_mount(self) -> None:
        from rich.text import Text
        from textual.widgets import OptionList
        from textual.widgets.option_list import Option
        from halo_harness.model_display import format_model_row
        from halo_harness.tui.dialogs.model_picker import _grouped
        from halo_harness.theme import get_config_value
        try:
            option_list = self.query_one("#wiz-model-list", OptionList)
        except Exception:
            return
        current = get_config_value("model", default=None)
        current_index, pos = None, 0
        for group, members in _grouped(self._entries):
            if group:
                option_list.add_option(Option(Text(f"── {group} ──", style="bold dim"), disabled=True))
                pos += 1
            for e in members:
                option_list.add_option(Option(Text(format_model_row(e), no_wrap=True, overflow="ellipsis"),
                                               id=e["ref"]))
                if current_index is None and isinstance(current, str) and e["ref"] == current:
                    current_index = pos
                pos += 1
        # Finding 1 fixpass (critical): highlight the EXISTING default, never
        # just the first catalog row -- Next with no interaction then writes
        # the same value back (a no-op) instead of silently overwriting it
        # on a re-run of init. No match (fresh install, or a default from a
        # provider not configured this run) leaves nothing highlighted;
        # commit() below keeps the literal current value untouched.
        if current_index is not None:
            option_list.highlighted = current_index
            mark_checked(option_list, option_list.get_option_at_index(current_index).id)
        focus_first(self, ["#wiz-model-list"])

    def on_option_list_option_highlighted(self, event) -> None:
        if event.option_list.id == "wiz-model-list" and event.option_id:
            mark_checked(event.option_list, event.option_id)

    def commit(self) -> None:
        from halo_harness.theme import get_config_value, set_config_value
        from textual.widgets import OptionList
        chosen = None
        try:
            option_list = self.query_one("#wiz-model-list", OptionList)
            if option_list.highlighted is not None:
                opt = option_list.get_option_at_index(option_list.highlighted)
                chosen = str(opt.id) if opt.id else None
        except Exception:
            chosen = None
        if chosen:
            set_config_value("model", chosen)
            self.state.final_model = chosen
        else:
            current = get_config_value("model", default=None)
            self.state.final_model = current if isinstance(current, str) else ""


STEP_FACTORIES["default_model"] = DefaultModelStep


# ---------------------------------------------------------------------------
# Step: Permission mode.
# ---------------------------------------------------------------------------

class PermissionModeStep(StepScreen):
    DEFAULT_CSS = "PermissionModeStep OptionList { height: 1fr; margin-top: 1; }"

    def body(self) -> list:
        from textual.widgets import OptionList
        from textual.widgets.option_list import Option
        from halo_harness.init_cli import _PERMISSION_MODE_ROWS
        from halo_harness.theme import get_config_value
        current = get_config_value("permission_mode", default="auto") or "auto"
        option_list = OptionList(*[Option(label, id=ref) for ref, label in _PERMISSION_MODE_ROWS],
                                  id="wiz-permission-list")
        refs = [ref for ref, _label in _PERMISSION_MODE_ROWS]
        if current in refs:
            option_list.highlighted = refs.index(current)
            mark_checked(option_list, current)
        return [Static(one_sentence("Permission mode", current), classes="dialog-title"), option_list]

    def on_mount(self) -> None:
        focus_first(self, ["#wiz-permission-list"])

    def on_option_list_option_highlighted(self, event) -> None:
        if event.option_list.id == "wiz-permission-list" and event.option_id:
            mark_checked(event.option_list, event.option_id)

    def commit(self) -> None:
        from halo_harness.theme import set_config_value
        from halo_harness.init_cli import _PERMISSION_MODE_ROWS
        from textual.widgets import OptionList
        chosen = None
        try:
            option_list = self.query_one("#wiz-permission-list", OptionList)
            if option_list.highlighted is not None:
                chosen = str(option_list.get_option_at_index(option_list.highlighted).id)
        except Exception:
            chosen = None
        chosen = chosen or _PERMISSION_MODE_ROWS[0][0]
        set_config_value("permission_mode", chosen)
        self.state.permission_mode = chosen


STEP_FACTORIES["permission_mode"] = PermissionModeStep


# ---------------------------------------------------------------------------
# Step: Theme -- owner 2026-10-03: "the list of built-in themes with a
# live preview of the transcript and status bar in each". The preview is
# built directly from `tui/theme.py::variables_for` (explicit Rich spans,
# not real CSS variables) so it updates live without re-skinning the
# whole wizard app's own stylesheet.
# ---------------------------------------------------------------------------

class ThemeStep(StepScreen):
    DEFAULT_CSS = """
    ThemeStep OptionList { height: 10; margin-top: 1; }
    ThemeStep #wiz-theme-preview { height: 8; margin-top: 1; border: round $primary-darken-1; padding: 1; }
    """

    def body(self) -> list:
        from textual.widgets import OptionList
        from textual.widgets.option_list import Option
        from halo_harness.theme import DEFAULT_THEME, VALID_THEMES, get_config_value
        current = get_config_value("theme", default=None) or DEFAULT_THEME
        names = sorted(VALID_THEMES)
        option_list = OptionList(*[Option(n, id=n) for n in names], id="wiz-theme-list")
        if current in names:
            option_list.highlighted = names.index(current)
            mark_checked(option_list, current)
        return [Static(one_sentence("Theme", current), classes="dialog-title"),
                option_list, Static(id="wiz-theme-preview")]

    def on_mount(self) -> None:
        from textual.widgets import OptionList
        try:
            option_list = self.query_one("#wiz-theme-list", OptionList)
        except Exception:
            return
        if option_list.highlighted is not None:
            opt = option_list.get_option_at_index(option_list.highlighted)
            if opt.id:
                self._update_preview(str(opt.id))
        focus_first(self, ["#wiz-theme-list"])

    def on_option_list_option_highlighted(self, event) -> None:
        if event.option_list.id == "wiz-theme-list" and event.option_id:
            self._update_preview(str(event.option_id))
            mark_checked(event.option_list, event.option_id)

    def _update_preview(self, name: str) -> None:
        from rich.text import Text
        from halo_harness.tui.theme import variables_for
        try:
            preview = self.query_one("#wiz-theme-preview", Static)
        except Exception:
            return
        v = variables_for(name)
        text = Text()
        text.append("You: ", style=f"bold {v['bridge-user']}")
        text.append("add a .gitignore entry\n", style=v["bridge-text"])
        text.append("Claude: ", style=f"bold {v['bridge-accent']}")
        text.append("Sure -- writing that now.\n", style=v["bridge-assistant"])
        text.append("  * Write(.gitignore)\n", style=v["bridge-tool"])
        text.append("model dbx:databricks-deepseek-v4-1-flash  ", style=v["bridge-muted"])
        text.append("auto  ", style=v["bridge-success"])
        text.append("3 MCP", style=v["bridge-warning"])
        preview.update(text)

    def commit(self) -> None:
        from halo_harness import theme as theme_mod
        from textual.widgets import OptionList
        chosen = None
        try:
            option_list = self.query_one("#wiz-theme-list", OptionList)
            if option_list.highlighted is not None:
                opt = option_list.get_option_at_index(option_list.highlighted)
                chosen = str(opt.id) if opt.id else None
        except Exception:
            chosen = None
        if chosen and theme_mod.is_valid_theme(chosen):
            theme_mod.persist_theme(chosen)
            self.state.theme_name = chosen


STEP_FACTORIES["theme"] = ThemeStep


# ---------------------------------------------------------------------------
# Step: Team -- Halo 2.0.5 round 2c, rule 11: the round-2/2b "Agents" step
# and "Roles and lineup" step merge into ONE "Team" step. `TeamStep` lives
# in its OWN module (`team_step.py`, the hard constraint: this file gains
# only the registration lines below) -- imported here, at the point of
# registration, same as every OTHER cross-module dialog this file already
# pushes. "agents"/"roles" stay registered too, as plain aliases of the
# SAME factory, so `--step agents`/`--step roles` (`_resolve_start_index`'s
# own alias map) and the pre-existing `step_keys=("agents",)`/`("roles",)`
# literals in `setup_cli.py`/`tui/slash.py` keep landing here unchanged.
# ---------------------------------------------------------------------------
from halo_harness.tui.dialogs.team_step import TeamStep  # noqa: E402

STEP_FACTORIES["team"] = TeamStep
STEP_FACTORIES["agents"] = TeamStep
STEP_FACTORIES["roles"] = TeamStep


# ---------------------------------------------------------------------------
# Step: Organizations -- brief item 3. `orgs.enabled` defaults False
# (unlike roles): the switch starts OFF. "Next" and "Make this the
# default org" are the SAME action, same reasoning as `TeamStep`'s own
# Next/"apply the highlighted lineup" merge.
# ---------------------------------------------------------------------------

class OrgsStep(StepScreen):
    DEFAULT_CSS = """
    OrgsStep #wiz-orgs-list { height: 6; margin-top: 1; }
    OrgsStep #wiz-orgs-preview { height: 8; margin-top: 1; border: round $primary-darken-1; padding: 1; }
    OrgsStep .wizard-extra-buttons { height: 3; margin-top: 1; }
    OrgsStep .wizard-extra-buttons Button { margin-right: 1; }
    OrgsStep .wizard-switch-row { height: 3; margin-top: 1; }
    """

    def __init__(self, state: WizardState) -> None:
        super().__init__(state)
        self._orgs: "list[str]" = []

    def body(self) -> list:
        from textual.widgets import OptionList, Switch
        from textual.widgets.option_list import Option
        from halo_harness.orgs import list_orgs, orgs_mode_enabled
        self._orgs = list_orgs()
        enabled = orgs_mode_enabled()
        option_list = OptionList(*[Option(n, id=n) for n in self._orgs], id="wiz-orgs-list")
        on_body = Vertical(
            Static("An organization is a tree of positions that runs as sub-agents -- most people start "
                   "with solo or release-flow."),
            option_list, Static(id="wiz-orgs-preview"),
            Horizontal(Button("Make this the default org", id="wiz-orgs-default", variant="primary"),
                       Button("Edit org...", id="wiz-orgs-edit"), classes="wizard-extra-buttons"),
            id="wiz-orgs-on-body",
        )
        switch_row = Horizontal(Switch(value=enabled, id="wiz-orgs-switch"),
                                 Static(" Organizations enabled", classes="wizard-switch-label"),
                                 classes="wizard-switch-row")
        from halo_harness.theme import get_config_value
        default_name = get_config_value("orgs.default", default=None)
        current = ("off (no organization runs)" if not enabled else default_name or "on, no default yet")
        return [Static(one_sentence("Organizations", current, hint="Enter to change, or Make this the default."),
                        classes="dialog-title"), switch_row, on_body]

    def on_mount(self) -> None:
        self._sync_visibility()
        try:
            option_list = self.query_one("#wiz-orgs-list")
        except Exception:
            return
        if option_list.option_count:
            option_list.action_first()
            opt = option_list.get_option_at_index(option_list.highlighted or 0)
            if opt.id:
                self._update_preview(str(opt.id))
        self._mark_default()
        focus_first(self, ["#wiz-orgs-list"])

    def _mark_default(self) -> None:
        from halo_harness.theme import get_config_value
        try:
            option_list = self.query_one("#wiz-orgs-list")
        except Exception:
            return
        mark_checked(option_list, get_config_value("orgs.default", default=None))

    def _sync_visibility(self) -> None:
        try:
            on_body, switch = self.query_one("#wiz-orgs-on-body"), self.query_one("#wiz-orgs-switch")
        except Exception:
            return
        on_body.styles.display = "block" if switch.value else "none"

    def on_switch_changed(self, event) -> None:
        if event.switch.id == "wiz-orgs-switch":
            self._sync_visibility()

    def on_option_list_option_highlighted(self, event) -> None:
        if event.option_list.id == "wiz-orgs-list" and event.option_id:
            self._update_preview(str(event.option_id))

    def _highlighted_org_name(self) -> Optional[str]:
        try:
            option_list = self.query_one("#wiz-orgs-list")
        except Exception:
            return None
        if option_list.highlighted is None:
            return None
        opt = option_list.get_option_at_index(option_list.highlighted)
        return str(opt.id) if opt.id else None

    def _update_preview(self, name: str) -> None:
        from halo_harness.orgs import describe, load_org
        try:
            preview = self.query_one("#wiz-orgs-preview", Static)
        except Exception:
            return
        org = load_org(name)
        preview.update(describe(org) if org else "(no such organization)")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        # See `ProvidersStep.on_button_pressed`'s own comment -- this must
        # never re-handle wiz-back/skip/next.
        bid = event.button.id or ""
        if bid == "wiz-orgs-default":
            # Same reasoning as `TeamStep`'s own "apply the highlighted
            # lineup" -- choosing a default org IS the opt-in, even if
            # the switch (off by default here) was never touched.
            try:
                self.query_one("#wiz-orgs-switch").value = True
            except Exception:
                pass
            self.action_do_next()
        elif bid == "wiz-orgs-edit":
            self._open_editor()

    def _controller_models(self) -> list:
        """See `team_step.TeamStep._models_for_picker`'s own docstring --
        same "this wizard run's own enumeration cache wins once it exists,
        else fall back to a live Controller" rule, for the org editor."""
        if self.state.enumeration_done:
            return self.state.enumerated_models
        list_models = getattr(getattr(self.app, "controller", None), "list_models", None)
        try:
            return list_models() if callable(list_models) else []
        except Exception:
            return []

    def _open_editor(self) -> None:
        name = self._highlighted_org_name() or "custom"
        self.run_worker(lambda: self._editor_worker(name), thread=True, name="wiz-orgs-editor")

    def _editor_worker(self, name: str) -> None:
        from halo_harness.orgs import load_org
        org = load_org(name) or {"name": name, "description": "", "positions": [
            {"title": "Orchestrator", "role": "orchestrator", "reports": [], "instructions": ""}]}
        self.app.call_from_thread(self._open_editor_screen, name, org, self._controller_models())

    def _open_editor_screen(self, name: str, org: dict, models: list) -> None:
        from halo_harness.tui.dialogs.org_editor import OrgEditor
        self.app.push_screen(OrgEditor(name, org, models), lambda _saved: self._refresh_orgs())

    def _refresh_orgs(self) -> None:
        from textual.widgets.option_list import Option
        from halo_harness.orgs import list_orgs
        try:
            option_list = self.query_one("#wiz-orgs-list")
        except Exception:
            return
        previous = self._highlighted_org_name()
        self._orgs = list_orgs()
        option_list.clear_options()
        for n in self._orgs:
            option_list.add_option(Option(n, id=n))
        if self._orgs:
            idx = self._orgs.index(previous) if previous in self._orgs else 0
            option_list.highlighted = idx
            self._update_preview(self._orgs[idx])
        self._mark_default()

    def commit(self) -> None:
        from halo_harness.theme import set_config_value
        from halo_harness.orgs import set_default_org
        enabled = False
        try:
            enabled = bool(self.query_one("#wiz-orgs-switch").value)
        except Exception:
            pass
        set_config_value("orgs.enabled", enabled)
        if not enabled:
            return
        name = self._highlighted_org_name()
        if not name:
            return
        ok, _problems = set_default_org(name)
        if ok:
            self.state.default_org = name


STEP_FACTORIES["orgs"] = OrgsStep


# ---------------------------------------------------------------------------
# Step: Linux fixes -- only ever reachable when `linux_fixes_needed()`
# put it in `step_keys` at all (see `full_step_keys`); Next applies
# whichever of the two fixes still applies (same default `_confirm(...,
# default=True)` already used on the console path), Skip applies neither.
# ---------------------------------------------------------------------------

class LinuxFixesStep(StepScreen):
    def body(self) -> list:
        import shutil
        from halo_harness.linux_fixes import local_bin_on_noninteractive_path, rc_file_for_shell
        lines = []
        if not shutil.which("rg"):
            lines.append("- install a static ripgrep (rg) into ~/.local/bin")
        if not local_bin_on_noninteractive_path():
            lines.append(f"- add ~/.local/bin to PATH via {rc_file_for_shell()}")
        text = ("Next applies these fixes, Skip leaves them alone:\n" + "\n".join(lines)) if lines \
            else "Nothing left to fix."
        return [Static("Linux setup fixes:", classes="dialog-title"), Static(text)]

    def commit(self) -> None:
        import shutil
        from halo_harness.linux_fixes import ensure_local_bin_on_rc, install_static_ripgrep, \
            local_bin_on_noninteractive_path
        if not shutil.which("rg"):
            ok, msg = install_static_ripgrep(Path.home() / ".local" / "bin")
            if ok:
                self.state.written.append(msg)
        if not local_bin_on_noninteractive_path():
            written, path = ensure_local_bin_on_rc()
            if written:
                self.state.written.append(str(path))


STEP_FACTORIES["linux_fixes"] = LinuxFixesStep


# ---------------------------------------------------------------------------
# Step: Summary -- reuses `init_cli.py`'s own `_step_checks`/`_step_live_
# pong`/`_step_summary` verbatim (captured into a StringIO-backed Console,
# the same trick `init_cli._run_live_pong` already uses) so this step's
# text can never drift from what the plain console path prints.
# ---------------------------------------------------------------------------

class SummaryStep(StepScreen):
    DEFAULT_CSS = """
    SummaryStep #wiz-summary-text { margin-top: 1; }
    SummaryStep #wiz-summary-change-list { height: 6; margin-top: 1; }
    """

    def body(self) -> list:
        from textual.widgets import OptionList
        from textual.widgets.option_list import Option
        widgets = [Static("Summary:", classes="dialog-title")]
        # Deliverable 5 (rule 5): "the Summary says what it chose" --
        # Quick setup's own "activates the standard lineup with roles
        # off" is otherwise invisible (no Team step ever ran this run to
        # print its own state line).
        if self.state.quick_setup:
            widgets.append(Static(
                "Quick setup: every role (including the sub-agents halo spawns on its own) uses the "
                "default model picked above -- the same observable state as the standard lineup with "
                "custom roles off. Full setup (Theme, Team, Organizations, ...) is still one `halo init "
                "--step team` (or `halo setup`) away any time.", id="wiz-summary-quick-note"))
        widgets.append(Static("Running checks…", id="wiz-summary-text"))
        # Rule 10: "Change" jumps back into each step -- every key this
        # run actually used (never "summary" itself, nothing to jump to).
        change_rows = [(k, STEP_TITLES.get(k, k)) for k in self.state.step_keys if k != "summary"]
        if change_rows:
            widgets.append(Static("Change:", classes="dialog-subtitle"))
            widgets.append(OptionList(*[Option(f"Change: {title}", id=key) for key, title in change_rows],
                                       id="wiz-summary-change-list"))
        return widgets

    def on_mount(self) -> None:
        if self.state.quick_setup:
            self._activate_standard_quick()
        self.run_worker(self._run_checks_worker, thread=True, name="wiz-summary-checks")

    def _activate_standard_quick(self) -> None:
        """Rule 5: "Quick setup ... activates the standard lineup with
        roles off" -- run HERE (Summary's own `on_mount`), after every
        earlier step's `commit()` already ran, specifically so the
        `standard` lineup's own `models.preference: default` bio
        resolves against the REAL default model `DefaultModelStep.
        commit()` just wrote -- applying this any earlier (e.g. the
        instant Quick is picked, before a model is even chosen) would
        freeze the literal string "default" into every `roles.<name>`
        config entry instead of a real ref (`agents_yaml.resolve_agent_
        bio`'s own "left as typed" rule for an unset session default),
        defeating the whole point of the standard lineup's live
        tracking. Written explicitly (`team: "standard"` AND `roles.
        enabled: false`) rather than left as whatever the switch already
        was, so the result is the same named, inspectable state a Full
        setup's "Use this lineup" on `standard` would leave (`docs/
        AGENTS.md`'s "the `default` model reference and the `standard`
        lineup"), never an accident of a machine's pre-existing config."""
        from halo_harness.roles import set_roles_enabled
        from halo_harness.teams_yaml import apply_team_template, ensure_builtin_team_templates
        try:
            ensure_builtin_team_templates()
            ok, _problems, _notes = apply_team_template("standard", cwd=self.state.cwd)
            if ok:
                self.state.written.append("quick setup: lineup 'standard' applied, roles off")
        except Exception:
            pass
        set_roles_enabled(False)

    def on_option_list_option_selected(self, event) -> None:
        if event.option_list.id == "wiz-summary-change-list" and event.option_id:
            self._jump_to(str(event.option_id))

    def _jump_to(self, key: str) -> None:
        """Rule 10: pushes that step fresh, on top of this Summary (still
        on the stack underneath) -- its own Next/Finish then simply
        continues the chain forward from there (through any later steps
        again) to a fresh Summary, same as a normal walk-through; Back/
        Esc from it return to THIS Summary instance unchanged, never
        losing what was already decided (rule 8)."""
        if key not in self.state.step_keys:
            return
        self.state.index = self.state.step_keys.index(key)
        screen = _build_step(self.state, key)
        self.state.pushed += 1
        self.app.push_screen(screen)

    def _run_checks_worker(self) -> None:
        import io
        from types import SimpleNamespace
        from rich.console import Console
        from halo_harness.init_cli import _step_checks, _step_live_pong, _step_summary
        stream = io.StringIO()
        console = Console(file=stream, width=100)
        args = SimpleNamespace(no_live=self.state.no_live)
        doctor_lines, _ok = _step_checks(args, console, self.state.cwd)
        self.state.doctor_lines = doctor_lines
        pong_ok = True
        if not self.state.no_live and self.state.final_model:
            pong_ok = _step_live_pong(self.state.final_model, self.state.cwd, console)
        self.state.pong_ok = pong_ok
        _step_summary(console, self.state.written, pong_ok, doctor_lines, no_live=self.state.no_live,
                      configured_this_run=self.state.configured_this_run, final_model=self.state.final_model)
        text = stream.getvalue()
        # Halo 2.0.4 round 4 (deliverable 1): "the merged list is ... reused
        # by ... the summary" -- the Providers step's own post-keys
        # enumeration (`WizardState.enumerated_models`'s own docstring),
        # never recomputed here (a pure read of what already ran).
        if self.state.enumeration_done:
            selectable = [m for m in self.state.enumerated_models if isinstance(m, dict) and m.get("ref")]
            groups = {m.get("group") or m.get("provider") for m in selectable}
            text += (f"\n\nModel enumeration: {len(selectable)} model(s) across {len(groups)} "
                     f"provider group(s).")
            not_reachable = [ln for ln in self.state.enumeration_lines if "not reachable" in ln]
            if not_reachable:
                text += "\n  not reachable: " + "; ".join(not_reachable)
        self.app.call_from_thread(self._show_text, text)

    def _show_text(self, text: str) -> None:
        try:
            self.query_one("#wiz-summary-text", Static).update(text)
        except Exception:
            pass


STEP_FACTORIES["summary"] = SummaryStep


# ---------------------------------------------------------------------------
# Entry points.
# ---------------------------------------------------------------------------

class InitWizardApp(App):
    """The standalone host for `halo init`/`halo setup` -- `init_cli.py`/
    `setup_cli.py` read `.state` back after `.run()` returns (Finish, or
    an Esc-confirmed quit)."""
    TITLE = "halo init"

    def __init__(self, state: WizardState) -> None:
        super().__init__()
        self.state = state
        state.on_finish = lambda app: app.exit()

    def on_mount(self) -> None:
        # Halo 2.0.5 round 2c (deliverable 5): a genuine fresh `halo
        # init` (no `--step`) offers Quick/Full setup FIRST -- never
        # counted in `state.pushed` (see `SetupModeStep._choose`, which
        # pops this chooser and pushes the real step 1 itself once a
        # choice is made).
        if self.state.offer_quick_full:
            from halo_harness.tui.dialogs.setup_mode import SetupModeStep
            self.push_screen(SetupModeStep(self.state))
            return
        first = _build_step(self.state, self.state.step_keys[self.state.index])
        self.state.pushed += 1
        self.push_screen(first)


def _resolve_start_index(start_step, step_keys: tuple) -> int:
    """`start_step` names where to begin, over the FULL `step_keys` list
    -- either the 1-based ordinal the brief's own step list uses ("step 5
    is Roles") or the step's own key string ("roles"); anything else (or
    out of range) starts at step 1, same as omitting it. Round 2c:
    "roles"/"agents" (no longer real keys in `step_keys` -- rule 11
    merged both into "team") still resolve, through `_STEP_KEY_ALIASES`,
    to wherever "team" actually sits."""
    if isinstance(start_step, bool):
        return 0
    if isinstance(start_step, int) and 1 <= start_step <= len(step_keys):
        return start_step - 1
    if isinstance(start_step, str):
        key = _STEP_KEY_ALIASES.get(start_step, start_step)
        if key in step_keys:
            return step_keys.index(key)
    return 0


def run_init_wizard(*, cwd, team: Optional[str] = None, no_live: bool = False,
                     start_step=None) -> InitWizardApp:
    """Runs the whole interactive `halo init` as a standalone full-screen
    app. `start_step` (brief item 3: used by `halo setup`'s own "roles,
    then orgs, then summary" path, and pinned directly by its own test --
    "start_step=5 opens on roles") starts partway through this SAME full
    step list rather than at step 1, as either the 1-based step number
    or the step's own key; `halo setup`/`/setup` themselves use the
    SEPARATE, shorter `build_truncated_state`/`first_step_screen` below
    instead (Back has nowhere useful to go before "roles" there, unlike
    a mid-wizard resume of the full chain)."""
    step_keys = full_step_keys()
    index = _resolve_start_index(start_step, step_keys)
    state = WizardState(cwd=Path(cwd), step_keys=step_keys, index=index, team=team, no_live=no_live,
                         # Deliverable 5: Quick/Full setup is offered only
                         # for a genuine fresh run -- `--step` (any
                         # `start_step`) means the owner already knows
                         # exactly where they want to land, so the gate
                         # would just be in the way.
                         offer_quick_full=(start_step is None))
    app = InitWizardApp(state)
    app.run()
    return app


def build_truncated_state(cwd, *, step_keys, on_finish: "Callable[[object], None]") -> WizardState:
    """`/setup`/`/setup roles`/`/setup orgs` (pushed onto a LIVE
    `BridgeApp`, never a standalone app of its own -- `tui/slash.py`'s
    `_handle_setup`) and `halo setup`'s own interactive path (`setup_cli.
    py`, which DOES build a standalone `InitWizardApp` around this same
    state). `on_finish` is what pops back to (or exits) the hosting app
    once the chain ends or is quit early."""
    state = WizardState(cwd=Path(cwd), step_keys=tuple(step_keys), index=0)
    state.on_finish = on_finish
    return state


def first_step_screen(state: WizardState) -> Screen:
    state.pushed += 1
    return _build_step(state, state.step_keys[0])
