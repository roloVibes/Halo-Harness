"""halo_harness.studio.setup_api -- the routes of Studio's Setup section (Halo
3.3.0.0 R1; docs/STUDIO-sections.md "Setup"): the terminal wizard's blocks
as forms, each saved on its own. Same loopback / origin / token guard as
every Studio route; every write lands in `~/.halo/config.json` through the
functions the wizard and `halo config set` use, and the answer is the fresh
state (studio/setup_state.py) plus the lines saying what was written.

    GET  setup/state                    the blocks' values and rows (setup_state.setup_state)
    POST setup/config {key, value}      key one of model | permission_mode | theme; the value checked
                                        against the rows the state lists, then `set_config_value`
                                        -> 200 {...state, lines}; 422 {error, problems} and nothing written
    POST setup/team {map}               3.6.0.0 R5, the Map step (the Team step before): new sessions run on that
                                        map (config `crew.map`, as `halo maps use`; `starter` = the default, the key
                                        unset; `one-model` = One model for everything, roles off and no map)
                                        -> 200 {...state, lines}; a body naming a lineup gets one line: lineups are gone
    GET  setup/team/<name>/preview      {name, lines}: the map in words (crew/tools_show.py, as `halo maps show`)
    POST setup/provider/<name>, setup/ollama-host[/remove], setup/hf, setup/model-dir, setup/runtime
                                        the Providers and Local models blocks (studio/setup_providers_api.py, R2)
    POST setup/check, GET setup/check, POST setup/check/stop, POST setup/linux-fixes
                                        the Check and Linux fixes blocks (studio/setup_check_api.py, R3)
    POST setup/done                     3.3.3.0 R1: the Summary's Done: <state>/setup-done.json and a `setup` frame
                                        {stage: "done", at} -> {ok, done_at}; the state's `done_at` (studio/setup_done.py)
    GET setup/packs, GET|POST setup/packs/<id>/<block>
                                        3.3.11.0 R3: a pack's own Setup blocks (studio/setup_packs_api.py)
    GET setup/copilot, POST setup/copilot/config|signin|signout
                                        3.3.17.0 R2: the Copilot card of Providers (studio/setup_copilot_api.py)

The page reads the state again on `files_changed` (config.json moved: a
`halo config set` in a terminal, another Studio), so every open Setup page
shows what is on disk.
"""

from __future__ import annotations

import re

WHITELIST = ("model", "permission_mode", "theme")
_PREVIEW = re.compile(r"^setup/team/(?P<name>[A-Za-z0-9@][A-Za-z0-9_.@-]*)/preview$")


def _body(req) -> dict:
    return req.body if isinstance(req.body, dict) else {}


def _refused(lines: list):
    return 422, {"error": lines[0] if lines else "not saved", "problems": list(lines)}


def _state(req) -> dict:
    from halo_harness.studio.setup_state import setup_state
    return setup_state(req.cwd, req.state_dir)


def get_state(req):
    return 200, _state(req)


def _check(key: str, value: str, req) -> "list[str]":
    """Why `value` cannot be saved for `key` ([] when it can): the same rows the block offers."""
    from halo_harness.studio import setup_state as S
    if not value:
        return [f"{key}: the body needs a value"]
    if key == "permission_mode":
        modes = [r["id"] for r in S.permission_rows()]
        return [] if value in modes else [f"permission_mode: {value!r} is not a permission mode (one of {', '.join(modes)})"]
    if key == "theme":
        from halo_harness.themes.cli import ten_words  # 3.3.12.0 R1: the registry's names, a modifier included
        from halo_harness.themes.registry import is_name
        return [] if is_name(value) else [f"theme: {value!r} is not a palette (one of {ten_words()})"]
    refs = {r["ref"] for r in S.model_list(req.state_dir, req.cwd)}
    if value in refs:
        return []
    if not refs:
        return [f"model: {value!r} is not in the model catalog: no provider here lists a model yet (set one up first)"]
    return [f"model: {value!r} is not in the model catalog of the providers set up here (halo models lists them)"]


def post_config(req):
    body = _body(req)
    key = str(body.get("key") or "").strip()
    if key not in WHITELIST:
        return _refused([f"{key or '(no key)'!s} is not a Setup key: Setup saves {', '.join(WHITELIST)}"
                         " (halo config set changes any other key)"])
    value = body.get("value")
    value = value.strip() if isinstance(value, str) else ""
    problems = _check(key, value, req)
    if problems:
        return _refused(problems)
    from halo_harness.theme import persist_theme, set_config_value
    try:  # 3.3.12.0 R2: theme through persist_theme, which keeps a pack palette's restore record
        path = persist_theme(value) if key == "theme" else set_config_value(key, value)
    except Exception as e:  # a config.json that does not parse is never written over
        return _refused([f"{key}: {e}"])
    return 200, {**_state(req), "lines": [f"{key} = {value} (saved to {path})"]}


def _known(name: str, req) -> bool:
    from halo_harness.crew import store
    return store.find("map", name, cwd=req.cwd, state_dir=req.state_dir) is not None


def post_team(req):
    body = _body(req)
    name = str(body.get("map") or "").strip()
    if not name and body.get("lineup"):
        return _refused(["lineups are gone: pick a map (halo maps list names them)"])
    if not name:
        return _refused(["the body needs map: a map name (halo maps list names them)"])
    from halo_harness.crew.changes_map import ONE_MODEL, config_path, config_text
    if name != ONE_MODEL and not _known(name, req):
        return _refused([f"no map named {name!r} here (halo maps list names them)"])
    from halo_harness.crew.changes import write_all
    from halo_harness.crew.compile import DEFAULT_MAP
    write_all({config_path(): config_text(name)})
    line = (ONE_MODEL_LINE if name == ONE_MODEL else
            f"crew.map unset: new sessions draw the map {name} (the default)" if name == DEFAULT_MAP else
            f"crew.map = {name}: new sessions run on the map {name}")
    return 200, {**_state(req), "lines": [line]}


ONE_MODEL_LINE = "One model for everything: roles.enabled = false, no map; main does every job on your model"


def get_preview(req, name: str):
    from halo_harness.crew.changes_map import ONE_MODEL
    if name == ONE_MODEL:
        return 200, {"name": name, "lines": ["One model for everything: no map. Main does every job on the session's model",
                                             "and hands nothing to other agents (roles off, as Setup's choice before 3.6)."]}
    if not _known(name, req):
        return 404, {"error": f"no map named {name!r} here"}
    from halo_harness.crew.tools_show import studio_show
    text = studio_show({"what": "map", "name": name}, {"cwd": req.cwd, "state_dir": req.state_dir}).get("text") or ""
    return 200, {"name": name, "lines": str(text).splitlines()}


def dispatch_setup(req):
    from halo_harness.studio.setup_providers_api import dispatch_setup_providers  # 3.3.0.0 R2: Providers, Local models
    answered = dispatch_setup_providers(req)
    if answered is not None:
        return answered
    from halo_harness.studio.setup_check_api import dispatch_setup_check  # 3.3.0.0 R3: Check, Linux fixes
    answered = dispatch_setup_check(req)
    if answered is not None:
        return answered
    from halo_harness.studio.setup_done import post_done  # 3.3.3.0 R1: the Summary's Done
    if req.path == "setup/done-at" and req.method == "GET":  # 3.6.0.0 R14: what `halo init` polls each second
        from halo_harness.studio.setup_done import setup_done_at
        return 200, {"done_at": setup_done_at(req.state_dir)}
    routes = {"setup/state": ("GET", get_state), "setup/config": ("POST", post_config), "setup/team": ("POST", post_team),
              "setup/done": ("POST", post_done)}
    if req.path in routes:
        method, fn = routes[req.path]
        return fn(req) if req.method == method else (405, {"error": "method not allowed"})
    m = _PREVIEW.match(req.path)
    if m:
        return get_preview(req, m["name"]) if req.method == "GET" else (405, {"error": "method not allowed"})
    return 404, {"error": f"no route for {req.method} /api/{req.path}"}


# 3.3.0.0 R5 (Ollama everywhere): `setup/ollama/find|scan|add|measure` (studio/setup_discover_api.py) answer first;
# every other path goes on to the routes above.
_dispatch_setup_before_r5 = dispatch_setup


def dispatch_setup(req):  # noqa: F811  (the R5 routes, then the routes above)
    from halo_harness.studio.setup_discover_api import dispatch_setup_discover
    answered = dispatch_setup_discover(req)
    return answered if answered is not None else _dispatch_setup_before_r5(req)


# 3.3.11.0 R3: `setup/packs` and `setup/packs/<id>/<block>`, a pack's own Setup blocks (studio/setup_packs_api.py),
# answer first; every other path goes on to the routes above.
_dispatch_setup_before_packs = dispatch_setup


def dispatch_setup(req):  # noqa: F811  (a pack's blocks, then the routes above)
    from halo_harness.studio.setup_packs_api import dispatch_setup_packs
    answered = dispatch_setup_packs(req)
    return answered if answered is not None else _dispatch_setup_before_packs(req)


# 3.3.17.0 R2: `setup/copilot[/config|/signin|/signout]`, the Copilot card of Providers (studio/setup_copilot_api.py),
# answer first; every other path goes on to the routes above.
_dispatch_setup_before_copilot = dispatch_setup


def dispatch_setup(req):  # noqa: F811  (the Copilot card, then the routes above)
    from halo_harness.studio.setup_copilot_api import dispatch_setup_copilot
    answered = dispatch_setup_copilot(req)
    return answered if answered is not None else _dispatch_setup_before_copilot(req)
