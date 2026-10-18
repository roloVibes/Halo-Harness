"""halo_harness.work.states -- the one state machine every unit of work
follows (Halo 3.1.2.0 R1, docs/WORK.md), and the four alias tables that
map each engine's own state words onto it.

    pending -> ready -> running -> {gated -> ...} -> done | failed | skipped | stopped
                         \\-> waiting -> running             done -> merged

`waiting` is a unit that cannot go on until something outside it happens
(an upstream lane, a harness owner's card); `gated` is a unit whose result
waits for an answer (the merge and quality gate, a team stage's gate, a
flow's human gate). `merged` is the terminal state of a unit whose work
was merged into the run's result. A finished unit may be re-opened
(a redo, a piece the gate sent back): `done -> ready | running | waiting`.

The engines keep their words on disk: `ALIASES[kind]` maps an engine word
to the machine's word, `NATIVE[kind]` maps back. Every engine word
round-trips (`native(kind, unify(kind, w)) == w`); a machine word an
engine never uses maps to the engine word nearest to it (`NATIVE`).
R1 checks the words; R2's scheduler is what walks the edges (`can`).
"""

from __future__ import annotations

STATES = ("pending", "ready", "running", "waiting", "gated", "done", "failed", "skipped", "stopped", "merged")
TERMINAL = ("done", "failed", "skipped", "stopped", "merged")
LIVE = ("running", "waiting", "gated")
EDGES = {
    "pending": ("ready", "running", "waiting", "failed", "skipped", "stopped"),
    "ready": ("pending", "running", "waiting", "failed", "skipped", "stopped"),
    "running": ("waiting", "gated", "done", "failed", "skipped", "stopped"),
    "waiting": ("pending", "ready", "running", "gated", "failed", "skipped", "stopped"),
    "gated": ("ready", "running", "waiting", "done", "failed", "skipped", "stopped", "merged"),
    "done": ("ready", "running", "waiting", "gated", "merged"),
    "failed": (), "skipped": (), "stopped": (), "merged": (),
}
KINDS = ("lane", "part", "stage", "step")

# engine word -> machine word, per kind (the words on disk stay the engine's)
ALIASES = {
    "lane": {"": "pending", "joined": "ready", "writing": "running", "written": "done", "in_review": "gated",
             "waiting": "waiting", "merged": "merged", "failed": "failed"},
    "part": {"pending": "pending", "asked": "waiting", "running": "running", "done": "done", "failed": "failed",
             "stopped": "stopped", "skipped": "skipped", "merged": "merged"},
    "stage": {"pending": "pending", "ready": "ready", "running": "running", "gated": "gated", "done": "done",
              "failed": "failed", "skipped": "skipped"},
    "step": {"pending": "pending", "running": "running", "waiting": "gated", "done": "done", "failed": "failed",
             "skipped": "skipped"},
}
# machine word -> engine word, per kind (the inverse of ALIASES, plus the nearest word for the rest)
NATIVE = {
    "lane": {"pending": "", "ready": "joined", "running": "writing", "waiting": "waiting", "gated": "in_review",
             "done": "written", "failed": "failed", "skipped": "failed", "stopped": "failed", "merged": "merged"},
    "part": {"pending": "pending", "ready": "pending", "running": "running", "waiting": "asked", "gated": "running",
             "done": "done", "failed": "failed", "skipped": "skipped", "stopped": "stopped", "merged": "merged"},
    "stage": {"pending": "pending", "ready": "ready", "running": "running", "waiting": "running", "gated": "gated",
              "done": "done", "failed": "failed", "skipped": "skipped", "stopped": "skipped", "merged": "done"},
    "step": {"pending": "pending", "ready": "pending", "running": "running", "waiting": "waiting", "gated": "waiting",
             "done": "done", "failed": "failed", "skipped": "skipped", "stopped": "failed", "merged": "done"},
}


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


def is_over(state: str) -> bool:
    return state in TERMINAL
