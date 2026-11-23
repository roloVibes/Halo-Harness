"""halo_harness.studio.crew_live_api -- "Save as an agent" on a helper a session made up (Halo 3.6.0.0 R4, the v3
design's "from a live helper"; docs/STUDIO-map.md "While a session runs").

    POST crew/from-live {session, agent_id} -> {agent, from, problems, line}

`agent` is an UNSAVED agent/1 body built from the live helper: a name from its task's first words (one of yours is
never reused), `does` its task's first line, instructions that say what it was made up for, its model when it ran
on a catalog model (else auto), and the `uses` and `careful` of the map's main -- what the helper could use, since a
made-up helper runs on main's own tools and mode (crew/map_run.py `_made_up`). 3.6.0.12 SP: the names taken and
main are read in the SESSION's project (its row's `cwd`), not in the folder Studio was started in; a name either
folder's agents have is taken (the saved agent is yours, and a project's agent of that name would hide it). Nothing is written: the page opens the
Agents form with it, and only Save there writes. Owner-only like every write route, though it writes nothing (it
reads a session's agent).
"""

from __future__ import annotations

import os
import re

from halo_harness.crew import store
from halo_harness.crew.formats import AGENT, NAME, agent_problems
from halo_harness.studio.owner_proof import owner_only

BUILT = "Built from {helper} on {model}, not saved yet: read it, change what you like, then Save."
STOP = {"a", "an", "the", "of", "to", "for", "and", "in", "on", "it", "this", "that", "with", "please"}


def _row(sid: str, aid: str) -> "tuple[dict | None, dict | None]":
    """(the session row, the agent row) as GET fleet lists them, or Nones."""
    from halo_harness.peers import local_view
    for s in local_view.sessions():
        if s.get("session_id") == sid:
            return s, next((a for a in s.get("agents") or [] if isinstance(a, dict) and a.get("agent_id") == aid), None)
    return None, None


def name_for(task: str, taken) -> str:
    words = [w for w in re.findall(r"[a-z0-9]+", str(task or "").lower()) if w not in STOP][:3]
    base = "-".join(words)[:40].strip("-") or "helper"
    base = base if NAME.match(base) else f"helper-{base}"[:40].strip("-")
    name, n = base, 2
    while name in taken:
        name, n = f"{base}-{n}", n + 1
    return name


def project_of(srow: dict, fallback):
    """3.6.0.12 SP: the project a session works in -- its row's `cwd` (the registry's) when that folder is there --
    else Studio's own folder. The card reads that project's agents and main, never the folder Studio was started in."""
    cwd = srow.get("cwd")
    return cwd if isinstance(cwd, str) and cwd and os.path.isdir(cwd) else fallback


def _main_of(map_name: str, cwd) -> dict:
    raw = store.load("map", map_name, cwd=cwd) if map_name else None
    main = ((raw or {}).get("main") or {}).get("agent") or "main"
    return store.load("agent", main, cwd=cwd) or {}


def body_for(srow: dict, arow: dict, cwd=None, also=None, kind: str = "MADE-UP", facts=None) -> dict:
    """The unsaved agent/1 body built from a live helper. 3.6.0.15 OP2 (O2-3): `kind` (crew_model_api.kind_of) picks
    the builder: SHIPPED the shipped file's body, ROUTED its card's shipped agent (else the card's words and prompt),
    BUILT-IN the built-in's description, body, tools and mode; every other kind today's made-up body, byte for byte."""
    if kind in ("SHIPPED", "ROUTED", "BUILT-IN"):
        built = _built(kind, facts or {}, srow, arow, cwd, also)
        if built is not None:
            return built
    task =str(arow.get("task") or "").strip()
    first = next((x.strip() for x in task.splitlines() if x.strip()), "") or "a task main handed it"
    main = _main_of(str((arow.get("crew") or {}).get("map") or srow.get("map") or ""), cwd)
    folders = [cwd] + ([also] if also is not None and str(also) != str(cwd) else [])  # the session's, then Studio's
    taken = {r.get("name") for folder in folders for r in store.rows("agent", cwd=folder)}
    model = str(arow.get("model") or "")
    return {"format": AGENT, "name": name_for(first, taken), "does": first[:200],
            "instructions": (f"Main made you up in a session for this task: {first[:400]}\n"
                             "Do that kind of task when you are handed one, and hand back what you did in a few lines."),
            "model": model if ":" in model else "auto",
            "uses": list(main.get("uses") or ["read"]), "careful": str(main.get("careful") or "ask-changes")}


def _built(kind: str, facts: dict, srow: dict, arow: dict, cwd, also) -> "dict | None":
    from halo_harness.studio.crew_model_api import name_of
    name = name_of(kind, facts, srow, arow, cwd, also)
    if kind in ("SHIPPED", "ROUTED"):
        got = store.load("agent", name, cwd=cwd, scope="starter")
        if got is not None:
            return {**store.clean(got), "name": name}
        if kind == "SHIPPED":
            return None
        from halo_harness.crew.plain import load
        plain = load()
        card = (plain.cards if plain is not None else {}).get(str((facts.get("routed") or {}).get("card") or "")) or {}
        return {"format": AGENT, "name": name, "does": ", ".join(str(w) for w in card.get("use_for") or []) or name,
                "instructions": str(card.get("prompt") or ""), "model": "auto", "uses": ["read"], "careful": "ask-changes"}
    from halo_harness.config.agents_md import _builtin_specs
    from halo_harness.crew.spec import MODES, TOOLS
    spec = _builtin_specs().get(str(arow.get("name") or ""))
    if spec is None:
        return None
    has = set(spec.tools) if spec.tools is not None else {t for g in ("read", "edit", "bash", "web") for t in TOOLS[g]}
    uses = [g for g, tools in TOOLS.items() if has & set(tools)]
    uses = [g for g in uses if not (g == "fetch" and "web" in uses)]  # `web` holds `fetch`'s one tool
    careful = {mode: word for word, mode in MODES.items()}.get(str(spec.permission_mode or ""), "ask-changes")
    return {"format": AGENT, "name": name, "does": str(spec.description or "")[:200], "instructions": str(spec.body or ""),
            "model": "auto", "uses": uses, "careful": careful}


def post_from_live(req):
    body = req.body if isinstance(req.body, dict) else {}
    sid, aid = str(body.get("session") or "").strip(), str(body.get("agent_id") or "").strip()
    if not sid or not aid:
        return 422, {"error": "name the session and the helper: {session, agent_id}", "problems": []}
    srow, arow = _row(sid, aid)
    if srow is None:
        return 404, {"error": f"no live session {sid!r} on this harness"}
    if arow is None:
        return 404, {"error": f"no agent {aid!r} in session {sid!r}"}
    from halo_harness.studio.crew_model_api import kind_of
    cwd = project_of(srow, req.cwd)
    kind, facts = kind_of(srow, arow, cwd)  # 3.6.0.15 OP2 B11: the face's Save and the sheet's Make share one builder
    agent = body_for(srow, arow, cwd=cwd, also=req.cwd, kind=kind, facts=facts)
    return 200, {"agent": agent, "problems": agent_problems(agent),
                 "from": {"session": sid, "agent_id": aid, "name": arow.get("name"), "task": arow.get("task")},
                 "line": BUILT.format(helper=arow.get("name"), model=agent.get("model"))}


ROUTES: list = [("POST", r"^crew/from-live$", owner_only(post_from_live))]

from halo_harness.studio.crew_model_api import ROUTES as _MODEL  # noqa: E402  3.6.0.15 OP2: the sheet's MODEL block

ROUTES += _MODEL
