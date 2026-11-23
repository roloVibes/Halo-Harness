"""halo_harness.studio.crew_model_api -- the MODEL block of the sheet that opens at a helper's box (Halo 3.6.0.15 OP2,
rules O2-2 and O2-3; docs/STUDIO-live.md).

    GET crew/agent-model?session=&agent=  -> {kind, name, model, first, line, can, now}
    POST crew/agent-model {session, agent, model} -> {line, undo, terminal?, model?}   (O2-3, owner-only)
    POST crew/agent-model/undo {undo}             -> {line}                            (O2-3, owner-only)

O2-3: a pick saves HIS agent with the Agents form's own PUT (MINE) or makes one with its POST (SHIPPED, ROUTED,
BUILT-IN, MADE-UP; the body from crew_live_api.body_for, the builder crew/from-live shares), so package UN's push is
what makes it count in the running session; never a second path into a session. MAIN runs "/model {ref}" through the
session's door (or the socket's own `model` with no terminal), refused before the door while main is in a turn (R7).
PACK, CLAUDE and GONE: 409. Undo carries no path: it finds the file by name and acts only while its sha256 holds.

`kind` is one of nine: MAIN (main itself), MINE (an agent of his, yours or the project's), SHIPPED (an agent that
ships with Halo), ROUTED (a general helper Auto sent to one of its cards), BUILT-IN (one built into Halo, no file),
MADE-UP (one main made up for its task), PACK (a pack's), CLAUDE (a Claude Code agent file), GONE (3.6.0.15 O2-8: his
agent, whose file was deleted after the helper started). `name` is the name a pick writes (never a built-in's), `model`
what the picker shows ("" = Auto), `first` ROUTED's state line ("" for the rest), `line` what a pick does for THIS
kind, letter for letter, in its "now" form when the session's row says `use_now` (package UN: an agent put to it is
taken now) else in its "later" form; `can` False where nothing can be picked (PACK, CLAUDE, GONE). The facts are the
session's row and the helper's (`spawn.source`, `spawn.routed`: O2-1). A read: not owner-only.
No answer carries a scope or the word that names the shipped set.
"""

from __future__ import annotations

from halo_harness.config.agents_md import BUILTIN_NAMES
from halo_harness.crew import store
from halo_harness.studio.owner_proof import owner_only

MAIN, MINE, SHIPPED, ROUTED, BUILTIN, MADE_UP, PACK, CLAUDE, GONE = (
    "MAIN", "MINE", "SHIPPED", "ROUTED", "BUILT-IN", "MADE-UP", "PACK", "CLAUDE", "GONE")
FIXED = (PACK, CLAUDE, GONE)  # nothing can be picked: no picker, no button, a pick refused 409 with the kind's line
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
GONE_LINE = "Your agent {name} is gone: it was deleted after this helper started."
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
    if src in ("crew:yours", "crew:project"):  # his agent; its file gone (deleted, or Undo took it back) while it runs
        return (MINE if _his_file(name, cwd) else GONE), {}
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
    out = {"kind": kind, "name": name, "model": "", "first": "", "line": "", "can": kind not in FIXED, "now": now}
    if kind == MAIN:
        return {**out, "model": str(srow.get("model") or ""), "line": MAIN_LINE}
    if kind == PACK:
        return {**out, "line": PACK_LINE.format(name=name, P=name.split("--", 1)[0])}
    if kind == CLAUDE:
        return {**out, "line": CLAUDE_LINE.format(name=name)}
    if kind == GONE:
        return {**out, "line": GONE_LINE.format(name=name)}
    if kind in (MINE, SHIPPED):
        body = store.load("agent", name, cwd=cwd) or {}
        model = str(body.get("model") or "")
        out["model"] = "" if model.strip().lower() == "auto" else model
    routed = facts.get("routed") or {}
    if kind == ROUTED:  # `first` is "" for every other kind (ruling B): a routed helper whose card's agent is his reads MINE
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


# -- O2-3: a pick writes through the Agents form's OWN routes (so UN's push makes it count in the running session) -------

SAVED_NOW = "Saved: {name} runs on {model} from its next start, in this session too, unless main names a model itself."
SAVED_LATER = "Saved: {name} runs on {model} from your next session."
MADE_NOW = "Made {name}, an agent of yours on {model}: main can start it now, unless it names a model itself."
MADE_LATER = "Made {name}, an agent of yours on {model}: main can start it from your next session."
NOT_SAVED = "Not saved: {error}."
SWITCHED_TERMINAL = "Switched main to {model} now, as /model in its terminal, and saved for your next launch."
SWITCHED_SESSION = "Switched main to {model} for this session; not saved for your next launch."
NOT_SWITCHED = "Not switched: {why}."
IN_A_TURN = "Not switched: main is in a turn: pick again when it ends."
PUT_BACK = "Put back: {name} runs on {old} again."
TAKEN_BACK = "Taken back: {name} is gone."
NOT_UNDONE = "Not undone: {name} was changed since."
NOT_AN_UNDO = "not an undo this route made"
STATUS_WAIT_S, STATUS_STEP_S = 3.0, 0.1  # main's swap is queued (agent/loop.py set_model): read it back a while


def _sub(req, name: str, body, cwd):
    """A sub-request of the Agents form's routes for `name` in the session's project."""
    import dataclasses
    from pathlib import Path
    return dataclasses.replace(req, params={"name": name}, body=body, cwd=Path(cwd))


def _sha(path) -> str:
    import hashlib
    from pathlib import Path
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _said(text: str) -> str:
    return (str(text or "").strip().splitlines() or [""])[0].strip().rstrip(".")


def _on(body: dict, ref: str) -> dict:
    """`body` on the pick; `needs` (only with model: auto, crew/formats.py) goes when the pick is a model."""
    out = {**body, "model": ref}
    if ref.strip().lower() != "auto":
        out.pop("needs", None)
    return out


def _took(live, sid: str) -> bool:
    return any(isinstance(x, dict) and x.get("session_id") == sid and x.get("took") is True for x in live or [])


def _main_pick(sid: str, ref: str):
    """R7: the door "/model {ref}" for an idle main; `terminal` when a terminal's own table ran it, else the socket's
    own `model` (this session only); the line says Switched only when the session's model is then the pick."""
    import time
    from halo_harness.studio import live_agents_api as lv
    st, status = lv.forward(sid, "status", {})
    if st != 200:
        return st, {"error": status.get("error"), "line": NOT_SWITCHED.format(why=_said(status.get("error"))),
                    "undo": None, "terminal": None, "model": None}
    if status.get("busy"):  # the swap would wait for the turn's end: nothing is sent
        return 409, {"line": IN_A_TURN, "undo": None, "terminal": None, "model": status.get("model")}
    st, got = lv.forward(sid, "slash", {"line": f"/model {ref}"})
    terminal = st == 200 and got.get("terminal") is True
    why = str(got.get("output") or "") if st == 200 else str(got.get("error") or "")
    if not terminal:
        st, got = lv.forward(sid, "model", {"ref": ref})
        if st != 200:
            why = str(got.get("error") or "")
    model, end = status.get("model"), time.monotonic() + STATUS_WAIT_S
    while st == 200:
        s2, now = lv.forward(sid, "status", {})
        model = now.get("model") if s2 == 200 else model
        if model == ref or time.monotonic() >= end:
            break
        time.sleep(STATUS_STEP_S)
    if model == ref:
        return 200, {"line": (SWITCHED_TERMINAL if terminal else SWITCHED_SESSION).format(model=ref), "undo": None,
                     "terminal": terminal, "model": model}
    line = NOT_SWITCHED.format(why=_said(why))
    return 409, {"error": line, "line": line, "undo": None, "terminal": terminal, "model": model}


def post_agent_model(req):
    from halo_harness.studio import crew_api
    from halo_harness.studio.crew_live_api import _row, body_for, project_of
    b = req.body if isinstance(req.body, dict) else {}
    sid, aid = str(b.get("session") or "").strip(), str(b.get("agent") or "").strip()
    ref = b.get("model").strip() if isinstance(b.get("model"), str) else ""
    if not sid or not aid:
        return 422, {"error": "name the session and the helper: {session, agent}"}
    if not ref:
        return 422, {"error": "pick a model: {model}"}
    srow, arow = _row(sid, aid)
    if srow is None:
        return 404, {"error": f"no live session {sid!r} on this harness"}
    if arow is None:
        return 404, {"error": f"no agent {aid!r} in session {sid!r}"}
    cwd = project_of(srow, req.cwd)
    kind, facts = kind_of(srow, arow, cwd)
    if kind == MAIN:
        return _main_pick(sid, ref)
    if kind in FIXED:
        line = answer(srow, arow, cwd, req.cwd)["line"]
        return 409, {"error": line, "line": line}
    name = name_of(kind, facts, srow, arow, cwd, req.cwd)
    old = None
    if kind == MINE:
        found = store.find("agent", name, cwd=cwd, state_dir=req.state_dir)
        scope = found[1] if found and found[1] in HIS else ""
        got = store.load("agent", name, cwd=cwd, state_dir=req.state_dir, scope=scope) if scope else None
        if got is None:
            error = f"no agent of yours named {name!r}"
            return 404, {"error": error, "line": NOT_SAVED.format(error=error)}
        old = store.clean(got)
        st, out = crew_api.put_agent(_sub(req, name, {"agent": _on(old, ref)}, cwd))
    else:
        scope = "yours"
        body = _on({**body_for(srow, arow, cwd=cwd, also=req.cwd, kind=kind, facts=facts), "name": name}, ref)
        st, out = crew_api.post_agent(_sub(req, name, {"agent": body}, cwd))
    if st != 200:
        error = str(out.get("error") or "")
        return st, {**out, "error": error, "line": NOT_SAVED.format(error=error.rstrip("."))}
    took = _took(out.get("live"), sid)
    if kind == MINE:
        line = (SAVED_NOW if took else SAVED_LATER).format(name=name, model=ref)
    else:
        line = (MADE_NOW if took else MADE_LATER).format(name=name, model=ref)
    undo = {"session": sid, "name": name, "scope": scope, "sha256": _sha(out["path"]), "made": kind != MINE, "old": old}
    return 200, {"line": line, "undo": undo}


def _session_cwd(sid: str, fallback):
    """The project of the session the token names; Studio's folder once that session has ended."""
    from halo_harness.peers import local_view
    from halo_harness.studio.crew_live_api import project_of
    srow = next((s for s in local_view.sessions() if isinstance(s, dict) and s.get("session_id") == sid), None)
    return project_of(srow, fallback) if srow is not None else fallback


def post_agent_model_undo(req):
    """Every field of the token is judged as TEXT before the disk is asked; the file is found by name, never by a
    path the request sends; it is put back or deleted only while its sha256 is the one the pick wrote."""
    import re
    from halo_harness.studio import crew_api
    tok = (req.body if isinstance(req.body, dict) else {}).get("undo")
    tok = tok if isinstance(tok, dict) else {}
    name, scope, sha = tok.get("name"), tok.get("scope"), tok.get("sha256")
    if not (isinstance(name, str) and re.fullmatch(crew_api._NAME, name) and scope in HIS
            and isinstance(sha, str) and re.fullmatch(r"[0-9a-f]{64}", sha)):
        return 422, {"error": NOT_AN_UNDO}
    cwd = _session_cwd(str(tok.get("session") or ""), req.cwd)
    found = store.find("agent", name, cwd=cwd, state_dir=req.state_dir, scope=scope)
    if found is None or _sha(found[0]) != sha:
        line = NOT_UNDONE.format(name=name)
        return 409, {"error": line, "line": line}
    if tok.get("made") is True:
        if scope != "yours":  # a pick makes an agent of YOURS: no other scope's file is checked while yours is deleted
            return 422, {"error": NOT_AN_UNDO}
        st, out = crew_api.delete_agent(_sub(req, name, None, cwd))
        if st != 200:
            return st, {**out, "line": str(out.get("error") or "")}
        return 200, {"line": TAKEN_BACK.format(name=name)}
    old = tok.get("old")
    if not isinstance(old, dict):
        return 422, {"error": NOT_AN_UNDO}
    st, out = crew_api.put_agent(_sub(req, name, {"agent": old}, cwd))
    if st != 200:
        error = str(out.get("error") or "")
        return st, {**out, "line": f"Not undone: {error.rstrip('.')}."}  # Undo's own head, as the page's fallback
    return 200, {"line": PUT_BACK.format(name=name, old=str(old.get("model") or "auto"))}


ROUTES: list = [("GET", r"^crew/agent-model$", get_agent_model),
                ("POST", r"^crew/agent-model$", owner_only(post_agent_model)),
                ("POST", r"^crew/agent-model/undo$", owner_only(post_agent_model_undo))]
