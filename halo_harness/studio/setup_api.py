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
    POST setup/team {lineup}            a lineup name, "one-model" or "auto": the Team step's three
                                        writes (lineup_choice.apply_lineup_choice) -> 200 {...state, lines}
    GET  setup/team/<name>/preview      {name, lines}: the Team step's preview (team_preview.preview_lines)
    POST setup/provider/<name>, setup/ollama-host[/remove], setup/hf, setup/model-dir, setup/runtime
                                        the Providers and Local models blocks (studio/setup_providers_api.py, R2)
    POST setup/check, GET setup/check, POST setup/check/stop, POST setup/linux-fixes
                                        the Check and Linux fixes blocks (studio/setup_check_api.py, R3)
    POST setup/done                     3.3.3.0 R1: the Summary's Done: <state>/setup-done.json and a `setup` frame
                                        {stage: "done", at} -> {ok, done_at}; the state's `done_at` (studio/setup_done.py)

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
        names = [r["name"] for r in S.theme_rows()]
        return [] if value in names else [f"theme: {value!r} is not a terminal theme (one of {', '.join(names)})"]
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
    from halo_harness.theme import set_config_value
    try:
        path = set_config_value(key, value)
    except Exception as e:  # a config.json that does not parse is never written over
        return _refused([f"{key}: {e}"])
    return 200, {**_state(req), "lines": [f"{key} = {value} (saved to {path})"]}


def _known(name: str, req) -> bool:
    from halo_harness import teams_yaml as T
    from halo_harness.lineup_choice import is_one_model
    if is_one_model(name):
        return True
    T.ensure_builtin_team_templates(state_dir=req.state_dir)
    return name in T.list_team_templates(cwd=req.cwd, state_dir=req.state_dir)


def post_team(req):
    from halo_harness.lineup_choice import apply_lineup_choice
    name = str(_body(req).get("lineup") or "").strip()
    if not name:
        return _refused(["the body needs lineup: a lineup name, one-model or auto"])
    if not _known(name, req):
        return _refused([f"no lineup named {name!r} here (halo teams list names them)"])
    details: list = []
    ok, line, _kind = apply_lineup_choice(name, cwd=req.cwd, state_dir=req.state_dir, details=details)
    if not ok:
        return _refused([line])
    return 200, {**_state(req), "lines": [line], "details": details}  # 3.3.5.0 R0 (h): the per-role notes


def get_preview(req, name: str):
    from halo_harness.lineup_choice import is_one_model
    from halo_harness.tui.dialogs.team_preview import ONE_MODEL_ID, preview_lines
    if not _known(name, req):
        return 404, {"error": f"no lineup named {name!r} here"}
    target = ONE_MODEL_ID if is_one_model(name) else name
    lines = preview_lines(target, cwd=req.cwd, state_dir=req.state_dir, width=400)  # wide: the page wraps them
    return 200, {"name": name, "lines": lines}


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
