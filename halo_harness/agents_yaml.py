"""halo_harness.agents_yaml -- Halo 2.0.4 round 4 (deliverable 6, two-layer
design approved 2026-10-05 ~22:45/later same night): an AGENT BIO is one
YAML file per agent NAME, describing what that agent IS (models, tools,
context, limits, output, environment, acceptance) -- never a role or an
org position; a bio is a reusable building block a TEAM TEMPLATE
(`teams_yaml.py`) assigns to a role/position. See `docs/AGENTS.md` for
the full field reference and `plans/ROADMAP.md`'s "agent declaration
files" section for the approved schema.

Storage (nearest wins, same precedence `team_config.py`'s own project/
user split and `config/agents_md.py`'s `.claude/agents` search already
use): `.halo/agents/<name>.yaml` (project, relative to cwd) -> `~/.halo/
agents/<name>.yaml` (user) -> `halo_harness/templates/agents/<name>.yaml`
(shipped, read-only -- never written to, used for `--from <template>`
and as an `extends:` target). `extends: <name>` resolves against this
SAME search order, merged ONE SECTION AT A TIME (a child's own key inside
e.g. `models` overrides the parent's same key; a section the child never
mentions at all is inherited whole) -- "an agent file carries only
overrides" (the roadmap's own wording), never a deep per-field diff.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

# Halo 2.0.4 round 4: pyyaml added to pyproject's dependencies specifically
# for this round (bios + team templates) -- every read/write of a `.yaml`
# file in this module and `teams_yaml.py` goes through here, never a
# second `import yaml` elsewhere, so a parse-error message stays
# consistent and a future swap (ruamel, a stricter loader, ...) touches
# one place.
import yaml

_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")

# The eight BIO sections (roadmap wording) -- "identity" isn't its own
# nested section, its fields (name/description/version/tags/kind/extends)
# live at the TOP level, same as a role template's own "name"/
# "description". No "org"/role section at all (two-layer refinement:
# "No role or org position inside a bio").
BIO_SECTIONS = ("models", "tools", "context", "limits", "output", "environment", "acceptance")
IDENTITY_FIELDS = ("name", "description", "version", "tags", "kind", "extends")
KNOWN_KINDS = ("main", "subagent", "researcher", "judge", "reviewer", "custom")


def is_valid_agent_name(name: str) -> bool:
    """Same "safe, single path segment" bar `roles.is_valid_template_name`
    already applies to a role template's own file stem."""
    return bool(name) and bool(_NAME_RE.match(name)) and ".." not in name


def bundled_agent_templates_dir() -> Path:
    return Path(__file__).resolve().parent / "templates" / "agents"


def user_agents_dir(state_dir=None) -> Path:
    from halo_harness.config.paths import bridge_home
    base = state_dir if state_dir is not None else bridge_home()
    return Path(base) / "agents"


def project_agents_dir(cwd=None) -> Path:
    base = cwd if cwd is not None else Path.cwd()
    return Path(base) / ".halo" / "agents"


def agent_search_dirs(*, cwd=None, state_dir=None) -> "list[tuple[Path, str]]":
    """`[(dir, source_label), ...]`, NEAREST WINS first -- project, then
    user, then the shipped, read-only templates (an `extends:`/`--from`
    target, never itself a place `save_agent_bio` writes to)."""
    return [(project_agents_dir(cwd), "project"), (user_agents_dir(state_dir), "user"),
            (bundled_agent_templates_dir(), "template")]


def _read_yaml_file(path: Path) -> "Optional[dict]":
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError:
        return None
    return data if isinstance(data, dict) else (None if data is not None else {})


def _write_yaml_file(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = yaml.safe_dump(data, sort_keys=False, default_flow_style=False, allow_unicode=True)
    path.write_text(text, encoding="utf-8")


def list_agent_bios(*, cwd=None, state_dir=None, include_templates: bool = True) -> "list[str]":
    """Every agent name reachable from here, deduplicated (nearest-wins
    source is irrelevant to this LIST, only to which file `load_agent_
    bio` actually reads for a given name), sorted. `include_templates`:
    whether a shipped template with no project/user override of its own
    name also counts as an installed bio (brief: these ARE usable bios
    out of the box, not just `extends:` targets) -- off for a caller that
    only wants what the user has actually created/customized."""
    names: "set[str]" = set()
    dirs = agent_search_dirs(cwd=cwd, state_dir=state_dir)
    if not include_templates:
        dirs = [d for d in dirs if d[1] != "template"]
    for d, _source in dirs:
        try:
            names.update(p.stem for p in d.glob("*.yaml") if p.is_file())
        except OSError:
            pass
    return sorted(names)


def find_agent_bio_path(name: str, *, cwd=None, state_dir=None) -> "Optional[tuple[Path, str]]":
    for d, source in agent_search_dirs(cwd=cwd, state_dir=state_dir):
        path = d / f"{name}.yaml"
        if path.is_file():
            return path, source
    return None


def load_agent_bio_raw(name: str, *, cwd=None, state_dir=None) -> "Optional[dict]":
    """ONE file's own contents, no `extends:` resolution -- `None` for a
    missing/unparseable file. `resolve_agent_bio` below is what callers
    outside this module should use almost always."""
    found = find_agent_bio_path(name, cwd=cwd, state_dir=state_dir)
    if found is None:
        return None
    path, source = found
    data = _read_yaml_file(path)
    if data is None:
        return None
    data = dict(data)
    _normalize_thinking_field(data)
    data["_source"] = source
    data["_path"] = str(path)
    return data


def _normalize_thinking_field(data: dict) -> None:
    """`models.thinking` only ever means the literal string `"native"` or
    `"off"` -- but YAML 1.1's bare-word boolean resolver (PyYAML's
    default) reads an UNQUOTED `off`/`on`/`yes`/`no` as the Python bool
    `False`/`True`, not the string, confirmed against the shipped
    `implementer.yaml`/`researcher.yaml`/etc. (every one of them writes
    `thinking: off` unquoted). Normalized here, once, right after the
    raw YAML read, rather than asking every shipped/hand-written bio to
    quote it (`thinking: "off"`) -- a bio author gets the plain-English
    spelling either way."""
    models = data.get("models")
    if isinstance(models, dict) and isinstance(models.get("thinking"), bool):
        models["thinking"] = "native" if models["thinking"] else "off"


def _merge_section(parent_section, child_section):
    if not isinstance(parent_section, dict):
        return child_section if child_section is not None else parent_section
    if not isinstance(child_section, dict):
        return parent_section if child_section is None else child_section
    merged = dict(parent_section)
    merged.update(child_section)
    return merged


def resolve_agent_bio(name: str, *, cwd=None, state_dir=None, _chain: "Optional[list]" = None) -> "Optional[dict]":
    """The bio `name` resolves to once `extends:` is followed all the way
    down -- each SECTION (`BIO_SECTIONS`) merged key-by-key (child's key
    wins; a section the child never mentions is inherited whole from the
    parent); identity fields (`name`/`description`/`version`/`tags`/
    `kind`) are NEVER inherited -- only `extends` itself chains, every
    other identity field always describes THIS bio. `None` for a missing
    file, a parse error, or an `extends:` CYCLE (reported by `validate_
    agent_bio`, not raised here -- this function degrades to "stop
    inheriting further" on a cycle rather than hanging)."""
    chain = _chain if _chain is not None else []
    if name in chain:
        return None
    raw = load_agent_bio_raw(name, cwd=cwd, state_dir=state_dir)
    if raw is None:
        return None
    parent_name = raw.get("extends")
    if isinstance(parent_name, str) and parent_name.strip():
        parent = resolve_agent_bio(parent_name.strip(), cwd=cwd, state_dir=state_dir, _chain=chain + [name])
    else:
        parent = None
    resolved = dict(parent) if parent else {}
    for section in BIO_SECTIONS:
        resolved[section] = _merge_section((parent or {}).get(section), raw.get(section))
    for field in ("description", "version", "tags", "kind"):
        if field in raw:
            resolved[field] = raw[field]
    resolved["name"] = name
    resolved["extends"] = raw.get("extends")
    resolved["_source"] = raw.get("_source")
    resolved["_path"] = raw.get("_path")
    return resolved


def _extends_cycle(name: str, data: dict, *, cwd=None, state_dir=None) -> "Optional[list]":
    chain = [name]
    current = data
    while True:
        parent_name = (current or {}).get("extends")
        if not isinstance(parent_name, str) or not parent_name.strip():
            return None
        parent_name = parent_name.strip()
        if parent_name in chain:
            return chain + [parent_name]
        chain.append(parent_name)
        current = load_agent_bio_raw(parent_name, cwd=cwd, state_dir=state_dir)
        if current is None:
            return None  # an unresolvable extends target is a separate problem, not a cycle


def validate_agent_bio(data, *, name: "Optional[str]" = None, cwd=None, state_dir=None) -> "list[str]":
    """One plain sentence per problem; `[]` means valid. Never raises.
    Deliberately light on the DEEPLY nested per-field shapes (a tool
    limit's own number, an acceptance block's own expected-shape text) --
    this is a storage/round-trip layer, not a schema-enforcement engine;
    `halo doctor --agents` is where a bad VALUE (e.g. a `models.
    preference` nothing can resolve) surfaces as a real, running
    problem."""
    if not isinstance(data, dict):
        return ["bio must be a YAML mapping (top-level key: value)"]
    problems = []
    if "description" in data and data["description"] is not None and not isinstance(data["description"], str):
        problems.append('"description" must be a string')
    if "tags" in data and data["tags"] is not None and not isinstance(data["tags"], list):
        problems.append('"tags" must be a list')
    kind = data.get("kind")
    if kind is not None and kind not in KNOWN_KINDS:
        problems.append(f'"kind" {kind!r} is not one of {", ".join(KNOWN_KINDS)}')
    for section in BIO_SECTIONS:
        if section in data and data[section] is not None and not isinstance(data[section], dict):
            problems.append(f'"{section}" must be a mapping')
    extends = data.get("extends")
    if extends is not None:
        if not isinstance(extends, str) or not extends.strip():
            problems.append('"extends" must be a non-empty string')
        else:
            cycle = _extends_cycle(name or (data.get("name") or "?"), data, cwd=cwd, state_dir=state_dir)
            if cycle:
                problems.append(f'"extends" forms a cycle: {" -> ".join(cycle)}')
            elif resolve_agent_bio(extends.strip(), cwd=cwd, state_dir=state_dir) is None \
                    and load_agent_bio_raw(extends.strip(), cwd=cwd, state_dir=state_dir) is None:
                problems.append(f'"extends" names an agent bio that does not exist: {extends!r}')
    return problems


def save_agent_bio(name: str, data: dict, *, cwd=None, state_dir=None, project: bool = False) -> "tuple[bool, list[str]]":
    """Writes `.halo/agents/<name>.yaml` (`project=True`) or `~/.halo/
    agents/<name>.yaml` (default) -- never to the shipped templates
    directory. `(True, [])` on success; never writes a partial/invalid
    file."""
    if not is_valid_agent_name(name):
        return False, [f"invalid agent name {name!r}"]
    problems = validate_agent_bio(data, name=name, cwd=cwd, state_dir=state_dir)
    if problems:
        return False, problems
    payload = {k: v for k, v in data.items() if not k.startswith("_")}
    payload["name"] = name
    d = project_agents_dir(cwd) if project else user_agents_dir(state_dir)
    _write_yaml_file(d / f"{name}.yaml", payload)
    return True, []


def delete_agent_bio(name: str, *, cwd=None, state_dir=None, project: bool = False) -> bool:
    d = project_agents_dir(cwd) if project else user_agents_dir(state_dir)
    try:
        (d / f"{name}.yaml").unlink()
        return True
    except OSError:
        return False


def list_bundled_agent_templates() -> "list[str]":
    """Every shipped bio under `halo_harness/templates/agents/*.yaml` --
    `halo agents new <name> --from <template>` and the Auto tab's own
    roster read this to offer starting points."""
    try:
        return sorted(p.stem for p in bundled_agent_templates_dir().glob("*.yaml") if p.is_file())
    except OSError:
        return []


def new_agent_bio_from_template(name: str, template_name: "Optional[str]" = None, *, cwd=None, state_dir=None,
                                 project: bool = False) -> "tuple[bool, list[str]]":
    """`halo agents new <name> [--from <template>]` -- `template_name`
    omitted (or not found) starts from an EMPTY bio (just `name`); found,
    copies that bio's own file VERBATIM as a new, independent bio (not an
    `extends:` reference -- "new" means a fresh, editable starting point,
    matching `roles.py`'s own `/roles new`)."""
    base = {}
    if template_name:
        base = load_agent_bio_raw(template_name, cwd=cwd, state_dir=state_dir) or {}
        base = {k: v for k, v in base.items() if not k.startswith("_")}
    base.setdefault("description", "")
    return save_agent_bio(name, base, cwd=cwd, state_dir=state_dir, project=project)
