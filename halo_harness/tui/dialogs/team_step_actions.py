"""halo_harness.tui.dialogs.team_step_actions -- Halo 2.1.0 round B1: the
non-layout half of `team_step.TeamStep` (split out to keep both files under
the house write cap): the row builder, the View / Edit in Studio / New /
Agents actions and the commit that applies the highlighted row. `TeamStep`
supplies `_highlighted_lineup_name`, `_refresh_lineups` and `self.state`.
3.1.1.0 R3: Studio is the one editor of lineups: Enter shows the highlighted
lineup read-only (`LineupView`), Edit in Studio opens Studio on it
(`halo studio --edit lineup:<name>`, tui/studio_open.py), New writes a starter
lineup and opens Studio on it."""

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
    # -- helpers shared with the lineup view ---------------------------------
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
        from halo_harness.tui.dialogs.teams_list import team_rows
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
    def _hint(self, text: str, *, persist: bool = False) -> None:
        toast(self.query_one("#wiz-team-lineup-hint", Static), text, persist=persist)

    def action_new_lineup(self) -> None:
        from halo_harness.tui import studio_open
        name, problems = studio_open.new_lineup(cwd=self.state.cwd)
        if not name:
            self._hint("; ".join(problems), persist=True)
            return
        self._refresh_lineups()
        self._studio(name)

    def action_customize(self) -> None:
        """Edit in Studio (Ctrl+E): Studio's Roles on the highlighted lineup (a shipped one saves as your copy)."""
        name = self._highlighted_lineup_name()
        if name is None or name == tp.ONE_MODEL_ID:
            self._hint("Highlight a lineup to edit it in Studio, or press New lineup (Ctrl+N).")
            return
        self._studio(name)

    def _studio(self, name: str) -> None:
        from halo_harness.tui import studio_open
        studio_open.open_target(self, f"lineup:{name}", cwd=self.state.cwd,
                                on_line=lambda line: self._hint(line, persist=True))

    def _open_view(self, name: str) -> None:
        if name == tp.ONE_MODEL_ID:
            self._hint("One model for everything has no lineup to show: Next uses the default model for every job.")
            return
        from halo_harness.tui.dialogs.lineup_editor import LineupView
        self.app.push_screen(LineupView(name, None, self._models_for_picker(), cwd=self.state.cwd),
                             lambda _r: self._refresh_lineups())

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


