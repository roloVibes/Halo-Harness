"""halo_harness.crew.kinds_note -- what main is told when an agent is added to its running session or taken back (Halo
3.6.0.15 UN, the design's rule U5: notes N1 and N2, letter for letter).

    step(session) -> list | None    before EACH of main's model calls (agent/loop.py, beside the mode notice's sync):
                                    take what crew/use_now.py queued, then log ONE snapshot of kind "kinds_note" with
                                    N1 for each name that comes in, N2 for each name that goes out or comes back
    cleared(session) / compacted(session)
                                    after /clear or a compaction, the next step tells once more what main can no longer
                                    have read (N1 for each name still added, N2 for each start name taken out)

"Once" (3.6.0.16 C1): main is told exactly when the set of names it can start changes (crew/use_now.py `take`'s
`change`), never when only what stands behind a name it can already start changes: N1 when a name comes in (a new one,
or one the session started with, saved again after its delete), N2_GONE when a name goes out, N2_BACK when an undo
brings back a start name that was out. An edit, his own agent taking the place of one the session started with, and the
undo of either are never told; N1 again only after its N2. A put with note False (the Builder's: its result line
"Ready in this session now" tells main, crew/ready_now.py) sends no N1. A session nothing is put to or taken from
returns before any lock, log write or attribute: it sends byte for byte what it sent before this module. Never raises.
"""

from __future__ import annotations

N1 = "[Halo] A new helper you can start now: {name} ({words})."
# The design gives the one N1 form; a kind whose `does` yields no first-sentence words is written bare, as M2's own line
# writes a name with no words (crew/kinds.py `_line`).
N1_BARE = "[Halo] A new helper you can start now: {name}."
N2_GONE = "[Halo] Taken back: {name} can no longer be started in this session."
N2_BACK = "[Halo] Taken back: {name} starts as it did when this session began."
KIND = "kinds_note"


def n1(name: str, spec) -> str:
    """N1 for `name`, its words M2's (crew/kinds.py `kinds`: his agent's first sentence of `does`, at most 8 words)."""
    words = ""
    try:
        from halo_harness.crew.kinds import kinds
        rows = kinds({name: spec})
        words = rows[0]["words"] if rows else ""
    except Exception:
        words = ""
    return N1.format(name=name, words=words) if words else N1_BARE.format(name=name)


def _gone_starts(session) -> list:
    """The names the session started with that are no longer in its agents (taken back by a delete)."""
    starts = getattr(session, "_start_specs", None) or {}
    agents = session.agent_runtime.agents
    return [n for n, sp in starts.items() if sp is not None and n not in agents]


def _retold(session, told: set) -> list:
    from halo_harness.crew import use_now
    texts = []
    agents = session.agent_runtime.agents
    for name in use_now.added(session):
        if name not in told and name in agents:
            texts.append(n1(name, agents[name]))
            told.add(name)
    for name in _gone_starts(session):
        if name not in told:
            texts.append(N2_GONE.format(name=name))
            told.add(name)
    return texts


def step(session) -> "list | None":
    retell = getattr(session, "_kinds_retell", False)
    if not getattr(session, "_kinds_pending", None) and not retell:
        return None  # the fast path: nothing queued, nothing to tell again
    try:
        from halo_harness.crew import use_now
        texts: list = []
        told: set = set()
        for ch in use_now.take(session):
            name, change = ch.get("name"), ch.get("change")
            if change in ("added", "again"):
                if ch.get("note", True):
                    texts.append(n1(name, ch.get("spec")))
                told.add(name)
            elif change == "gone":
                texts.append(N2_GONE.format(name=name))
                told.add(name)
            elif change == "back":
                texts.append(N2_BACK.format(name=name))
                told.add(name)
        if retell:
            session._kinds_retell = False
            texts.extend(_retold(session, told))
        if not texts:
            return None
        session.log.append_snapshot([{"type": "text", "text": t} for t in texts], kind=KIND)
        return texts
    except Exception:
        return None


def _mark(session) -> None:
    try:
        if getattr(session, "_kinds_added", None) or (getattr(session, "_start_specs", None) and _gone_starts(session)):
            session._kinds_retell = True
    except Exception:
        pass


def cleared(session) -> None:
    """/clear: the new conversation has none of the notes; the next step tells them once more."""
    _mark(session)


def compacted(session) -> None:
    """A compaction: the notes may be out of the tail it keeps; the next step tells them once more."""
    _mark(session)
