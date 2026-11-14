"""halo_harness.settings_catalog -- every key of `~/.halo/config.json` as one row (Halo 3.3.3.0 R2).

Studio's Settings section (Alt+9), `halo settings --terminal`, the palette's "Settings: <title>" entries and
the `settings/` routes (studio/settings_api.py) all draw from this one list. A row is

    Row(key, group, title, kind, default, choices, help, effect, secret)

`key` is the dotted path `halo config set` takes; a `keyed` row has a placeholder segment
(`connectors.<slug>.enabled`, `databricks.gateway.<endpoint>`, `ollama.hosts[].ssh`): the row describes the
leaf, and the saved config holds its entries. `default` is the value Halo uses when the key is unset (None:
derived at run time, the help line says from what). `choices` are an `enum` row's values (a keyed row's: its
leaf's). `effect` says when a change is read: "now" (read fresh per call), "next session" (read when a session
starts), "next launch" (read when the process starts). `secret`: the value is never shown, only that it is set.

The rows live in `settings_catalog_rows_*.py`, one row per line; tests/test_settings_catalog.py holds them, the
config schema (schemas/config_json.py) and docs/CONFIG.md's key table to the same set of keys.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Optional

KINDS = ("bool", "enum", "int", "float", "string", "list", "mapping", "model", "path", "keyed")
kinds = KINDS
EFFECTS = ("now", "next session", "next launch")
EFFECT_WORDS = {"now": "takes effect now", "next session": "takes effect in the next session",
                "next launch": "takes effect on the next launch"}

GROUPS = (("general", "General"), ("studio", "Studio"), ("agents", "Agents and roles"),
          ("knowledge", "Knowledge and recall"), ("supervise", "Supervise"), ("steer", "Steer and turn"),
          ("models", "Models"), ("providers", "Providers"), ("ollama", "Ollama"), ("network", "Network and routing"),
          ("remote", "Remote"), ("packs", "Packs"), ("connectors", "Connectors"),
          ("worktree", "Worktree"), ("update", "Update"), ("local", "Local"), ("from_packs", "From packs"))
#: 3.4.0.0 B2: an enabled pack's `contributes.settings` rows (packs/contrib_settings.py), `packs.settings.<id>.<key>`
PACK_KINDS = {"string": "string", "integer": "int", "number": "float", "boolean": "bool"}
GROUP_TITLES = dict(GROUPS)

_PLACEHOLDER = re.compile(r"<[^>]+>|\[\]")
_PLAIN = re.compile(r"[\w@%+=:,./~-]+")


@dataclass(frozen=True)
class Row:
    key: str
    group: str
    title: str
    kind: str
    default: Any
    choices: tuple = field(default_factory=tuple)
    help: str = ""
    effect: str = "now"
    secret: bool = False

    def to_json(self) -> dict:
        out = {"key": self.key, "group": self.group, "title": self.title, "kind": self.kind, "default": self.default,
               "choices": list(self.choices), "help": self.help, "effect": self.effect, "effect_words": EFFECT_WORDS[self.effect],
               "secret": self.secret, "page": studio_page(self)}
        if self.kind == "keyed":
            section, leaf, listy = keyed_parts(self)
            out.update(leaf_kind=leaf_kind(self), section=section, leaf=leaf, listy=listy, entry_names=list(entry_names(self)))
        return out


_ROWS: "list[Row] | None" = None


def rows() -> "list[Row]":
    """Every row, in the groups' order and, inside a group, the order the rows files give; last, the rows of the
    packs enabled here (group "From packs", read each call: a pack turned off takes its rows with it)."""
    global _ROWS
    if _ROWS is None:
        from halo_harness import settings_catalog_rows_a as A, settings_catalog_rows_b as B, settings_catalog_rows_c as C
        found = [*A.ROWS, *B.ROWS, *C.ROWS]
        order = [g for g, _ in GROUPS]
        _ROWS = sorted(found, key=lambda r: order.index(r.group) if r.group in order else len(order))
    return list(_ROWS) + pack_rows()


def pack_rows() -> "list[Row]":
    """3.4.0.0 B2: the `contributes.settings` rows of every enabled pack, `packs.settings.<id>.<key>`."""
    try:
        from halo_harness.packs.contrib_settings import rows as contributed
        got = contributed()
    except Exception:
        return []
    return [Row(r["key"], "from_packs", f"{r['title']} ({r['pack']})", PACK_KINDS[r["type"]], r.get("default"), (),
                (r.get("help") or "") + f" From the {r['pack']} pack.", "now") for r in got if r.get("type") in PACK_KINDS]


def shown() -> "list[Row]":
    """The rows Settings shows: every row."""
    return rows()


def row(key: str) -> Optional[Row]:
    """The row whose key is exactly `key` (a keyed row by its placeholder key), or None."""
    return next((r for r in rows() if r.key == key), None)


def groups() -> "list[dict]":
    """[{id, title, count}] in the rail's order; "From packs" only while an enabled pack has rows (3.4.0.0 B2)."""
    counts: dict = {}
    for r in shown():
        counts[r.group] = counts.get(r.group, 0) + 1
    return [{"id": g, "title": t, "count": counts.get(g, 0)} for g, t in GROUPS
            if g != "from_packs" or counts.get(g)]


def studio_page(r: Row) -> str:
    """Where the row is in Studio: `Settings -> Fleet` (docs/CONFIG.md's Studio column)."""
    return f"Settings -> {GROUP_TITLES.get(r.group, r.group)}"


def keyed_parts(r: Row) -> "tuple[str, str, bool]":
    """(section, leaf, listy) of a keyed row: `connectors.<slug>.enabled` -> ('connectors', 'enabled', False);
    `databricks.gateway.<endpoint>` -> ('databricks.gateway', '', False); `ollama.hosts[].ssh` -> ('ollama.hosts',
    'ssh', True)."""
    parts = r.key.split(".")
    for i, part in enumerate(parts):
        if part.endswith("[]"):
            return ".".join(parts[:i] + [part[:-2]]), ".".join(parts[i + 1:]), True
        if _PLACEHOLDER.fullmatch(part):
            return ".".join(parts[:i]), ".".join(parts[i + 1:]), False
    return r.key, "", False


def leaf_kind(r: Row) -> str:
    """The control of one entry of a keyed row, from its choices and default: enum, bool, int, float, mapping,
    list, else string; a role's model (`roles.<role>`) is a model."""
    if r.kind != "keyed":
        return r.kind
    if r.key == "roles.<role>":  # 3.4.1.3: a role's model is picked from the catalog (a mapping value keeps its JSON)
        return "model"
    if r.choices:
        return "enum"
    d = r.default
    if isinstance(d, bool):
        return "bool"
    if isinstance(d, int):
        return "int"
    if isinstance(d, float):
        return "float"
    if isinstance(d, dict):
        return "mapping"
    if isinstance(d, list):
        return "list"
    return "string"


def entry_names(r: Row) -> tuple:
    """The entry names a keyed row lists even before one is saved (the providers, the built-in roles)."""
    if r.key == "providers.<name>.enabled":
        from halo_harness.providers.enablement import PROVIDER_NAMES
        return tuple(PROVIDER_NAMES)
    if r.key == "roles.<role>":
        from halo_harness.roles import ROLE_NAMES
        return tuple(ROLE_NAMES)
    return ()


def _keyed_pattern(r: Row) -> "re.Pattern":
    out = ""
    for piece in re.split(r"(<[^>]+>|\[\])", r.key):
        if piece == "[]":
            out += r"\[(?P<entry>[^\]]+)\]"
        elif piece.startswith("<"):
            out += r"(?P<entry>[^.\[\]]+)"
        else:
            out += re.escape(piece)
    return re.compile(out + r"\Z")


def match(key: str) -> "tuple[Optional[Row], str]":
    """The row a concrete key belongs to and the entry name it fills: `control.enabled` -> (its row, '');
    `connectors.gmail.enabled` -> (`connectors.<slug>.enabled`, 'gmail'); `ollama.hosts[lan].ssh` ->
    (`ollama.hosts[].ssh`, 'lan'); (None, '') when no row holds it. An exact row wins over a keyed one."""
    exact = row(key)
    if exact is not None:
        return exact, ""
    for r in rows():
        if r.kind != "keyed":
            continue
        m = _keyed_pattern(r).match(key)
        if m and not (r.key == "roles.<role>" and m["entry"] in ("enabled", "editor")):
            return r, m["entry"]
    return None, ""


def _cli_value(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return json.dumps(value)
    if isinstance(value, str):
        try:
            json.loads(value)
            looks_json = True
        except ValueError:
            looks_json = False
        text = json.dumps(value) if looks_json else value
        if _PLAIN.fullmatch(text) and not looks_json:
            return text
        return "'" + text.replace("'", "'\\''") + "'"
    text = json.dumps(value)
    return "'" + text.replace("'", "'\\''") + "'"


def cli_line(key: str, value) -> str:
    """The `halo config set` line that writes `value` to `key`: `halo config set control.enabled true`, JSON in
    single quotes for a list or a mapping. None: the placeholder `<value>`. A `[]` row's field lives in each
    entry of its list, so its line sets the whole list (`value` is that list)."""
    if "[]" in key:
        key = key.split("[]", 1)[0]
    if value is None:
        return f"halo config set {key} <value>"
    return f"halo config set {key} {_cli_value(value)}"


def effect_words(effect: str) -> str:
    return EFFECT_WORDS.get(effect, EFFECT_WORDS["now"])


def catalog_json() -> dict:
    """`GET settings/catalog`: the groups and the rows."""
    return {"groups": groups(), "rows": [r.to_json() for r in shown()], "kinds": list(KINDS), "effects": list(EFFECTS)}
