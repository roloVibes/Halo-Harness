"""halo_harness.tui.dialogs.team_step_actions -- Halo 2.1.0 round B1: the
non-layout half of `team_step.TeamStep` (split out to keep both files under
the house write cap): the row builder, Customize/New/Agents actions and the
commit that applies the highlighted row. `TeamStep` supplies
`_highlighted_lineup_name`, `_refresh_lineups` and `self.state`."""

from __future__ import annotations

from halo_harness.tui.dialogs import team_preview as tp
from halo_harness.tui.dialogs.wizard_ux import toast
from textual.widgets import Static


def _lineup_row_label(r: dict) -> str:
    mark = "✓ " if r["active"] else ""
    desc = f": {r['description']}" if r["description"] else ""
    roles = r.get("roles")
    count = f"  · {roles} role{'s' if roles != 1 else ''}" if isinstance(roles, int) else ""
    return f"{mark}{r['name']} [{r['scope']}]{count}{desc}"



class TeamActionsMixin:
    # -- helpers shared with the lineup editor --------------------------------
    def _models_for_picker(self) -> list:
        if self.state.enumeration_done:
            return self.state.enumerated_models
        list_models = getattr(getattr(self.app, "controller", None), "list_models", None)
        try:
            rows = list_models() if callable(list_models) else []
        except Exception:
            rows = []
        if not rows:
            from halo_harness.tui.dialogs.agents_step import _cache_only_model_rows
            rows = _cache_only_model_rows()
            self.state.enumerated_models, self.state.enumeration_done = rows, True
        return rows

    def _rows(self) -> "list[dict]":
        from halo_harness.roles import roles_mode_enabled
        from halo_harness.tui.dialogs.lineup_editor import team_rows
        rows = team_rows(cwd=self.state.cwd)
        off = not roles_mode_enabled()
        if off:
            for r in rows:
                r["active"] = False
        one = {"name": tp.ONE_MODEL_ID, "scope": "", "active": off or not any(r["active"] for r in rows),
               "description": "", "roles": None}
        return [one, *rows]

    def _label(self, r: dict) -> str:
        if r["name"] == tp.ONE_MODEL_ID:
            return f"{'✓ ' if r['active'] else ''}{tp.ONE_MODEL_LABEL}: the default model runs every job"
        return _lineup_row_label(r)

    # -- actions ----------------------------------------------------------------
    def _hint(self, text: str) -> None:
        toast(self.query_one("#wiz-team-lineup-hint", Static), text)

    def action_new_lineup(self) -> None:
        self._open_editor(f"lineup-{__import__('uuid').uuid4().hex[:6]}", {}, True)

    def action_customize(self) -> None:
        """A shipped lineup is duplicated into user scope first (same name,
        so it shadows the shipped one -- the Duplicate action's semantic)."""
        name = self._highlighted_lineup_name()
        if name is None or name == tp.ONE_MODEL_ID:
            self._hint("Highlight a lineup to customize it, or press New lineup.")
            return
        from halo_harness.teams_yaml import find_team_template_path, load_team_template_raw, save_team_template
        raw = load_team_template_raw(name, cwd=self.state.cwd) or {}
        found = find_team_template_path(name, cwd=self.state.cwd)
        if found and found[1] == "template":
            save_team_template(name, raw, cwd=self.state.cwd)
        self._open_editor(name, raw, False)

    def _open_editor(self, name: str, template: dict, is_new: bool) -> None:
        from halo_harness.tui.dialogs.lineup_editor import LineupEditor

        def _after(saved) -> None:
            self._refresh_lineups()
            if saved:
                self._hint(f"Saved lineup {saved!r}.")
        self.app.push_screen(LineupEditor(name, template, self._models_for_picker(), cwd=self.state.cwd,
                                           is_new=is_new), _after)

    def _open_agents(self) -> None:
        from halo_harness.tui.dialogs.agents_step import AgentsListScreen
        self.app.push_screen(AgentsListScreen(cwd=self.state.cwd, state_dir=None,
                                               models=self._models_for_picker()))

    # -- commit -----------------------------------------------------------------
    def commit(self) -> None:
        from halo_harness.roles import set_roles_enabled
        name = self._highlighted_lineup_name()
        if name is None:
            return
        if name == tp.ONE_MODEL_ID:
            self._commit_lineup("standard")
            set_roles_enabled(False)
            return
        if self._commit_lineup(name):
            set_roles_enabled(True)

    def _commit_lineup(self, name: str) -> bool:
        from halo_harness.teams_yaml import apply_team_template, ensure_builtin_team_templates, \
            resolve_role_table, resolve_team_template
        ensure_builtin_team_templates()
        ok, problems, notes = apply_team_template(name, cwd=self.state.cwd)
        if not ok:
            self.state.written.append(f"could not apply lineup {name!r}: {'; '.join(problems)}")
            return False
        self.state.written.append(f"lineup {name!r} applied (roles.*, team: {name!r})"
                                   + (f" -- {'; '.join(notes)}" if notes else ""))
        session = getattr(getattr(self.app, "controller", None), "session", None)
        template = resolve_team_template(name, cwd=self.state.cwd) if session is not None else None
        if template:
            role_table, _notes = resolve_role_table(template, cwd=self.state.cwd)
            live = getattr(getattr(session, "agent_runtime", None), "role_table", None)
            if isinstance(live, dict):
                live.update(role_table)
            elif isinstance(getattr(session, "roles", None), dict):
                session.roles.update(role_table)
        return True


