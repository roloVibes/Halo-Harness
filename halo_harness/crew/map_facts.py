"""The facts of a session's map, in one place (3.6.0.2 "Session map", R40 with R21 R24 R41).

F1 started: when this session started on its map (`map_start`'s `t`, kept on the session as `_map_started_at`).
F2 running: the map it runs on (`team_control.map`), and whether that is the default (`compile.is_default`).
F4 new sessions: config `crew.map` (None when unset), and since when: config `crew.map_since {map, at}`, written in the
   same write as `crew.map` (theme.set_config_value, changes_map.config_text); valid only while its `map` equals
   `crew.map` -- else the map was set outside Halo and when is not known (T11): None.
F5 changes: the last `builder_done` outcome of the session (`_builder_built`, crew/map_events.py), no map bodies.

S13 and its terminal tail are the sentence every place says (the Builder card's use row, the result tail main repeats,
the facts note); Studio's twin is `truth.ts`. Times are `%H:%M` (R41: never `%-H`/`%-I`, which raise on Windows).
Nothing here calls a model, writes a file or reads the disk beyond config through the theme's stat-keyed cache.
"""
from __future__ import annotations

import time

S13 = "This session keeps running on {old}, as it started. Start a new session to run on {new}."
TERMINAL_TAIL = "In the terminal: quit, then run halo; /clear keeps {old}."
DEFAULT_WORDS = "Auto (the default)"  # 3.6.0.5 A7: `auto`, `starter` and no map set are one map


def s13(old: str, new: str) -> str:
    return S13.format(old=old, new=new)


def terminal_tail(old: str) -> str:
    return TERMINAL_TAIL.format(old=old)


def hhmm(t) -> str:
    """A time as the person reads it: `%H:%M`, local."""
    return time.strftime("%H:%M", time.localtime(float(t)))


def words_of(name, plain: bool = False) -> str:
    """{A}/{B}/{old}/{new}: "Auto (the default)" for the default map (or no map named, or `auto`/`starter`: new
    sessions draw the default), else the map's name."""
    from halo_harness.crew.store import is_auto
    if plain or not name or is_auto(name):
        return DEFAULT_WORDS
    return str(name)


def _name(v):
    return v.strip() if isinstance(v, str) and v.strip() else None


def roles_flip(data: dict, roles_on: bool) -> bool:
    """P2 batch 8: config `data` (as read for a write) going to `roles.enabled` = roles_on changes what new sessions use:
    with `crew.map` unset, roles on draws the default map and roles off ("One model for everything") draws none."""
    roles = data.get("roles") if isinstance(data.get("roles"), dict) else {}
    crew = data.get("crew") if isinstance(data.get("crew"), dict) else {}
    return bool(roles.get("enabled", True)) != bool(roles_on) and _name(crew.get("map")) is None


def since_for(crew_before, value, switched: bool = False) -> dict:
    """The `crew.map_since` to write with `crew.map` = value: the one already there when it names the same map and the
    map does not change (choosing the map in use again is no switch), else `{map: value, at: now}`. `switched`: what
    new sessions use changes though `crew.map` does not (the default map <-> One model for everything, `roles_flip`)."""
    crew_before = crew_before if isinstance(crew_before, dict) else {}
    old = crew_before.get("map_since")
    if (not switched and _name(crew_before.get("map")) == _name(value) and isinstance(old, dict)
            and _name(old.get("map")) == _name(value) and _num(old.get("at")) is not None):
        return dict(old)
    return {"map": _name(value), "at": round(time.time(), 3)}


def _num(v):
    return v if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def _crew_config() -> dict:
    """config's `crew` section, read through the theme's stat-keyed cache (never a file opened here)."""
    try:
        from halo_harness.theme import get_config_value
        crew = get_config_value("crew", default=None)
    except Exception:
        return {}
    return crew if isinstance(crew, dict) else {}


def next_map() -> "tuple":
    """F4: (the map new sessions use or None, since when or None). One read of config's `crew` section."""
    crew = _crew_config()
    name = _name(crew.get("map"))
    from halo_harness.crew.store import is_auto
    if is_auto(name):  # 3.6.0.5 A2: an old `crew.map: starter` is the default, as unset
        name = None
    since = crew.get("map_since")
    at = None
    if isinstance(since, dict) and _name(since.get("map")) == name:
        at = _num(since.get("at"))
    return name, at


def facts(session) -> dict:
    """F1, F2, F4, F5 of `session`: {map, words, plain, since, next, next_words, next_since, next_none, built, asked}.
    `next_none`: new sessions start with no map (crew.map unset and roles off, compile.in_use); `next_words` then still
    names the default and is not to be said (`next_sentence`)."""
    tc = getattr(session, "team_control", None)
    on_map = bool(getattr(tc, "is_map", False))
    name = (getattr(tc, "map_name", None) or None) if on_map else None
    plain = False
    if on_map:
        try:
            from halo_harness.crew.compile import is_default
            plain = bool(is_default(getattr(tc, "map", None)))
        except Exception:
            plain = False
    nxt, nxt_at = next_map()
    built = getattr(session, "_builder_built", None)
    built = {k: v for k, v in built.items() if k != "maps"} if isinstance(built, dict) else None
    return {"map": name, "words": words_of(name, plain) if name else None, "plain": plain,
            "since": _num(getattr(session, "_map_started_at", None)), "next": nxt,
            "next_words": words_of(nxt, nxt is None), "next_since": nxt_at,
            "next_none": nxt is None and _none_next(), "built": built,
            "asked": bool(getattr(session, "_map_asked", False) or getattr(session, "turn_count", 0))}


# ---- R38 R39: the facts given to the agent (section 6, letter for letter) ---------------------------------------------
NOTE_PREFIX = "[Halo] "
NOTE_RUNS = "This session runs on {A}, as it started at {t}."
NOTE_NEXT = "New sessions will run on {B} (switched on at {t2}{by})."
NOTE_NEXT_UNTIMED = "New sessions will run on {B}."  # the switch time is not known (T11: set outside Halo)
NOTE_NEXT_NONE = "New sessions will run with no map."  # roles off and no crew.map (section 6 has no words: P2 batch 10)
NOTE_BY = ", by this session"
NOTE_REST = ("This session keeps running on {A} until a new session starts; nothing needs restarting, Studio included. "
             "Asked which map or workflow you use, answer from this note.")
SHOW_RUNS = "THIS SESSION runs on {A}, as it started at {t}."
SHOW_NEXT = "NEW SESSIONS run on {B} (switched on at {t2})."
SHOW_NEXT_UNTIMED = "NEW SESSIONS run on {B}."
SHOW_NEXT_NONE = "NEW SESSIONS run with no map."  # roles off and no crew.map (section 4 has no words: P2 batch 9)
T4 = "This session runs with no map, as it started at {t}: main does the work and starts its own agents."


def _runs(template: str, words: str, since) -> str:
    """"... runs on {A}, as it started at {t}." -- with no start time known, the clause ends at "as it started."."""
    if since is None:
        return template.replace(" at {t}", "").format(A=words)
    return template.format(A=words, t=hhmm(since))


def _by_this_session(session, f: dict) -> bool:
    """This session's own Builder card wrote the switch to `next` (crew/session_tool.py `finish` keeps
    `_map_switched_by_me = {map, from, to}` around its write: `crew.map_since.at` falls inside it only when that card
    wrote the switch -- a re-choice keeps an older `at`, a later switch elsewhere writes a newer one)."""
    mine = getattr(session, "_map_switched_by_me", None)
    if not isinstance(mine, dict) or _name(mine.get("map")) != f["next"] or f["next_since"] is None:
        return False
    lo, hi = _num(mine.get("from")), _num(mine.get("to"))
    return lo is not None and hi is not None and lo <= f["next_since"] <= hi


def _key(f: dict) -> tuple:
    """What the agent was told: this session's map, the map new sessions use, and whether that is no map at all (roles
    on or off with crew.map unset changes only `next_none`)."""
    return (f["map"], f["next"], f["next_none"])


def note_text(session, f: "dict | None" = None) -> str:
    """The facts note (R38), `[Halo] ` and section 6's words."""
    f = f if f is not None else facts(session)
    a = f["words"] or words_of(None)
    nxt = next_sentence(session, f, show=False)
    return NOTE_PREFIX + " ".join((_runs(NOTE_RUNS, a, f["since"]), nxt, NOTE_REST.format(A=a)))


def next_sentence(session, f: dict, show: bool) -> str:
    """The ONE place the facts note (R38) and `studio_show`'s line 1 (R39) say what new sessions run on, from the same
    facts: with no map (`next_none`), on {B} untimed (T11), or on {B} since {t2} (the note adds ", by this session")."""
    if f["next_none"]:
        return SHOW_NEXT_NONE if show else NOTE_NEXT_NONE
    if f["next_since"] is None:
        return (SHOW_NEXT_UNTIMED if show else NOTE_NEXT_UNTIMED).format(B=f["next_words"])
    if show:
        return SHOW_NEXT.format(B=f["next_words"], t2=hhmm(f["next_since"]))
    return NOTE_NEXT.format(B=f["next_words"], t2=hhmm(f["next_since"]), by=NOTE_BY if _by_this_session(session, f) else "")


def is_note(text) -> bool:
    """A text block is the facts note (a compaction leaves it out of the tail it keeps: `compacted` retells it once)."""
    return isinstance(text, str) and text.startswith(NOTE_PREFIX + NOTE_RUNS.split("{", 1)[0]) \
        and text.endswith(NOTE_REST.rsplit(". ", 1)[-1])


def _none_next() -> bool:
    """New sessions run with no map: `crew.map` unset and roles off ("One model for everything": compile.in_use)."""
    try:
        from halo_harness.crew.compile import in_use
        return in_use(None, None)[1] == "none"
    except Exception:
        return False


def show_line(session) -> str:
    """`studio_show {what: map}`'s first line from a session (R39): the same facts and the same new-sessions sentence as
    the note (`next_sentence`); a session with no map says T4 (P2 batch 9: never "starter (the default)" for either)."""
    f = facts(session)
    a = f["words"] or words_of(None)
    return _runs(SHOW_RUNS if f["map"] else T4, a, f["since"]) + " " + next_sentence(session, f, show=True)


def turn_note(session) -> "str | None":
    """At a turn's start (agent/loop.py, after the user node and the mode line): log the facts note when F2 or F4
    changed since the agent was last told (R38). The first turn only records what the agent starts from; a note
    logged but not yet in a request sent stays pending (`sent` makes it told), so an interrupted turn's note is
    logged again next turn; after a compaction (`compacted`) a note sent before is sent again. Only a top-level
    session on a map. Never raises; returns the text logged or None."""
    try:
        tc = getattr(session, "team_control", None)
        if not getattr(tc, "is_map", False) or getattr(session, "agent_depth", 0):
            return None
        f = facts(session)
        key = _key(f)
        told = getattr(session, "_map_told", None)
        if told is None and not getattr(session, "_map_note_sent", False):
            # the first turn: nothing sent (decision 7); the baseline is what the session started under (map_events
            # `started` keeps F4 then), so a switch between its start and this turn is told at the next turn
            start = getattr(session, "_map_next_at_start", None)
            session._map_told = ((f["map"], start[0], start[1] if len(start) > 1 else f["next_none"])
                                 if isinstance(start, tuple) else key)
            return None
        pending = getattr(session, "_map_note_pending", None)
        retell = getattr(session, "_map_retell", False)
        if not retell and (key == pending or (key == told and pending is None)):
            return None  # told, or an unsent note saying this is still in the log and rides the next request
        text = note_text(session, f)
        session.log.append_snapshot([{"type": "text", "text": text}], kind="map_facts")
        session._map_note_pending = key
        session._map_retell = False
        return text
    except Exception:
        return None


def sent(session) -> None:
    """The provider answered a request (agent/loop.py `_step`, at its first event): a pending note is told (R38: only
    a SENT note counts). A turn stopped before that leaves it pending; its node stays in the log and goes with the
    next request, so it is not logged twice."""
    pending = getattr(session, "_map_note_pending", None)
    if pending is not None:
        session._map_told = pending
        session._map_note_pending = None
        session._map_note_sent = True


def cleared(session) -> None:
    """`/clear` (agent/loop.py `Session.clear`) started a new conversation: the facts note starts over -- the next turn
    is a first turn again (no note; its baseline is what `map_events.started` keeps on the re-logged `map_start`)."""
    session._map_told = None
    session._map_note_pending = None
    session._map_note_sent = False
    session._map_retell = False


CLEAR_KEEPS = "This session still runs on {A}."  # R51: the terminal's line after /clear's own


def clear_line(session) -> "str | None":
    """R51: what `/clear` says after its own line (tui/slash.py), or None for a session not on a map."""
    f = facts(session)
    return CLEAR_KEEPS.format(A=f["words"]) if f["map"] else None


def compacted(session) -> None:
    """A compaction folded the log: a note sent before, or one still pending (its node is folded away), is logged
    again at the next turn's start."""
    if getattr(session, "_map_note_sent", False) or getattr(session, "_map_note_pending", None) is not None:
        session._map_retell = True


# ---- R36 R37 R21: the Builder's card and result in a session (section 4, letter for letter) --------------------------
NAME_THE_MAP = ("Name the map: this session runs on {A}, where main chooses who works. Pass a new name in args.map to "
                "make a map that routes.")
NAME_A_NEW_MAP = ("Name the map: Auto (the default) stays as it is, where main chooses who works. Pass a new name in "
                  "args.map to make a map that routes.")  # 3.6.0.5 RULINGS 3: no name typed and none to take
NEXT_HANDOFF = "this session takes it at its next hand-off"
ROW_NEW_MAP = "Make a new map {B} (main, then the boxes below)"
ROW_WORKFLOW = "Make the workflow {W}: {steps}"  # steps: "1 {a}, 2 {b}"
ROW_BOX = "Add box {x} ({kind} {ref})"
ROW_LINE = "Add line {a} -> {x} (When: {words})"
USE_NEW = "New sessions run on {B}. "  # + S13 (+ " " + the terminal tail)
USE_EDITED = "New sessions do not run on {B}; they run on {F4}. Run new sessions on it instead?"
FIRST_WORKFLOW = "Your {words} workflow: the workflow {W} ({steps}), run from a box on the new map {M}."
T1 = "This session runs on {A}, as it started at {t}. New sessions will too."
RESULT_TAIL = "Written: {written}. Undo: {u}. Tell the person, word for word: "
USE_LEFT = "Left out: new sessions still run on {F4}: {B} changed after the card was shown and now lets agents do more."
USE_UNCHECKED = ("Left out: new sessions still run on {F4}: whether {B} lets agents do more could not be checked again "
                 "({why}).")  # R54 fails closed (P2 batch 9; section 4 has no words for it)
UNCHECKED_UNREAD = "its file cannot be read"
UNCHECKED_RAISED = "the check failed"


def in_terminal(session) -> bool:
    """The person reads this session in a terminal (the TUI), not only in Studio: its control handle's kind is `tui`;
    a session no handle names (a private one) answers in its own terminal when it is interactive."""
    try:
        from halo_harness.remote import runtime
        for act in runtime.actives():
            if getattr(getattr(act, "handle", None), "session", None) is session:
                return getattr(act.handle, "kind", "") == "tui"
    except Exception:
        pass
    return bool(getattr(session, "interactive", False))


def _words_here(f: dict) -> str:
    return f["words"] or words_of(None)


def name_the_map(session) -> str:
    """R36: a nameless map change in a session on the default map."""
    return NAME_THE_MAP.format(A=_words_here(facts(session)))


def use_new(session, b: str) -> str:
    """R36: the use row of a map created in the card: "New sessions run on {B}. " + S13 (+ the terminal tail)."""
    a = _words_here(facts(session))
    return USE_NEW.format(B=b) + s13(a, b) + (" " + terminal_tail(a) if in_terminal(session) else "")


def use_edited(b: str) -> str:
    """R36: an edited map new sessions do not use (F4 unset: the default's words)."""
    nxt = next_map()[0]
    return USE_EDITED.format(B=b, F4=words_of(nxt, nxt is None))


def use_left(b: str) -> str:
    """R54: a use row left out at Apply because its map changed since the card and now widens."""
    nxt = next_map()[0]
    return USE_LEFT.format(B=b, F4=words_of(nxt, nxt is None))


def use_unchecked(b: str, why: str) -> str:
    """R54 fails closed: a use row left out at Apply because its recheck could not decide (`why`)."""
    nxt = next_map()[0]
    return USE_UNCHECKED.format(B=b, F4=words_of(nxt, nxt is None), why=why)


def tell(session) -> str:
    """What main repeats word for word after a card (R21): S13 (+ the terminal tail) when this session's map and the
    map new sessions use differ, else T1. New sessions with no map (`next_none`): this session's own line and
    next_sentence()'s, the one source the note and studio_show use too."""
    from halo_harness.crew.compile import DEFAULT_MAP
    f = facts(session)
    a = _words_here(f)
    if f["next_none"]:
        return _runs(NOTE_RUNS if f["map"] else T4, a, f["since"]) + " " + next_sentence(session, f, show=False)
    if (f["map"] or DEFAULT_MAP) == (f["next"] or DEFAULT_MAP):
        return _runs(T1, a, f["since"])
    return s13(a, f["next_words"]) + (" " + terminal_tail(a) if in_terminal(session) else "")


def written(wrote) -> str:
    """"the map {B} (new); the agents {x}, {y} (new)" for the `builder_done` items written (R25's `wrote`)."""
    groups: dict = {}
    for w in wrote or []:
        tag = " (new)" if w.get("added") else " (removed)" if w.get("removed") else ""
        groups.setdefault(w.get("kind"), []).append(f"{w.get('name')}{tag}")
    parts = [f"the {k}{'s' if len(groups[k]) > 1 else ''} {', '.join(groups[k])}" for k in ("map", "agent", "workflow")
             if groups.get(k)]
    return "; ".join(parts)


def result_tail(session, wrote, undo, use_written: bool = False) -> str:
    """The Builder's result tail (section 4; replaces "Studio follows the files.")."""
    said = written(wrote) or ("config.json" if use_written else "nothing")
    return RESULT_TAIL.format(written=said, u=undo) + tell(session)


def row(session) -> dict:
    """The status row's map facts (R40): map_since, map_plain, map_next, map_next_none (new sessions start with no map:
    map_next None is then not "the default"), map_next_since, built, asked. Never raises."""
    try:
        f = facts(session)
    except Exception:
        return {}
    return {"map_since": f["since"], "map_plain": f["plain"], "map_next": f["next"], "map_next_none": f["next_none"],
            "map_next_since": f["next_since"], "built": f["built"], "asked": f["asked"]}
