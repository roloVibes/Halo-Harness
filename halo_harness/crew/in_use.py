"""halo_harness.crew.in_use -- what the rest of Halo asks about the agents a session runs (Halo 3.6.0.0 R5b).

Local scheduling, warm sets, the steward, placement, doctor, Studio's model lookup, the run engine's lanes and outcomes
ask a few questions that a lineup or a bio answered on 3.5. This module answers them from the map in use
(crew/compile.py) and the agent files (crew/store.py), and for a plain session from crew/plain.py:

    map_name(cwd) -> str | None                 the map in use ("starter" when none is set; None: One model for
                                                everything, roles off)
    role_table(name, cwd, state_dir) -> dict    {agent: model value} of the map `name` (None: the one in use): an
                                                agent's own model, `auto` (picked per task), `default` (main: the
                                                session's model); a plain session's cards (auto / default). None
                                                when the map cannot be read
    session_table(name, cwd, state_dir)         R5c: role_table, and for a plain session your `roles.<name>` over its
                                                cards (what a new session's agents run on: the adviser reads it); only
                                                the roles a session reads (read_roles)
    read_roles() -> (name, ...)                 a plain session's cards and the roles the code reads (SYSTEM_ROLES)
    lanes(name, main_ref, cwd, state_dir) -> list   the local models of that table (local_sched/warm_set.lanes_of)
    agent(name, cwd, state_dir) -> dict | None  an agent as the fields the run engine and outcomes read: name, kind,
                                                models {preference, needs}, prompt, tools, careful, acceptance
    agent_names(cwd, state_dir) -> [name]       every agent file with no problem (yours, the project's, a pack's, the
                                                starters)
    main_model() -> str | None                  the session's own model (config `model`)
"""

from __future__ import annotations

from typing import Optional


def main_model() -> Optional[str]:
    try:
        from halo_harness.theme import get_config_value
        v = get_config_value("model", default=None)
    except Exception:
        return None
    return v if isinstance(v, str) and v.strip() else None


def map_name(cwd=None) -> Optional[str]:
    from halo_harness.crew.compile import in_use
    try:
        return in_use(None, cwd)[0]
    except Exception:
        return None


def _is_plain(name: str, cwd=None) -> bool:
    from halo_harness.crew.compile import in_use
    from halo_harness.crew.store import is_auto
    try:
        _got, source = in_use(None, cwd)
    except Exception:
        return False
    return is_auto(name) and source == "default"  # 3.6.0.5 A2: `auto`, `starter` and none set are one map


def role_table(name: Optional[str] = None, *, cwd=None, state_dir=None) -> Optional[dict]:
    name = name or map_name(cwd)
    if not name:
        return None
    if _is_plain(name, cwd):
        from halo_harness.crew.plain import load
        plain = load()
        if plain is None:
            return None
        return plain.role_table()  # as 3.5 read the auto lineup's (your roles.* are reported as roles of their own)
    from halo_harness.crew.compile import compile_map
    c = compile_map(name, cwd=cwd, state_dir=state_dir)
    if c.problems and not c.specs:
        return None
    table = {"main": c.main.get("model") or "default"}
    for n, spec in c.specs.items():
        table[n] = spec.model or "auto"
    return table


#: 3.6.0.0 R5c (the judge's F1): the roles Halo's own code reads by name, beside a plain session's cards -- the
#: built-in agents' roles (config/agents_md.py: general-purpose `orchestrator`, Judge `judge`, Tester `tester`), the
#: judge and escalation (`judge`), the small model (headless.py `small`), compaction (agent/loop.py `compaction`), a
#: sub-agent's default (`subagent_default`), the eyes offer (agent/eyes_offer.py `visual`, `eyes`) and the concierge.
SYSTEM_ROLES = ("orchestrator", "judge", "tester", "small", "compaction", "subagent_default", "visual", "eyes",
                "concierge")


def read_roles() -> tuple:
    """Every `roles.<name>` a session reads: a plain session's cards (crew/plain.py; `main` is the session's model, set
    with `halo config set model`, so it is not one) and SYSTEM_ROLES. A role outside these changes nothing."""
    try:
        from halo_harness.crew.plain import load
        plain = load()
        cards = tuple(n for n in plain.cards if n != "main") if plain is not None else ()
    except Exception:
        cards = ()
    return tuple(dict.fromkeys(cards + SYSTEM_ROLES))


def session_table(name: Optional[str] = None, *, cwd=None, state_dir=None) -> Optional[dict]:
    """What a new session's agents run on (3.6.0.0 R5c, the adviser's question): the map's table, and for a plain
    session each card's model under your `roles.<name>` (a card runs on its role's model when you set one: `halo
    roles point`), plus the roles of yours the code reads that the table does not name (`roles.judge`,
    `roles.small`; read_roles). A role nothing reads (`roles.verify`) is no lane."""
    name = name or map_name(cwd)
    table = role_table(name, cwd=cwd, state_dir=state_dir)
    if table is None or not _is_plain(name, cwd):
        return table
    try:
        from halo_harness.roles import configured_role_table
        own = configured_role_table()
    except Exception:
        own = {}
    read = read_roles()
    return {**table, **{k: v for k, v in own.items() if k in read and v not in (None, "")}}


def lanes(name: Optional[str] = None, *, main_ref: Optional[str] = None, cwd=None, state_dir=None) -> list:
    from halo_harness.local_sched.warm_set import lanes_of
    return lanes_of(role_table(name, cwd=cwd, state_dir=state_dir) or {}, main_ref if main_ref is not None else main_model())


def agent(name: str, *, cwd=None, state_dir=None) -> Optional[dict]:
    if not name:
        return None
    from halo_harness.crew import store
    from halo_harness.crew.compile import AUTO_NEEDS
    from halo_harness.crew.spec import MODES, prompt_of, tools_of
    body = store.load("agent", str(name), cwd=cwd, state_dir=state_dir)
    if body is None:
        return None
    raw = store.clean(body)
    tools, disallowed, _skills = tools_of(raw)
    check = (raw.get("more") or {}).get("check")
    acceptance = {"prompt": check.get("ask"), "expect": check.get("expect")} if isinstance(check, dict) else {}
    model = str(raw.get("model") or "auto")
    return {"name": str(raw.get("name") or name), "kind": raw.get("kind") or str(name), "description": raw.get("does"),
            "models": {"preference": model, "needs": [AUTO_NEEDS.get(str(n), str(n)) for n in raw.get("needs") or []]},
            "prompt": prompt_of(raw), "tools": {"allow": tools, "deny": disallowed}, "uses": list(raw.get("uses") or []),
            "careful": raw.get("careful"), "mode": MODES.get(raw.get("careful"), "default"),
            "acceptance": {k: v for k, v in acceptance.items() if v}, "scope": body.get("_scope"), "path": body.get("_path")}


def agent_names(*, cwd=None, state_dir=None) -> list:
    from halo_harness.crew import store
    out: list = []
    try:
        rows = store.rows("agent", cwd=cwd, state_dir=state_dir)
    except Exception:
        return out
    for r in rows:
        if not r["_problems"] and r["name"] not in out:
            out.append(r["name"])
    return out


def agent_or_bio(name: str, *, cwd=None, state_dir=None) -> Optional[dict]:
    """An agent file, else (the run engine's lanes and the two shipped packs that still name bios: first-run, coach)
    the 3.5 bio of that name. The bio half goes when agents_yaml.py does."""
    got = agent(name, cwd=cwd, state_dir=state_dir)
    if got is not None or not name:
        return got
    try:
        from halo_harness.agents_yaml import resolve_agent_bio
        return resolve_agent_bio(name, cwd=cwd, state_dir=state_dir)
    except Exception:
        return None
