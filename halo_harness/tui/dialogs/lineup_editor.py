"""halo_harness.tui.dialogs.lineup_editor -- Halo 2.0.5 round 2 (wizard:
agent bios and lineups), deliverable 3: the lineup (team template) editor
-- the assignments grid (role, agent-or-model via the two-source picker,
alias, instances, use_for), the other `teams_yaml.TOP_SECTIONS` as
collapsed optional groups, and the free-text `about:` field ("How the
pieces work together"). Shared by the wizard's "Roles and lineup" step
(`init_wizard.RolesStep`'s own new Lineup tab), `/teams new|edit`, and
`halo teams new|edit --form` (deliverable 4). A NEW module (hard
constraint: `init_wizard.py` gains only the registration/tab lines).

The nine `TOP_SECTIONS` beyond the assignments grid are each edited as ONE
YAML-mapping-body `TextArea` inside a `Collapsible` (its own one-line
meaning as the collapsible's title) rather than a bespoke typed widget per
field -- the brief's own field list only demands individually-typed
widgets for the assignments grid itself; every secondary section's own
"fields" still round-trip correctly (parsed with the SAME `yaml.safe_load`
every other section of this codebase already uses), just as one text
block instead of N separate inputs."""

from __future__ import annotations

from typing import Optional

from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Collapsible, Input, Static, Switch, TextArea
from textual.widgets.option_list import Option
from textual.widgets import OptionList

from halo_harness.teams_yaml import TOP_SECTIONS
from halo_harness.tui.dialogs.autocomplete import AutocompleteDropdown, AutocompleteInput, apply_pick, \
    refresh_dropdown

SECTION_MEANING = {
    "delegation": "how work is handed to sub-agents (mode, parallelism, handoff shape).",
    "routing": "which role/alias handles each kind of task.",
    "budget": "spending/turn/time caps for the whole lineup.",
    "escalation": "when and where to escalate a stuck sub-agent.",
    "context": "shared files/skills/memory every member starts with.",
    "permissions": "the lineup's own permission mode/rules/offline flag.",
    "org": "a tree of positions (titles, reporting lines) built from this SAME lineup.",
    "pipeline": "an ordered list of stages (implement -> review -> ...); order shown, gates not enforced yet.",
    "acceptance": "one smoke prompt `halo doctor --teams` runs through this lineup.",
}


def _same_gateway(ref_a: str, ref_b: str) -> bool:
    """A rough "can the fallback actually help" check: same prefix before
    the first `:` (or:/dbx:/ol:/cc:/...) -- a fallback on the SAME gateway
    as the preference can't help if that gateway itself is down. Advisory
    only (the brief's own "inline warnings that need no Governor")."""
    prefix = lambda r: r.split(":", 1)[0] if ":" in r else r  # noqa: E731
    return bool(ref_a) and bool(ref_b) and prefix(ref_a) == prefix(ref_b)


def resolved_assignment_line(entry: dict, *, cwd=None, state_dir=None, models_by_ref: "Optional[dict]" = None) -> str:
    """Fold-in "the grid shows the resolved truth per row": agent,
    preferred model, fallback, price, context, gym score when present,
    tools count."""
    from halo_harness.agents_yaml import resolve_agent_bio
    role, alias, agent_name = entry.get("role") or "?", entry.get("as"), entry.get("agent")
    label = alias or role
    if not agent_name:
        return f"{role} ({label}): (no agent)"
    bio = resolve_agent_bio(agent_name, cwd=cwd, state_dir=state_dir)
    if bio is None:
        return f"{role} ({label}): agent {agent_name!r} NOT FOUND"
    models = bio.get("models") or {}
    override = entry.get("models") or {}
    pref = override.get("preference") or models.get("preference")
    fallback = override.get("fallback") or models.get("fallback")
    parts = [f"{role} ({label}): agent={agent_name}", f"pref={pref or '?'}"]
    if fallback:
        parts.append(f"fallback={fallback}")
    row = (models_by_ref or {}).get(pref) if pref else None
    if row:
        from halo_harness.model_display import format_price_per_m, format_token_count
        price = format_price_per_m(row.get("price_in_per_m"))
        if price:
            parts.append(f"price={price}")
        ctx = format_token_count(row.get("context_tokens"))
        if ctx:
            parts.append(f"ctx={ctx}")
    tools_n = len((bio.get("tools") or {}).get("allow") or [])
    parts.append(f"tools={tools_n}")
    if pref:
        try:
            from halo_harness.gym import picker_score_suffix
            gym = picker_score_suffix(pref, state_dir=state_dir).strip()
            if gym:
                parts.append(gym)
        except Exception:
            pass
    return "  ".join(parts)


def lineup_warnings(agents: "list", *, cwd=None, state_dir=None) -> "list[str]":
    """Fold-in "inline warnings that need no Governor": a missing bio, no
    reachable model for the slot, a fallback on the same gateway host as
    the preference, a duplicate alias, two (or zero) rows with
    `role: main`. One plain sentence per problem."""
    from halo_harness.agents_yaml import resolve_agent_bio
    warnings: "list[str]" = []
    seen_alias: "dict[str, str]" = {}
    main_count = 0
    for i, e in enumerate(agents):
        if not isinstance(e, dict):
            continue
        agent_name, role, alias = e.get("agent"), e.get("role"), e.get("as")
        label = alias or role or f"#{i}"
        if agent_name:
            bio = resolve_agent_bio(agent_name, cwd=cwd, state_dir=state_dir)
            if bio is None:
                warnings.append(f"{label}: agent bio {agent_name!r} not found.")
            else:
                models = bio.get("models") or {}
                override = e.get("models") or {}
                pref = override.get("preference") or models.get("preference")
                fallback = override.get("fallback") or models.get("fallback")
                if not pref and not fallback:
                    warnings.append(f"{label}: no reachable model for this slot.")
                elif pref and fallback and _same_gateway(pref, fallback):
                    warnings.append(f"{label}: fallback {fallback!r} is on the same gateway as the "
                                     f"preference {pref!r} -- it can't help if that gateway is down.")
        if role == "main":
            main_count += 1
        if alias:
            if alias in seen_alias:
                warnings.append(f"duplicate alias {alias!r} (used by both {seen_alias[alias]!r} and {label!r}).")
            seen_alias[alias] = label
    if agents:
        if main_count > 1:
            warnings.append(f"{main_count} rows have role: main -- exactly one is expected.")
        elif main_count == 0:
            warnings.append("no row has role: main yet.")
    return warnings


def draft_about_text(template: dict) -> str:
    """Fold-in "the about text is drafted, never blank": one sentence per
    assignment plus the delegation/pipeline sections, in the house's own
    plain, declarative voice."""
    lines = []
    for e in template.get("agents") or []:
        if not isinstance(e, dict):
            continue
        label = e.get("as") or e.get("role") or "?"
        lines.append(f"{label} runs as {e.get('role') or '?'} using the {e.get('agent') or '(no agent)'!r} agent.")
    delegation = template.get("delegation") or {}
    if delegation.get("mode"):
        lines.append(f"Delegation is {delegation['mode']}.")
    stages = (template.get("pipeline") or {}).get("stages") or []
    if stages:
        order = " -> ".join(s.get("name", "?") for s in stages if isinstance(s, dict))
        lines.append(f"The pipeline runs {order}.")
    return " ".join(lines) or "This lineup has no assignments yet."


def _about_signature(template: dict) -> str:
    """What the stale marker compares against -- the lineup-SHAPE inputs
    `draft_about_text` itself reads (never the about text itself)."""
    import json
    return json.dumps({"agents": template.get("agents"), "delegation": template.get("delegation"),
                        "pipeline": template.get("pipeline")}, sort_keys=True, default=str)


class LineupEditor(ModalScreen):
    """`template`: the lineup's own RESOLVED-SHAPE dict (at minimum
    `{"agents": [...]}` -- `teams_yaml.load_team_template_raw`'s own
    shape, `roles:` shorthand already expanded, is also accepted). `models`:
    the enumerated catalog, reused verbatim (never re-enumerated)."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
        Binding("ctrl+s", "save", "Save", show=True, priority=True),
        Binding("ctrl+n", "add_assignment", "Add assignment", show=True, priority=True),
        Binding("ctrl+d", "delete_assignment", "Delete assignment", show=True, priority=True),
        Binding("ctrl+p", "pick_agent_or_model", "Pick agent/model", show=True, priority=True),
        Binding("ctrl+g", "draft_about", "Draft the about text", show=True, priority=True),
    ]
    DEFAULT_CSS = """
    LineupEditor { align: center middle; }
    LineupEditor > Horizontal { width: 97%; height: 94%; border: round $primary; background: $surface; }
    LineupEditor #lineup-left-pane { width: 42%; padding: 1 2; border-right: solid $primary-darken-1; }
    LineupEditor #lineup-right-pane { width: 58%; padding: 1 2; }
    LineupEditor #lineup-assignments { height: 10; margin-top: 1; }
    LineupEditor #lineup-warnings { color: $warning; margin-top: 1; }
    LineupEditor #lineup-roles-projection { color: $text-muted; margin-top: 1; height: auto; max-height: 10; }
    LineupEditor .lineup-field-row { height: 3; }
    LineupEditor TextArea { height: 4; margin-bottom: 1; }
    LineupEditor #lineup-about { height: 5; }
    LineupEditor #lineup-about-stale { color: $warning; }
    LineupEditor .wizard-extra-buttons { height: 3; margin-top: 1; }
    LineupEditor .wizard-extra-buttons Button { margin-right: 1; }
    """

    def __init__(self, name: str, template: dict, models: "list[dict]", *, cwd=None, state_dir=None,
                 project: bool = False, is_new: bool = False) -> None:
        super().__init__()
        self.lineup_name = name  # NOT self.name -- see agent_bio_editor.py's own comment on this trap
        self.template = dict(template or {})
        self.template.setdefault("agents", [])
        self.models = models or []
        self._models_by_ref = {m.get("ref"): m for m in self.models if isinstance(m, dict) and m.get("ref")}
        self.cwd, self.state_dir, self.project, self.is_new = cwd, state_dir, project, is_new
        self._current_index: "Optional[int]" = None
        self._about_drafted_signature: "Optional[str]" = None
        self._pending_pick_field: "Optional[str]" = None

    def _agents(self) -> "list[dict]":
        return [e for e in self.template.get("agents") or [] if isinstance(e, dict)]

    # -- compose -------------------------------------------------------------
    def compose(self):
        with Horizontal():
            with Vertical(id="lineup-left-pane"):
                title = "New lineup" if self.is_new else f"Lineup: {self.lineup_name}"
                yield Static(title, classes="dialog-title")
                # 2.0.7 wizard deep review: the ONE plain sentence a
                # first-time user needs before any field.
                yield Static("A lineup is the role table: each row picks the model (and effort) for one "
                              "job. It applies when custom roles are ON and this lineup is active.",
                              id="lineup-what-sentence")
                yield Static("Ctrl+N add  |  Ctrl+D delete  |  Ctrl+P pick agent/model  |  Ctrl+G draft about  |  "
                              "Ctrl+S save  |  Esc cancel", classes="dialog-subtitle")
                yield OptionList(id="lineup-assignments")
                with Horizontal(classes="wizard-extra-buttons"):
                    yield Button("Add", id="lineup-add")
                    yield Button("Remove", id="lineup-remove")
                yield Static("", id="lineup-warnings")
                # 2.0.7 wizard deep review: visible consequences -- what
                # each row costs, while it's being edited, not after.
                yield Static("Costs, while you pick (per 1M tokens, in+out -- what each row spends "
                              "when it fires):", classes="dialog-subtitle")
                yield Static("", id="lineup-cost-footer")
                yield Static("Roles table (read-only projection -- edited through the lineup above):",
                              classes="dialog-subtitle")
                yield Static("", id="lineup-roles-projection")
            with VerticalScroll(id="lineup-right-pane"):
                yield Static("Selected assignment", classes="bio-section-title")
                with Horizontal(classes="lineup-field-row"):
                    yield Static("Role -- which job this row picks the model for (coder, reviewer, ...)")
                yield Input(id="lineup-field-role")
                with Horizontal(classes="lineup-field-row"):
                    yield Static("Agent or model (Ctrl+P to pick) -- what runs that job; a price shows in Costs")
                with Horizontal():
                    yield AutocompleteInput(id="lineup-field-agent", option_list_id="lineup-field-agent-ac")
                    yield Button("Pick...", id="lineup-field-agent-pick")
                yield AutocompleteDropdown(id="lineup-field-agent-ac")
                with Horizontal(classes="lineup-field-row"):
                    yield Static("Alias (as) -- the name positions/bios call this role by")
                yield Input(id="lineup-field-as")
                with Horizontal(classes="lineup-field-row"):
                    yield Static("Instances -- how many copies may run at once")
                yield Input(id="lineup-field-instances")
                with Horizontal(classes="lineup-field-row"):
                    yield Static("Use for (comma-separated task kinds)")
                yield Input(id="lineup-field-use-for")
                yield Static("Other sections (collapsed -- each is a short YAML mapping body):",
                              classes="bio-section-title")
                for section in TOP_SECTIONS:
                    with Collapsible(title=f"{section}: {SECTION_MEANING.get(section, '')}",
                                      id=f"lineup-collapsible-{section}"):
                        yield TextArea(id=f"lineup-section-{section}")
                yield Static("How the pieces work together (about):", classes="bio-section-title")
                yield TextArea(id="lineup-about")
                with Horizontal(classes="wizard-extra-buttons"):
                    yield Button("Draft (ctrl+g)", id="lineup-about-draft")
                    yield Button("Smoke run (cost first)", id="lineup-smoke", compact=True)
                yield Static("", id="lineup-about-stale")
                with Horizontal(classes="wizard-extra-buttons"):
                    yield Switch(value=self.project, id="lineup-project-toggle")
                    yield Static(" Save to project scope (.halo/teams/)", classes="wizard-switch-label")
                with Horizontal(classes="wizard-extra-buttons"):
                    yield Button("Save (ctrl+s)", id="lineup-save", variant="primary")
                    yield Button("Cancel (esc)", id="lineup-cancel")
                yield Static("", id="lineup-hint")

    def on_mount(self) -> None:
        for section in TOP_SECTIONS:
            self._set_section_text(section, self.template.get(section))
        about = self.template.get("about") or ""
        self.query_one("#lineup-about", TextArea).text = about
        if about:
            self._about_drafted_signature = _about_signature(self.template)
        self._refresh_assignments()
        self._refresh_roles_projection()
        self._update_stale_marker()
        # Same fix as `agent_bio_editor.AgentBioEditor.on_mount` (see its
        # own comment for the root cause): Textual's App ALWAYS claims
        # ctrl+p for its command palette as a priority binding, which a
        # Screen's own `priority=True` Binding on the same key can never
        # win against -- borrow `app.action_command_palette` for this
        # dialog's own lifetime instead of renaming the chord.
        self._restore_command_palette = self.app.action_command_palette
        self.app.action_command_palette = self.action_pick_agent_or_model
        try:
            self.query_one("#lineup-assignments", OptionList).focus()
        except Exception:
            pass

    def on_unmount(self) -> None:
        try:
            self.app.action_command_palette = self._restore_command_palette
        except Exception:
            pass

    # -- the 9 TOP_SECTIONS, each a YAML-mapping-body TextArea --------------
    def _set_section_text(self, section: str, value) -> None:
        import yaml
        text = "" if not value else yaml.safe_dump(value, sort_keys=False, default_flow_style=False,
                                                     allow_unicode=True)
        try:
            self.query_one(f"#lineup-section-{section}", TextArea).text = text
        except Exception:
            pass

    def _section_dict(self, section: str) -> "Optional[dict]":
        import yaml
        try:
            text = self.query_one(f"#lineup-section-{section}", TextArea).text
        except Exception:
            return self.template.get(section)
        if not text.strip():
            return None
        try:
            parsed = yaml.safe_load(text)
        except yaml.YAMLError:
            return self.template.get(section)  # kept as-was; action_save's own validate_team_template still runs
        return parsed if isinstance(parsed, dict) else self.template.get(section)

    # -- assignments list ----------------------------------------------------
    def _refresh_assignments(self) -> None:
        try:
            option_list = self.query_one("#lineup-assignments", OptionList)
        except Exception:
            return
        option_list.clear_options()
        for e in self._agents():
            option_list.add_option(Option(resolved_assignment_line(e, cwd=self.cwd, state_dir=self.state_dir,
                                                                     models_by_ref=self._models_by_ref)))
        if self._agents():
            idx = self._current_index if self._current_index is not None else 0
            idx = min(idx, len(self._agents()) - 1)
            option_list.highlighted = idx
            self._load_assignment(idx)
        else:
            self._current_index = None
        self._refresh_warnings()
        self._refresh_cost_footer()

    def _refresh_cost_footer(self) -> None:
        """2.0.7 wizard deep review: visible consequences -- per role, the
        model's own price from the picker rows (when the enumerated
        catalog carries one), so the cost of a lineup is on screen WHILE
        it's edited, never discovered on the first bill. A model the
        catalog doesn't price (a local `ol:` lane, an unknown id) shows
        'free/unknown' -- never a fabricated number."""
        from halo_harness.model_display import format_price_per_m
        lines = []
        for e in self._agents():
            label = e.get("role") or e.get("as") or "?"
            ref = e.get("model") or e.get("agent") or ""
            row = self._models_by_ref.get(ref) if ref else None
            if row:
                pin, pout = row.get("price_in_per_m"), row.get("price_out_per_m")
                if pin is not None or pout is not None:
                    lines.append(f"{label}: {format_price_per_m(pin)} in / {format_price_per_m(pout)} out")
                    continue
            lines.append(f"{label}: {ref or '(unset)'} -- free/unknown price")
        try:
            self.query_one("#lineup-cost-footer", Static).update(
                "\n".join(lines) or "(no rows yet -- Ctrl+N adds the first)")
        except Exception:
            pass

    def _show_note(self, text: str) -> None:
        """2.0.6 round 14: the smoke-run status line -- the warnings
        static, prefixed so a warnings refresh never eats it silently."""
        try:
            self.query_one("#lineup-warnings", Static).update(text)
        except Exception:
            pass

    def _refresh_warnings(self) -> None:
        warnings = lineup_warnings(self._agents(), cwd=self.cwd, state_dir=self.state_dir)
        try:
            self.query_one("#lineup-warnings", Static).update("\n".join(warnings))
        except Exception:
            pass

    def _refresh_roles_projection(self) -> None:
        """Fold-in "one source of truth": `teams_yaml.resolve_role_table`'s
        own projection -- READ-ONLY here (the lineup above is where a role
        actually gets edited)."""
        from halo_harness.teams_yaml import resolve_role_table
        role_table, notes = resolve_role_table(self.template, cwd=self.cwd, state_dir=self.state_dir)
        lines = [f"{k}: {v if isinstance(v, str) else v.get('model')}" for k, v in sorted(role_table.items())]
        lines.extend(f"(note) {n}" for n in notes)
        try:
            self.query_one("#lineup-roles-projection", Static).update("\n".join(lines) or "(no roles resolved yet)")
        except Exception:
            pass

    def _update_stale_marker(self) -> None:
        """Fold-in "the about text is drafted and marked stale": shown
        once a draft exists AND the lineup's own shape has since changed."""
        try:
            static = self.query_one("#lineup-about-stale", Static)
        except Exception:
            return
        if self._about_drafted_signature is None:
            static.update("")
            return
        static.update("" if self._about_drafted_signature == _about_signature(self.template)
                      else "stale -- redraft (ctrl+g) or edit the about text.")

    def _highlighted_index(self) -> "Optional[int]":
        try:
            option_list = self.query_one("#lineup-assignments", OptionList)
        except Exception:
            return None
        return option_list.highlighted

    def _load_assignment(self, index: int) -> None:
        agents = self._agents()
        if index is None or not (0 <= index < len(agents)):
            return
        self._current_index = index
        e = agents[index]
        self.query_one("#lineup-field-role", Input).value = e.get("role") or ""
        self.query_one("#lineup-field-agent", Input).value = e.get("agent") or ""
        self.query_one("#lineup-field-as", Input).value = e.get("as") or ""
        self.query_one("#lineup-field-instances", Input).value = str(e.get("instances") or "")
        self.query_one("#lineup-field-use-for", Input).value = ", ".join(e.get("use_for") or [])

    def _commit_current_assignment(self) -> None:
        if self._current_index is None:
            return
        agents = self._agents()
        if not (0 <= self._current_index < len(agents)):
            return
        e = agents[self._current_index]
        e["role"] = self.query_one("#lineup-field-role", Input).value.strip() or e.get("role") or "subagent"
        agent_val = self.query_one("#lineup-field-agent", Input).value.strip()
        if agent_val:
            e["agent"] = agent_val
        else:
            e.pop("agent", None)
        alias = self.query_one("#lineup-field-as", Input).value.strip()
        if alias:
            e["as"] = alias
        else:
            e.pop("as", None)
        instances_text = self.query_one("#lineup-field-instances", Input).value.strip()
        if instances_text:
            try:
                e["instances"] = int(instances_text)
            except ValueError:
                pass
        else:
            e.pop("instances", None)
        use_for = [t.strip() for t in self.query_one("#lineup-field-use-for", Input).value.split(",") if t.strip()]
        if use_for:
            e["use_for"] = use_for
        else:
            e.pop("use_for", None)

    # -- events --------------------------------------------------------------
    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        if event.option_list.id == "lineup-field-agent-ac":
            field = self.query_one("#lineup-field-agent", Input)
            apply_pick(field, event.option_list, str(event.option_id))
            field.focus()
            self._commit_current_assignment()
            self._refresh_assignments()
            self._refresh_roles_projection()
            self._update_stale_marker()
            return
        if event.option_list.id != "lineup-assignments":
            return
        self._commit_current_assignment()
        self._load_assignment(event.option_list.highlighted)
        self._refresh_assignments()

    def on_input_changed(self, event: Input.Changed) -> None:
        field_id = event.input.id or ""
        if field_id == "lineup-field-agent":
            self._refresh_agent_dropdown(event.value)
        if field_id.startswith("lineup-field-"):
            # vibes/review.md finding 66: the commit+reload used to run on
            # EVERY keystroke -- committing re-reads every field through
            # .strip()/int()/comma-split and the reload writes the parsed
            # value back, so a space or comma was eaten the instant it was
            # typed. The live keystroke now only marks the form stale;
            # `_commit_current_assignment` runs on submit/blur/pick (the
            # places that already call it) and on save.
            self._update_stale_marker()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if (event.input.id or "").startswith("lineup-field-"):
            self._commit_current_assignment()
            self._refresh_assignments()
            self._refresh_roles_projection()
            self._update_stale_marker()

    def on_blur(self, event) -> None:
        from textual.widgets import Input as _Input
        if isinstance(event.widget, _Input) and (event.widget.id or "").startswith("lineup-field-"):
            self._commit_current_assignment()
            self._refresh_assignments()

    def _refresh_agent_dropdown(self, query: str) -> None:
        """Rule 3: autocomplete here suggests BIO NAMES (what this field
        actually holds -- `teams_yaml`'s own `agents:` entries always
        name a bio, never a bare model ref; Ctrl+P's Models source still
        auto-creates one via `agents_yaml.ensure_bio_for_model`)."""
        from halo_harness.agents_yaml import list_agent_bios
        try:
            names = list_agent_bios(cwd=self.cwd, state_dir=self.state_dir)
        except Exception:
            names = []
        refresh_dropdown(self.query_one("#lineup-field-agent-ac"), [{"ref": n} for n in names], query)

    def on_text_area_changed(self, event) -> None:
        tid = getattr(event.text_area, "id", "") or ""
        if tid.startswith("lineup-section-"):
            section = tid[len("lineup-section-"):]
            self.template[section] = self._section_dict(section)
            self._refresh_roles_projection()
            self._update_stale_marker()
        elif tid == "lineup-about":
            self._update_stale_marker()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id or ""
        if bid == "lineup-add":
            self.action_add_assignment()
        elif bid == "lineup-remove":
            self.action_delete_assignment()
        elif bid == "lineup-field-agent-pick":
            self.action_pick_agent_or_model()
        elif bid == "lineup-about-draft":
            self.action_draft_about()
        elif bid == "lineup-smoke":
            self.action_smoke_run()
        elif bid == "lineup-save":
            self.action_save()
        elif bid == "lineup-cancel":
            self.action_cancel()

    # -- assignment add/delete ------------------------------------------------
    def action_add_assignment(self) -> None:
        self._commit_current_assignment()
        agents = self.template.setdefault("agents", [])
        agents.append({"role": "subagent"})
        self._current_index = len(agents) - 1
        self._refresh_assignments()
        self._update_stale_marker()

    def action_delete_assignment(self) -> None:
        if self._current_index is None:
            return
        agents = self.template.get("agents") or []
        if 0 <= self._current_index < len(agents):
            agents.pop(self._current_index)
        self._current_index = None
        self._refresh_assignments()
        self._update_stale_marker()

    # -- picking an agent-or-model for the selected assignment ---------------
    def action_pick_agent_or_model(self) -> None:
        from halo_harness.tui.dialogs.model_picker import ModelPicker
        current = ""
        try:
            current = self.query_one("#lineup-field-agent", Input).value
        except Exception:
            pass
        self.app.push_screen(ModelPicker(self.models, current=current, cwd=self.cwd, state_dir=self.state_dir),
                              self._agent_or_model_picked)

    def _agent_or_model_picked(self, result) -> None:
        """`teams_yaml`'s own `agents:` entries always name a BIO, never a
        bare model ref -- picking "Models" here auto-creates (or reuses)
        a tiny pinning bio via `agents_yaml.ensure_bio_for_model` (the
        brief's own "one role by model" is this UI's convenience over
        that same bio-only schema, not a second slot on the entry)."""
        if not result:
            return
        if isinstance(result, dict) and result.get("new_bio"):
            self._open_new_bio_then_pick()
            return
        if isinstance(result, dict):
            agent_name = result.get("agent") or ""
        else:
            from halo_harness.agents_yaml import ensure_bio_for_model
            agent_name = ensure_bio_for_model(result, cwd=self.cwd, state_dir=self.state_dir) or ""
        try:
            self.query_one("#lineup-field-agent", Input).value = agent_name
        except Exception:
            pass
        self._commit_current_assignment()
        self._refresh_assignments()

    def _open_new_bio_then_pick(self) -> None:
        from halo_harness.tui.dialogs.agent_bio_editor import AgentBioEditor
        import uuid
        new_name = f"new-bio-{uuid.uuid4().hex[:8]}"
        self.app.push_screen(AgentBioEditor(new_name, {}, self.models, cwd=self.cwd, state_dir=self.state_dir,
                                             is_new=True),
                              lambda saved: self._agent_or_model_picked({"agent": saved}) if saved else None)

    # -- draft the about text -------------------------------------------------
    def action_smoke_run(self) -> None:
        """2.0.6 round 14 (the lineup smoke run, cost shown first): every
        distinct model the lineup resolves to gets its cost line printed
        BEFORE anything runs, then each member's own acceptance prompt
        (the same probe `halo doctor --teams` exercises) fires on a
        worker through the real print-mode subprocess path. The result
        note lands beside the warnings when the worker finishes."""
        from halo_harness.smoke_run import smoke_cost_line
        agents = self._agents()
        prefs = []
        for e in agents:
            if isinstance(e, dict):
                ov = e.get("models") or {}
                pref = (ov.get("preference")
                        or ((self._bio_models(e.get("agent")) or {}).get("preference")))
                if isinstance(pref, str) and pref.strip() and pref not in prefs:
                    prefs.append(pref.strip())
        if not prefs:
            self._show_note("Smoke run: no models resolve in this lineup yet -- pick preferences first.")
            return
        cost_lines = [smoke_cost_line(p) for p in prefs]
        self._show_note("Smoke run -- cost first:\n  " + "\n  ".join(cost_lines)
                   + "\nrunning " + str(len(prefs)) + " smoke call(s) on a worker...")

        def _work() -> None:
            from halo_harness.agents_doctor import run_all_acceptance
            results = run_all_acceptance(
                names=[e.get("agent") for e in agents if isinstance(e, dict) and e.get("agent")])
            summary = "; ".join(f"{n}: {'ok' if ok else m[:40]}" for n, ok, m in results) or "nothing ran"
            try:
                self.app.call_from_thread(
                    self._show_note,
                    "Smoke run -- cost first:\n  " + "\n  ".join(cost_lines)
                    + "\nresults: " + summary[:400])
            except Exception:
                pass
        try:
            self.run_worker(_work, thread=True, name="lineup-smoke", group="lineup-smoke")
        except Exception:
            pass

    @staticmethod
    def _bio_models(agent_name):
        from halo_harness.agents_yaml import resolve_agent_bio
        try:
            bio = resolve_agent_bio(agent_name, cwd=None, state_dir=None) or {}
        except Exception:
            return {}
        m = bio.get("models")
        return m if isinstance(m, dict) else {}

    def action_draft_about(self) -> None:
        self._commit_current_assignment()
        text = draft_about_text(self.template)
        try:
            self.query_one("#lineup-about", TextArea).text = text
        except Exception:
            pass
        self._about_drafted_signature = _about_signature(self.template)
        self._update_stale_marker()

    # -- save / cancel --------------------------------------------------------
    def action_save(self) -> None:
        from halo_harness.teams_yaml import save_team_template, validate_team_template
        self._commit_current_assignment()
        data = {k: v for k, v in self.template.items() if not k.startswith("_")}
        for section in TOP_SECTIONS:
            value = self._section_dict(section)
            if value:
                data[section] = value
            else:
                data.pop(section, None)
        about = self.query_one("#lineup-about", TextArea).text.strip()
        if about:
            data["about"] = about
        else:
            data.pop("about", None)
        name = self.lineup_name
        problems = validate_team_template(data, name=name, cwd=self.cwd, state_dir=self.state_dir)
        if problems:
            self.query_one("#lineup-hint", Static).update("; ".join(problems))
            return
        project = bool(self.query_one("#lineup-project-toggle", Switch).value)
        ok, save_problems = save_team_template(name, data, cwd=self.cwd, state_dir=self.state_dir, project=project)
        if not ok:
            self.query_one("#lineup-hint", Static).update("; ".join(save_problems))
            return
        # A bare statement, NOT `lambda _r: self.dismiss(name)` -- that
        # lambda's own return value would be `self.dismiss(name)`'s own
        # (awaitable) return value, which Textual then tries to AWAIT from
        # inside this very callback and raises `ScreenError: Can't await
        # screen.dismiss() from the screen's message handler` (confirmed
        # live). A `def` with a bare-statement body returns `None`.
        def _finish(_activated) -> None:
            self.dismiss(name)
        self.app.push_screen(_ActivateLineupConfirm(name), _finish)

    def action_cancel(self) -> None:
        self.dismiss(None)


class _ActivateLineupConfirm(ModalScreen):
    """"Save ... asks whether to make it the active team:"."""

    BINDINGS = [Binding("escape", "no", "No", show=False), Binding("n", "no", "No", show=False),
                Binding("y", "yes", "Yes", show=False)]
    DEFAULT_CSS = """
    _ActivateLineupConfirm { align: center middle; }
    _ActivateLineupConfirm > Vertical { width: 70; height: auto; border: round $primary; background: $surface;
                                          padding: 1 2; }
    _ActivateLineupConfirm Horizontal { height: 3; align: right middle; margin-top: 1; }
    _ActivateLineupConfirm Button { margin-left: 1; }
    """

    def __init__(self, name: str) -> None:
        super().__init__()
        self.lineup_name = name

    def compose(self):
        with Vertical():
            yield Static(f"Saved {self.lineup_name!r}. Make it the active team? [y/N]", classes="dialog-title")
            with Horizontal():
                yield Button("No", id="confirm-no")
                yield Button("Yes, activate", id="confirm-yes", variant="primary")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self._resolve(event.button.id == "confirm-yes")

    def action_yes(self) -> None:
        self._resolve(True)

    def action_no(self) -> None:
        self._resolve(False)

    def _resolve(self, activate: bool) -> None:
        if activate:
            from halo_harness.theme import set_config_value
            set_config_value("team", self.lineup_name)
        self.dismiss(activate)


def run_lineup_editor_standalone(name: str, *, cwd=None, state_dir=None, project: bool = False,
                                  is_new: bool = False, from_template: "Optional[str]" = None) -> "Optional[str]":
    """Deliverable 4: `halo teams new|edit <name> --form` -- the ONE form
    module run as its own standalone app, same reasoning as `agent_bio_
    editor.run_agent_bio_editor_standalone`."""
    from textual.app import App

    from halo_harness.config.paths import bridge_home
    from halo_harness.providers.model_enumeration import build_model_rows
    from halo_harness.teams_yaml import load_team_template_raw
    sd = state_dir if state_dir is not None else bridge_home()
    try:
        models = build_model_rows(sd)
    except Exception:
        models = []
    template: dict = {}
    if is_new and from_template:
        base = load_team_template_raw(from_template, cwd=cwd, state_dir=state_dir) or {}
        template = {k: v for k, v in base.items() if not k.startswith("_") and k != "roles"}
    elif not is_new:
        template = load_team_template_raw(name, cwd=cwd, state_dir=state_dir) or {}

    class _LineupEditorApp(App):
        TITLE = "halo teams"
        result: "Optional[str]" = None

        def on_mount(self) -> None:
            def _after(saved) -> None:
                self.result = saved
                self.exit()
            self.push_screen(LineupEditor(name, template, models, cwd=cwd, state_dir=state_dir,
                                           project=project, is_new=is_new), _after)

    app = _LineupEditorApp()
    app.run()
    return app.result


def team_rows(*, cwd=None, state_dir=None) -> "list[dict]":
    """Deliverable 4: `[{"name", "scope", "description", "active"}, ...]`
    -- the `/teams`/`--form` list screen's own pure row builder, the
    `bio_rows()` of this module."""
    from halo_harness.teams_yaml import ensure_builtin_team_templates, find_team_template_path, \
        list_team_templates, resolve_team_template
    from halo_harness.theme import get_config_value
    ensure_builtin_team_templates(state_dir=state_dir)
    active = get_config_value("team", default=None)
    rows = []
    for name in list_team_templates(cwd=cwd, state_dir=state_dir):
        found = find_team_template_path(name, cwd=cwd, state_dir=state_dir)
        template = resolve_team_template(name, cwd=cwd, state_dir=state_dir) or {}
        # 2.0.7 wizard deep review: the role COUNT rides every row (the
        # "what the lineup is" half; the editor's cost footer is the
        # price half) -- resolved from the same template, so the shipped
        # `roles:` shorthand and a full `agents:` list both count right.
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
    """Deliverable 4: `/teams` (list, new, edit, activate) and `halo teams
    --form` open this standalone screen -- same shape `agents_step.
    AgentsListScreen` uses for bios."""

    BINDINGS = [Binding("escape", "cancel", "Close", show=False)]
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
            yield Static("Enter/Edit: open  |  New/Activate  |  Esc: close", classes="dialog-subtitle")
            self._rows = team_rows(cwd=self.cwd, state_dir=self.state_dir)
            yield OptionList(*[Option(_team_row_label(r), id=r["name"]) for r in self._rows], id="teams-list")
            with Horizontal(classes="wizard-extra-buttons"):
                yield Button("New", id="teams-new", variant="primary")
                yield Button("Edit", id="teams-edit")
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
        self._open_editor(is_new=False)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id or ""
        if bid == "teams-new":
            self._open_editor(is_new=True)
        elif bid == "teams-edit":
            self._open_editor(is_new=False)
        elif bid == "teams-activate":
            self._activate_highlighted()

    def _open_editor(self, *, is_new: bool) -> None:
        from halo_harness.teams_yaml import load_team_template_raw
        if is_new:
            import uuid
            name, template = f"lineup-{uuid.uuid4().hex[:6]}", {}
        else:
            name = self._highlighted_name()
            if name is None:
                self._hint("Highlight a lineup first.")
                return
            template = load_team_template_raw(name, cwd=self.cwd, state_dir=self.state_dir) or {}
        self.app.push_screen(LineupEditor(name, template, self.models, cwd=self.cwd, state_dir=self.state_dir,
                                           is_new=is_new),
                              lambda _saved: self._refresh())

    def _activate_highlighted(self) -> None:
        name = self._highlighted_name()
        if name is None:
            self._hint("Highlight a lineup first.")
            return
        from halo_harness.teams_yaml import validate_team_template, resolve_team_template
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


def run_teams_list_standalone(*, cwd=None, state_dir=None) -> None:
    """Deliverable 4: `halo teams --form` with no name."""
    from textual.app import App

    from halo_harness.config.paths import bridge_home
    from halo_harness.providers.model_enumeration import build_model_rows
    sd = state_dir if state_dir is not None else bridge_home()
    try:
        models = build_model_rows(sd)
    except Exception:
        models = []

    class _TeamsListApp(App):
        TITLE = "halo teams"

        def on_mount(self) -> None:
            self.push_screen(TeamsListScreen(cwd=cwd, state_dir=state_dir, models=models), lambda _r: self.exit())

    _TeamsListApp().run()
