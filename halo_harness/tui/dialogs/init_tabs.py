"""halo_harness.tui.dialogs.init_tabs -- H15 Part A: `halo init`'s
tabbed provider setup, one tab per `init_providers.TAB_PROVIDERS` entry
(Databricks, OpenRouter, Anthropic API (key), Ollama, Hugging Face, OpenAI
API (key), TypeSafe, Experiential Labs). A standalone Textual `App` (same reason `init_picker.py`'s own
pickers are standalone: a plain CLI command has no host `BridgeApp` screen
stack to push onto) -- `init_cli.py` runs this synchronously via
`run_init_tabs`, on a real terminal only; a piped/non-tty run never reaches
this module (see `init_cli.py::cmd_init`'s own TTY gate).

Navigation: Shift+Tab always switches tabs (app-level, priority); Left/
Right switch tabs too whenever the tab bar itself has focus (Textual's own
`Tabs` widget already binds them there) -- while a credential field has
focus, Left/Right move the cursor instead (`Input`'s own binding correctly
wins, matching how every real wizard behaves: you don't lose cursor
movement just because tabs exist). Up/Down move between the active tab's
own fields/button (app-level, non-priority -- `Input` binds neither key,
so these never fight it). Enter activates a focused field (saves) or
button. Esc leaves the whole dialog (`.run()` returns) -- `init_cli.py`
proceeds to the default-model/permission-mode steps exactly as it does
after the old one-at-a-time picker loop.
"""

from __future__ import annotations

from halo_harness.tui.worker_guard import guarded_worker
from pathlib import Path
from typing import Optional

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.widgets import Button, Input, Static, TabbedContent, TabPane

from halo_harness.init_providers import TAB_LABEL, TAB_PROVIDERS, tab_credential_state


def _pane_id(provider: str) -> str:
    return f"pane-{provider}"


def _status_text(provider: str, *, state: Optional[dict] = None) -> str:
    """A.2: "picked up from <source>" + masked value once configured; a
    discovered Databricks HOST with no token yet gets its own in-between
    wording (A.1's Databricks-specific "host and token" fields)."""
    state = state if state is not None else tab_credential_state(provider)
    if state["configured"]:
        return f"picked up from {state['source']}: {state['masked']}"
    if state.get("known_host"):
        return f"host picked up from {state['source']}: {state['known_host']} -- token still needed"
    return "not set up"


def _reach_text(provider: str) -> str:
    from halo_harness.providers.reachability import reachability_tag
    return f"reachability: {reachability_tag(provider)}"


class InitTabsApp(App):
    TITLE = "halo init"
    BINDINGS = [
        Binding("shift+tab", "prev_tab", "Previous provider", priority=True, show=False),
        Binding("up", "focus_prev_field", "Up", show=False),
        Binding("down", "focus_next_field", "Down", show=False),
        Binding("escape", "finish", "Done", priority=True, show=False),
    ]
    CSS = """
    Screen { align: center middle; }
    #tabs-body { width: 92%; height: 88%; border: round $primary; padding: 1 2; }
    .tab-status { margin-top: 1; color: $text-muted; }
    .tab-reach { margin-top: 1; }
    .tab-help { margin-top: 1; color: $text-muted; }
    Input { margin-top: 1; }
    Button { margin-top: 1; }
    """

    def __init__(self, *, team: "Optional[str]" = None, no_live: bool = False) -> None:
        super().__init__()
        # Read by init_cli.py AFTER .run() returns.
        self.configured_this_run: "list[str]" = []
        self.catalog_notes: "dict[str, str]" = {}
        self.written: "list[str]" = []
        # 1.0.1 part 2 fixpass finding 6: --team/--no-live, silently ignored
        # by this app before this fix.
        self._no_live = no_live
        self._team_flag = team
        self.team_warnings: "list[str]" = []
        # 1.0.1 part 2 fixpass finding 4: each tab's credential state is
        # computed ONCE (synchronously here -- every provider is purely
        # local, never a spawn or the network) and CACHED -- a keystroke
        # (`on_input_changed`) only ever reads this cache, it never
        # re-derives the state itself. `team_cfg` is loaded eagerly
        # too, but ONLY from a local file (`team_config.team_config_path`
        # is pure/fast); a `--team https://...` URL is resolved in a worker
        # instead (see `_team_cfg_worker`) -- a real network fetch must
        # never run inline in `__init__`/`compose`.
        self._team_cfg, self._team_cfg_pending = self._load_team_cfg_fast()
        self._state_cache: "dict[str, dict]" = {
            p: tab_credential_state(p, team_cfg=self._team_cfg) for p in TAB_PROVIDERS
        }

    def _load_team_cfg_fast(self) -> "tuple[Optional[dict], bool]":
        from halo_harness.team_config import load_team_config, team_config_path
        try:
            source = team_config_path(Path.cwd(), team_flag=self._team_flag)
        except Exception:
            return None, False
        if source and (source.startswith("http://") or source.startswith("https://")):
            return None, True  # resolved in _team_cfg_worker instead
        cfg, warnings = load_team_config(Path.cwd(), team_flag=self._team_flag)
        self.team_warnings.extend(warnings)
        return cfg, False

    def compose(self) -> ComposeResult:
        with Vertical(id="tabs-body"):
            yield Static("Set up providers below -- Esc when done (default model/permission mode come next)",
                         classes="dialog-title")
            with TabbedContent(initial=_pane_id(TAB_PROVIDERS[0])):
                for provider in TAB_PROVIDERS:
                    with TabPane(TAB_LABEL[provider], id=_pane_id(provider)):
                        yield from self._tab_widgets(provider)

    def _tab_widgets(self, provider: str) -> ComposeResult:
        # finding 4: every tab's state is purely local (env vars/settings
        # files, no subprocess/network) and was already computed once in
        # `__init__` -- compose() must return instantly.
        state = self._state_cache[provider]
        if provider in ("ollama", "huggingface"):
            # Round 5b part 2 (brief item 5): see `init_wizard.py`'s
            # identical sibling widget for the full rationale -- this app
            # is the lighter-weight twin of that wizard step.
            yield Static("detecting what's already on this machine…", id=f"{provider}-detect",
                        classes="tab-help")
        status_text = _status_text(provider, state=state)
        yield Static(status_text, id=f"{provider}-status", classes="tab-status")
        for f in state["fields"]:
            prefill = state.get("known_host") or "" if f["name"] == "host" else ""
            yield Input(value=prefill, placeholder=f["label"], password=f["secret"],
                        id=f"{provider}-field-{f['name']}")
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
            yield Static("Paste OPENAI_API_KEY to use the real OpenAI API directly (oai: models).",
                         classes="tab-help")
        if provider == "typesafe":
            yield Static("Stores TYPESAFE_API_KEY only -- for a later feature, no routed models yet.",
                         classes="tab-help")
        if provider == "experiential":
            yield Static("Paste EXPLABS_API_KEY (the inference key, prefix xpl_) to use the Experiential "
                         "Labs gateway (xp: models) -- its catalog, credits balance and model prices come "
                         "from this same key; the separate provisioning key is never asked for here.",
                         classes="tab-help")
        yield Button("Save", id=f"{provider}-save", variant="primary")
        # finding 4: NEVER a real probe here (compose() must return
        # instantly) -- always "checking…" to start; on_mount's own workers
        # below resolve the real tag, or --no-live skips it outright.
        reach = "reachability: skipped (--no-live)" if self._no_live else "reachability: checking…"
        yield Static(reach, id=f"{provider}-reach", classes="tab-reach")

    def on_mount(self) -> None:
        if self._team_cfg_pending:
            guarded_worker(self, self._team_cfg_worker, thread=True, name="init-team-config")
        if self._no_live:
            return  # finding 6: --no-live skips every reachability probe/catalog fetch below
        # A.3: the bounded background probe runs right away for whatever's
        # ALREADY configured (re-running init on a partially-set-up box) --
        # never for a tab that still needs credentials, which starts "not
        # set up" until Save. Read from the cache computed in __init__ --
        # never re-derives it (finding 4).
        for provider in TAB_PROVIDERS:
            if self._state_cache[provider]["configured"]:
                guarded_worker(self, lambda p=provider: self._probe_worker(p), thread=True, name=f"init-tab-probe-{provider}")
        if "ollama" in TAB_PROVIDERS or "huggingface" in TAB_PROVIDERS:
            guarded_worker(self, self._detect_local_worker, thread=True, name="init-detect-local")

    def _detect_local_worker(self) -> None:
        from halo_harness.providers.local_models import detection_summary_lines
        try:
            lines = detection_summary_lines()
        except Exception:
            lines = []
        text = "\n".join(lines) if lines else "nothing detected on this machine yet (no Ollama daemon, no " \
                                               "local server, no cached model files)."
        self.call_from_thread(self._apply_detect_text, text)

    def _apply_detect_text(self, text: str) -> None:
        for provider in ("ollama", "huggingface"):
            try:
                self.query_one(f"#{provider}-detect", Static).update(text)
            except Exception:
                pass

    def _team_cfg_worker(self) -> None:
        from halo_harness.team_config import load_team_config
        cfg, warnings = load_team_config(Path.cwd(), team_flag=self._team_flag)
        self.call_from_thread(self._apply_team_cfg, cfg, warnings)

    def _apply_team_cfg(self, cfg: "Optional[dict]", warnings: list) -> None:
        self._team_cfg = cfg
        self.team_warnings.extend(warnings)
        if not cfg or "databricks" in self.configured_this_run:
            return
        state = tab_credential_state("databricks", team_cfg=self._team_cfg)
        self._state_cache["databricks"] = state
        if state["configured"] or not state.get("known_host"):
            return
        try:
            self.query_one("#databricks-status", Static).update(_status_text("databricks", state=state))
            host_input = self.query_one("#databricks-field-host", Input)
            if not host_input.value:
                host_input.value = state["known_host"]
        except Exception:
            pass

    # ---- navigation --------------------------------------------------

    def action_prev_tab(self) -> None:
        tabs = self.query_one(TabbedContent)
        tab_ids = [_pane_id(p) for p in TAB_PROVIDERS]
        try:
            idx = tab_ids.index(tabs.active)
        except ValueError:
            idx = 0
        tabs.active = tab_ids[(idx - 1) % len(tab_ids)]

    def action_focus_prev_field(self) -> None:
        self.screen.focus_previous()

    def action_focus_next_field(self) -> None:
        self.screen.focus_next()

    def action_finish(self) -> None:
        self.exit()

    # ---- live status as a value is entered (A.2) ----------------------

    def on_input_changed(self, event: Input.Changed) -> None:
        field_id = event.input.id or ""
        if "-field-" not in field_id:
            return
        provider = field_id.split("-field-", 1)[0]
        # finding 4: reads the CACHE -- a field only exists on a tab that
        # was already computed synchronously in __init__, so this never
        # re-derives it.
        state = self._state_cache[provider]
        if state["configured"]:
            return  # already resolved elsewhere -- editing here only matters once Saved
        try:
            status = self.query_one(f"#{provider}-status", Static)
        except Exception:
            return
        any_value = any((self._field_value(provider, f["name"]) or "").strip() for f in state["fields"])
        status.update("value entered -- Enter (or Save) stores it" if any_value
                      else _status_text(provider, state=state))

    def _field_value(self, provider: str, name: str) -> str:
        try:
            return self.query_one(f"#{provider}-field-{name}", Input).value
        except Exception:
            return ""

    # ---- save ----------------------------------------------------------

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id or ""
        if button_id.endswith("-save"):
            self._save(button_id[: -len("-save")])

    def on_input_submitted(self, event: Input.Submitted) -> None:
        field_id = event.input.id or ""
        if "-field-" in field_id:
            self._save(field_id.split("-field-", 1)[0])

    def _collect_values(self, provider: str) -> dict:
        state = self._state_cache[provider]
        return {f["name"]: self._field_value(provider, f["name"]) for f in state["fields"]}

    def _save(self, provider: str) -> None:
        from halo_harness.init_providers import save_tab_credentials
        values = self._collect_values(provider)
        ok, message = save_tab_credentials(provider, values, team_cfg=self._team_cfg)
        try:
            status = self.query_one(f"#{provider}-status", Static)
        except Exception:
            return
        if not ok:
            status.update(f"not set up ({message})")
            return
        # 1.0.1 part 2 fixpass finding 15: `enable_if_was_explicitly_
        # disabled`, never a bare `enable()` -- see its own docstring; item
        # 21.1 ("completing a tab is what enables it") is already covered
        # live by auto-detection, so this only ever flips an EXISTING
        # explicit `enabled: false` back to `true`, never writes a fresh
        # permanent override that would outlive a later revocation.
        from halo_harness.providers.enablement import enable_if_was_explicitly_disabled
        enable_if_was_explicitly_disabled(provider)
        if provider not in self.configured_this_run:
            self.configured_this_run.append(provider)
        # finding 4: refreshes the cache -- the save just changed the
        # underlying credential/login state this provider's cached entry
        # was computed from.
        state = tab_credential_state(provider, team_cfg=self._team_cfg)
        self._state_cache[provider] = state
        status.update(_status_text(provider, state=state))
        if self._no_live:
            # finding 6: --no-live skips the reachability probe AND the
            # catalog fetch below -- "Save" still works and
            # enables the tab, it just never touches the network.
            try:
                self.query_one(f"#{provider}-reach", Static).update("reachability: skipped (--no-live)")
            except Exception:
                pass
            return
        try:
            self.query_one(f"#{provider}-reach", Static).update("reachability: checking…")
        except Exception:
            pass
        guarded_worker(self, lambda: self._finish_tab_worker(provider), thread=True, name=f"init-tab-save-{provider}")

    def _probe_worker(self, provider: str) -> None:
        from halo_harness.providers.reachability import reachability_tag
        tag = reachability_tag(provider)
        self.call_from_thread(self._apply_reach, provider, tag)

    def _finish_tab_worker(self, provider: str) -> None:
        """A.4: a tab that now has credentials gets its catalog fetched
        and cached right away, off the UI thread -- the reachability tag
        comes from its OWN probe pass.

        W3b test-determinism fix: the reachability tag is pushed to the UI
        RIGHT AWAY, before `refresh_tab_catalog` runs -- previously the tag
        update waited on BOTH calls finishing, so a slow/unreachable
        catalog fetch (its own, separate up-to-8s connect attempt) left
        "reachability: checking..." on screen for as long as the catalog
        fetch took, even though the reachability answer itself was already
        known. `catalog_notes` is only ever read AFTER the whole tabs app
        closes (`init_cli.py`'s own summary step) -- nothing live displays
        it mid-session, so finishing the catalog fetch after the tag update
        changes no visible behaviour, only its timing."""
        from halo_harness.init_providers import refresh_tab_catalog
        from halo_harness.providers.reachability import reachability_tag
        tag = reachability_tag(provider)
        self.call_from_thread(self._apply_reach, provider, tag)
        _ok, note = refresh_tab_catalog(provider)
        if note:
            self.catalog_notes[provider] = note

    def _apply_reach(self, provider: str, tag: str) -> None:
        try:
            self.query_one(f"#{provider}-reach", Static).update(f"reachability: {tag}")
        except Exception:
            pass


def run_init_tabs(*, team: Optional[str] = None, no_live: bool = False) -> InitTabsApp:
    """Runs the tabbed app as a standalone full-screen app; the caller
    reads `.configured_this_run`/`.catalog_notes`/`.written`/`.team_warnings`
    back off the returned instance once `.run()` has returned (Esc, or any
    other exit). `team`/`no_live` (1.0.1 part 2 fixpass finding 6): the
    same `--team`/`--no-live` flags `init_cli.py`'s own sequential path
    already honors."""
    app = InitTabsApp(team=team, no_live=no_live)
    app.run()
    return app
