"""halo_harness.studio.crew_model_api -- the MODEL block of the sheet that opens at a helper's box (Halo 3.6.0.15 OP2,
rules O2-2 and O2-3; docs/STUDIO-live.md).

    GET crew/agent-model?session=&agent=  -> {kind, name, model, first, line, can, now}

`kind` is one of eight: MAIN (main itself), MINE (an agent of his, yours or the project's), SHIPPED (an agent that
ships with Halo), ROUTED (a general helper Auto sent to one of its cards), BUILT-IN (one built into Halo, no file),
MADE-UP (one main made up for its task), PACK (a pack's), CLAUDE (a Claude Code agent file). `name` is the name a pick
writes (never a built-in's), `model` what the picker shows ("" = Auto), `first` ROUTED's state line ("" for the rest),
`line` what a pick does for THIS kind, letter for letter, in its "now" form when the session's row says `use_now`
(package UN: an agent put to it is taken now) else in its "later" form; `can` False where nothing can be picked (PACK,
CLAUDE). The facts are the session's row and the helper's (`spawn.source`, `spawn.routed`: O2-1). A read: not owner-only.
No answer carries a scope or the word that names the shipped set.
"""

from __future__ import annotations

from halo_harness.config.agents_md import BUILTIN_NAMES
from halo_harness.crew import store

MAIN, MINE, SHIPPED, ROUTED, BUILTIN, MADE_UP, PACK, CLAUDE = (
    "MAIN", "MINE", "SHIPPED", "ROUTED", "BUILT-IN", "MADE-UP", "PACK", "CLAUDE")
HIS = ("yours", "project")
ENDED = ("done", "failed", "stopped")

LINES = {
    (MINE, True): "Picking a model saves it in your agent {name}: its next start uses it, in this session too, unless main "
                  "names a model itself.",
    (MINE, False): "Picking a model saves it in your agent {name}: from your next session, unless main names a model itself.",
    (SHIPPED, True): "{name} ships with Halo and Auto picks its model per task. Picking a model saves your own {name} on "
                     "that model: its next start uses it, in this session too, unless main names a model itself.",
    (SHIPPED, False): "{name} ships with Halo and Auto picks its model per task. Picking a model saves your own {name} on "
                      "that model: from your next session, unless main names a model itself.",
    (ROUTED, True): "Picking a model saves your own agent {name} on that model: helpers Auto sends to its {card} card "
                    "start as yours from their next start, in this session too, unless main names a model itself.",
    (ROUTED, False): "Picking a model saves your own agent {name} on that model: helpers Auto sends to its {card} card "
                     "start as yours from your next session, unless main names a model itself.",
    (BUILTIN, True): "{X} is built into Halo and has no file. Picking a model makes {name}, an agent of yours built from "
                     "{X}, on that model: main can start {name} from now, in this session too, unless it names a model "
                     "itself.",
    (BUILTIN, False): "{X} is built into Halo and has no file. Picking a model makes {name}, an agent of yours built from "
                      "{X}, on that model: main can start {name} from your next session, unless it names a model itself.",
    (MADE_UP, True): "Main made this helper up for its task. Picking a model makes {name}, an agent of yours built from "
                     "it, on that model: main can start {name} from now, in this session too, unless it names a model "
                     "itself.",
    (MADE_UP, False): "Main made this helper up for its task. Picking a model makes {name}, an agent of yours built from "
                      "it, on that model: main can start {name} from your next session, unless it names a model itself.",
}
FIRST_ROUTED = "A general helper that Auto sent to its {card} card for the word \"{word}\"."
MAP_MINE = " Your map {M} names {name}: it uses this model from its next session."
MAP_MADE = " Your map {M} names {name}: it uses yours from its next session."
KEEPS = "This helper keeps {model} until it ends."
RAN = "It ran on {model}."
PACK_LINE = "{name} comes with the pack {P}; Halo does not change it here."
CLAUDE_LINE = "{name} is a Claude Code agent file; Halo reads it and does not change it."
MAIN_LINE = "Picking a model runs /model in this session."


def _scope_of(name: str, cwd) -> str:
    """The scope `store.find` gives an agent's name in `cwd` ("" when no file has it)."""
    got = store.find("agent", name, cwd=cwd) if name else None
    return got[1] if got else ""


def _his_file(name: str, cwd) -> bool:
    return bool(name) and any(store.find("agent", name, cwd=cwd, scope=sc) for sc in HIS)


def _on_auto(srow: dict) -> bool:
    return store.is_auto(srow.get("map")) or srow.get("map_plain") is True


def kind_of(srow: dict, arow: dict, cwd) -> "tuple[str, dict]":
    """(kind, facts) of one helper of a live session: the ONE reading O2-2's GET, O2-3's POST and crew/from-live share.
    `facts`: `routed` {word, card} for a routed helper, `card_agent` its card's agent."""
    name = str(arow.get("name") or "")
    if arow.get("agent_id") == "main" or arow.get("kind") == "main":
        return MAIN, {}
    spawn = arow.get("spawn") if isinstance(arow.get("spawn"), dict) else {}
    src = str(spawn.get("source") or "")
    if src == "crew:workflow":  # a workflow's step runs a file: read it as that file's scope
        sc = _scope_of(name, cwd)
        src = f"crew:{sc}" if sc else ""
    routed = spawn.get("routed") if isinstance(spawn.get("routed"), dict) else None
    if src in ("crew:yours", "crew:project") and _his_file(name, cwd):
        return MINE, {}
    if src == "crew:pack":
        return PACK, {}
    if src == "crew:starter":
        return (MINE if _his_file(name, cwd) else SHIPPED), {}
    if src == "built-in":
        if name == "general-purpose":
            if routed and _on_auto(srow):
                from halo_harness.crew.plain import load
                plain = load()
                card = str(routed.get("card") or "")
                agent = plain.starter_of(card) if plain is not None else card
                facts = {"routed": {"word": str(routed.get("word") or ""), "card": card}, "card_agent": agent}
                return (MINE if _his_file(agent, cwd) else ROUTED), facts
            return MADE_UP, {}
        return BUILTIN, {}
    if src and not src.startswith("crew:"):
        return CLAUDE, {}
    # a row written before O2-1 (no spawn.source), or his file is gone: read the name as it is found now
    if (arow.get("crew") or {}).get("made_up") or name == "general-purpose":
        return MADE_UP, {}
    if name in BUILTIN_NAMES:
        return BUILTIN, {}
    return {"yours": MINE, "project": MINE, "starter": SHIPPED, "pack": PACK}.get(_scope_of(name, cwd), CLAUDE), {}


def _his_names(cwd, also) -> set:
    folders = [cwd] + ([also] if also is not None and str(also) != str(cwd) else [])
    return {r.get("name") for f in folders for r in store.rows("agent", cwd=f) if r.get("_scope") in HIS}


def name_of(kind: str, facts: dict, srow: dict, arow: dict, cwd, also) -> str:
    """The name a pick writes: never a built-in's; a built-in's copy takes "-2", "-3" ... while one of HIS has it."""
    name = str(arow.get("name") or "")
    if kind == MAIN:
        return "main"
    if facts.get("card_agent"):
        return str(facts["card_agent"])
    if kind == BUILTIN:
        taken = _his_names(cwd, also) | set(BUILTIN_NAMES)
        base = name.lower()
        out, n = base, 2
        while out in taken:
            out, n = f"{base}-{n}", n + 1
        return out
    if kind == MADE_UP:
        from halo_harness.studio.crew_live_api import body_for
        return body_for(srow, arow, cwd=cwd, also=also)["name"]
    return name


def answer(srow: dict, arow: dict, cwd, also) -> dict:
    kind, facts = kind_of(srow, arow, cwd)
    name = name_of(kind, facts, srow, arow, cwd, also)
    now = srow.get("use_now") is True
    out = {"kind": kind, "name": name, "model": "", "first": "", "line": "", "can": kind not in (PACK, CLAUDE), "now": now}
    if kind == MAIN:
        return {**out, "model": str(srow.get("model") or ""), "line": MAIN_LINE}
    if kind == PACK:
        return {**out, "line": PACK_LINE.format(name=name, P=name.split("--", 1)[0])}
    if kind == CLAUDE:
        return {**out, "line": CLAUDE_LINE.format(name=name)}
    if kind in (MINE, SHIPPED):
        body = store.load("agent", name, cwd=cwd) or {}
        model = str(body.get("model") or "")
        out["model"] = "" if model.strip().lower() == "auto" else model
    routed = facts.get("routed") or {}
    if routed:
        out["first"] = FIRST_ROUTED.format(card=routed["card"], word=routed["word"])
    line = LINES[(kind, now)].format(name=name, X=str(arow.get("name") or ""), card=routed.get("card", ""))
    maps = [u[4:] for u in store.used_by(name, cwd=cwd) if u.startswith("map ")]
    if maps:
        line += (MAP_MINE if kind == MINE else MAP_MADE).format(M=maps[0], name=name)
    ran = str(arow.get("model") or srow.get("model") or "")
    last = (RAN if str(arow.get("state") or "") in ENDED else KEEPS).format(model=ran)
    return {**out, "line": f"{line}\n{last}"}


def get_agent_model(req):
    from halo_harness.studio.crew_live_api import _row, project_of
    q = req.query or {}
    sid, aid = str(q.get("session") or "").strip(), str(q.get("agent") or "").strip()
    if not sid or not aid:
        return 422, {"error": "name the session and the helper: {session, agent}"}
    srow, arow = _row(sid, aid)
    if srow is None:
        return 404, {"error": f"no live session {sid!r} on this harness"}
    if arow is None:
        return 404, {"error": f"no agent {aid!r} in session {sid!r}"}
    return 200, answer(srow, arow, project_of(srow, req.cwd), req.cwd)


ROUTES: list = [("GET", r"^crew/agent-model$", get_agent_model)]
