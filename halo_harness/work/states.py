"""halo_harness.work.states -- the one state machine every unit of work
follows (Halo 3.1.2.0 R1, docs/WORK.md), and the three alias tables that
map each engine's own state words onto it.

    pending -> ready -> running -> {gated -> ...} -> done | failed | skipped | stopped
                         \\-> waiting -> running             done -> merged

`waiting` is a unit that cannot go on until something outside it happens
(an upstream lane, a harness owner's card); `gated` is a unit whose result
waits for an answer (the merge and quality gate, a team stage's gate).
`merged` is the terminal state of a unit whose work
was merged into the run's result. A finished unit may be re-opened
(a redo, a piece the gate sent back): `done -> ready | running | waiting`.

R2 enforces the edges: every engine write of a unit's state goes through
`Unit.move` (work/unit.py), which raises `IllegalMove` for a move that is
not in `EDGES`. Moving a unit to the state it is in is no edge: it is the
engine saying the state again with a new line (a lane `waiting` with a new
reason), and it is always allowed. The edges R2 added because an engine
needs them (each named in docs/WORK.md):

    failed  -> ready | running   a failed stage runs again when asked; a lane's worker that
                                 fell over gets its one more run, a resumed lane runs again
    skipped -> ready             a skipped stage (the run's budget held it) is asked to run again
    merged  -> waiting           the gate sends a merged piece back (the tests fail on the finished
                                 branch), and a downstream lane of it goes stale
    waiting -> done              a mission part's result lands while the hub still shows it asked

The engines keep their words on disk: `ALIASES[kind]` maps an engine word
to the machine's word, `NATIVE[kind]` maps back. Every engine word
round-trips (`native(kind, unify(kind, w)) == w`); a machine word an
engine never uses maps to the engine word nearest to it (`NATIVE`).
"""

from __future__ import annotations

STATES = ("pending", "ready", "running", "waiting", "gated", "done", "failed", "skipped", "stopped", "merged")
TERMINAL = ("done", "failed", "skipped", "stopped", "merged")
LIVE = ("running", "waiting", "gated")
EDGES = {
    "pending": ("ready", "running", "waiting", "failed", "skipped", "stopped"),
    "ready": ("pending", "running", "waiting", "failed", "skipped", "stopped"),
    "running": ("waiting", "gated", "done", "failed", "skipped", "stopped"),
    "waiting": ("pending", "ready", "running", "gated", "done", "failed", "skipped", "stopped"),
    "gated": ("ready", "running", "waiting", "done", "failed", "skipped", "stopped", "merged"),
    "done": ("ready", "running", "waiting", "gated", "merged"),
    "failed": ("ready", "running"),
    "skipped": ("ready",),
    "stopped": (),
    "merged": ("waiting",),
}
# the edges R2 added to R1's machine, each because an engine needs it (the docstring says which)
ADDED = (("failed", "ready"), ("failed", "running"), ("skipped", "ready"), ("merged", "waiting"), ("waiting", "done"))
KINDS = ("lane", "part", "stage", "goal")  # 3.1.8.0 R1: a supervisor goal is a unit too

# engine word -> machine word, per kind (the words on disk stay the engine's)
ALIASES = {
    "lane": {"": "pending", "joined": "ready", "writing": "running", "written": "done", "in_review": "gated",
             "waiting": "waiting", "merged": "merged", "failed": "failed"},
    # 3.2.1.0 R3: a part `waiting` is ready, held by the hub until its pack capability has a free slot on its harness
    "part": {"pending": "pending", "waiting": "ready", "asked": "waiting", "running": "running", "done": "done",
             "failed": "failed", "stopped": "stopped", "skipped": "skipped", "merged": "merged"},
    "stage": {"pending": "pending", "ready": "ready", "running": "running", "gated": "gated", "done": "done",
              "failed": "failed", "skipped": "skipped"},
    # 3.1.8.0 R1: a supervisor goal (supervise/queue.py). queued -> ready, parked -> waiting (it waits on the owner).
    "goal": {"queued": "ready", "running": "running", "parked": "waiting", "done": "done", "stopped": "stopped",
             "failed": "failed"},
}
# machine word -> engine word, per kind (the inverse of ALIASES, plus the nearest word for the rest)
NATIVE = {
    "lane": {"pending": "", "ready": "joined", "running": "writing", "waiting": "waiting", "gated": "in_review",
             "done": "written", "failed": "failed", "skipped": "failed", "stopped": "failed", "merged": "merged"},
    "part": {"pending": "pending", "ready": "waiting", "running": "running", "waiting": "asked", "gated": "running",
             "done": "done", "failed": "failed", "skipped": "skipped", "stopped": "stopped", "merged": "merged"},
    "stage": {"pending": "pending", "ready": "ready", "running": "running", "waiting": "running", "gated": "gated",
              "done": "done", "failed": "failed", "skipped": "skipped", "stopped": "skipped", "merged": "done"},
    "goal": {"pending": "queued", "ready": "queued", "running": "running", "waiting": "parked", "gated": "parked",
             "done": "done", "failed": "failed", "skipped": "stopped", "stopped": "stopped", "merged": "done"},
}


class IllegalMove(ValueError):
    """A move the machine has no edge for: `str(e)` names the unit, from and to."""

    def __init__(self, label: str, a: str, b: str):
        self.label, self.a, self.b = label, a, b
        allowed = ", ".join(EDGES.get(a, ())) or "nothing: it is over"
        super().__init__(f"{label} cannot move from {a} to {b} (from {a} it moves to {allowed})")


def words(kind: str) -> tuple:
    """The engine's own state words for `kind`, in its order."""
    return tuple(ALIASES[_kind(kind)])


def _kind(kind: str) -> str:
    if kind not in KINDS:
        raise ValueError(f"a unit's kind is one of {', '.join(KINDS)}, got {kind!r}")
    return kind


def unify(kind: str, word) -> str:
    """The machine's word for engine word `word` (ValueError for a word the engine does not use)."""
    table = ALIASES[_kind(kind)]
    w = "" if word is None else str(word)
    if w not in table:
        raise ValueError(f"{kind} state must be one of {', '.join(repr(x) for x in table)}, got {word!r}")
    return table[w]


def native(kind: str, state: str) -> str:
    """The engine word that machine state `state` is written as."""
    if state not in STATES:
        raise ValueError(f"state must be one of {', '.join(STATES)}, got {state!r}")
    return NATIVE[_kind(kind)][state]


def check_word(kind: str, word, label: str = "") -> str:
    """`word` itself when the engine uses it, else the engine's own ValueError text."""
    table = ALIASES[_kind(kind)]
    if word not in table:
        name = label or f"{kind} state"
        raise ValueError(f"{name} must be one of {', '.join(w for w in table if w)}, got {word!r}")
    return word


def can(a: str, b: str) -> bool:
    """True when the machine has the edge `a -> b`."""
    return b in EDGES.get(a, ())


def allowed(a: str, b: str) -> bool:
    """A move the machine takes: an edge, or the state said again (`a == b`)."""
    return a == b or can(a, b)


def check_move(label: str, a: str, b: str) -> str:
    """`b` when `a -> b` is allowed, else IllegalMove naming `label`, from and to."""
    for s in (a, b):
        if s not in STATES:
            raise ValueError(f"state must be one of {', '.join(STATES)}, got {s!r}")
    if not allowed(a, b):
        raise IllegalMove(label, a, b)
    return b


def is_over(state: str) -> bool:
    return state in TERMINAL
