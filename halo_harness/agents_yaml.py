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
# Halo 2.0.5 round 5: `hooks`/`schedule`/`triggers` join the merge set --
# the roadmap's own "Deferred to 2.0.5 with the Governor" deferral coming
# due; a bio's hooks/schedule/triggers inherit through `extends:` exactly
# like every other section (child's key wins inside one).
BIO_SECTIONS = ("models", "tools", "context", "limits", "output", "environment", "acceptance",
                "hooks", "schedule", "triggers")
HOOK_EVENT_KEYS = ("pre_tool", "post_tool", "on_start", "on_finish")
SCHEDULE_TRIGGER_KINDS = ("file_change", "event", "message")
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


#: Halo 2.0.5 round 2b (deliverable 2): the ONE reference literal a bio's
#: `models.preference`/`models.fallback` may hold instead of a real model
#: ref -- substituted, AT RESOLVE TIME, with the session's own current
#: default model (`~/.halo/config.json`'s plain `model` key). The shipped
#: `default-model` bio (`templates/agents/default-model.yaml`), which the
#: shipped `standard` lineup (`templates/teams/standard.yaml`) assigns to
#: every role, is the one case this matters for today; see docs/AGENTS.md.
DEFAULT_MODEL_REFERENCE = "default"


def _substitute_default_model_reference(models: dict) -> None:
    """Replaces a bare `"default"` in `preference`/`fallback` with the
    session's current default model, in place -- "resolved at run time to
    the session's default model" (the brief's own wording), so changing
    that model (the init wizard's own Default model step, `halo config
    set model ...`, `/model`) moves every role that uses it the very next
    time a bio resolves, with no file to re-save. Left exactly as typed
    when there is no session default configured yet (never resolved to
    `None`/empty) -- same leniency an unknown ref anywhere else in this
    codebase already gets; a caller that cares can still see the literal
    `"default"` and act on it (`roles.py`'s own cost-aware-default rung
    works the same way for an entirely empty role table)."""
    from halo_harness.theme import get_config_value
    for key in ("preference", "fallback"):
        if models.get(key) == DEFAULT_MODEL_REFERENCE:
            real = get_config_value("model", default=None)
            if isinstance(real, str) and real.strip():
                models[key] = real.strip()


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
    if isinstance(resolved.get("models"), dict):
        _substitute_default_model_reference(resolved["models"])
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


def validate_hook_section(hooks) -> "list[str]":
    """Halo 2.0.5 round 5 (deliverable 2): a bio's `hooks:` -- keys are the
    four agent-scoped events (`pre_tool`/`post_tool`/`on_start`/`on_finish`),
    each value a LIST of Claude-Code-hook-shaped entries `{command, match?,
    timeout?}` (a plain string is accepted as a one-command shorthand).
    One plain line per problem, never raises; `[]` for None/valid."""
    if hooks is None:
        return []
    if not isinstance(hooks, dict):
        return ['"hooks" must be a mapping of pre_tool/post_tool/on_start/on_finish to hook entries']
    problems: "list[str]" = []
    for key, entries in hooks.items():
        if key not in HOOK_EVENT_KEYS:
            problems.append(f'"hooks.{key}" is not one of {", ".join(HOOK_EVENT_KEYS)}')
            continue
        if isinstance(entries, (str, dict)):
            entries = [entries]
        if not isinstance(entries, list):
            problems.append(f'"hooks.{key}" must be a list of hook entries')
            continue
        for i, entry in enumerate(entries):
            if isinstance(entry, str):
                continue  # the one-command shorthand
            if not isinstance(entry, dict) or not isinstance(entry.get("command"), str) or not entry["command"].strip():
                problems.append(f'"hooks.{key}[{i}]": "command" is required')
                continue
            match = entry.get("match")
            if match is not None and not isinstance(match, str):
                problems.append(f'"hooks.{key}[{i}]": "match" must be a string')
            timeout = entry.get("timeout")
            if timeout is not None and (not isinstance(timeout, (int, float)) or isinstance(timeout, bool)
                                        or timeout <= 0):
                problems.append(f'"hooks.{key}[{i}]": "timeout" must be a positive number')
    return problems


def validate_schedule_section(schedule) -> "list[str]":
    """Halo 2.0.5 round 5 (deliverable 3): a bio's `schedule:` -- exactly one
    cadence (`cron`: a 5-field expression, or `every`: a duration like
    `30m`/`1h30m`/`45s`) plus a required `prompt`, optional `model`. Fires
    only while a session that loaded the agent's team is alive -- never a
    system service."""
    if schedule is None:
        return []
    if not isinstance(schedule, dict):
        return ['"schedule" must be a mapping with one of "cron"/"every" and a "prompt"']
    problems: "list[str]" = []
    cron, every = schedule.get("cron"), schedule.get("every")
    if (cron is None) == (every is None):
        problems.append('"schedule" needs exactly one of "cron" (5 fields) or "every" (e.g. 30m)')
    if cron is not None and not valid_cron_expression(cron):
        problems.append(f'"schedule.cron" {cron!r} is not a valid 5-field cron expression')
    if every is not None and parse_every_duration(every) is None:
        problems.append(f'"schedule.every" {every!r} is not a duration like 30m, 1h30m or 45s')
    prompt = schedule.get("prompt")
    if not isinstance(prompt, str) or not prompt.strip():
        problems.append('"schedule.prompt" is required')
    if schedule.get("model") is not None and not isinstance(schedule.get("model"), str):
        problems.append('"schedule.model" must be a string')
    return problems


def validate_trigger_section(triggers) -> "list[str]":
    """Halo 2.0.5 round 5 (deliverable 3): a bio's `triggers:` -- a list of
    `{on: file_change, paths: [...]}` / `{on: event, name: <halo event>}` /
    `{on: message, from: <role>}` entries that start the agent once per
    occurrence while a session that loaded the team is alive."""
    if triggers is None:
        return []
    if not isinstance(triggers, list):
        return ['"triggers" must be a list of {on: ...} entries']
    problems: "list[str]" = []
    for i, t in enumerate(triggers):
        if not isinstance(t, dict) or t.get("on") not in SCHEDULE_TRIGGER_KINDS:
            problems.append(f'triggers[{i}]: "on" must be one of {", ".join(SCHEDULE_TRIGGER_KINDS)}')
            continue
        kind = t.get("on")
        if kind == "file_change":
            paths = t.get("paths")
            if not isinstance(paths, list) or not paths or not all(isinstance(p, str) and p for p in paths):
                problems.append(f'triggers[{i}]: "paths" must be a non-empty list of path strings')
        elif kind == "event":
            if not isinstance(t.get("name"), str) or not t.get("name").strip():
                problems.append(f'triggers[{i}]: "name" (a halo event kind) is required')
        else:  # message
            if not isinstance(t.get("from"), str) or not t.get("from").strip():
                problems.append(f'triggers[{i}]: "from" (a role or alias) is required')
        if t.get("prompt") is not None and (not isinstance(t.get("prompt"), str) or not t.get("prompt").strip()):
            problems.append(f'triggers[{i}]: "prompt" must be a non-empty string when given')
    return problems


def valid_cron_expression(expr) -> bool:
    """True iff `expr` is a 5-field cron expression whose every field parses
    (a number, a range `a-b`, a list `a,b`, a step `*/n` or `a-b/n`, or
    `*`). Field VALUE ranges are checked by `agents_schedule.cron_next`
    at compute time; this is the schema-level gate."""
    if not isinstance(expr, str):
        return False
    fields = expr.split()
    if len(fields) != 5:
        return False
    return all(valid_cron_field(f) for f in fields)


def valid_cron_field(field: str) -> bool:
    import re as _re
    if field == "*":
        return True
    for part in field.split(","):
        if not part:
            return False
        base, slash, step = part.partition("/")
        if slash and (not step.isdigit() or int(step) == 0):
            return False
        if base == "*":
            continue
        if not _re.fullmatch(r"\d+(-\d+)?", base):
            return False
    return True


def parse_every_duration(raw) -> "Optional[float]":
    """`"45s"`/`"30m"`/`"1h30m"` -> seconds (float), else None. A bare
    number is seconds. Never raises."""
    if isinstance(raw, (int, float)) and not isinstance(raw, bool) and raw > 0:
        return float(raw)
    if not isinstance(raw, str) or not raw.strip():
        return None
    text = raw.strip().lower()
    import re as _re
    total, pos = 0.0, 0
    for m in _re.finditer(r"(\d+(?:\.\d+)?)(s|m|h|d)?", text):
        if m.start() != pos:
            return None
        value = float(m.group(1))
        unit = {"s": 1.0, "m": 60.0, "h": 3600.0, "d": 86400.0}.get(m.group(2) or "s")
        total += value * unit
        pos = m.end()
    return total if pos == len(text) and total > 0 else None


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
        if section in data and data[section] is not None and not isinstance(data[section], dict) \
                and section != "triggers":  # triggers is a LIST (its own validator below)
            problems.append(f'"{section}" must be a mapping')
    problems.extend(validate_hook_section(data.get("hooks")))
    problems.extend(validate_schedule_section(data.get("schedule")))
    problems.extend(validate_trigger_section(data.get("triggers")))
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


def ensure_bio_for_model(model_ref: str, *, cwd=None, state_dir=None) -> "Optional[str]":
    """Halo 2.0.5 round 2 (deliverable 3): a team template's own `agents:`
    entries always name a BIO (`teams_yaml.validate_team_template`'s own
    "agent" is required / "no such agent bio" rule) -- there is no slot
    for a bare model ref. Picking a MODEL directly for a lineup role (the
    brief's own "one role by model") therefore needs a tiny, reusable bio
    that pins JUST `models.preference` to that ref, auto-created here the
    SAME way `teams_yaml.migrate_legacy_role_table`'s own `_bio_for_model`
    helper already does for the legacy-table migration (same slug shape,
    `model-<slug>`, so the two paths can never collide on a name). Reuses
    an existing bio whose OWN `models.preference` already matches `ref`
    instead of creating a duplicate every time the same model is picked
    again. `None` only for an empty/blank `ref`."""
    if not model_ref or not model_ref.strip():
        return None
    model_ref = model_ref.strip()
    for existing in list_agent_bios(cwd=cwd, state_dir=state_dir):
        raw = load_agent_bio_raw(existing, cwd=cwd, state_dir=state_dir)
        if raw and (raw.get("models") or {}).get("preference") == model_ref:
            return existing
    slug = re.sub(r"[^A-Za-z0-9_-]+", "-", model_ref).strip("-").lower() or "model"
    name = f"model-{slug}"[:60].rstrip("-") or "model"
    if not is_valid_agent_name(name):
        name = "model-pin"
    ok, _problems = save_agent_bio(
        name, {"description": f"Pins the model {model_ref} -- auto-created from a lineup's own model pick.",
               "models": {"preference": model_ref}},
        cwd=cwd, state_dir=state_dir)
    return name if ok else None


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
