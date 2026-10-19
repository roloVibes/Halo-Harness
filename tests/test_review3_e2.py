"""tests.test_review3_e2 -- 3.0.2.0 review fix pass, round E (session data),
part 2: the config, role, bio/team and design-project writers.

  * review item 75  the game-theme toggle-off rewrote config.json 0644
  * review item 80  role/bio/team writers truncated in place and raised
  * review item 41  a torn design.json read was saved back over the project
"""
from __future__ import annotations

import json
import os
import stat
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all
from tests.helpers.provider_env_defaults import ensure_scoped_state_dir_once

ensure_scoped_state_dir_once()

test, TESTS = new_registry()


class _StateDir:
    """Scope BRIDGE_STATE_DIR to a fresh directory for one test; restores
    the previous value (or its absence) afterwards."""

    def __enter__(self) -> Path:
        self.saved = os.environ.get("BRIDGE_STATE_DIR")
        self.path = Path(tempfile.mkdtemp(prefix="r3e2-state-"))
        os.environ["BRIDGE_STATE_DIR"] = str(self.path)
        return self.path

    def __exit__(self, *exc):
        if self.saved is None:
            os.environ.pop("BRIDGE_STATE_DIR", None)
        else:
            os.environ["BRIDGE_STATE_DIR"] = self.saved
        return False


def _temp_leftovers(d: Path) -> list:
    return [p.name for p in d.iterdir() if ".tmp" in p.name]


# ---- item 75: toggle-off keeps config.json private ----------------------------

@test
def test_i75_game_theme_toggle_off_keeps_config_private_and_atomic(ctx: Ctx):
    from halo_harness import theme as theme_mod
    from halo_harness.theme_toggle import PREVIOUS_KEY, toggle_game_theme
    with _StateDir() as state:
        cfg = state / "config.json"
        cfg.write_text(json.dumps({"theme": "doom", PREVIOUS_KEY: "claude-dark", "ollama": {"token": "x"}}),
                       encoding="utf-8")
        if os.name != "nt":
            cfg.chmod(0o600)
        restored = toggle_game_theme("doom", "doom")
        data = json.loads(cfg.read_text(encoding="utf-8"))
        ctx.check(f"the previous theme came back, got {restored!r}", restored == "claude-dark")
        ctx.check("the remembered key is gone, other keys kept",
                  PREVIOUS_KEY not in data and data.get("ollama") == {"token": "x"})
        ctx.check(f"no temp file left, got {_temp_leftovers(state)}", _temp_leftovers(state) == [])
        if os.name != "nt":
            ctx.check(f"config.json stays 0600, got {oct(stat.S_IMODE(cfg.stat().st_mode))}",
                      stat.S_IMODE(cfg.stat().st_mode) == 0o600)
        ctx.check("the config path is the scoped one", theme_mod._config_path() == cfg)


# ---- item 80: writers never raise, never truncate in place ---------------------

@test
def test_i80_role_template_into_a_blocked_dir_returns_a_problem(ctx: Ctx):
    from halo_harness.roles import role_templates_dir, save_role_template
    state = Path(tempfile.mkdtemp(prefix="r3e2-roles-"))
    role_templates_dir(state).write_text("not a directory", encoding="utf-8")
    ok, problems = save_role_template("mine", {"roles": {}}, state_dir=state)
    ctx.check(f"(False, [...]) instead of raising, got {(ok, problems)}",
              ok is False and problems and "cannot write" in problems[0])


@test
def test_i80_role_template_save_is_atomic(ctx: Ctx):
    from halo_harness.roles import load_role_template, role_templates_dir, save_role_template
    state = Path(tempfile.mkdtemp(prefix="r3e2-roles-ok-"))
    ok, _ = save_role_template("mine", {"description": "first", "roles": {}}, state_dir=state)
    ok2, _ = save_role_template("mine", {"description": "second", "roles": {}}, state_dir=state)
    ctx.check("both saves succeed", ok and ok2)
    loaded = load_role_template("mine", state_dir=state)
    ctx.check(f"the second save is what is on disk, got {loaded!r}", (loaded or {}).get("description") == "second")
    ctx.check("no temp file left", _temp_leftovers(role_templates_dir(state)) == [])


@test
def test_i80_bio_and_team_writers_into_a_blocked_dir_return_problems(ctx: Ctx):
    from halo_harness.agents_yaml import save_agent_bio, user_agents_dir
    from halo_harness.teams_yaml import save_team_template, user_teams_dir
    state = Path(tempfile.mkdtemp(prefix="r3e2-bios-"))
    ok, problems = save_agent_bio("bob", {"description": "a bio"}, state_dir=state)
    ctx.check(f"a normal bio save works, got {(ok, problems)}", ok)
    ctx.check("no temp file left beside the bio", _temp_leftovers(user_agents_dir(state)) == [])
    user_teams_dir(state).write_text("not a directory", encoding="utf-8")
    ok, problems = save_team_template("crew", {"description": "t", "agents": [{"agent": "bob", "role": "main"}]},
                                      state_dir=state)
    ctx.check(f"save_team_template returns a problem, got {(ok, problems)}",
              ok is False and problems and "cannot write" in problems[0])
    blocked = Path(tempfile.mkdtemp(prefix="r3e2-bios-blocked-"))
    user_agents_dir(blocked).write_text("not a directory", encoding="utf-8")
    ok, problems = save_agent_bio("bob", {"description": "a bio"}, state_dir=blocked)
    ctx.check(f"save_agent_bio returns a problem, got {(ok, problems)}",
              ok is False and problems and "cannot write" in problems[0])


# ---- item 41: design.json is never rewritten from a torn read -------------------

def _project():
    from halo_harness.design.store import Project
    state = Path(tempfile.mkdtemp(prefix="r3e2-design-"))
    return Project.create("Landing page", model="or:mock/design", systems=["brand"], state_dir=state)


@test
def test_i41_unparsable_design_json_is_left_alone(ctx: Ctx):
    from halo_harness.design.store import UnreadableFile
    p = _project()
    (p.path / "artboards" / "hero").mkdir(parents=True)
    (p.path / "artboards" / "hero" / "index.html").write_text("<p>hi</p>", encoding="utf-8")
    torn = '{"name": "Landing page", "created": "2026'
    (p.path / "design.json").write_text(torn, encoding="utf-8")
    ctx.check("discover_artboards registers nothing", p.discover_artboards() == [])
    p.snapshot(note="after a turn")
    ctx.check("snapshot never rewrites the torn file",
              (p.path / "design.json").read_text(encoding="utf-8") == torn)
    for name, call in (("add_artboard", lambda: p.add_artboard("Footer")),
                       ("remove_artboard", lambda: p.remove_artboard("hero"))):
        try:
            call()
            raised = False
        except UnreadableFile:
            raised = True
        ctx.check(f"{name} refuses instead of saving over it", raised)
    ctx.check("design.json is still byte-for-byte what it was",
              (p.path / "design.json").read_text(encoding="utf-8") == torn)


@test
def test_i41_good_design_json_keeps_name_model_and_systems(ctx: Ctx):
    p = _project()
    (p.path / "artboards" / "hero").mkdir(parents=True)
    (p.path / "artboards" / "hero" / "index.html").write_text("<p>hi</p>", encoding="utf-8")
    found = p.discover_artboards()
    meta = p.meta()
    ctx.check(f"the folder was registered, got {found!r}", [a["id"] for a in found] == ["hero"])
    ctx.check("name, model and systems survive", meta.get("name") == "Landing page"
              and meta.get("model") == "or:mock/design" and meta.get("systems") == ["brand"])
    ctx.check("no temp file left", _temp_leftovers(p.path) == [])


@test
def test_i41_torn_comments_and_controls_are_not_overwritten(ctx: Ctx):
    from halo_harness.design.store import UnreadableFile
    p = _project()
    (p.path / "comments.json").write_text("[{\"id\": \"c1\"", encoding="utf-8")
    d = p.artboard_dir("hero")
    d.mkdir(parents=True)
    (d / "controls.json").write_text("[{\"name\": \"gap\"", encoding="utf-8")
    for name, call in (("add_comment", lambda: p.add_comment("hero", "bigger")),
                       ("resolve_comments", lambda: p.resolve_comments(["c1"])),
                       ("set_control", lambda: p.set_control("hero", "gap", 4))):
        try:
            call()
            raised = False
        except UnreadableFile:
            raised = True
        ctx.check(f"{name} refuses instead of saving over the torn file", raised)
    ctx.check("comments.json untouched", (p.path / "comments.json").read_text(encoding="utf-8") == "[{\"id\": \"c1\"")
    ctx.check("controls.json untouched", (d / "controls.json").read_text(encoding="utf-8") == "[{\"name\": \"gap\"")
    ctx.check("lenient readers still answer", p.comments() == [] and p.controls("hero") == [])


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
