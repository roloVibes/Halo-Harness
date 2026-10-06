"""halo_harness.tui.dialogs.roles_editor -- `/roles edit <name>` (Halo
2.0.2 brief A.5): one row per role (every built-in `roles.ROLE_NAMES` plus
any custom name the template already defines), each showing its current
model/effort. Enter on a row opens the SAME `ModelPicker` `/model` uses to
pick that row's model; an inline effort `Input` then appears, pre-filled
with the row's current effort (or blank), validated against the harness's
own accepted effort words. `ctrl+s` saves back to the named template
(`roles.save_role_template`) and dismisses with `True`; Escape cancels
with no write, dismissing with `False`. `tui/slash.py::_handle_roles`
builds this with the template's already-loaded `roles` dict and
`controller.list_models()`'s own catalog -- never loads either itself, so
it stays unit-testable with a plain fake `models` list.
"""

from __future__ import annotations

from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, OptionList, Static, TabbedContent, TabPane
from textual.widgets.option_list import Option

from halo_harness.tui.dialogs.autocomplete import AutocompleteDropdown, AutocompleteInput, hide_dropdown, \
    refresh_dropdown


class RolesEditor(ModalScreen):
    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
        Binding("ctrl+s", "save", "Save", show=True),
        # Halo 2.0.4 round 4 (deliverable 4): "one key fills every role
        # from a preset" -- applies the Auto tab's own HIGHLIGHTED option
        # into the form, from anywhere in this screen (not just while
        # that tab/list has focus), same reach `ctrl+s` already has.
        Binding("ctrl+a", "auto_apply", "Auto-fill highlighted preset", show=True),
    ]
    DEFAULT_CSS = """
    RolesEditor { align: center middle; }
    RolesEditor > Vertical { width: 90%; height: 80%; border: round $primary; background: $surface; padding: 1 2; }
    RolesEditor TabbedContent { height: 1fr; }
    RolesEditor #roles-list { height: 1fr; }
    RolesEditor #roles-template-picker { height: 5; margin-bottom: 1; }
    RolesEditor #roles-effort-input { display: none; }
    RolesEditor #roles-save-as-input { display: none; }
    RolesEditor #roles-save-as-row { height: 3; margin-top: 1; }
    RolesEditor #roles-auto-list { height: 6; margin-top: 1; }
    RolesEditor #roles-auto-preview { height: 1fr; margin-top: 1; border: round $primary-darken-1; padding: 1; }
    """

    def __init__(self, template_name: str, roles: dict, models: list, *, description: str = "") -> None:
        super().__init__()
        self.template_name = template_name
        self.roles = dict(roles)
        self.models = models
        self.description = description
        self._pending_role = None
        self._pending_model = None
        # Halo 2.0.5 round 2 (deliverable 2): set only when the pick came
        # from the picker's Agents source -- `role_value_parts`/`_
        # normalize_role_value` carry it through as a bare `agent` key
        # beside `model`/`effort` (same precedented pattern that function
        # already uses for `escalation`).
        self._pending_agent = None
        self._auto_options: list = []

    def _all_role_names(self) -> list:
        from halo_harness.roles import ROLE_NAMES
        names = list(ROLE_NAMES)
        for name in self.roles:
            if name not in names:
                names.append(name)
        return names

    def compose(self):
        from textual.containers import Horizontal
        with Vertical():
            title = f"Role template: {self.template_name}"
            if self.description:
                title += f" -- {self.description}"
            yield Static(title, classes="dialog-title")
            yield Static("Enter: pick a model for the highlighted role  |  ctrl+a: auto-fill  |  "
                          "ctrl+s: save  |  Esc: cancel", classes="dialog-subtitle")
            # Halo 2.0.4 round 4 (deliverable 4): the "Auto" tab -- "one
            # key fills every role from a preset (local-first, balanced,
            # quality) or from `halo gym propose` when gym data exists,
            # shows the resulting table with one sentence per choice,
            # lets the user adjust, then Save." "Roles" stays the FIRST,
            # initially-active tab so every existing `#roles-list`/
            # `#roles-template-picker` interaction (and the tests pinning
            # them) is completely unaffected by this tab existing at all.
            with TabbedContent(initial="roles-tab-form"):
                with TabPane("Roles", id="roles-tab-form"):
                    # Halo 2.0.2 round 7 (init wizard brief, item 2): "the
                    # roles editor gains the template picker at its top" --
                    # choosing one REPLACES the form's current roles with
                    # that template's own (`_apply_template`), it does not
                    # merge; ctrl+s still saves to THIS SAME
                    # `template_name`, never the one picked from here.
                    yield Static("Start from a template (replaces the roles below):", classes="dialog-subtitle")
                    yield OptionList(id="roles-template-picker")
                    # Round 2c (deliverable 3, rule 3): a quick inline
                    # model autocomplete for the HIGHLIGHTED role below --
                    # Enter here assigns it (the same effort prompt the
                    # modal `ModelPicker` flow already shows); Ctrl+P on a
                    # highlighted role still opens that full picker too.
                    yield Static("Quick model filter for the highlighted role below:", classes="dialog-subtitle")
                    yield AutocompleteInput(placeholder="Type to filter models...", id="roles-quick-filter",
                                             option_list_id="roles-quick-filter-ac")
                    yield AutocompleteDropdown(id="roles-quick-filter-ac")
                    yield OptionList(id="roles-list")
                    yield Input(placeholder="", id="roles-effort-input")
                    with Horizontal(id="roles-save-as-row"):
                        yield Button("Save as template...", id="roles-save-as-button")
                    yield Input(placeholder="New template name, Enter to save a copy", id="roles-save-as-input")
                with TabPane("Auto", id="roles-tab-auto"):
                    yield Static("Fill every role at once -- a built-in preset, or `halo gym propose`'s own "
                                  "picks when this machine has saved gym data. Replaces the form below; adjust "
                                  "there, then ctrl+s to save.", classes="dialog-subtitle")
                    yield OptionList(id="roles-auto-list")
                    yield Static("", id="roles-auto-preview")
                    yield Button("Apply (ctrl+a)", id="roles-auto-apply-button", variant="primary")
            yield Static("", id="roles-hint")

    def on_mount(self) -> None:
        self._refresh_list()
        self._refresh_template_picker()
        self._refresh_auto_picker()
        # The template picker sits ABOVE #roles-list in DOM order, so
        # Textual's own "focus the first focusable widget" default would
        # otherwise land there instead -- #roles-list is the form's own
        # main focus (Enter there opens the model picker for the
        # highlighted ROLE), unchanged from before this picker existed.
        self.query_one("#roles-list", OptionList).focus()

    def _row_text(self, name: str) -> str:
        from halo_harness.roles import role_value_parts
        value = self.roles.get(name)
        model, effort = role_value_parts(value)
        if not model:
            return f"{name}: (unset -- session model)"
        text = f"{name}: {model}" + (f" ({effort})" if effort else "")
        agent = value.get("agent") if isinstance(value, dict) else None
        return f"{text}  agent:{agent}" if agent else text

    def _refresh_list(self) -> None:
        option_list = self.query_one("#roles-list", OptionList)
        highlighted = option_list.highlighted
        option_list.clear_options()
        for name in self._all_role_names():
            option_list.add_option(Option(self._row_text(name), id=name))
        if highlighted is not None and highlighted < len(option_list.options):
            option_list.highlighted = highlighted

    def _refresh_template_picker(self) -> None:
        # Deliberately NEVER calls `ensure_builtin_role_presets()` here --
        # this round-1 form (any `/roles edit <name>`) must not manufacture
        # the three round-7 preset files as a side effect of simply being
        # OPENED; that belongs to the wizard's own Roles step, the actual
        # "setting up with presets" entry point. This picker shows
        # whatever already exists, same as it would before presets existed.
        from halo_harness.roles import list_role_templates
        picker = self.query_one("#roles-template-picker", OptionList)
        picker.clear_options()
        for name in list_role_templates():
            picker.add_option(Option(name, id=name))
        if not picker.option_count:
            picker.add_option(Option("(no saved templates yet)", disabled=True))

    def _refresh_auto_picker(self) -> None:
        """Halo 2.0.4 round 4 (deliverable 4): computed FRESH every time
        this screen opens (never written to disk, unlike the template
        picker just above -- `roles.auto_fill_options` is a pure,
        in-memory read, so opening this tab is never the thing that
        manufactures the three builtin preset FILES; that stays the
        wizard's own Roles step's job, same boundary `_refresh_template_
        picker`'s own comment already draws)."""
        from halo_harness.roles import auto_fill_options
        try:
            self._auto_options = auto_fill_options()
        except Exception:
            self._auto_options = []
        picker = self.query_one("#roles-auto-list", OptionList)
        picker.clear_options()
        for opt in self._auto_options:
            picker.add_option(Option(opt["label"], id=opt["key"]))
        if not picker.option_count:
            picker.add_option(Option("(no presets available)", disabled=True))
            return
        picker.highlighted = 0
        self._update_auto_preview(self._auto_options[0]["key"])

    def _auto_option(self, key: str) -> "dict | None":
        return next((o for o in self._auto_options if o["key"] == key), None)

    def _highlighted_auto_key(self) -> "str | None":
        try:
            picker = self.query_one("#roles-auto-list", OptionList)
        except Exception:
            return None
        if picker.highlighted is None:
            return None
        opt = picker.get_option_at_index(picker.highlighted)
        return str(opt.id) if opt.id else None

    def _update_auto_preview(self, key: str) -> None:
        try:
            preview = self.query_one("#roles-auto-preview", Static)
        except Exception:
            return
        opt = self._auto_option(key)
        if opt is None:
            preview.update("(no such preset)")
            return
        lines = [opt["description"]] if opt.get("description") else []
        lines.extend(opt.get("lines") or [])
        preview.update("\n".join(lines))

    def action_auto_apply(self) -> None:
        """"one key fills every role from a preset" -- REPLACES
        `self.roles` with the HIGHLIGHTED Auto option's own (never
        merges, same "start from" rule the template picker above already
        follows), then shows the resulting table so the user can see
        and adjust it ("Roles" tab, `#roles-list`) before ctrl+s. A
        legacy role-table-with-no-files wizard save migrates these exact
        values into `~/.halo/agents/*.yaml` on the FIRST such save (round
        4 deliverable 7) -- this tab makes no files of its own either
        way."""
        key = self._highlighted_auto_key()
        if key is None:
            return
        opt = self._auto_option(key)
        if opt is None:
            return
        self.roles = dict(opt.get("roles") or {})
        self._refresh_list()
        try:
            self.query_one(TabbedContent).active = "roles-tab-form"
        except Exception:
            pass
        self.query_one("#roles-hint", Static).update(
            f"Auto-filled from {opt['label']!r} -- adjust below, then ctrl+s to save.")
        self.query_one("#roles-list", OptionList).focus()

    def on_option_list_option_highlighted(self, event) -> None:
        if event.option_list.id == "roles-auto-list" and event.option_id:
            self._update_auto_preview(str(event.option_id))

    def _highlighted_role_name(self) -> "str | None":
        try:
            option_list = self.query_one("#roles-list", OptionList)
        except Exception:
            return None
        if option_list.highlighted is None:
            return None
        opt = option_list.get_option_at_index(option_list.highlighted)
        return str(opt.id) if opt.id else None

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "roles-quick-filter":
            refresh_dropdown(self.query_one("#roles-quick-filter-ac"), self.models, event.value)

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        if event.option_list.id == "roles-quick-filter-ac":
            ref = str(event.option_id)
            role_name = self._highlighted_role_name()
            hide_dropdown(event.option_list)
            try:
                quick_filter = self.query_one("#roles-quick-filter", Input)
                quick_filter.value = ""
            except Exception:
                pass
            if role_name:
                self._model_picked(role_name, ref)
            return
        if event.option_list.id == "roles-template-picker":
            if event.option_id:
                self._apply_template(str(event.option_id))
            return
        if event.option_list.id == "roles-auto-list":
            self.action_auto_apply()
            return
        role_name = str(event.option_id)
        from halo_harness.roles import role_value_parts
        from halo_harness.tui.dialogs.model_picker import ModelPicker
        current_model, _effort = role_value_parts(self.roles.get(role_name))
        self.app.push_screen(ModelPicker(self.models, current=current_model or ""),
                              lambda result: self._model_picked(role_name, result))

    def _apply_template(self, name: str) -> None:
        """Round 7, item 2: "choose a template, the form prefills" --
        REPLACES `self.roles` with the template's own (never merges), so
        the form genuinely reflects just that template once picked; the
        description only fills in when this editor started with none, so
        a template already named here is never silently overwritten."""
        from halo_harness.roles import load_role_template
        template = load_role_template(name)
        if template is None:
            self.query_one("#roles-hint", Static).update(f"No such template: {name!r}")
            return
        self.roles = dict(template["roles"])
        if not self.description:
            self.description = template.get("description") or ""
        self._refresh_list()
        self.query_one("#roles-hint", Static).update(f"Loaded template {name!r} into the form -- ctrl+s "
                                                       f"saves it as {self.template_name!r}.")

    def _model_picked(self, role_name: str, result) -> None:
        """`result` is `None` (cancelled), a bare model-ref string (the
        Models source, unchanged since before this round), or -- Halo
        2.0.5 round 2 deliverable 2 -- a `{"agent", "model"}` dict (a bio
        picked from the Agents source) or `{"new_bio": True}` ("New
        bio..." -- opens the bio editor, then treats its own save exactly
        like picking that freshly-created bio, "returns with the new bio
        selected")."""
        if not result:
            return
        if isinstance(result, dict) and result.get("new_bio"):
            self._open_new_bio_for(role_name)
            return
        if isinstance(result, dict):
            agent_name, ref = result.get("agent"), result.get("model") or ""
        else:
            agent_name, ref = None, result
        if not ref:
            return
        from halo_harness.roles import role_value_parts
        self._pending_role, self._pending_model, self._pending_agent = role_name, ref, agent_name
        _model, effort = role_value_parts(self.roles.get(role_name))
        effort_input = self.query_one("#roles-effort-input", Input)
        label = f"agent={agent_name}, model={ref}" if agent_name else f"model={ref}"
        effort_input.placeholder = f"Effort for {role_name} (Enter for none), {label}"
        effort_input.value = effort or ""
        effort_input.styles.display = "block"
        effort_input.focus()

    def _open_new_bio_for(self, role_name: str) -> None:
        from halo_harness.tui.dialogs.agent_bio_editor import AgentBioEditor
        import uuid
        new_name = f"new-bio-{uuid.uuid4().hex[:8]}"
        self.app.push_screen(
            AgentBioEditor(new_name, {}, self.models, is_new=True),
            lambda saved: self._model_picked(role_name, self._bio_pick_result(saved)) if saved else None)

    @staticmethod
    def _bio_pick_result(bio_name: str) -> "dict | None":
        if not bio_name:
            return None
        from halo_harness.agents_yaml import resolve_agent_bio
        bio = resolve_agent_bio(bio_name) or {}
        models = bio.get("models") or {}
        return {"agent": bio_name, "model": models.get("preference") or models.get("fallback") or ""}

    def _ref_known(self, ref: str) -> bool:
        """Halo 2.0.4 round 4 (deliverable 2): `ModelPicker`'s own filter
        Input accepts a typed ref with zero matches on Enter (see its
        `on_input_submitted`) -- that ref never came from a row in
        `self.models`, so it carries none of the enumerated catalog's own
        group/price/gym-score data. Never refused, just noted (see
        `on_input_submitted` below, the one place this is actually
        reported -- AFTER the effort step, not here, since that same
        handler's own existing `hint.update("")` on a successful commit
        would otherwise wipe a note set any earlier than that)."""
        known_refs = {m.get("ref") for m in self.models if isinstance(m, dict) and m.get("ref")}
        return ref in known_refs

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "roles-save-as-button":
            save_as_input = self.query_one("#roles-save-as-input", Input)
            save_as_input.styles.display = "block"
            save_as_input.focus()
        elif event.button.id == "roles-auto-apply-button":
            self.action_auto_apply()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "roles-save-as-input":
            self._save_as(event.value.strip())
            return
        if self._pending_role is None:
            return
        effort = event.value.strip()
        from halo_harness.providers.profiles import EFFORT_LEVELS
        hint = self.query_one("#roles-hint", Static)
        if effort and effort not in EFFORT_LEVELS:
            hint.update(f"Not a recognized effort level: {effort!r} (expected one of {', '.join(EFFORT_LEVELS)}, "
                        f"or blank for the route's own default)")
            return
        picked_ref = self._pending_model
        picked_agent = self._pending_agent
        # Halo 2.0.5 round 2 (deliverable 2): "In a legacy role table a
        # bio pick stores the bio's resolved preference as the model and
        # `agent: <name>` beside it" -- `roles._normalize_role_value` now
        # carries an `agent` key through a save/reload round trip the same
        # way it already does `effort`/`escalation`.
        if picked_agent or effort:
            value = {"model": picked_ref}
            if effort:
                value["effort"] = effort
            if picked_agent:
                value["agent"] = picked_agent
            self.roles[self._pending_role] = value
        else:
            self.roles[self._pending_role] = picked_ref
        self._pending_role = self._pending_model = self._pending_agent = None
        event.input.value = ""
        event.input.styles.display = "none"
        # Deliverable 2: the note names the FINAL, actually-committed ref
        # -- shown here (not back in `_model_picked`) so it survives this
        # same method's own commit, instead of being overwritten by it.
        hint.update("" if self._ref_known(picked_ref) else
                    f"{picked_ref!r} is not in the enumerated list; kept as typed.")
        self._refresh_list()
        self.query_one("#roles-list", OptionList).focus()

    def _save_as(self, name: str) -> None:
        """Round 7, item 2: "Save as template..." -- a COPY of the
        form's current roles under a NEW name, distinct from ctrl+s
        (which always saves to `self.template_name`); the input hides
        again either way, and a successful save refreshes the picker so
        the new name shows up immediately."""
        input_widget = self.query_one("#roles-save-as-input", Input)
        hint = self.query_one("#roles-hint", Static)
        if not name:
            hint.update("Save as template: enter a name first.")
            return
        from halo_harness.roles import save_role_template
        ok, problems = save_role_template(name, {"description": self.description, "roles": self.roles})
        input_widget.value = ""
        input_widget.styles.display = "none"
        if not ok:
            hint.update("Could not save: " + "; ".join(problems))
            return
        hint.update(f"Saved a copy as template {name!r}.")
        self._refresh_template_picker()
        self.query_one("#roles-list", OptionList).focus()

    def action_save(self) -> None:
        from halo_harness.roles import save_role_template
        ok, problems = save_role_template(self.template_name, {"description": self.description, "roles": self.roles})
        if not ok:
            self.query_one("#roles-hint", Static).update("Could not save: " + "; ".join(problems))
            return
        self.dismiss(True)

    def action_cancel(self) -> None:
        self.dismiss(False)
