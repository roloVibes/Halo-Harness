"""halo_harness.work.unit -- the unit of work (Halo 3.1.2.0 R1, docs/WORK.md).

An Orchestra lane, a mission part, a team stage and a flow step are all a
`Unit`: something one owner runs, with claims, hand-offs, a state on the
one machine (work/states.py), a gate, an acceptance, a cost and refs.

    {"kind": "lane|part|stage|step", "id": "2", "title": "...", "run_id": "...",
     "owner": "the bio / member / harness that runs it",
     "claims": {"keys": [...], "mode": "unit|path|block|none"},
     "needs": [{"from", "take"}], "gives": [{"name", "kind", "path"}], "after": [...], "base": "<sha>" | null,
     "state": "<machine word>", "native": "<the engine's word>",
     "gate": {"mode": "required|optional|none", "id", "round", "answer": {"action", "text", "ts"} | null},
     "acceptance": {"prompt", "expect", "ok", "note"} | null,
     "cost_usd": 0.0, "started": ts | null, "ended": ts | null, "attempts": 0, "error": "",
     "refs": {"sessions", "run", "worktree", "branch", "head", ...}, "extra": {what only one kind has}}

`Unit.source` keeps the engine record it was read from (not part of
`to_dict`): the adapter writes the unit back onto that record, key order
kept, so an unchanged unit writes the file back byte for byte.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Optional

from halo_harness.work import states as ST

GATE_MODES = ("required", "optional", "none")
CLAIM_MODES = ("unit", "path", "block", "none")


def gate(mode: str = "none", gid: Optional[str] = None, rnd: int = 0, answer: Optional[dict] = None) -> dict:
    """A unit's gate: its mode, the open gate's id and round, the last answer."""
    if mode not in GATE_MODES:
        mode = "none"
    return {"mode": mode, "id": gid, "round": int(rnd or 0), "answer": answer_of(answer)}


def answer_of(raw) -> Optional[dict]:
    if not isinstance(raw, dict) or not raw.get("action"):
        return None
    return {"action": str(raw.get("action")), "text": str(raw.get("text") or raw.get("instruction") or ""),
            "ts": raw.get("ts")}


def claims(keys=None, mode: str = "none") -> dict:
    return {"keys": [str(k) for k in keys or []], "mode": mode if mode in CLAIM_MODES else "none"}


@dataclass
class Unit:
    kind: str
    id: str
    title: str = ""
    run_id: str = ""
    owner: str = ""
    claims: dict = field(default_factory=claims)
    needs: list = field(default_factory=list)
    gives: list = field(default_factory=list)
    after: list = field(default_factory=list)
    base: Optional[str] = None
    state: str = "pending"
    native: str = ""
    gate: dict = field(default_factory=gate)
    acceptance: Optional[dict] = None
    cost_usd: float = 0.0
    started: Optional[float] = None
    ended: Optional[float] = None
    attempts: int = 0
    error: str = ""
    refs: dict = field(default_factory=dict)
    extra: dict = field(default_factory=dict)
    source: dict = field(default_factory=dict, repr=False, compare=False)

    def __post_init__(self) -> None:
        if self.kind not in ST.KINDS:
            raise ValueError(f"a unit's kind is one of {', '.join(ST.KINDS)}, got {self.kind!r}")
        if self.state not in ST.STATES:
            raise ValueError(f"a unit's state is one of {', '.join(ST.STATES)}, got {self.state!r}")

    @classmethod
    def from_native(cls, kind: str, uid, native_word, **fields) -> "Unit":
        """A unit whose state is the engine word `native_word` (mapped through the kind's alias table)."""
        return cls(kind=kind, id=str(uid), state=ST.unify(kind, native_word), native=str(native_word or ""), **fields)

    def move(self, state: str) -> "Unit":
        """Set the machine state (and the engine word it is written as)."""
        self.native = ST.native(self.kind, state)
        self.state = state
        return self

    def move_native(self, word: str) -> "Unit":
        self.state = ST.unify(self.kind, word)
        self.native = str(word or "")
        return self

    @property
    def over(self) -> bool:
        return ST.is_over(self.state)

    def to_dict(self) -> dict:
        data = asdict(self)
        data.pop("source", None)
        return data


def from_dict(data: dict) -> Unit:
    keys = set(Unit.__dataclass_fields__) - {"source"}
    return Unit(**{k: v for k, v in data.items() if k in keys})
