"""tests.test_team_preview -- Halo 2.1.0 round B1: `tui/dialogs/team_preview.py`
(`preview_lines`, `cost_hint`, `applied_summary_lines`), the plain-text
lineup tree the Team step, the Summary step and (round B2) `halo teams
preview` share. Hermetic: scoped `BRIDGE_TEST_HOME`/`BRIDGE_STATE_DIR`, a
fixture price catalog passed in directly, no network."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all

test, TESTS = new_registry()

CATALOG = {
    "or:vendor/pricey": {"ref": "or:vendor/pricey", "price_in_per_m": 10.0, "price_out_per_m": 30.0,
                         "context_tokens": 200000},
    "or:vendor/mid": {"ref": "or:vendor/mid", "price_in_per_m": 10.0, "price_out_per_m": 10.0,
                      "context_tokens": 128000},
    "ol:local": {"ref": "ol:local", "context_tokens": 32000},
}


class _Env:
    def __enter__(self):
        self._saved = {k: os.environ.get(k) for k in ("BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR")}
        d = Path(tempfile.mkdtemp(prefix="team-preview-"))
        os.environ["BRIDGE_TEST_HOME"] = str(d)
        os.environ["BRIDGE_STATE_DIR"] = str(d / ".halo")
        self.state_dir, self.cwd = d / ".halo", d / "project"
        self.cwd.mkdir(parents=True, exist_ok=True)
        return self

    def __exit__(self, *exc):
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


@test
def test_cost_hint_with_every_price_known(ctx: Ctx):
    from halo_harness.tui.dialogs.team_preview import cost_hint
    table = {"main": "or:vendor/pricey", "coder": {"model": "or:vendor/mid", "effort": "high"}}
    out = cost_hint(table, models_by_ref=CATALOG)
    ctx.check(f"the average of $0.26 and $0.22, got {out!r}", out == "Roughly $0.24 per turn at these prices")


@test
def test_cost_hint_names_every_model_without_a_price(ctx: Ctx):
    from halo_harness.tui.dialogs.team_preview import cost_hint
    out = cost_hint({"main": "or:vendor/pricey", "small": "ol:local", "judge": "or:vendor/missing"},
                    models_by_ref=CATALOG)
    ctx.check(f"names the unpriced models, got {out!r}",
              out == "price unknown for ol:local, or:vendor/missing")
    ctx.check("never prints a dollar figure when a price is missing", "$" not in out)
    empty = cost_hint({}, models_by_ref=CATALOG)
    ctx.check(f"an empty table is not blank, got {empty!r}", "price unknown" in empty)


@test
def test_preview_lines_for_every_shipped_lineup(ctx: Ctx):
    from halo_harness.teams_yaml import ensure_builtin_team_templates, list_bundled_team_templates, \
        resolve_team_template
    from halo_harness.tui.dialogs.team_preview import preview_lines
    with _Env() as e:
        ensure_builtin_team_templates(state_dir=e.state_dir)
        names = list_bundled_team_templates()
        ctx.check(f"six lineups ship, got {names}", len(names) == 6)
        for name in names:
            lines = preview_lines(name, cwd=e.cwd, state_dir=e.state_dir, models_by_ref={})
            tree = [ln for ln in lines if " -> " in ln]
            roles = len(resolve_team_template(name, cwd=e.cwd, state_dir=e.state_dir).get("agents") or [])
            ctx.check(f"{name}: one tree line per role ({roles}), got {len(tree)}", len(tree) == roles and roles > 0)
            ctx.check(f"{name}: starts with its name, got {lines[0]!r}", lines[0].startswith(name))
            ctx.check(f"{name}: ends with a cost line, got {lines[-1]!r}",
                      "per turn" in lines[-1] or "price unknown" in lines[-1])
            ctx.check(f"{name}: plain text, no markup", not any("[bold" in ln or "[/" in ln for ln in lines))


@test
def test_preview_lines_one_model_names_the_default(ctx: Ctx):
    from halo_harness.tui.dialogs.team_preview import ONE_MODEL_ID, preview_lines
    with _Env():
        text = " ".join(preview_lines(ONE_MODEL_ID, default_model="or:vendor/mid", width=200))
        ctx.check(f"names the default model, got {text!r}", "or:vendor/mid" in text)
        ctx.check("says everything and sub-agents", "everything" in text and "sub-agents" in text)


@test
def test_preview_lines_show_price_context_about_and_warnings(ctx: Ctx):
    from halo_harness.teams_yaml import user_teams_dir
    from halo_harness.agents_yaml import user_agents_dir
    from halo_harness.tui.dialogs.team_preview import preview_lines
    with _Env() as e:
        agents = user_agents_dir(e.state_dir)
        agents.mkdir(parents=True, exist_ok=True)
        (agents / "pinned.yaml").write_text(
            "name: pinned\ndescription: pinned bio\nversion: '1'\nkind: main\n"
            "models:\n  preference: or:vendor/pricey\n  fallback: or:vendor/mid\ntools: {}\n", encoding="utf-8")
        teams = user_teams_dir(e.state_dir)
        teams.mkdir(parents=True, exist_ok=True)
        (teams / "mine.yaml").write_text(
            "name: mine\ndescription: my lineup\nversion: '1'\nabout: Plans big, codes cheap.\n"
            "agents:\n  - {role: main, agent: pinned}\n  - {role: coder, agent: ghost-agent}\n", encoding="utf-8")
        lines = preview_lines("mine", cwd=e.cwd, state_dir=e.state_dir, width=200, models_by_ref=CATALOG)
        text = "\n".join(lines)
        ctx.check(f"the about text is shown, got {text!r}", "Plans big, codes cheap." in text)
        ctx.check(f"the tree carries price and context, got {text!r}",
                  "main -> pinned -> or:vendor/pricey" in text and "$10.00/M in" in text and "ctx 200k" in text)
        ctx.check("a missing agent is a warning line", any(ln.startswith("warning:") and "ghost-agent" in ln
                                                           for ln in lines))
        ctx.check(f"the cost line is last, got {lines[-1]!r}", lines[-1].startswith("Roughly $"))


@test
def test_preview_lines_unknown_lineup_never_raises(ctx: Ctx):
    from halo_harness.tui.dialogs.team_preview import preview_lines
    with _Env() as e:
        lines = preview_lines("no-such-lineup", cwd=e.cwd, state_dir=e.state_dir, models_by_ref={})
        ctx.check(f"a plain sentence, got {lines!r}", len(lines) == 1 and "no such lineup" in lines[0])


@test
def test_applied_summary_lines_follow_the_config(ctx: Ctx):
    from halo_harness.roles import set_roles_enabled
    from halo_harness.teams_yaml import apply_team_template, ensure_builtin_team_templates
    from halo_harness.tui.dialogs.team_preview import applied_summary_lines
    with _Env() as e:
        ensure_builtin_team_templates(state_dir=e.state_dir)
        set_roles_enabled(False)
        off = applied_summary_lines(cwd=e.cwd, state_dir=e.state_dir, default_model="or:vendor/mid")
        ctx.check(f"roles off is the one-model line, got {off!r}",
                  off == ["One model for everything: or:vendor/mid"])
        apply_team_template("balanced", cwd=e.cwd, state_dir=e.state_dir)
        set_roles_enabled(True)
        on = applied_summary_lines(cwd=e.cwd, state_dir=e.state_dir, default_model="or:vendor/mid")
        ctx.check(f"roles on names the lineup, got {on!r}", on[0] == "Lineup: balanced")


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
