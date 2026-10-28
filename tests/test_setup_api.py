"""tests.test_setup_api -- Studio's Setup section routes (Halo 3.3.0.0 R1,
studio/setup_api.py, studio/setup_state.py, lineup_choice.py) through
`api.dispatch` over a scratch home; no model call, no network:

1. `GET setup/state`: every block's value and rows (the wizard's four
   permission modes, the six terminal themes with their palettes, the eight
   provider tabs by name, the lineups with One model first and auto the
   default), and no key in it even with one set in the environment;
2. `POST setup/config`: a key outside model / permission_mode / theme is a
   422; a bad mode, theme or model is a 422 with `problems` and nothing is
   written; a good one lands in config.json and the state says so;
3. `POST setup/team`: one-model (team removed, roles off), auto (roles on, no
   team), a lineup (roles.*, team, roles on), auto over a set team (the
   wizard's rule: team auto), an unknown lineup 422; the preview route;
4. the wizard's Team step commits through the same function;
5. methods and unknown paths.
Run: python -m tests.test_setup_api
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
PREFIXES = ("OPENROUTER_", "DATABRICKS_", "ANTHROPIC_", "OPENAI_", "TYPESAFE_", "EXPLABS_", "HF_", "HALO_SECRET_", "BRIDGE_STATE_DIR",
            "HALO_ENV_FILE", "BRIDGE_ENV_FILE")
MOCK_ROWS = [{"ref": "or:mock/alpha", "provider": "openrouter", "detail": "Mock Alpha", "price": "$1.00", "context": "128k",
              "best_at": {"line": "code, review", "kinds": ["code"]}},
             {"ref": "or:mock/beta", "provider": "openrouter", "detail": "Mock Beta", "price": "?", "context": "?", "best_at": {}}]


class _Env:
    """A scratch home (BRIDGE_TEST_HOME) with every provider variable taken out of the environment and put back."""

    def __init__(self, rows=None):
        self.rows = rows

    def __enter__(self):
        self._saved = {k: v for k, v in os.environ.items() if k.startswith(PREFIXES) or k == "BRIDGE_TEST_HOME"}
        for k in self._saved:
            os.environ.pop(k, None)
        d = Path(tempfile.mkdtemp(prefix="setup-api-"))
        os.environ["BRIDGE_TEST_HOME"] = str(d)
        from halo_harness.providers.config import default_state_dir
        self.state_dir, self.cwd = Path(default_state_dir()), d / "project"
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.cwd.mkdir(parents=True)
        from halo_harness.studio import model as M
        self._rows_fn = M.model_rows
        if self.rows is not None:
            M.model_rows = lambda *_a, **_k: [dict(r) for r in self.rows]
        return self

    def __exit__(self, *exc):
        from halo_harness.studio import model as M
        M.model_rows = self._rows_fn
        for k in [k for k in os.environ if k.startswith(PREFIXES) or k == "BRIDGE_TEST_HOME"]:
            os.environ.pop(k, None)
        os.environ.update(self._saved)

    def call(self, method: str, path: str, body=None):
        from halo_harness.studio.api import Request, dispatch
        return dispatch(Request(method=method, path=path, query={}, body=body or {}, cwd=self.cwd, state_dir=self.state_dir))

    def config(self) -> dict:
        p = self.state_dir / "config.json"
        return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else {}


@test
def test_the_state_has_every_block_and_no_key(ctx: Ctx):
    with _Env() as e:
        os.environ["OPENROUTER_API_KEY"] = "sk-or-v1-setup-test-key-0123456789abcdef"
        status, s = e.call("GET", "setup/state")
        ctx.check(f"200, got {status}", status == 200)
        want = {"model", "permission_mode", "theme", "theme_default", "themes", "permission_modes", "team", "models", "providers",
                "linux_fixes", "last_check", "checks", "gym_models", "card", "no_provider", "model_notes"}  # R3: the last five
        ctx.check(f"the blocks' keys, got {sorted(s)}", want <= set(s))
        ctx.check("nothing saved yet: model, mode and theme are blank, the default theme named",
                  s["model"] == "" and s["permission_mode"] == "" and s["theme"] == "" and s["theme_default"] == "claude-dark")
        ctx.check(f"the wizard's four modes in order, got {[m['id'] for m in s['permission_modes']]}",
                  [m["id"] for m in s["permission_modes"]] == ["auto", "acceptEdits", "default", "plan"])
        ctx.check("each mode carries its label and note", s["permission_modes"][0] == {
            "id": "auto", "label": "auto (recommended)", "note": "allow everything except explicit deny/ask rules"})
        names = [t["name"] for t in s["themes"]]
        ctx.check(f"six terminal themes, got {names}", names == ["claude-dark", "claude-dark-daltonized", "claude-dark-ansi",
                                                                  "claude-light", "claude-light-daltonized", "claude-light-ansi"])
        pal = s["themes"][0]["palette"]
        ctx.check(f"a palette from tui/theme.py, got {pal}", pal["bg"] == "#1e1e2e" and pal["accent"] == "#89b4fa" and len(pal) == 10)
        ctx.check(f"the eight provider tabs by name, got {list(s['providers'])}",
                  sorted(s["providers"]) == sorted(["databricks", "openrouter", "anthropic", "openai", "typesafe", "experiential",
                                                     "ollama", "huggingface"]))
        orp = s["providers"]["openrouter"]
        ctx.check(f"the key in the environment shows as set, from the environment, its tail, got {orp}",
                  orp["set"] is True and orp["source"] == "environment" and orp["tail"] == "****cdef")
        ctx.check("and the key is nowhere in the answer", "sk-or-v1" not in json.dumps(s) and "0123456789abcdef" not in json.dumps(s))
        team = s["team"]
        rows = {r["name"]: r for r in team["lineups"]}
        ctx.check(f"a fresh home runs the auto lineup by default, got {team['active']} {team['source']}",
                  team["active"] == "auto" and team["source"] == "default" and team["roles_enabled"] is True)
        ctx.check("One model for everything first, then the lineups; auto checked as the default",
                  team["lineups"][0]["name"] == "one-model" and team["lineups"][0]["label"] == "One model for everything"
                  and rows["auto"]["default"] and rows["auto"]["active"] and not rows["one-model"]["active"] and "balanced" in rows)
        ctx.check("R3: no check ran yet; the Linux fixes block's shape (its items depend on the box)",
                  s["last_check"] is None and set(s["linux_fixes"]) == {"needed", "items", "platform"}
                  and s["linux_fixes"]["needed"] == bool(s["linux_fixes"]["items"]))


@test
def test_config_takes_three_keys_and_checks_each_value(ctx: Ctx):
    with _Env(MOCK_ROWS) as e:
        status, body = e.call("POST", "setup/config", {"key": "team", "value": "balanced"})
        ctx.check(f"a key outside the list is a 422, got {status} {body}", status == 422 and body["problems"] and "team" in body["error"])
        for key, value in (("permission_mode", "yolo"), ("theme", "doom"), ("model", "or:mock/gamma"), ("theme", "")):
            status, body = e.call("POST", "setup/config", {"key": key, "value": value})
            ctx.check(f"{key}={value!r} is a 422 with problems, got {status} {body.get('problems')}",
                      status == 422 and body["problems"] and body["error"] == body["problems"][0] and body["error"].startswith(key))
        ctx.check(f"nothing written, got {e.config()}", all(k not in e.config() for k in ("permission_mode", "theme", "model", "team")))
        status, s = e.call("POST", "setup/config", {"key": "permission_mode", "value": "acceptEdits"})
        ctx.check(f"a good mode saves, got {status} {s.get('lines')}", status == 200 and e.config().get("permission_mode") == "acceptEdits"
                  and s["permission_mode"] == "acceptEdits" and s["lines"][0].startswith("permission_mode = acceptEdits (saved to "))
        status, s = e.call("POST", "setup/config", {"key": "theme", "value": "claude-light-ansi"})
        ctx.check("a good theme saves", status == 200 and e.config().get("theme") == "claude-light-ansi" and s["theme"] == "claude-light-ansi")
        status, s = e.call("POST", "setup/config", {"key": "model", "value": "or:mock/beta"})
        ctx.check("a model the catalog lists saves", status == 200 and e.config().get("model") == "or:mock/beta" and s["model"] == "or:mock/beta")
        ctx.check(f"the state lists the catalog's rows, got {s['models'][0]}", s["models"][0] == {
            "ref": "or:mock/alpha", "provider": "openrouter", "label": "Mock Alpha", "best_at": "code, review", "price": "$1.00", "context": "128k"})
    with _Env([]) as e:
        status, body = e.call("POST", "setup/config", {"key": "model", "value": "or:mock/alpha"})
        ctx.check(f"no provider, no catalog: the model line says to set one up, got {body.get('error')}",
                  status == 422 and "set one up first" in body["error"] and "model" not in e.config())


@test
def test_team_writes_the_wizards_three_choices(ctx: Ctx):
    with _Env() as e:
        status, s = e.call("POST", "setup/team", {"lineup": "one-model"})
        cfg = e.config()
        ctx.check(f"one-model: no team, roles off, got {status} {cfg}", status == 200 and "team" not in cfg
                  and cfg.get("roles", {}).get("enabled") is False and s["team"]["active"] == "one-model")
        ctx.check(f"its line, got {s.get('lines')}", s["lines"] == ["one model for everything (roles off, no lineup)"])
        status, s = e.call("POST", "setup/team", {"lineup": "auto"})
        cfg = e.config()
        ctx.check(f"auto: roles on, still no team, got {cfg}", status == 200 and "team" not in cfg and cfg["roles"]["enabled"] is True
                  and s["team"]["active"] == "auto" and s["team"]["source"] == "default")
        status, s = e.call("POST", "setup/team", {"lineup": "balanced"})
        cfg = e.config()
        roles = {k for k in cfg.get("roles", {}) if k != "enabled"}
        from halo_harness.teams_yaml import resolve_role_table, resolve_team_template
        table, _notes = resolve_role_table(resolve_team_template("balanced", cwd=e.cwd, state_dir=e.state_dir), cwd=e.cwd, state_dir=e.state_dir)
        ctx.check(f"a lineup: team, the roles.* its table resolves and roles on, got {cfg.get('team')} {sorted(roles)}",
                  status == 200 and cfg.get("team") == "balanced" and cfg["roles"]["enabled"] is True and roles == set(table)
                  and s["team"]["active"] == "balanced" and s["lines"][0].startswith("lineup 'balanced' applied")
                  and isinstance(s.get("details"), list))
        rows = {r["name"]: r for r in s["team"]["lineups"]}
        ctx.check("the rows follow: balanced checked, auto no longer the default", rows["balanced"]["active"] and not rows["auto"]["default"])
        status, s = e.call("POST", "setup/team", {"lineup": "auto"})
        ctx.check("auto over a set team applies auto (the wizard's rule)", status == 200 and e.config().get("team") == "auto")
        before = e.config()
        for body in ({"lineup": "no-such-lineup"}, {}, {"lineup": "../x"}):
            status, got = e.call("POST", "setup/team", body)
            ctx.check(f"{body} is a 422 with problems, got {status} {got.get('error')}", status == 422 and got["problems"])
        ctx.check("and wrote nothing", e.config() == before)
        status, p = e.call("GET", "setup/team/balanced/preview")
        ctx.check(f"the preview: the Team step's lines, got {status} {p.get('lines', [''])[:1]}",
                  status == 200 and p["name"] == "balanced" and p["lines"][0].startswith("balanced"))
        status, p = e.call("GET", "setup/team/one-model/preview")
        ctx.check(f"One model's preview, got {p.get('lines', [''])[:1]}", status == 200 and p["lines"][0] == "One model for everything:")
        status, _ = e.call("GET", "setup/team/nope/preview")
        ctx.check(f"an unknown lineup's preview is a 404, got {status}", status == 404)


@test
def test_the_wizard_commits_through_the_same_function(ctx: Ctx):
    from halo_harness import lineup_choice
    from halo_harness.tui.dialogs import team_preview as tp
    from halo_harness.tui.dialogs.team_step_actions import TeamActionsMixin
    calls = []
    real = lineup_choice.apply_lineup_choice

    def spy(name, **kw):
        calls.append((name, kw))
        return real(name, **kw)

    with _Env() as e:
        lineup_choice.apply_lineup_choice = spy
        try:
            for name in (tp.ONE_MODEL_ID, "balanced"):
                step = SimpleNamespace(state=SimpleNamespace(cwd=e.cwd, written=[]), app=SimpleNamespace(controller=None),
                                       _highlighted_lineup_name=lambda n=name: n)
                TeamActionsMixin.commit(step)
                ctx.check(f"{name}: the step called apply_lineup_choice and kept its line, got {step.state.written}",
                          calls[-1] == (name, {"cwd": e.cwd}) and len(step.state.written) == 1)
        finally:
            lineup_choice.apply_lineup_choice = real
        ctx.check("the wizard's choice landed as Studio's does", e.config().get("team") == "balanced" and e.config()["roles"]["enabled"] is True)
        ctx.check("the wizard's One model id is Studio's one-model", lineup_choice.is_one_model(tp.ONE_MODEL_ID) and lineup_choice.is_one_model("one-model"))


@test
def test_methods_and_unknown_paths(ctx: Ctx):
    with _Env() as e:
        ctx.check("POST setup/state is a 405", e.call("POST", "setup/state")[0] == 405)
        ctx.check("GET setup/config is a 405", e.call("GET", "setup/config")[0] == 405)
        ctx.check("POST a preview is a 405", e.call("POST", "setup/team/auto/preview")[0] == 405)
        ctx.check("an unknown setup/ path is a 404", e.call("GET", "setup/nothing")[0] == 404)
        ctx.check("the prefix is registered", any(p[0] == "setup" for p in __import__("halo_harness.studio.api", fromlist=["_PREFIXES"])._PREFIXES))
        ctx.check("3.3.3.0 R1: GET setup/done is a 405", e.call("GET", "setup/done")[0] == 405)


@test
def test_done_writes_the_marker_publishes_the_frame_and_the_state_carries_it(ctx: Ctx):
    """3.3.3.0 R1: POST setup/done -> setup-done.json {at, home} (over an earlier one), a `setup` frame {stage: done},
    {ok, done_at}; GET setup/state's done_at; no key in either."""
    from halo_harness.studio import events
    from halo_harness.studio.api import Request, dispatch
    from halo_harness.studio.setup_done import parse_at, setup_done_at
    from halo_harness.studio.setup_state import home_id
    frames: list = []
    real = events.bridge_for
    events.bridge_for = lambda _server: SimpleNamespace(publish_local=frames.append)
    try:
        with _Env() as e:
            os.environ["OPENROUTER_API_KEY"] = "sk-or-v1-setup-done-key-0123456789abcdef"
            status, s = e.call("GET", "setup/state")
            ctx.check(f"no Done yet: done_at null, got {status} {s.get('done_at')!r}", status == 200 and "done_at" in s and s["done_at"] is None)
            post = lambda: dispatch(Request(method="POST", path="setup/done", query={}, body={}, cwd=e.cwd, state_dir=e.state_dir, server=object()))
            status, got = post()
            marker = e.state_dir / "setup-done.json"
            data = json.loads(marker.read_text(encoding="utf-8")) if marker.is_file() else {}
            ctx.check(f"200 {{ok, done_at}}, got {status} {got}", status == 200 and got.get("ok") is True and parse_at(got.get("done_at")) is not None)
            ctx.check(f"the marker: at and this home, got {data}", data == {"at": got.get("done_at"), "home": home_id(e.state_dir)})
            ctx.check(f"one setup frame {{stage: done, at}}, got {frames}", len(frames) == 1 and frames[0]["event"] == "setup"
                      and frames[0]["data"] == {"stage": "done", "at": got.get("done_at")})
            status, s = e.call("GET", "setup/state")
            ctx.check(f"the state carries done_at, got {s.get('done_at')!r}", s.get("done_at") == got.get("done_at") == setup_done_at(e.state_dir))
            again = post()[1]
            ctx.check("a second Done writes over the first, not earlier", parse_at(again["done_at"]) >= parse_at(got["done_at"])
                      and json.loads(marker.read_text(encoding="utf-8"))["at"] == again["done_at"])
            text = json.dumps([got, again, s, frames, data])
            ctx.check("no key in the answers, the frame or the marker", "sk-or-v1" not in text and "0123456789abcdef" not in text)
            ctx.check("not the Setup hook's .setup_done marker", not (e.state_dir / ".setup_done").exists())
            marker.write_text("{not json", encoding="utf-8")
            ctx.check("a marker that does not parse reads as none", setup_done_at(e.state_dir) is None)
    finally:
        events.bridge_for = real


@test
def test_a_card_says_where_each_value_came_from(ctx: Ctx):
    """3.3.5.0 R0 (g): `field_sources` -- a host discovered in Claude Code's settings.json (a fake one, the
    placeholder host), a key in the env file, a key typed into the card; the words the terminal wizard and
    `halo doctor --config` print come from the same function."""
    from halo_harness.init_providers import prefilled_line
    from halo_harness.studio.setup_providers_state import TYPED
    TYPED.clear()
    with _Env() as e:
        claude = Path(os.environ["BRIDGE_TEST_HOME"]) / ".claude"
        claude.mkdir(parents=True, exist_ok=True)
        (claude / "settings.json").write_text(json.dumps({"env": {
            "ANTHROPIC_MODEL": "databricks-claude-sonnet-4", "DATABRICKS_HOST": "https://your-workspace.cloud.databricks.com"}}),
            encoding="utf-8")
        status, s = e.call("GET", "setup/state")
        dbx = s["providers"]["databricks"]
        ctx.check(f"a host from Claude Code's settings.json, no token, got {dbx.get('field_sources')}",
                  status == 200 and dbx["set"] is False and dbx.get("field_sources") == {"host": "Claude Code's settings.json", "token": ""})
        from halo_harness.init_providers import tab_credential_state
        line = prefilled_line(tab_credential_state("databricks", cwd=e.cwd))
        ctx.check(f"the wizard's and doctor's words, never the host, got {line!r}",
                  line == "host from Claude Code's settings.json · token not set" and "your-workspace" not in line)
        env_file = e.state_dir.parent / "halo-env"
        env_file.write_text("OPENROUTER_API_KEY=sk-or-v1-fieldsource-0123456789abcdef\n", encoding="utf-8")
        os.environ["HALO_ENV_FILE"] = str(env_file)
        status, s = e.call("GET", "setup/state")
        ctx.check(f"a key in the env file, got {s['providers']['openrouter'].get('field_sources')}",
                  s["providers"]["openrouter"].get("field_sources") == {"key": "env file"})
        status, s = e.call("POST", "setup/provider/anthropic", {"fields": {"key": "sk-ant-testtesttesttest"}})
        ctx.check(f"a key typed into the card, got {status} {s.get('providers', {}).get('anthropic', {}).get('field_sources')}",
                  status == 200 and s["providers"]["anthropic"].get("field_sources") == {"key": "typed here"})
        ctx.check("no key in the answer", "testtesttesttest" not in json.dumps(s) and "fieldsource-0123456789abcdef" not in json.dumps(s))
    TYPED.clear()


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
