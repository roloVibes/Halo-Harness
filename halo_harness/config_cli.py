"""halo_harness.config_cli -- `halo config ...` subcommand (U0 scope
A, harness-only: not one of Claude Code's own top-level commands). Reads
and writes THIS harness's own small local store, `~/.halo/config.json`
(theme, and whatever else accumulates there later, e.g. a model preload
list) -- never Claude Code's `settings.json`, which this project only ever
reads. `halo config` / `config list` prints every key; `config get
<key>` prints one value; `config set <key> <value>` persists one (the value
is parsed as JSON when possible, e.g. `true`/`123`/`"a string"`, so a caller
can set non-string values too, else stored as the raw string given; 3.6.0.0 R5d: a key the Settings catalog types
`list` stores a list: `a,b`, one name or a JSON list);
`config where [--json]` lists every file in effect here (config_where.py).
"""

from __future__ import annotations

import argparse
import json
import sys

from halo_harness import theme as theme_mod
from halo_harness.redact import sanitize_text


def _print_all() -> int:
    data = theme_mod.load_config()
    if not data:
        print("(no config set -- ~/.halo/config.json is empty or missing)")
        return 0
    for key in sorted(data):
        # Halo 2.0.3 fix pass C-1 (review finding 16): `halo config
        # list`/`config get` must never print a secret verbatim -- the
        # same shared `sanitize_text` pass `/export --sanitize` and
        # `halo bugreport` already use catches `"api_key": "..."`/
        # `"token": "..."` wherever they appear in the serialized value,
        # legacy plaintext entries included (an env-ref entry has
        # nothing left to mask -- it only ever holds a variable NAME).
        print(f"{key}={_mask_value(key, data[key])}")
    return 0


def _mask_value(key: str, value) -> str:
    """The serialized value, secret-shaped content redacted -- EXCEPT for
    `*_env` reference fields (2.0.6 round 12, the carried minor): a value
    like `api_key_env: "OPENROUTER_API_KEY"` holds a variable NAME, not a
    secret, and the name-based redactor masks it into uselessness; the
    reference shows while any actual secret stays hidden."""
    text = json.dumps(value)
    if key.endswith("_env") or key.split(".")[-1].endswith("_env"):
        return text
    return sanitize_text(text)


def _cmd_get(rest: list) -> int:
    parser = argparse.ArgumentParser(prog="halo config get", add_help=True)
    parser.add_argument("key")
    args = parser.parse_args(rest)
    # H10 Part B: a dotted key ("improve.model") reads a nested value;
    # a plain key is unchanged from before.
    try:
        value = theme_mod.get_config_value(args.key, default=theme_mod._MISSING)
    except KeyError:
        # get_config_value raises when the sentinel default is passed and the
        # key (or a dotted path segment) is absent -- report it, never traceback.
        value = theme_mod._MISSING
    from halo_harness.schemas.config_json import MOVED_KEYS, moved_key_line
    if args.key in MOVED_KEYS:  # 3.3.13.0 R3: an old key of a feature that is a pack now: its new home
        print(f"halo config: {moved_key_line(args.key)}", file=sys.stderr)
    bad = theme_mod.config_problem() if value is theme_mod._MISSING else ""
    if bad:  # 3.6.0.0 fx: "not set" was a lie when config.json cannot be read
        print(f"halo config: {args.key!r} is unknown: config.json cannot be read: {bad}", file=sys.stderr)
        return 2
    if value is theme_mod._MISSING and args.key == "theme":  # 3.3.15.0 R4: unset has a value everywhere
        print(f"(unset: {theme_mod.DEFAULT_THEME})")
        return 0
    from halo_harness.packs.contrib_settings import row_for  # 3.4.0.0 B2: an enabled pack's own Settings row
    pack_row = row_for(args.key) if value is theme_mod._MISSING else None
    if pack_row is not None:
        print(f"(unset: {json.dumps(pack_row['default'])}, the {pack_row['pack']} pack's default)")
        return 0
    if value is theme_mod._MISSING:
        print(f"halo config: {args.key!r} is not set", file=sys.stderr)
        return 1
    # finding 16: same masking as _print_all above (incl. the round-12
    # *_env reference-name exemption).
    print(_mask_value(args.key, value))
    return 0


def list_typed(key: str) -> bool:
    """3.6.0.0 R5d: the Settings catalog types `key` a list (settings_catalog.py: a `list` row, or a keyed row whose
    entry is one)."""
    from halo_harness.settings_catalog import leaf_kind, match
    r, _entry = match(key)
    return r is not None and leaf_kind(r) == "list"


def _item(text: str):
    try:
        got = json.loads(text)
    except ValueError:
        return text
    return got if isinstance(got, (int, float)) and not isinstance(got, bool) else text


def as_list(key: str, value):
    """3.6.0.0 R5d: the value `halo config set` stores for a list-typed key: a JSON list as given, `a,b` the list of
    its names (a number stays a number), one name a list of one, "" the empty list. A mapping, null or any other key's
    value is unchanged."""
    if isinstance(value, (list, dict)) or value is None or not list_typed(key):
        return value
    if isinstance(value, str):
        return [_item(p.strip()) for p in value.split(",") if p.strip()]
    return [value]


def _cmd_set(rest: list) -> int:
    parser = argparse.ArgumentParser(prog="halo config set", add_help=True)
    parser.add_argument("key")
    parser.add_argument("value")
    args = parser.parse_args(rest)
    try:
        value = json.loads(args.value)
    except (ValueError, TypeError):
        value = args.value
    value = as_list(args.key, value)
    if args.key == "theme" and not theme_mod.is_theme_value(value):
        from halo_harness.themes.cli import refusal  # 3.3.12.0 R1: the ten palettes named
        print(f"halo config: {refusal(value)}",
              file=sys.stderr)
        return 2
    from halo_harness.schemas.config_json import MOVED_KEYS, REMOVED_KEYS, moved_key_line, removed_key_line
    if args.key in REMOVED_KEYS:
        print(f"halo config: {removed_key_line(args.key)}", file=sys.stderr)
        return 2
    if args.key in MOVED_KEYS:  # 3.3.13.0 R3: the Signal bridge's keys are the signal pack's
        print(f"halo config: {moved_key_line(args.key)}", file=sys.stderr)
        return 2
    from halo_harness.packs.contrib_settings import row_for, value_problem  # 3.4.0.0 B2: a pack's row, its type
    pack_row = row_for(args.key)
    if pack_row is not None and value_problem(pack_row, value):
        print(f"halo config: {value_problem(pack_row, value)}", file=sys.stderr)
        return 2
    problem = _set_problem(args.key, value)
    if problem:
        print(f"halo config: {problem}", file=sys.stderr)
        return 2
    try:
        if args.key == "theme":  # 3.3.12.0 R2: through persist_theme, which keeps a pack palette's restore record
            theme_mod.persist_theme(value)
        else:
            theme_mod.set_config_value(args.key, value)
    except theme_mod.CorruptConfigError as e:
        # vibes/review.md finding 19: the human-facing writer surfaces the
        # refusal instead of crashing -- the file is left exactly as it was.
        print(f"halo config: {e}", file=sys.stderr)
        return 2
    # 2.0.6 round 12 (the carried minor): the echo masks exactly like the
    # readers -- a value that IS secret-shaped prints back redacted, so a
    # recorded/shared terminal never sees it twice.
    print(f"{args.key}={_mask_value(args.key, value)}")
    if args.key == "model" and isinstance(value, str) and value.strip():
        _main_model_lines(value.strip())  # 3.3.5.0 R0b (d)
    return 0


def _set_problem(key: str, value) -> str:
    """fix pass 2 (sessions-storage batch 2): '' when `halo config set key value` may be saved, else the one line it
    prints. A top-level key nothing reads (a typo) is refused with the nearest known key; a value outside its
    setting's choices (settings catalog) is refused; a model that does not parse is refused before it is saved
    (every later run would fail on it). Unset (null or "") is always allowed."""
    if value is None or value == "":
        return ""
    from halo_harness.schemas.check import closest_key
    from halo_harness.schemas.config_json import MOVED_IN, PACKED_SECTIONS, known_keys
    top = key.split(".", 1)[0]
    known = known_keys()
    if top not in known and top not in MOVED_IN and top not in PACKED_SECTIONS:
        near = closest_key(top, known)
        hint = f" (did you mean {near!r}?)" if near else ""
        return f"unknown key {key!r}{hint}; nothing reads it, so it was not saved"
    from halo_harness import settings_catalog
    row = settings_catalog.row(key)
    choices = tuple(row.choices) if row is not None and row.kind == "enum" and key != "theme" else ()
    if key == "permission_mode":  # every mode --permission-mode takes is read from config.json too
        choices += ("dontAsk", "bypassPermissions", "manual")
    if choices and value not in choices:
        return f"{key} is one of {', '.join(map(str, choices))}; {value!r} is not"
    # only the settings read as a routed model ref; embeddings.model, ollama.steward.model and host.steward.model
    # take an Ollama model's own name (or "none"), which parse_model_ref would wrongly refuse
    if key in ("model", "compactionModel", "studio.builder.model") and isinstance(value, str):
        from halo_harness.config.paths import bridge_home
        from halo_harness.model import parse_model_ref
        from halo_harness.providers.config import load_routes
        try:
            parse_model_ref(value.strip(), load_routes(bridge_home() / "routes.json"))
        except Exception as e:
            return f"{key}: {e}"
    return ""


def _cmd_unset(rest: list) -> int:
    """fx studio batch 2: `halo config unset <key>` -- the key leaves config.json and its default applies again (what
    Studio's Themes page and the docs offer for `theme`); a dotted key takes its leaf and any section left empty."""
    parser = argparse.ArgumentParser(prog="halo config unset", add_help=True)
    parser.add_argument("key")
    args = parser.parse_args(rest)
    try:
        gone = theme_mod.unset_config_value(args.key)
    except theme_mod.CorruptConfigError as e:
        print(f"halo config: {e}", file=sys.stderr)
        return 2
    if not gone:
        print(f"halo config: {args.key!r} is not set", file=sys.stderr)
        return 1
    print(f"{args.key} unset" + (f" (the default: {theme_mod.DEFAULT_THEME})" if args.key == "theme" else ""))
    return 0


def _main_model_lines(ref: str) -> None:
    """The main-model line when `ref` cannot orchestrate here, with the lineup command (nothing is asked)."""
    try:
        from halo_harness.agent.main_model_check import config_lines
        from halo_harness.config.paths import bridge_home
        for line in config_lines(ref, bridge_home()):
            print(line)
    except Exception:
        pass


def cmd_config(argv: list) -> int:
    if not argv or argv[0] == "list":
        return _print_all()
    if argv[0] in ("-h", "--help"):
        print("Usage: halo config [list|get <key>|set <key> <value>|unset <key>|where [--json] [--cwd DIR]]")
        return 0
    if argv[0] == "unset":
        return _cmd_unset(argv[1:])
    if argv[0] == "where":
        from halo_harness.config_where import cmd_config_where
        return cmd_config_where(argv[1:])
    if argv[0] == "get":
        return _cmd_get(argv[1:])
    if argv[0] == "set":
        return _cmd_set(argv[1:])
    # `config key=value` (Claude Code's own slash-command shorthand,
    # accepted here too since it reads naturally as a single argv token).
    if "=" in argv[0] and len(argv) == 1:
        key, _, value = argv[0].partition("=")
        return _cmd_set([key, value])
    print(f"halo config: unrecognized arguments: {' '.join(argv)}", file=sys.stderr)
    return 2
