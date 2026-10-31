"""halo_harness.studio.settings_api -- the routes of Studio's Settings section (Halo 3.3.3.0 R2; docs/STUDIO-sections.md
"Settings"): every key of `~/.halo/config.json` from one catalog (halo_harness/settings_catalog.py). Same loopback /
origin / token guard as every Studio route; every write goes through `theme.set_config_value`, the path
`halo config set` takes, with its refusals (a theme name it does not know, a key of a removed feature).

    GET  settings/catalog            {groups, rows, kinds, effects}: the catalog as JSON
    GET  settings/values             {values: {row key: {value, set, default, masked, cli[, entries, section]}}}:
                                     the saved value per row (masked as `halo config get` masks, a secret row only
                                     says it is set), a keyed row's saved entries and its whole section
    POST settings/set {key, value}   the row (or a keyed row's entry: `connectors.gmail.enabled`, `ollama.hosts[lan].ssh`;
                                     or a keyed row's whole section, a mapping) must exist; the value coerced and checked
                                     by kind and choices -> 422 {error, problems} and nothing written; else written ->
                                     200 {key, row, value, set, effect, effect_words, line, cli, entry}
    POST settings/unset {key}        the key removed (a section it leaves empty with it) -> 200 {..., set: false, default}

The page reads the values again on `files_changed` (config.json moved: a `halo config set` in a terminal, another
Studio, the Setup section). No answer and no log line ever carries a key or a token.
"""

from __future__ import annotations


def _body(req) -> dict:
    return req.body if isinstance(req.body, dict) else {}


def _refused(lines: list):
    return 422, {"error": lines[0] if lines else "not saved", "problems": list(lines)}


def _data() -> dict:
    from halo_harness.theme import load_config
    return load_config()


def get_catalog(_req):
    from halo_harness.settings_catalog import catalog_json
    return 200, catalog_json()


def get_values(_req):
    from halo_harness.studio.settings_values import values
    return 200, {"values": values(_data())}


def _section_row(key: str):
    """The keyed row whose whole section is `key` (the JSON editor under a keyed row's table), or None."""
    from halo_harness.settings_catalog import keyed_parts, rows
    return next((r for r in rows() if r.kind == "keyed" and keyed_parts(r)[0] == key and not keyed_parts(r)[2]), None)


def _resolve(key: str):
    """(row, entry, kind, problems): what a posted key writes and with which control's rules."""
    from halo_harness.schemas.config_json import REMOVED_KEYS, removed_key_line
    from halo_harness.settings_catalog import leaf_kind, match
    if not key:
        return None, "", "", ["the body needs key: a config key"]
    if key in REMOVED_KEYS:
        return None, "", "", [removed_key_line(key)]
    r, entry = match(key)
    if r is None:
        sec = _section_row(key)
        if sec is not None:
            return sec, "", "mapping", []
        return None, "", "", [f"{key}: not a config key Settings knows (docs/CONFIG.md lists every key)"]
    if r.kind == "keyed" and not entry:
        return None, "", "", [f"{key}: name the entry ({r.key.replace('[]', '[<name>]')})"]
    return r, entry, leaf_kind(r) if r.kind == "keyed" else r.kind, []


def _answer(key: str, r, is_set: bool, value=None) -> dict:
    from halo_harness.settings_catalog import cli_line, effect_words
    from halo_harness.studio.settings_values import masked, value_of
    words = effect_words(r.effect)
    shown = masked(key, value, r.secret) if is_set else None
    line = f"{key} saved: {words}" if is_set else f"{key} back to its default: {words}"
    return {"key": key, "row": r.key, "value": shown, "set": is_set, "default": r.default, "effect": r.effect,
            "effect_words": words, "line": line, "cli": cli_line(key, None if r.secret else (value if is_set else r.default)),
            "entry": value_of(r, _data())}


def post_set(req):
    from halo_harness import theme as T
    from halo_harness.settings_catalog import keyed_parts
    from halo_harness.studio.settings_values import coerce, write_list_entry
    body = _body(req)
    key = str(body.get("key") or "").strip()
    r, entry, kind, problems = _resolve(key)
    if problems:
        return _refused(problems)
    if key == "theme" and not T.is_valid_theme(body.get("value")):  # the words `halo config set theme` says
        value = body.get("value")
        return _refused([f"not a valid theme name: {value!r} (expected one of {sorted(T.VALID_THEMES)})" + T.removed_theme_hint(value)])
    value, problems = coerce(kind, r.choices, body.get("value"), key, r.secret)
    if problems:
        return _refused(problems)
    try:
        section, leaf, listy = keyed_parts(r) if r.kind == "keyed" else ("", "", False)
        if listy:
            problems = write_list_entry(section, entry, leaf, value)
            if problems:
                return _refused(problems)
        else:
            T.set_config_value(key, value)
    except T.CorruptConfigError as e:  # a config.json that does not parse is never written over
        return _refused([f"{key}: {e}"])
    from halo_harness.studio.settings_values import walk
    got = walk(_data(), key) if not listy else value
    return 200, _answer(key, r, True, got)


def post_unset(req):
    from halo_harness import theme as T
    from halo_harness.schemas.config_json import REMOVED_KEYS
    from halo_harness.settings_catalog import keyed_parts
    from halo_harness.studio.settings_values import write_list_entry
    key = str(_body(req).get("key") or "").strip()
    if key in REMOVED_KEYS:  # a removed feature's leftover: Reset takes it out
        T.unset_config_value(key)
        return 200, {"key": key, "set": False, "line": f"{key} removed"}
    r, entry, _kind, problems = _resolve(key)
    if problems:
        return _refused(problems)
    try:
        section, leaf, listy = keyed_parts(r) if r.kind == "keyed" else ("", "", False)
        if listy:
            problems = write_list_entry(section, entry, leaf, remove=True)
            if problems:
                return _refused(problems)
        else:
            T.unset_config_value(key)
    except T.CorruptConfigError as e:
        return _refused([f"{key}: {e}"])
    return 200, _answer(key, r, False)


def _profiles_now(key: str):
    if not key.startswith("ollama.profiles"):
        return None
    from halo_harness.ollama_steward.profiles import all_profiles
    return all_profiles()


def _profile_rows(req, key: str, before) -> None:
    """3.3.6.0 R5: an edit of ollama.profiles from Settings is a change with a scope (ollama_steward/changes.py): keep,
    or until-restart when the body names it."""
    if before is None:
        return
    from halo_harness.ollama_steward import changes
    from halo_harness.ollama_steward.profiles import CHANGEABLE, all_profiles
    after, scope = all_profiles(), str(_body(req).get("scope") or "keep")
    for k in sorted(set(before) | set(after)):
        b, a = before.get(k) or {}, after.get(k) or {}
        for f in CHANGEABLE:
            if b.get(f) != a.get(f):
                changes.record(req.state_dir, by="settings", key=k, field=f, before=b.get(f), after=a.get(f),
                               scope=scope if scope in ("keep", "until-restart") else "keep", why="Settings",
                               before_by=b.get("by"))


def _with_rows(fn):
    def run(req):
        key = str(_body(req).get("key") or "").strip()
        before = _profiles_now(key)
        code, answer = fn(req)
        if code == 200:
            _profile_rows(req, key, before)
        return code, answer
    return run


ROUTES = {"settings/catalog": ("GET", get_catalog), "settings/values": ("GET", get_values),
          "settings/set": ("POST", _with_rows(post_set)), "settings/unset": ("POST", _with_rows(post_unset))}


def dispatch_settings(req):
    if req.path in ROUTES:
        method, fn = ROUTES[req.path]
        return fn(req) if req.method == method else (405, {"error": "method not allowed"})
    return 404, {"error": f"no route for {req.method} /api/{req.path}"}
