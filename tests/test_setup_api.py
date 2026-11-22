"""tests.test_setup_api -- Studio's Setup section routes (Halo 3.3.0.0 R1,
studio/setup_api.py, studio/setup_state.py, lineup_choice.py) through
`api.dispatch` over a scratch home; no model call, no network:

1. `GET setup/state`: every block's value and rows (the wizard's four
   permission modes, the ten palettes (3.3.12.0) with their colours, the eight
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
                "linux_fixes", "last_check", "checks", "gym_models", "no_provider", "model_notes"}  # R3; 3.4.0.0 B: no card
        ctx.check(f"the blocks' keys, got {sorted(s)}", want <= set(s))
        ctx.check("nothing saved yet: model, mode and theme are blank, the default theme named",
                  s["model"] == "" and s["permission_mode"] == "" and s["theme"] == "" and s["theme_default"] == "instrument")  # 3.3.15.0 R4
        ctx.check(f"the wizard's four modes in order, got {[m['id'] for m in s['permission_modes']]}",
                  [m["id"] for m in s["permission_modes"]] == ["auto", "acceptEdits", "default", "plan"])
        ctx.check("each mode carries its label and note", s["permission_modes"][0] == {
            "id": "auto", "label": "auto (recommended)", "note": "allow everything except explicit deny/ask rules"})
        names = [t["name"] for t in s["themes"]]
        from halo_harness.themes.registry import ids  # 3.3.12.0 R1: the ten palettes, the modifiers on Settings -> Themes
        ctx.check(f"the ten palettes, got {names}", names == list(ids()) and names[:3] == ["claude-dark", "claude-light", "holo"])
        pal = s["themes"][0]["palette"]
        ctx.check(f"a palette from tui/theme.py, got {pal}", pal["bg"] == "#1e1e2e" and pal["accent"] == "#89b4fa" and len(pal) == 10)
        ctx.check(f"the seven provider tabs by name, got {list(s['providers'])}",
                  sorted(s["providers"]) == sorted(["databricks", "openrouter", "anthropic", "openai", "experiential",
                                                     "ollama", "huggingface"]))
        orp = s["providers"]["openrouter"]
        ctx.check(f"the key in the environment shows as set, from the environment, its tail, got {orp}",
                  orp["set"] is True and orp["source"] == "environment" and orp["tail"] == "****cdef")
        ctx.check("and the key is nowhere in the answer", "sk-or-v1" not in json.dumps(s) and "0123456789abcdef" not in json.dumps(s))
        team = s["team"]  # 3.6.0.0 R5: the Map step (its block id stays team)
        rows = {r["name"]: r for r in team["maps"]}
        ctx.check(f"a fresh home runs Auto by default, got {team['active']} {team['source']}",
                  team["active"] == "auto" and team["source"] == "default")
        ctx.check(f"every map listed, Auto checked as the default, got {list(rows)}",
                  rows["auto"]["default"] and rows["auto"]["active"] and "ship-it" in rows and not rows["ship-it"]["active"])
        ctx.check("R3: no check ran yet; the Linux fixes block's shape (its items depend on the box)",
                  s["last_check"] is None and set(s["linux_fixes"]) == {"needed", "items", "platform"}
                  and s["linux_fixes"]["needed"] == bool(s["linux_fixes"]["items"]))


@test
def test_config_takes_three_keys_and_checks_each_value(ctx: Ctx):
    with _Env(MOCK_ROWS) as e:
        from halo_harness import launch_state  # 3.6.0.11: a default model picked here is newer than an older /model
        elsewhere = Path(tempfile.mkdtemp(prefix="setup-api-switched-"))
        launch_state.record_last_model("or:mock/alpha", cwd=elsewhere)
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
        ctx.check("a refused model and the other two keys leave the /model choice remembered",
                  launch_state.resolve_last_model(elsewhere) == "or:mock/alpha")
        status, s = e.call("POST", "setup/config", {"key": "model", "value": "or:mock/beta"})
        ctx.check("a model the catalog lists saves", status == 200 and e.config().get("model") == "or:mock/beta" and s["model"] == "or:mock/beta")
        ctx.check("and the older /model choice, made in another folder, no longer outranks it",
                  launch_state.resolve_last_model(elsewhere) is None and launch_state.resolve_last_model(Path.cwd()) is None)
        ctx.check(f"the state lists the catalog's rows, got {s['models'][0]}", s["models"][0] == {
            "ref": "or:mock/alpha", "provider": "openrouter", "label": "Mock Alpha", "best_at": "code, review", "price": "$1.00", "context": "128k",
            "takes": ["?"]})  # 3.3.15.0 R2: the mock row states no takes
    with _Env([]) as e:
        status, body = e.call("POST", "setup/config", {"key": "model", "value": "or:mock/alpha"})
        ctx.check(f"no provider, no catalog: the model line says to set one up, got {body.get('error')}",
                  status == 422 and "set one up first" in body["error"] and "model" not in e.config())


@test
def test_the_map_step_writes_crew_map(ctx: Ctx):
    """3.6.0.0 R5: the Team step is the Map step: a map name writes config `crew.map` (as `halo maps use`); a lineup
    name gets the one line; the preview is the map in words."""
    with _Env() as e:
        status, s = e.call("POST", "setup/team", {"map": "ship-it"})
        cfg = e.config()
        ctx.check(f"ship-it: crew.map, got {status} {cfg.get('crew')} {s.get('lines')}", status == 200
                  and (cfg.get("crew") or {}).get("map") == "ship-it" and s["team"]["active"] == "ship-it" and s["team"]["source"] == "config"
                  and s["lines"] == ["crew.map = ship-it: new sessions run on the map ship-it"])
        rows = {r["name"]: r for r in s["team"]["maps"]}
        ctx.check("the rows follow: ship-it checked, Auto no longer the default", rows["ship-it"]["active"] and not rows["auto"]["default"])
        before = e.config()
        for body in ({"map": "no-such-map"}, {}, {"map": "../x"}, {"lineup": "balanced"}):
            status, got = e.call("POST", "setup/team", body)
            ctx.check(f"{body} is a 422 with problems, got {status} {got.get('error')}", status == 422 and got["problems"])
        status, got = e.call("POST", "setup/team", {"lineup": "balanced"})
        ctx.check(f"a lineup's name: lineups are gone, got {got.get('error')}", "lineups are gone" in str(got.get("error")))
        ctx.check("and wrote nothing", e.config() == before)
        status, p = e.call("GET", "setup/team/ship-it/preview")
        ctx.check(f"the preview: the map in words, got {status} {p.get('lines', [''])[:2]}",
                  status == 200 and p["name"] == "ship-it" and any("plan" in ln for ln in p["lines"]))
        status, _ = e.call("GET", "setup/team/nope/preview")
        ctx.check(f"an unknown map's preview is a 404, got {status}", status == 404)


def _own_map(e, name: str, text: str) -> None:
    folder = e.state_dir / "crew" / "maps"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{name}.yaml").write_text(text, encoding="utf-8")


@test
def test_the_map_step_says_when_new_sessions_will_not_run_the_map(ctx: Ctx):
    """3.6.0.11 SM: a map of his own that names a missing workflow is still saved, and Setup says new sessions run on
    Auto until it is fixed (the answer's lines, `team.runs`, `team.problems`); a healthy map runs as picked."""
    shipped = (Path(__file__).resolve().parent.parent / "halo_harness" / "templates" / "crew" / "maps" / "ship-it.yaml").read_text(encoding="utf-8")
    with _Env() as e:
        _own_map(e, "broken", shipped.replace("name: ship-it", "name: broken").replace("workflow: plan", "workflow: no-such-workflow"))
        _own_map(e, "notyaml", "format: map/1\nboxes: [\n")
        status, s = e.call("POST", "setup/team", {"map": "broken"})
        team, lines = s.get("team") or {}, s.get("lines") or []
        ctx.check(f"the broken map is saved (200, crew.map), got {status} {(e.config().get('crew') or {}).get('map')}",
                  status == 200 and (e.config().get("crew") or {}).get("map") == "broken" and team.get("active") == "broken")
        head = "broken has a problem: new sessions run on Auto until it is fixed"
        tail = lines[lines.index(head) + 1:] if head in lines else []
        ctx.check(f"its lines say new sessions run on Auto, then the compile's problems, got {lines}",
                  any("no-such-workflow" in ln for ln in tail))
        ctx.check(f"team.runs is auto and team.problems names it, got {team.get('runs')} {team.get('problems')}",
                  team.get("runs") == "auto" and any("no-such-workflow" in p for p in team.get("problems") or []))
        _, st = e.call("GET", "setup/state")
        ctx.check(f"the state says the same, got {st['team'].get('runs')}", st["team"].get("runs") == "auto" and st["team"].get("problems"))
        status, s = e.call("POST", "setup/team", {"map": "notyaml"})
        ctx.check(f"a map that is not YAML: saved, a problem line, never a crash, got {status} {s.get('team', {}).get('problems')}",
                  status == 200 and s["team"]["runs"] == "auto" and s["team"]["problems"])
        status, s = e.call("POST", "setup/team", {"map": "ship-it"})
        ctx.check(f"a healthy map: runs == active, no problems, no problem line, got {s['team'].get('runs')} {s['team'].get('problems')} {s['lines']}",
                  s["team"].get("runs") == "ship-it" and s["team"].get("problems") == [] and len(s["lines"]) == 1)
        for name, runs in (("auto", "auto"), ("one-model", "one-model")):
            status, s = e.call("POST", "setup/team", {"map": name})
            ctx.check(f"{name}: runs {runs}, no problems, got {s['team'].get('runs')} {s['team'].get('problems')}",
                      s["team"].get("runs") == runs and s["team"].get("problems") == [])


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
            dstatus, d = e.call("GET", "setup/done-at")  # 3.6.0.0 R14: what `halo init` polls, the done_at alone
            ctx.check(f"GET setup/done-at answers the same done_at and nothing else, got {dstatus} {d}",
                      dstatus == 200 and d == {"done_at": got.get("done_at")})
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
def test_done_says_who_starts_halo(ctx: Ctx):
    """3.3.15.0 R6: Done with a `halo init` waiting answers "halo is starting in your terminal" and opens nothing; with
    none waiting Studio opens a terminal running halo (the launcher stubbed), and with no terminal emulator it says
    "no terminal found to start halo in; run `halo` yourself" -- never silent. GET setup/state's `init_waiting`."""
    from halo_harness.studio import events, halo_terminal, init_waiting
    from halo_harness.studio.api import Request, dispatch
    real = (events.bridge_for, halo_terminal.open_halo)
    opened: list = []
    events.bridge_for = lambda _server: SimpleNamespace(publish_local=lambda _f: None)
    try:
        with _Env() as e:
            os.environ["OPENROUTER_API_KEY"] = "sk-or-v1-setup-done-key-0123456789abcdef"  # Done needs a model a session can call
            post = lambda: dispatch(Request(method="POST", path="setup/done", query={}, body={}, cwd=e.cwd, state_dir=e.state_dir, server=object()))
            halo_terminal.open_halo = lambda cwd, **_k: opened.append(cwd) or (True, halo_terminal.OPENED_LINE.format(name="xterm"))
            init_waiting.mark(e.state_dir, e.cwd)  # what a waiting `halo init` writes (this process stands in for it)
            _s, s = e.call("GET", "setup/state")
            status, got = post()
            ctx.check(f"an init waits: the state says so, Done answers it, no terminal opened, got {s.get('init_waiting')} {got} {opened}",
                      s.get("init_waiting") is True and status == 200 and got.get("starts") == "init"
                      and got.get("line") == "halo is starting in your terminal" and opened == [])
            init_waiting.clear(e.state_dir)
            _s, s = e.call("GET", "setup/state")
            status, got = post()
            ctx.check(f"none waits: Studio opens a terminal running halo, got {s.get('init_waiting')} {got} {opened}",
                      s.get("init_waiting") is False and got.get("starts") == "terminal" and opened == [e.cwd]
                      and got.get("line") == "halo is starting in a new terminal window (xterm)")
            halo_terminal.open_halo = real[1]  # the real one, under a test home: no window, the plain line
            status, got = post()
            ctx.check(f"no terminal: the plain line, got {got}", got.get("starts") == "none"
                      and got.get("line") == "no terminal found to start halo in; run `halo` yourself" and got.get("ok") is True)
            stale = e.state_dir / init_waiting.RECORD
            stale.write_text(json.dumps({"pid": 999999991, "since": "x", "cwd": str(e.cwd)}), encoding="utf-8")
            ctx.check("a record whose init is gone does not count and is removed", init_waiting.waiting(e.state_dir) is None
                      and not stale.exists())
    finally:
        events.bridge_for, halo_terminal.open_halo = real


@test
def test_done_refuses_a_setup_that_cannot_run_a_session(ctx: Ctx):
    """Local models only: a Setup that added only an Ollama host (down) and picked no model marked Providers done, and
    its Done started halo, which failed on 'OpenRouter not configured'. The state's `ready` says, from the resolver a
    session uses, what is missing and which page fixes it; a Done sent anyway gets the same line and writes nothing.
    With a model that resolves, Done is as before."""
    from halo_harness.studio import events, halo_terminal
    from halo_harness.studio.api import Request, dispatch
    from halo_harness.studio.setup_done import NO_MODEL, NO_PROVIDER
    real = (events.bridge_for, halo_terminal.open_halo)
    events.bridge_for = lambda _server: SimpleNamespace(publish_local=lambda _f: None)
    halo_terminal.open_halo = lambda cwd, **_k: (True, halo_terminal.OPENED_LINE.format(name="xterm"))
    try:
        with _Env() as e:
            post = lambda: dispatch(Request(method="POST", path="setup/done", query={}, body={}, cwd=e.cwd, state_dir=e.state_dir, server=object()))
            marker = e.state_dir / "setup-done.json"
            _s, s = e.call("GET", "setup/state")
            ctx.check(f"nothing set up: not ready, the Providers page, got {s.get('ready')}",
                      s.get("ready") == {"ok": False, "line": NO_PROVIDER, "page": "providers", "usable": False})
            status, got = post()
            ctx.check(f"a Done sent anyway: 409 with the same line, no marker, got {status} {got}",
                      status == 409 and got.get("error") == NO_PROVIDER and not marker.exists())
            e.call("POST", "setup/ollama-host", {"url": "http://127.0.0.1:9"})  # as in the finding: a host, down
            _s, s = e.call("GET", "setup/state")
            ctx.check(f"an Ollama host and no model: not ready, the Default model page, got {s.get('ready')} "
                      f"{s['providers']['ollama'].get('set')}",
                      s["providers"]["ollama"].get("set") is True and s.get("ready") == {"ok": False, "line": NO_MODEL, "page": "model",
                                                                                         "usable": False})
            status, got = post()
            ctx.check(f"Done refused with that line, got {status} {got}", status == 409 and got.get("error") == NO_MODEL
                      and not marker.exists())
            from halo_harness.theme import set_config_value
            set_config_value("model", "ol:qwen3:30b@default")  # what the Default model page saves for an Ollama model
            _s, s = e.call("GET", "setup/state")
            status, got = post()
            ctx.check(f"a model that resolves: ready, Done as before, got {s.get('ready')} {status} {got}",
                      s.get("ready", {}).get("ok") is True and status == 200 and got.get("ok") is True and marker.exists())
    finally:
        events.bridge_for, halo_terminal.open_halo = real


@test
def test_the_rail_ticks_providers_only_when_a_provider_is_usable(ctx: Ctx):
    """jb10 (local models only): the rail ticked Providers when only an Ollama host was set and no model could run, and
    the Summary then refused Done. The state's `ready.usable` says whether a provider a session can call is set up (a
    key or a login; an Ollama host only once one of its models is the default). The rail reads it (pages.ts isDone)."""
    with _Env() as e:
        e.call("POST", "setup/ollama-host", {"url": "http://127.0.0.1:9"})
        _s, s = e.call("GET", "setup/state")
        ctx.check(f"an Ollama host alone, no model: no usable provider, got {s.get('ready')}",
                  s["providers"]["ollama"].get("set") is True and s["ready"].get("usable") is False
                  and s["ready"].get("ok") is False)
        os.environ["OPENROUTER_API_KEY"] = "sk-or-v1-setup-usable-key-0123456789abcdef"
        _s, s = e.call("GET", "setup/state")
        ctx.check(f"a key-based provider set: usable, got {s.get('ready')}", s["ready"].get("usable") is True)
        from halo_harness.theme import set_config_value
        set_config_value("model", "ol:qwen3:30b@default")
        _s, s = e.call("GET", "setup/state")
        ctx.check(f"a model that resolves: ready and usable, got {s.get('ready')}",
                  s["ready"].get("ok") is True and s["ready"].get("usable") is True)


@test
def test_ready_decides_a_local_server_model_from_configuration_and_never_connects(ctx: Ctx):
    """jb10 batch 2: ready() went through the session's resolver, which probes local ports (1.1 s on every Setup
    load), and a default model whose Halo-served server was simply not running read 'has no provider set up here'.
    It now decides from configuration only: a registered or configured server is ready, with zero connects."""
    import json
    import socket
    from halo_harness.providers.huggingface_mlx import is_apple_silicon
    from halo_harness.providers.local_runtime import registry_path
    from halo_harness.studio.setup_done import ready
    from halo_harness.studio.setup_state import setup_state
    from halo_harness.theme import set_config_value
    connects = []
    real = (socket.socket.connect, socket.socket.connect_ex)
    socket.socket.connect = lambda self, addr: connects.append(addr) or real[0](self, addr)
    socket.socket.connect_ex = lambda self, addr: connects.append(addr) or real[1](self, addr)
    os.environ["HF_LOCAL_PROBE_PORTS"] = "9"
    try:
        with _Env(rows=[]) as e:
            path = registry_path(e.state_dir)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps([{"model": "qwen-7b", "runtime": "llama-server", "pid": 999999, "port": 9,
                                         "base_url": "http://127.0.0.1:9/v1"}]), encoding="utf-8")
            set_config_value("model", "hf:local/qwen-7b")
            got = ready(e.cwd, e.state_dir)
            ctx.check(f"a Halo-served model whose server is not running now: Done stays, no connect, got {got} "
                      f"{connects}", got["ok"] is True and connects == [])
            setup_state(e.cwd, e.state_dir)
            ctx.check(f"one Setup state read connects nowhere, got {connects}", connects == [])
            set_config_value("model", "hf:local/never-served")
            got = ready(e.cwd, e.state_dir)
            ctx.check(f"a model no server serves or is set up for: refused, the line says to start one, not 'no "
                      f"provider', got {got} {connects}", got["ok"] is False and "no provider" not in got["line"]
                      and "not running" in got["line"] and connects == [])
            set_config_value("huggingface.local_servers", [{"name": "box", "url": "http://127.0.0.1:9/v1"}])
            for ref, ok in (("hf:local/never-served@box", True), ("hf:local/never-served@nobody", False)):
                set_config_value("model", ref)
                got = ready(e.cwd, e.state_dir)
                ctx.check(f"{ref}: ok {ok}, no connect, got {got} {connects}", got["ok"] is ok and connects == [])
            set_config_value("model", "hf:mlx/mlx-community/qwen-7b-4bit")
            got = ready(e.cwd, e.state_dir)
            ctx.check(f"an MLX model: ready only on Apple silicon (the session starts its server), got {got}",
                      got["ok"] is is_apple_silicon() and connects == [])
    finally:
        socket.socket.connect, socket.socket.connect_ex = real
        os.environ.pop("HF_LOCAL_PROBE_PORTS", None)


@test
def test_a_routes_file_that_is_not_a_mapping_reads_as_empty_and_done_agrees_with_the_state(ctx: Ctx):
    """jb10 batch 3: routes.json holding a JSON list made ready() raise AttributeError; the state read caught it and
    showed Done, the Done route did not and answered 500. The loader now answers {} for anything not a mapping, so the
    state and Done agree (both from the same ready())."""
    from halo_harness.providers.config import load_routes
    from halo_harness.studio import events, halo_terminal
    from halo_harness.studio.api import Request, dispatch
    real = (events.bridge_for, halo_terminal.open_halo)
    events.bridge_for = lambda _server: SimpleNamespace(publish_local=lambda _f: None)
    halo_terminal.open_halo = lambda cwd, **_k: (True, halo_terminal.OPENED_LINE.format(name="xterm"))
    try:
        with _Env() as e:
            os.environ["OPENROUTER_API_KEY"] = "sk-or-v1-setup-done-key-0123456789abcdef"
            (e.state_dir / "config.json").write_text(json.dumps({"model": "or:mock/alpha"}), encoding="utf-8")
            for bad in ("[1, 2]", '"text"', "3"):
                (e.state_dir / "routes.json").write_text(bad, encoding="utf-8")
                ctx.check(f"{bad}: the loader answers an empty mapping, got {load_routes(e.state_dir / 'routes.json')!r}",
                          load_routes(e.state_dir / "routes.json") == {})
            (e.state_dir / "routes.json").write_text("[1, 2]", encoding="utf-8")
            _s, s = e.call("GET", "setup/state")
            try:
                status, got = dispatch(Request(method="POST", path="setup/done", query={}, body={}, cwd=e.cwd,
                                               state_dir=e.state_dir, server=object()))
            except Exception as ex:  # what the server turns into a 500
                status, got = 500, {"error": repr(ex)}
            ctx.check(f"the state's ready and Done agree and neither fails, got {s.get('ready')} {status} {got}",
                      status == 200 and got.get("ok") is True and s["ready"].get("ok") is True
                      and "error" not in s["ready"])
    finally:
        events.bridge_for, halo_terminal.open_halo = real


@test
def test_the_terminal_a_done_opens(ctx: Ctx):
    """3.3.15.0 R6 (studio/halo_terminal.py): which terminal opens halo per platform, and none without a display."""
    from halo_harness.studio import halo_terminal as H
    on = {"xfce4-terminal", "halo"}
    which = lambda name: f"/usr/bin/{name}" if name in on else None
    name, argv = H.terminal_argv("/w", env={"DISPLAY": ":0"}, platform="linux", which=which)
    ctx.check(f"Kali (Xfce): xfce4-terminal -x halo, got {name} {argv}", name == "xfce4-terminal" and argv == ["xfce4-terminal", "-x", "/usr/bin/halo"])
    name, argv = H.terminal_argv("/w", env={"DISPLAY": ":0", "TERMINAL": "kitty"}, platform="linux",
                                 which=lambda n: f"/usr/bin/{n}" if n in ("kitty", "halo") else None)
    ctx.check(f"$TERMINAL first, got {argv}", argv == ["kitty", "-e", "/usr/bin/halo"])
    for env in ({}, {"DISPLAY": ":0", "SSH_CONNECTION": "1 2 3 4"}):
        ctx.check(f"no display / SSH {env}: none", H.terminal_argv("/w", env=env, platform="linux", which=which) == ("", []))
    ctx.check("no known terminal: none", H.terminal_argv("/w", env={"DISPLAY": ":0"}, platform="linux", which=lambda n: None) == ("", []))
    name, argv = H.terminal_argv("C:/w", env={}, platform="win32", which=lambda n: None)
    from halo_harness.selfexec import python_argv  # 3.6.0.0 R10: the safe-path form, never the working folder's copy
    ctx.check(f"Windows: a console window, halo through this Python, got {name} {argv}", name == "a console window"
              and argv == python_argv() and argv[0] == sys.executable and "halo_harness" in " ".join(argv))
    spawned: list = []
    ok, line = H.open_halo("/w", env={"DISPLAY": ":0"}, platform="linux", which=which, spawn=lambda argv, **kw: spawned.append((argv, kw)))
    ctx.check(f"open_halo spawns it in cwd, got {ok} {line} {spawned}", ok and line == "halo is starting in a new terminal window (xfce4-terminal)"
              and spawned and spawned[0][1]["cwd"] == "/w")
    ok, line = H.open_halo("/w", env={}, platform="linux", which=which, spawn=lambda *a, **k: spawned.append(a))
    ctx.check(f"no display: not spawned, the line, got {ok} {line}", not ok and line == H.NO_TERMINAL and len(spawned) == 1)


class _Osascript:
    def __init__(self, code: int, err: bytes = b"", hang: bool = False):
        self.returncode, self.err, self.hang, self.pid = code, err, hang, 0

    def communicate(self, timeout=None):
        if self.hang:
            import subprocess as sp
            raise sp.TimeoutExpired("osascript", timeout)
        return b"", self.err

    def poll(self):
        return self.returncode


@test
def test_macos_done_reads_osascripts_answer_and_carries_studios_home(ctx: Ctx):
    """fx studio batch 2 (4), macOS by its inputs: Done said "halo is starting in a new terminal window (Terminal)"
    without reading osascript's exit; macOS refusing the Apple event (-1743, Automation not allowed) opened nothing.
    And Terminal's `do script` starts a fresh login shell: Studio's home (BRIDGE_STATE_DIR) and HALO_* were lost."""
    from halo_harness.studio import halo_terminal as H
    which = lambda n: f"/usr/bin/{n}" if n in ("osascript", "halo") else None
    denied = b"36:80: execution error: Not authorized to send Apple events to Terminal. (-1743)\n"
    got = H.open_halo("/w", env={}, platform="darwin", which=which, spawn=lambda argv, **kw: _Osascript(1, denied))
    ctx.check(f"refused: not opened, the reason and the way round, got {got}", got[0] is False
              and "Not authorized to send Apple events to Terminal" in got[1] and "run `halo` yourself" in got[1])
    got = H.open_halo("/w", env={}, platform="darwin", which=which, spawn=lambda argv, **kw: _Osascript(0))
    ctx.check(f"osascript said yes: opened, got {got}", got == (True, "halo is starting in a new terminal window (Terminal)"))
    got = H.open_halo("/w", env={}, platform="darwin", which=which, spawn=lambda argv, **kw: _Osascript(None, hang=True))
    ctx.check(f"still asking the person (the consent prompt): opened, got {got}", got[0] is True)
    env = {"BRIDGE_STATE_DIR": "/Users/someone/my home", "HALO_NO_UPDATER": "1", "HALO_OWNER": "x1", "PATH": "/bin",
           "HALO_DBX_TOKEN": "dapi-secret"}
    _name, argv = H.terminal_argv("/w", env=env, platform="darwin", which=which)
    script = argv[-1] if argv else ""
    ctx.check(f"the new halo gets Studio's home and HALO_*, never the owner marker, got {script!r}",
              "export BRIDGE_STATE_DIR='/Users/someone/my home'" in script and "HALO_NO_UPDATER=1" in script
              and "HALO_OWNER" not in script and "PATH=" not in script and "dapi-secret" not in script and script.rstrip('"').endswith("/usr/bin/halo"))


_CONSOLE_PROBE = (  # writes whether its stdin is a console it can read keys from (what Textual's Windows driver needs)
    "import ctypes, sys\n"
    "k = ctypes.WinDLL('kernel32'); k.GetStdHandle.restype = ctypes.c_void_p\n"
    "h = k.GetStdHandle(-10); mode = ctypes.c_ulong()\n"
    "ok = k.GetConsoleMode(ctypes.c_void_p(h), ctypes.byref(mode))\n"
    "open(sys.argv[1], 'w').write('console' if ok else 'not a console')\n")


@test
def test_the_windows_console_window_is_the_sessions_keyboard(ctx: Ctx):
    """fx studio batch 1 (1): Setup's Done on Windows opens halo in a new console window; it must read keys from that
    console. A standard handle given to Popen (stdin=DEVNULL) made Python pass all three, so halo's stdin was NUL
    (a character device: `isatty()` true, no key ever read) and its output went to Studio's own streams."""
    from halo_harness.studio import halo_terminal as H
    spawned: list = []
    ok, _line = H.open_halo("C:/w", env={}, platform="win32", which=lambda n: None,
                            spawn=lambda argv, **kw: spawned.append((argv, kw)))
    kw = spawned[0][1] if spawned else {}
    ctx.check(f"Windows: no standard handle handed over (the console's own are used), got {sorted(kw)}",
              ok and not {"stdin", "stdout", "stderr"} & set(kw) and kw.get("cwd") == "C:/w"
              and kw.get("creationflags", 0) & 0x10)
    spawned.clear()
    H.open_halo("/w", env={"DISPLAY": ":0"}, platform="linux", which=lambda n: f"/usr/bin/{n}" if n == "xterm" else None,
                spawn=lambda argv, **kw: spawned.append((argv, kw)))
    kw = spawned[0][1] if spawned else {}
    ctx.check(f"POSIX launchers keep their own streams quiet (the terminal program, not halo), got {sorted(kw)}",
              kw.get("stdin") is not None and kw.get("start_new_session") is True)
    if sys.platform != "win32":
        return
    import subprocess as sp
    import tempfile
    out = Path(tempfile.mkdtemp(prefix="halo-console-")) / "probe.txt"
    si = sp.STARTUPINFO()
    si.dwFlags |= sp.STARTF_USESHOWWINDOW
    si.wShowWindow = 0  # SW_HIDE: the probe's console never shows on the desktop
    spawned.clear()
    H.open_halo(str(out.parent), env={}, platform="win32", which=lambda n: None,
                spawn=lambda argv, **kw: spawned.append((argv, kw)))
    kw = dict(spawned[0][1])
    proc = sp.Popen([sys.executable, "-c", _CONSOLE_PROBE, str(out)], startupinfo=si, **kw)
    proc.wait(30)
    got = out.read_text() if out.exists() else "(no answer)"
    ctx.check(f"Windows, a real process started with open_halo's arguments: its stdin is its console, got {got!r}",
              got == "console")


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


# 3.6.0.11 SM: Setup's store, pages and Done run in node (tests/helpers/node_ts.py) with lib/store, lib/api, lib/events and
# lib/filesLive stood in for (found by what they export, so the strip-types and the transpile paths stub the same files)
SETUP_UI = Path(__file__).resolve().parent.parent / "halo_harness" / "studio" / "ui" / "src" / "routes" / "setup"
_SETUP_STUBS = {
    r"export function createStore\b": (
        "export function createStore(s) { return { get: () => s, set: (n) => { s = n; }, update: (f) => { s = { ...s, ...f(s) }; } }; }\n"
        "export const useStore = () => undefined, setSectionStatus = () => {}, goSection = () => {}, toast = () => {};\n"
        "export const studio = createStore({ section: 'setup' });"),
    r"export class ApiError\b": (
        "export class ApiError extends Error { constructor(m, problems) { super(m); this.problems = problems || []; } }\n"
        "export const api = { get: async (u) => globalThis.__get(u), post: async (p, b) => { const r = await globalThis.__post(p, b);"
        " if (r && r.__refuse) throw new ApiError(r.__refuse, [r.__refuse]); return r; } };"),
    r"export function onEvent\b": "export function onEvent() { return () => {}; }",
    r"export function onFilesChanged\b": "export function onFilesChanged() { return () => {}; }",
}
_SETUP_HOOK = r"""import fs from 'node:fs'; import { fileURLToPath } from 'node:url';
const STUBS = %s;
export async function resolve(spec, ctx, next) {
  const r = await next(spec, ctx);
  if (!r.url.startsWith('file:')) return r;
  let src = ''; try { src = fs.readFileSync(fileURLToPath(r.url), 'utf8'); } catch { return r; }
  for (const [re, url] of STUBS) if (new RegExp(re).test(src)) return { url, shortCircuit: true };
  return r; }"""
_SETUP_JS = r"""import { register } from 'node:module';
register('data:text/javascript,' + encodeURIComponent(__HOOK__));
globalThis.localStorage = { getItem: () => null, setItem: () => {}, removeItem: () => {} };
const S = await import(__STORE__), P = await import(__PAGES__), D = await import(__DONE__);
const D0 = { model: 'm-old', permission_mode: 'default', theme: 'paper', theme_default: 'instrument', packs: [], providers: {},
  team: { active: 'auto', source: 'default', maps: [] }, linux_fixes: { needed: false, items: [] }, local_models: { model_dirs: [], runtime: '' } };
let saved, posts, refuse = '';
globalThis.__get = async () => structuredClone(saved);
globalThis.__post = async (p, b) => {
  posts.push([p, b, P.pages.get().page]);
  if (refuse === p) return { __refuse: 'refused' };
  if (p === 'setup/done') return { ok: true, done_at: 'now', line: 'halo is starting' };
  if (p === 'setup/team') saved.team = { ...saved.team, active: b.map }; else saved[b.key] = b.value;
  return { ...structuredClone(saved), lines: ['saved'] };
};
const fresh = (page) => { saved = structuredClone(D0); posts = []; refuse = ''; S.setup.update(() => ({ data: structuredClone(D0), loaded: true, picks: {}, last: {} })); P.pages.update(() => ({ page })); };
const out = {};
fresh('team'); S.pick('team', 'ship-it'); out.next = [await P.step(1), posts, P.pages.get().page, saved.team.active, S.setup.get().picks];
fresh('theme'); S.pick('theme', 'holo'); out.back = [await P.step(-1), posts, P.pages.get().page];
fresh('model'); S.pick('team', 'mine'); S.pick('theme', 'holo'); S.pick('permission_mode', 'plan'); S.pick('model', 'm-new');
out.rail = [await P.goto('summary'), posts, P.pages.get().page];
fresh('team'); S.pick('team', 'nope'); refuse = 'setup/team';
out.refused = [await P.step(1), posts.map((x) => x[0]), P.pages.get().page, S.setup.get().picks.team];
posts = []; out.doneRefused = [await D.pressDone(), posts.map((x) => x[0])];
fresh('summary'); S.pick('team', 'ship-it'); out.done = [await D.pressDone(), posts.map((x) => x[0]), saved.team.active];
fresh('team'); const p = P.goto('providers'); out.sync = [P.pages.get().page, await p, posts.length];
console.log(JSON.stringify(out));"""


@test
def test_leaving_a_setup_page_saves_what_he_picked(ctx: Ctx):
    """3.6.0.11 SM: a pick on the Map, Default model, Permissions or Theme page is saved when he leaves the page (Next,
    Back, the rail, the Summary's Change, Done), each block through its own route, in the pages' order, before the page
    changes; a refused save keeps the page and posts nothing more (no setup/done); with nothing picked the page changes
    at once. The foot says so while a pick stands."""
    import urllib.parse
    from tests.helpers import node_ts
    url = lambda src: "data:text/javascript," + urllib.parse.quote(src)  # noqa: E731
    hook = _SETUP_HOOK % json.dumps([[k, url(v)] for k, v in _SETUP_STUBS.items()])
    u = lambda n: json.dumps((SETUP_UI / n).resolve().as_uri())  # noqa: E731
    js = (_SETUP_JS.replace("__HOOK__", json.dumps(hook)).replace("__STORE__", u("store.ts")).replace("__PAGES__", u("pages.ts"))
          .replace("__DONE__", u("done.ts")))
    got = node_ts.run(js)
    ctx.check(f"Next on the Map page: setup/team {{map: ship-it}} posted on the Map page, then the next page, got {got.get('next')}",
              got.get("next") == [True, [["setup/team", {"map": "ship-it"}, "team"]], "check", "ship-it", {}])
    ctx.check(f"Back on the Theme page: setup/config theme posted first, got {got.get('back')}",
              got.get("back") == [True, [["setup/config", {"key": "theme", "value": "holo"}, "theme"]], "permissions"])
    ctx.check(f"the rail: model, mode, theme, map saved in the pages' order before the page changes, got {got.get('rail')}",
              got.get("rail") == [True, [["setup/config", {"key": "model", "value": "m-new"}, "model"],
                                         ["setup/config", {"key": "permission_mode", "value": "plan"}, "model"],
                                         ["setup/config", {"key": "theme", "value": "holo"}, "model"],
                                         ["setup/team", {"map": "mine"}, "model"]], "summary"])
    ctx.check(f"a refused save keeps the page and the pick, got {got.get('refused')}",
              got.get("refused") == [False, ["setup/team"], "team", "nope"])
    ctx.check(f"Done with a refused save posts no setup/done, got {got.get('doneRefused')}",
              got.get("doneRefused") == [False, ["setup/team"]])
    ctx.check(f"Done saves the pick before setup/done, got {got.get('done')}", got.get("done") == [True, ["setup/team", "setup/done"], "ship-it"])
    ctx.check(f"nothing picked: the page changes at once and nothing is posted, got {got.get('sync')}", got.get("sync") == ["providers", True, 0])
    foot = (SETUP_UI / "BlockFoot.tsx").read_text(encoding="utf-8")
    ctx.check("the foot's line while a pick stands ends with \" · saved when you leave this page\"",
              '" · saved when you leave this page"' in foot)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
