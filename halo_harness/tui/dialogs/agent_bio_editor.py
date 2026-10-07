"""halo_harness.tui.dialogs.agent_bio_editor -- Halo 2.0.5 round 2 (wizard:
agent bios and lineups), deliverable 1: ONE form over an agent bio's common
sections (`agents_yaml.py`'s own shape) -- shared by the wizard's Agents
step (`agents_step.py`), `/agents new|edit`, and `halo agents new|edit
--form` (deliverable 4: "one form module ... serves the wizard, the slash
dialogs, and --form"). A NEW module (hard constraint: `init_wizard.py` is
already past the house size convention, so the editor lives here, never
grown into that file).

Field granularity matches `agents_yaml.resolve_agent_bio`'s own merge rule
("each SECTION merged KEY BY KEY -- a child's own key wins, a section the
child never mentions is inherited whole"): every form field below belongs
to exactly one `agents_yaml.BIO_SECTIONS` section and carries its OWN
override toggle once `extends_from` is set (the "new from..." fold-in) --
never a single all-or-nothing switch per section. Identity fields (name/
description/tags/kind/extends) never inherit at all (same rule `resolve_
agent_bio` itself encodes), so they carry no toggle.

Any key the bio's raw file already has OUTSIDE this field list (e.g.
`models.escalation`, `context.obsidian`, a per-tool `limits` map) is
preserved verbatim through `_collect_form` (merged UNDER the form's own
output, never replaced) -- deliverable 1's own "keys the file already has
outside the form survive a round trip untouched".
"""

from __future__ import annotations

from typing import Optional

from textual.binding import Binding
from textual.containers import Horizontal, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Static, Switch, TextArea

from halo_harness.agents_yaml import BIO_SECTIONS, KNOWN_KINDS, is_valid_agent_name, save_agent_bio, \
    validate_agent_bio

# (section, key, kind, widget-id suffix, label) -- kind in
# {"modelref", "text", "list", "lines", "int", "float", "bool", "memory"}.
# This is deliberately the brief's OWN field list for deliverable 1, not
# every key a bio schema can carry (docs/AGENTS.md) -- `temperature`/
# `lean_prompt`/`escalation`/`context.obsidian`/per-tool `limits`/etc. have
# no form field this round and round-trip untouched (see module docstring).
FIELDS = (
    ("models", "preference", "modelref", "pref", "Preferred model"),
    ("models", "fallback", "modelref", "fallback", "Fallback model"),
    ("models", "effort", "text", "effort", "Effort (low/medium/high/xhigh/max)"),
    ("models", "thinking", "bool", "thinking", "Thinking: native"),
    ("models", "context_budget", "float", "context-budget", "Context budget (0-1 fraction of the model's own)"),
    ("tools", "allow", "list", "tools-allow", "Allow (tool names, comma-separated)"),
    ("tools", "deny", "list", "tools-deny", "Deny (tool names, comma-separated)"),
    ("tools", "mcp_servers", "list", "mcp-servers", "MCP servers (comma-separated)"),
    ("tools", "permission_mode", "text", "permission-mode", "Permission mode"),
    ("tools", "rules", "lines", "rules", "Rules (one per line, settings.json grammar)"),
    ("context", "files", "list", "ctx-files", "Context files (comma-separated paths, prepended)"),
    ("context", "skills", "list", "ctx-skills", "Skills (comma-separated)"),
    ("context", "memory", "memory", "ctx-memory", "Memory namespace (blank = off)"),
    ("limits", "max_iterations", "int", "limit-max-iter", "Max iterations"),
    ("limits", "timeout", "text", "limit-timeout", "Timeout (house words: 20m, 2h, 90s, 1d)"),
    ("limits", "max_budget_usd", "float", "limit-budget", "Max budget (USD)"),
    ("limits", "concurrency", "int", "limit-concurrency", "Concurrency"),
    ("output", "handoff", "text", "output-handoff", "Handoff (summary/full/structured)"),
    ("output", "report_to", "text", "output-report-to", "Report to"),
    ("environment", "worktree", "bool", "env-worktree", "Worktree"),
    ("environment", "offline", "bool", "env-offline", "Offline"),
    ("acceptance", "prompt", "text", "accept-prompt", "Acceptance prompt"),
    ("acceptance", "expect", "text", "accept-expect", "Acceptance expect"),
)
_IDENTITY_HINT_ID = "bio-identity-hint"


def known_tool_names() -> "list[str]":
    """Best-effort, local-only -- "" the harness's real tool names (the
    brief's own "allow and deny from the harness's tool names"). Never
    raises: an unresolvable registry just means the allow/deny fields fall
    back to free text with no live-catalog note, same leniency a typed-but-
    unenumerated model ref already gets elsewhere in this codebase."""
    try:
        from halo_harness.tools.registry import default_tools
        return sorted({t.name for t in default_tools()}) + ["Agent", "WebSearch"]
    except Exception:
        return []


_DURATION_RE = __import__("re").compile(r"^(\d+)\s*([smhd])$")


def parse_duration_word(text: str) -> "Optional[int]":
    """`"20m"`/`"2h"`/`"90s"`/`"1d"` -> whole seconds; `None` for anything
    else (never raises) -- the house duration words the brief's own "Rules
    you can read" fold-in asks `limits.timeout` to accept."""
    text = (text or "").strip().lower()
    if not text:
        return None
    m = _DURATION_RE.match(text)
    if not m:
        return None
    n, unit = int(m.group(1)), m.group(2)
    return n * {"s": 1, "m": 60, "h": 3600, "d": 86400}[unit]


def duration_hint(text: str) -> str:
    text = (text or "").strip()
    if not text:
        return ""
    seconds = parse_duration_word(text)
    if seconds is None:
        return f"{text!r} is not a recognized duration word (expected e.g. 20m, 2h, 90s, 1d) -- kept as typed."
    if seconds >= 3600:
        return f"= {seconds / 3600:.2g} hour(s)."
    if seconds >= 60:
        return f"= {seconds / 60:.2g} minute(s)."
    return f"= {seconds} second(s)."


def rule_sentence(line: str) -> str:
    """One `tools.rules` line (house grammar: an action word -- deny/ask/
    allow -- then the settings.json `Tool(content)` shape, e.g. `"deny
    Bash(git push*)"`) rendered as a plain sentence ("Bash may not run git
    push"), or the raw line plus its parse error when it doesn't parse.
    Fold-in: "each tools.rules line is syntax-checked and rendered as a
    plain sentence beside it"."""
    from halo_harness.permissions import parse_rule
    line = (line or "").strip()
    if not line:
        return ""
    parts = line.split(None, 1)
    action = parts[0].lower() if parts and parts[0].lower() in ("deny", "ask", "allow") else None
    rest = parts[1] if action and len(parts) > 1 else line
    rule = parse_rule(rest, action=action)
    if rule.kind == "invalid":
        return f"{line!r}: {rule.error}"
    verb = {"deny": "may not run", "ask": "asks before running", "allow": "may run"}.get(action, "matches")
    if rule.kind == "bare":
        return f"{rule.tool} {verb.replace('run', 'do anything')}."
    value = (rule.value or "").rstrip("* ").strip() or (rule.value or "")
    return f"{rule.tool} {verb} {value}."


def budget_hint(max_budget_usd: "Optional[str]", model_ref: str, models: "list[dict]") -> str:
    """"about N turns at this model's price" -- a ROUGH estimate (~3000
    input + 600 output tokens per turn, a plain guess, not a house
    constant) against the picked model's own enumerated price; blank when
    the budget field is empty or the model/its price is unknown."""
    try:
        budget = float(max_budget_usd) if (max_budget_usd or "").strip() else None
    except ValueError:
        return ""
    if budget is None or budget <= 0 or not model_ref:
        return ""
    row = next((m for m in models if isinstance(m, dict) and m.get("ref") == model_ref), None)
    if row is None:
        return ""
    price_in, price_out = row.get("price_in_per_m"), row.get("price_out_per_m")
    if not isinstance(price_in, (int, float)) or not isinstance(price_out, (int, float)):
        return ""
    per_turn = (3000 * price_in + 600 * price_out) / 1_000_000
    if per_turn <= 0:
        return ""
    return f"about {budget / per_turn:.0f} turn(s) at this model's price (rough estimate)."


def filter_models_for_bio(models: "list[dict]", form: dict, *, show_all: bool = False) -> "list[dict]":
    """Fold-in "a picker that knows the bio": tool-capable rows only when
    `tools.allow` is non-empty, local (`ol:`/`hf:local/`/`hf:mlx/`) rows
    only when `environment.offline` is on, and a context window of at
    least `models.context_budget`'s own SHARE of the row's context --
    `show_all=True` (the picker's own one-chord toggle) bypasses every
    filter here and returns `models` unchanged."""
    if show_all:
        return list(models)
    out = []
    tools_allow = (form.get("tools") or {}).get("allow")
    offline = bool((form.get("environment") or {}).get("offline"))
    budget_frac = (form.get("models") or {}).get("context_budget")
    for m in models:
        if not isinstance(m, dict) or not m.get("ref"):
            continue
        if tools_allow:
            supported = m.get("supported_parameters")
            if isinstance(supported, list) and "tools" not in supported:
                continue
        if offline and not any(m["ref"].startswith(p) for p in ("ol:", "hf:local/", "hf:mlx/")):
            continue
        if isinstance(budget_frac, (int, float)) and budget_frac > 0:
            ctx = m.get("context_tokens")
            if isinstance(ctx, (int, float)) and ctx > 0 and ctx * budget_frac < 4096:
                continue
        out.append(m)
    return out


def filter_models_for_bio_with_reason(models: "list[dict]", form: dict) -> "tuple[list[dict], Optional[str]]":
    """Deliverable 4: "the bio-needs filter never yields an empty list
    silently: when it would, show all rows with one line saying why" --
    `filter_models_for_bio`'s own narrowing stays exactly as it is (its
    own pinned return shape, a plain list, is unchanged); THIS function
    is the one `_open_picker` below actually calls, falling back to
    every candidate row plus the one-line reason the picker shows as its
    own initial hint whenever the narrowed list would otherwise be
    empty. `(filtered, None)` is the common case -- the filter kept at
    least one row, or `models` was already empty (nothing to explain)."""
    filtered = filter_models_for_bio(models, form)
    if filtered or not models:
        return filtered, None
    reasons = []
    if (form.get("tools") or {}).get("allow"):
        reasons.append("no model in the catalog declares tool support")
    if (form.get("environment") or {}).get("offline"):
        reasons.append("no local (ol:, hf:local/, hf:mlx/) model is configured")
    budget_frac = (form.get("models") or {}).get("context_budget")
    if isinstance(budget_frac, (int, float)) and budget_frac > 0:
        reasons.append(f"no model's context is large enough for a {budget_frac:.2g} budget")
    why = "; ".join(reasons) or "this bio's own filters matched nothing"
    return list(models), f"Showing every model -- {why} (ctrl+e does the same)."


def suggest_models(models: "Optional[list]" = None, *, state_dir=None,
                    default_model: "Optional[str]" = None) -> "tuple[str, str]":
    """Fold-in "Suggest fills preference and fallback the way the roles
    editor's Auto tab does (presets, then gym data when present)" --
    reuses `roles.auto_fill_options()` verbatim (the Auto tab's own single
    source of truth), preferring a `gym-proposed`/`team:*` entry with at
    least one resolved role over the plain presets (gym/real-bio data
    beats a guess), reading a capable role (`orchestrator`/`main`/
    `coder`) for the preference and a cheap one (`small`/`researcher`/
    `judge`) for the fallback. On a bare machine (no catalog, no default
    model, every shipped bio's own `models.*` still unset -- confirmed
    live: this is the common case right after install) every option's
    own `roles` comes back empty; this then falls back to `models` (the
    SAME enumerated catalog the caller already has, cheapest-priced row
    first) rather than leaving the chord looking like it did nothing.
    `("", "")` only when BOTH sources come up empty -- advisory either
    way, never blocks typing a ref by hand."""
    pref = fallback = ""
    try:
        from halo_harness.roles import auto_fill_options, role_value_parts
        options = [o for o in auto_fill_options(default_model=default_model, state_dir=state_dir) if o.get("roles")]
        chosen = next((o for o in reversed(options) if o["key"] not in ("balanced", "quality", "local-first")),
                      options[0] if options else None)
        if chosen is not None:
            roles = chosen.get("roles") or {}
            pref_val = next((roles[k] for k in ("orchestrator", "main", "coder") if roles.get(k)), None)
            fallback_val = next((roles[k] for k in ("small", "researcher", "judge") if roles.get(k)), None)
            pref_model, _e = role_value_parts(pref_val) if pref_val else (None, None)
            fallback_model, _e = role_value_parts(fallback_val) if fallback_val else (None, None)
            pref, fallback = pref_model or "", fallback_model or ""
    except Exception:
        pass
    if not pref and models:
        usable = [m for m in models if isinstance(m, dict) and m.get("ref")]

        def _price(m):
            v = m.get("price_in_per_m")
            return v if isinstance(v, (int, float)) and not isinstance(v, bool) and v >= 0 else float("inf")
        ranked = sorted(usable, key=_price)
        if ranked:
            pref = ranked[0]["ref"]
            fallback = next((m["ref"] for m in ranked[1:] if m["ref"] != pref), "")
    return pref, fallback


class AgentBioEditor(ModalScreen):
    """The bio form. `raw_bio`: the bio's own file contents (NOT resolved
    -- `{}` for a brand-new bio, `{"extends": X}` for "new from X" with
    nothing of its own yet, or an existing child's own overrides). `models`:
    the enumerated catalog (the SAME cached rows the wizard/roles editor
    already have -- never re-enumerated here, see the brief's own "never
    re-run the enumeration" hard constraint)."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
        Binding("ctrl+s", "save", "Save", show=True, priority=True),
        Binding("ctrl+p", "pick_preference", "Pick preferred model", show=True, priority=True),
        Binding("ctrl+f", "pick_fallback", "Pick fallback model", show=True, priority=True),
        Binding("ctrl+g", "suggest", "Suggest both models", show=True, priority=True),
    ]
    DEFAULT_CSS = """
    AgentBioEditor { align: center middle; }
    AgentBioEditor > Horizontal { width: 96%; height: 92%; border: round $primary; background: $surface; }
    AgentBioEditor #bio-form-pane { width: 62%; height: 100%; padding: 1 2; border-right: solid $primary-darken-1; }
    AgentBioEditor #bio-preview-pane { width: 38%; height: 100%; padding: 1 2; }
    AgentBioEditor .bio-section-title { color: $accent; text-style: bold; margin-top: 1; height: 1; }
    AgentBioEditor .bio-hint { color: $text-muted; }
    AgentBioEditor .bio-field-row { height: 1; margin-top: 1; }
    AgentBioEditor .bio-field-row Switch { width: 8; }
    AgentBioEditor .bio-modelref-row { height: 1; }
    AgentBioEditor .bio-modelref-row Input { width: 1fr; }
    AgentBioEditor .bio-modelref-row Button { width: auto; margin-left: 1; }
    AgentBioEditor TextArea#bio-rules { height: 4; }
    AgentBioEditor #bio-preview { color: $text-muted; }
    """

    def __init__(self, name: str, raw_bio: dict, models: "list[dict]", *, cwd=None, state_dir=None,
                 project: bool = False, is_new: bool = False, extends_from: "Optional[str]" = None) -> None:
        super().__init__()
        # NOT `self.name` -- shadows Textual's own read-only `DOMNode.name`
        # property (`OrgEditor`'s own `org_name`/`RolesEditor`'s own
        # `template_name` avoid the same trap).
        self.bio_name = name
        self.bio = dict(raw_bio or {})
        self.models = models or []
        self.cwd = cwd
        self.state_dir = state_dir
        self.project = project
        self.is_new = is_new
        self.extends_from = extends_from or self.bio.get("extends")
        self._parent_resolved: "Optional[dict]" = None
        if self.extends_from:
            from halo_harness.agents_yaml import resolve_agent_bio
            self._parent_resolved = resolve_agent_bio(self.extends_from, cwd=cwd, state_dir=state_dir)
        self._last_problems: "list[str]" = []

    # -- identity/current name -------------------------------------------------
    def _current_name(self) -> str:
        if self.is_new:
            try:
                return self.query_one("#bio-name", Input).value.strip() or self.bio_name
            except Exception:
                return self.bio_name
        return self.bio_name

    def _has_own(self, section: str, key: str) -> bool:
        return key in (self.bio.get(section) or {})

    def _own_value(self, section: str, key: str):
        return (self.bio.get(section) or {}).get(key)

    def _parent_value(self, section: str, key: str):
        if not self._parent_resolved:
            return None
        return (self._parent_resolved.get(section) or {}).get(key)

    # -- compose -----------------------------------------------------------
    def compose(self):
        with Horizontal():
            with VerticalScroll(id="bio-form-pane"):
                title = "New agent bio" if self.is_new else f"Agent bio: {self.bio_name}"
                if self.extends_from:
                    title += f"  (extends {self.extends_from})"
                yield Static(title, classes="dialog-title")
                yield Static("Ctrl+P/Ctrl+F: pick a model  |  Ctrl+G: suggest both  |  Ctrl+S: save  |  "
                              "Esc: cancel", classes="dialog-subtitle")
                yield Static("Identity", classes="bio-section-title")
                if self.is_new:
                    yield Input(value=self.bio_name, placeholder="name", id="bio-name", compact=True)
                else:
                    yield Static(f"Name: {self.bio_name} (fixed -- rename by duplicating)", id="bio-name-display")
                yield Input(value=self.bio.get("description") or "", placeholder="Description", id="bio-description",
                            compact=True)
                yield Input(value=self.bio.get("kind") or "", placeholder=f"Kind ({'/'.join(KNOWN_KINDS)})",
                            id="bio-kind", compact=True)
                yield Input(value=", ".join(self.bio.get("tags") or []), placeholder="Tags (comma-separated)",
                            id="bio-tags", compact=True)
                yield Input(value=self.extends_from or "", placeholder="Extends (another bio name)",
                            id="bio-extends", compact=True)
                yield Static("", id=_IDENTITY_HINT_ID, classes="bio-hint")
                for section in BIO_SECTIONS:
                    yield Static(section.capitalize(), classes="bio-section-title")
                    for (sec, key, kind, suffix, label) in FIELDS:
                        if sec == section:
                            yield from self._field_widgets(sec, key, kind, suffix, label)
                    yield Static("", id=f"bio-{section}-hint", classes="bio-hint")
                with Horizontal(classes="wizard-extra-buttons"):
                    yield Switch(value=self.project, id="bio-project-toggle")
                    yield Static(" Save to project scope (.halo/agents/)", classes="wizard-switch-label")
                with Horizontal(classes="wizard-extra-buttons"):
                    yield Button("Save (ctrl+s)", id="bio-save", variant="primary", compact=True)
                    yield Button("Try it (cost first)", id="bio-try", compact=True)
                    yield Button("Cancel (esc)", id="bio-cancel", compact=True)
                yield Static("", id="bio-hint")
            with VerticalScroll(id="bio-preview-pane"):
                yield Static("Preview -- the YAML that would be written:", classes="dialog-subtitle")
                yield Static("", id="bio-preview")

    def _field_widgets(self, section: str, key: str, kind: str, suffix: str, label: str):
        """One field's own row(s): a label, an override `Switch` (only
        when `extends_from` is set -- identity never shows one, and a
        plain, non-extending bio shows none either, since every field is
        always its own), a "Pick..." button for a `modelref` field, and
        (for `rules`) the rendered-sentences `Static` right under it."""
        wid = f"bio-{suffix}"
        has_own = self._has_own(section, key)
        override_default = has_own if self.extends_from else True
        inherited = self._parent_value(section, key) if self.extends_from else None
        own = self._own_value(section, key)
        with Horizontal(classes="bio-field-row"):
            if self.extends_from:
                yield Switch(value=override_default, id=f"{wid}-ov")
            yield Static(label)
        if kind == "bool":
            value = own if has_own else (inherited if inherited is not None else False)
            value = (value == "native") if key == "thinking" else bool(value)
            yield Switch(value=bool(value), id=wid, disabled=self.extends_from and not override_default)
        elif kind == "lines":
            text = "\n".join(own if has_own else (inherited or []))
            yield TextArea(text, id=wid, disabled=self.extends_from and not override_default, compact=True)
            yield Static("", id=f"{wid}-sentences", classes="bio-hint")
        else:
            if kind == "memory":
                src = own if has_own else (inherited if inherited is not None else {})
                text = (src or {}).get("namespace") or "" if isinstance(src, dict) else ""
            elif kind == "list":
                src = own if has_own else (inherited or [])
                text = ", ".join(src or [])
            else:
                src = own if has_own else inherited
                text = "" if src is None else str(src)
            placeholder = label if has_own or not self.extends_from else f"(inherited: {text or '(unset)'})"
            display_text = text if (has_own or not self.extends_from) else ""
            disabled = bool(self.extends_from and not override_default)
            if kind == "modelref":
                # Round 2c (deliverable 3, rule 3): an autocomplete
                # dropdown under the field, filtered by what's typed --
                # Ctrl+P/Ctrl+F still open the full `ModelPicker`. Deliverable
                # 3 (round 2): the preferred/fallback row shares ONE line
                # with its own "Pick..." button (never a separate row below
                # it) -- the biggest single saving toward "the model fields
                # are visible on open at 80x24".
                from halo_harness.tui.dialogs.autocomplete import AutocompleteDropdown, AutocompleteInput
                ac_id = f"{wid}-ac"
                widget = AutocompleteInput(value=display_text, placeholder=placeholder, id=wid,
                                            disabled=disabled, compact=True, option_list_id=ac_id)
                with Horizontal(classes="bio-modelref-row"):
                    yield widget
                    yield Button(f"Pick... (ctrl+{'p' if key == 'preference' else 'f'})", id=f"{wid}-pick",
                                 compact=True)
                yield AutocompleteDropdown(id=ac_id)
            else:
                yield Input(value=display_text, placeholder=placeholder, id=wid, disabled=disabled, compact=True)
            if suffix == "limit-timeout":
                yield Static("", id=f"{wid}-hint", classes="bio-hint")
            if suffix == "limit-budget":
                yield Static("", id=f"{wid}-hint", classes="bio-hint")

    # -- mount / change handling --------------------------------------------
    def on_mount(self) -> None:
        self._refresh_preview()
        # ROOT CAUSE of "pressing Ctrl+P shows no models" (traced live):
        # Textual's own App ALWAYS registers ctrl+p as a PRIORITY binding
        # for its command palette (`textual.app.App`'s own `__init__`/
        # `action_command_palette`) -- a Screen's own `priority=True`
        # Binding on the SAME key never even runs; Textual resolves the
        # key to the App's binding first and calls `app.action_command_
        # palette()` outright (confirmed: the screen that opened was
        # `CommandPalette`, never this dialog's own `ModelPicker`, no
        # matter how `AgentBioEditor.BINDINGS` is written). Toggling
        # `app.use_command_palette` alone does not fix it either -- the
        # App's binding still "claims" the key and no-ops, so the Screen's
        # own binding STILL never fires. The actual fix: borrow the one
        # method Textual calls, `app.action_command_palette`, for exactly
        # as long as this dialog is on top -- Ctrl+P keeps opening the
        # model picker everywhere else this dialog is open (the brief:
        # "Ctrl+P / Ctrl+F stay"), and the real command palette comes back
        # the instant it closes (`on_unmount` below).
        self._restore_command_palette = self.app.action_command_palette
        self.app.action_command_palette = self.action_pick_preference
        try:
            first = self.query_one("#bio-name", Input) if self.is_new else self.query_one("#bio-description", Input)
            first.focus()
        except Exception:
            pass

    def on_unmount(self) -> None:
        try:
            self.app.action_command_palette = self._restore_command_palette
        except Exception:
            pass

    def on_input_changed(self, event) -> None:
        fid = event.input.id or ""
        if fid in ("bio-pref", "bio-fallback"):
            self._refresh_modelref_dropdown(fid, event.value)
        self._refresh_preview()

    def _refresh_modelref_dropdown(self, field_id: str, query: str) -> None:
        """Rule 3: typing into the preference/fallback field narrows the
        SAME bio-aware candidate list Ctrl+P's `ModelPicker` would open
        (`filter_models_for_bio_with_reason` -- never a second, divergent
        data source)."""
        from halo_harness.tui.dialogs.autocomplete import refresh_dropdown
        try:
            dropdown = self.query_one(f"#{field_id}-ac")
        except Exception:
            return
        candidates, _reason = filter_models_for_bio_with_reason(self.models, self._collect_form())
        refresh_dropdown(dropdown, candidates, query)

    def on_option_list_option_selected(self, event) -> None:
        oid = event.option_list.id or ""
        if oid not in ("bio-pref-ac", "bio-fallback-ac"):
            return
        from halo_harness.tui.dialogs.autocomplete import apply_pick
        field_id = oid[: -len("-ac")]
        try:
            field = self.query_one(f"#{field_id}", Input)
        except Exception:
            return
        apply_pick(field, event.option_list, str(event.option_id))
        field.focus()
        self._refresh_preview()

    def on_text_area_changed(self, _event) -> None:
        self._refresh_preview()

    def on_switch_changed(self, event) -> None:
        sid = event.switch.id or ""
        if sid.endswith("-ov"):
            field_id = sid[: -len("-ov")]
            try:
                widget = self.query_one(f"#{field_id}")
                widget.disabled = not event.switch.value
            except Exception:
                pass
        self._refresh_preview()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id or ""
        if bid == "bio-save":
            self.action_save()
        elif bid == "bio-cancel":
            self.action_cancel()
        elif bid == "bio-pref-pick":
            self.action_pick_preference()
        elif bid == "bio-fallback-pick":
            self.action_pick_fallback()
        elif bid == "bio-try":
            self.action_try_it()

    def action_try_it(self) -> None:
        """2.0.6 round 14 ("Try it" on a bio, cost shown first): the COST
        LINE prints into the hint the moment the button is pressed --
        before a single token is spent -- then the smoke call runs on a
        worker (never the UI thread) and its one-sentence reply lands in
        the same hint. The bio's own acceptance prompt is the probe when
        it has one (that is what 'try' means for a bio); otherwise the
        fixed smoke prompt."""
        from halo_harness.smoke_run import run_bio_smoke, smoke_cost_line
        pref = ""
        try:
            pref = self.query_one("#bio-pref", Input).value.strip()
        except Exception:
            pref = ""
        acceptance_prompt = None
        try:
            data = self._collect_form()
            acceptance_prompt = ((data.get("acceptance") or {}).get("prompt")
                                 if isinstance(data.get("acceptance"), dict) else None)
        except Exception:
            acceptance_prompt = None
        if not pref:
            try:
                self.query_one("#bio-hint", Static).update(
                    "Try it: no model picked yet -- pick a preference first.")
            except Exception:
                pass
            return
        cost_line = smoke_cost_line(pref)
        try:
            hint_widget = self.query_one("#bio-hint", Static)
            hint_widget.update(
                f"Try it -- cost first: {cost_line}\nrunning the smoke call...")
        except Exception:
            return

        def _work() -> None:
            out = run_bio_smoke(pref, acceptance_prompt)
            summary = (out.strip().splitlines() or [""])[-1][:200]
            verdict = "replied" if summary else "no output (credentials/model issue?)"
            try:
                # the widget is captured ON the UI thread above; only the
                # .update rides call_from_thread (query_one itself is not
                # thread-safe)
                self.app.call_from_thread(
                    hint_widget.update,
                    f"Try it -- cost first: {cost_line}\n{verdict}: {summary if summary else '-'}")
            except Exception:
                pass
        try:
            self.run_worker(_work, thread=True, name="bio-try-it", group="bio-try-it")
        except Exception:
            pass

    # -- form <-> dict -------------------------------------------------------
    def _is_overridden(self, section: str, key: str) -> bool:
        if not self.extends_from:
            return True
        try:
            return bool(self.query_one(f"#bio-{self._suffix_for(section, key)}-ov", Switch).value)
        except Exception:
            return self._has_own(section, key)

    @staticmethod
    def _suffix_for(section: str, key: str) -> "Optional[str]":
        for sec, k, _kind, suffix, _label in FIELDS:
            if sec == section and k == key:
                return suffix
        return None

    def _read_field(self, section: str, key: str, kind: str, suffix: str):
        wid = f"#bio-{suffix}"
        try:
            if kind == "bool":
                value = self.query_one(wid, Switch).value
                return ("native" if value else "off") if key == "thinking" else bool(value)
            if kind == "lines":
                text = self.query_one(wid, TextArea).text
                return [ln for ln in (text or "").splitlines() if ln.strip()]
            if kind == "list":
                text = self.query_one(wid, Input).value
                return [s.strip() for s in (text or "").split(",") if s.strip()]
            if kind == "memory":
                text = self.query_one(wid, Input).value.strip()
                return {"enabled": True, "namespace": text} if text else {"enabled": False}
            text = self.query_one(wid, Input).value.strip()
            if not text:
                return None
            if kind == "int":
                try:
                    return int(text)
                except ValueError:
                    return None
            if kind == "float":
                try:
                    return float(text)
                except ValueError:
                    return None
            return text
        except Exception:
            return None

    def _collect_form(self) -> dict:
        """The full dict that WOULD be written -- the raw bio's own
        untouched keys/sections survive (module docstring); for a child
        (`extends_from` set), an un-overridden field is simply never
        written into its section (inherits at RESOLVE time, not copied
        here) -- "only the overridden keys are written to the child
        file"."""
        data = {k: v for k, v in self.bio.items() if not k.startswith("_") and k != "name"}
        data["description"] = self.query_one("#bio-description", Input).value.strip()
        tags = [t.strip() for t in self.query_one("#bio-tags", Input).value.split(",") if t.strip()]
        if tags:
            data["tags"] = tags
        else:
            data.pop("tags", None)
        kind = self.query_one("#bio-kind", Input).value.strip()
        if kind:
            data["kind"] = kind
        else:
            data.pop("kind", None)
        extends = self.query_one("#bio-extends", Input).value.strip()
        if extends:
            data["extends"] = extends
        else:
            data.pop("extends", None)
        for section in BIO_SECTIONS:
            sec_out = dict(self.bio.get(section) or {})
            for (sec, key, kind2, suffix, _label) in FIELDS:
                if sec != section:
                    continue
                if self.extends_from and not self._is_overridden(sec, key):
                    sec_out.pop(key, None)
                    continue
                value = self._read_field(sec, key, kind2, suffix)
                if value is None:
                    sec_out.pop(key, None)
                else:
                    sec_out[key] = value
            if sec_out:
                data[section] = sec_out
            else:
                data.pop(section, None)
        return data

    # -- live preview + inline problems --------------------------------------
    def _refresh_preview(self) -> None:
        data = self._collect_form()
        name = self._current_name()
        problems: "list[str]" = []
        if not is_valid_agent_name(name):
            problems.append(f'invalid agent name {name!r}')
        problems += validate_agent_bio(data, name=name, cwd=self.cwd, state_dir=self.state_dir)
        self._last_problems = problems
        try:
            import yaml
            payload = {k: v for k, v in data.items() if not k.startswith("_")}
            self.query_one("#bio-preview", Static).update(
                yaml.safe_dump(payload, sort_keys=False, default_flow_style=False, allow_unicode=True))
        except Exception:
            pass
        self._distribute_problems(problems)
        try:
            text = self.query_one("#bio-rules", TextArea).text
            sentences = "\n".join(rule_sentence(ln) for ln in (text or "").splitlines() if ln.strip())
            self.query_one("#bio-rules-sentences", Static).update(sentences)
        except Exception:
            pass
        try:
            pref = self.query_one("#bio-pref", Input).value.strip()
            budget_text = self.query_one("#bio-limit-budget", Input).value
            self.query_one("#bio-limit-budget-hint", Static).update(budget_hint(budget_text, pref, self.models))
        except Exception:
            pass
        try:
            timeout_text = self.query_one("#bio-limit-timeout", Input).value
            self.query_one("#bio-limit-timeout-hint", Static).update(duration_hint(timeout_text))
        except Exception:
            pass

    def _distribute_problems(self, problems: "list[str]") -> None:
        buckets: "dict[str, list]" = {s: [] for s in BIO_SECTIONS}
        identity_bucket: "list[str]" = []
        for p in problems:
            low = p.lower()
            if any(w in low for w in ('"kind"', '"tags"', '"description"', '"extends"', "agent name")):
                identity_bucket.append(p)
                continue
            for s in BIO_SECTIONS:
                if f'"{s}"' in low:
                    buckets[s].append(p)
                    break
        try:
            self.query_one(f"#{_IDENTITY_HINT_ID}", Static).update("; ".join(identity_bucket))
        except Exception:
            pass
        for s in BIO_SECTIONS:
            try:
                self.query_one(f"#bio-{s}-hint", Static).update("; ".join(buckets[s]))
            except Exception:
                pass
        try:
            self.query_one("#bio-hint", Static).update("; ".join(problems) if problems else "Looks good.")
        except Exception:
            pass

    # -- model picking -------------------------------------------------------
    # `allow_agent_source=False`: a bio's own preference/fallback MUST
    # resolve to a real model (there's no "agent:" pointer at this level --
    # that's a ROLE SLOT concept, deliverable 2) -- the Agents source/"New
    # bio..." toggle belongs to the roles/org/lineup pickers, never here.
    def _open_picker(self, *, target: str) -> None:
        from halo_harness.tui.dialogs.model_picker import ModelPicker
        current = ""
        try:
            current = self.query_one(f"#bio-{'pref' if target == 'preference' else 'fallback'}", Input).value
        except Exception:
            pass
        form = self._collect_form()
        candidates, reason = filter_models_for_bio_with_reason(self.models, form)
        self.app.push_screen(ModelPicker(candidates, current=current, all_models=self.models,
                                          allow_agent_source=False, initial_hint=reason or ""),
                              lambda result: self._model_picked(target, result))

    def action_pick_preference(self) -> None:
        self._open_picker(target="preference")

    def action_pick_fallback(self) -> None:
        self._open_picker(target="fallback")

    def _model_picked(self, target: str, ref) -> None:
        if not ref:
            return
        wid = "#bio-pref" if target == "preference" else "#bio-fallback"
        try:
            self.query_one(wid, Input).value = ref
        except Exception:
            pass
        self._refresh_preview()

    def action_suggest(self) -> None:
        pref, fallback = suggest_models(self.models, state_dir=self.state_dir)
        try:
            if pref:
                self.query_one("#bio-pref", Input).value = pref
            if fallback:
                self.query_one("#bio-fallback", Input).value = fallback
        except Exception:
            pass
        self._refresh_preview()

    # -- save / cancel -----------------------------------------------------
    def action_save(self) -> None:
        name = self._current_name()
        data = self._collect_form()
        problems = []
        if not is_valid_agent_name(name):
            problems.append(f"invalid agent name {name!r}")
        problems += validate_agent_bio(data, name=name, cwd=self.cwd, state_dir=self.state_dir)
        if problems:
            self._distribute_problems(problems)
            return
        project = False
        try:
            project = bool(self.query_one("#bio-project-toggle", Switch).value)
        except Exception:
            pass
        ok, save_problems = save_agent_bio(name, data, cwd=self.cwd, state_dir=self.state_dir, project=project)
        if not ok:
            self._distribute_problems(save_problems)
            return
        self.dismiss(name)

    def action_cancel(self) -> None:
        self.dismiss(None)


def run_agent_bio_editor_standalone(name: str, *, cwd=None, state_dir=None, project: bool = False,
                                     is_new: bool = False, from_template: "Optional[str]" = None) -> "Optional[str]":
    """Deliverable 4: `halo agents new|edit <name> --form` -- the ONE
    form module run as its OWN standalone app (same reason `init_wizard.
    run_init_wizard` is standalone: a bare CLI command has no host screen
    stack), blocking until Save/Cancel. Returns the saved name, or `None`
    on cancel."""
    from textual.app import App

    from halo_harness.agents_yaml import load_agent_bio_raw
    from halo_harness.config.paths import bridge_home
    from halo_harness.providers.model_enumeration import build_model_rows
    sd = state_dir if state_dir is not None else bridge_home()
    try:
        models = build_model_rows(sd)
    except Exception:
        models = []
    raw: dict = {}
    if is_new and from_template:
        base = load_agent_bio_raw(from_template, cwd=cwd, state_dir=state_dir) or {}
        raw = {k: v for k, v in base.items() if not k.startswith("_")}
    elif not is_new:
        raw = load_agent_bio_raw(name, cwd=cwd, state_dir=state_dir) or {}

    class _AgentBioEditorApp(App):
        TITLE = "halo agents"
        result: "Optional[str]" = None

        def on_mount(self) -> None:
            def _after(saved) -> None:
                self.result = saved
                self.exit()
            self.push_screen(AgentBioEditor(name, raw, models, cwd=cwd, state_dir=state_dir,
                                             project=project, is_new=is_new), _after)

    app = _AgentBioEditorApp()
    app.run()
    return app.result
