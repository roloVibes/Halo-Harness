"""halo_harness.workflows.contract -- a square: a workflow with a contract
(Halo 3.3.16.0 R3 "Workflows: squares and the router", docs/WORKFLOWS-squares.md).

The workflow file gains, at its root (the shape: schemas/workflow_yaml.py `square()`):

    does     one sentence (`description` stays its alias for old files)
    takes    what the square accepts: text files pdf images audio video urls
    gives    what comes back: text files report repo-change -- a workflow without it is not a square
             (it lists and runs as before; the router never picks it)
    covers   the needs it answers: pdf vision audio video code plan research media review work-data
    lineup   a lineup name, or {lead: {bio, model}, members: [...]}: the bios on their models
    engine   session (one agent on the lead, no worktree) | orchestra (the compile) | mission (across
             the fleet; run as orchestra when only this harness is here)
    budget   {band: low|mid|high, cap_usd}
    limits   {depth (default 1), turns, wall_s}

The root `takes` / `gives` are the square's contract; a stage's `takes` / `gives` stay its hand-offs
(`[{from, take}]`, `[{name, kind}]`). `read(data)` -> Contract; `contract_lines(L, data)` adds one
problem line per bad value to a workflow_rules.Lines (the manifest's words); `problems(data)` the same
lines as a plain list.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

TAKES = ("text", "files", "pdf", "images", "audio", "video", "urls")
GIVES = ("text", "files", "report", "repo-change")
COVERS = ("pdf", "vision", "audio", "video", "code", "plan", "research", "media", "review", "work-data")
ENGINES = ("session", "orchestra", "mission")
BANDS = ("low", "mid", "high")
DEFAULT_ENGINE = "orchestra"
DEFAULT_BAND = "mid"
DEFAULT_DEPTH = 1
CONTRACT_KEYS = ("takes", "gives", "covers", "lineup", "engine", "budget", "limits")
# a modality need (models_auto.NEEDS) and the word a square takes it as
TAKE_OF_NEED = {"vision": "images", "audio": "audio", "video": "video", "pdf": "pdf"}


def _words(v) -> list:
    return [str(x).strip() for x in v if isinstance(x, str) and str(x).strip()] if isinstance(v, list) else []


def _num(v) -> Optional[float]:
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def _int(v) -> Optional[int]:
    return int(v) if isinstance(v, int) and not isinstance(v, bool) else None


@dataclass
class Contract:
    does: str = ""
    takes: list = field(default_factory=list)
    gives: list = field(default_factory=list)
    covers: list = field(default_factory=list)
    lineup: object = None
    engine: str = DEFAULT_ENGINE
    band: str = DEFAULT_BAND
    cap_usd: Optional[float] = None
    depth: int = DEFAULT_DEPTH
    turns: Optional[int] = None
    wall_s: Optional[int] = None

    @property
    def square(self) -> bool:
        """A workflow is a square when it says what it gives."""
        return bool(self.gives)

    def run_engine(self, fleet: bool = False) -> str:
        """`mission` runs as `orchestra` when only this harness is here."""
        return "orchestra" if self.engine == "mission" and not fleet else self.engine

    def lead(self) -> "tuple[str, str]":
        """(bio, model) of the lead; ('', '') for a lineup name or none."""
        lead = self.lineup.get("lead") if isinstance(self.lineup, dict) else None
        if isinstance(lead, dict):
            return str(lead.get("bio") or ""), str(lead.get("model") or "")
        return "", ""

    def lineup_name(self) -> str:
        return self.lineup.strip() if isinstance(self.lineup, str) else ""

    def models(self) -> list:
        """The models its lineup names: the lead's, then each member's ([] for a lineup name)."""
        lineup = self.lineup if isinstance(self.lineup, dict) else {}
        people = [lineup.get("lead")] + list(lineup.get("members") or [])
        return [str(m.get("model") or "") for m in people if isinstance(m, dict)]

    def tenant(self) -> str:
        """3.3.17.0: "all" when every model it names is cp:work (billed by the tenant, never in dollars), "some" when
        one is, else ""."""
        return tenant_of(self.models())

    def costs(self) -> str:
        dollars = f"band {self.band}" + (f" · cap ${self.cap_usd:.2f}" if self.cap_usd is not None else " · no cap")
        return costs_words(dollars, self.tenant())

    def limits_chip(self) -> str:
        bits = [f"depth {self.depth}"]
        bits += [f"{self.turns} turns"] if self.turns else []
        bits += [f"{self.wall_s} s"] if self.wall_s else []
        return " · ".join(bits)

    def line(self, ref: str) -> str:
        """`halo workflows list`'s contract line: NAME · DOES · TAKES -> GIVES · band · depth."""
        return (f"{ref} · {self.does or '-'} · {','.join(self.takes) or 'text'} -> {','.join(self.gives) or '-'}"
                f" · {self.band} · depth {self.depth}")

    def to_json(self) -> dict:
        bio, model = self.lead()
        return {"does": self.does, "takes": list(self.takes), "gives": list(self.gives), "covers": list(self.covers),
                "lineup": self.lineup, "lead": {"bio": bio, "model": model} if bio else None, "engine": self.engine,
                "band": self.band, "cap_usd": self.cap_usd, "depth": self.depth, "turns": self.turns,
                "wall_s": self.wall_s, "square": self.square, "costs": self.costs(), "limits": self.limits_chip(),
                "tenant": self.tenant()}


def tenant_of(models) -> str:
    """"all" / "some" / "" -- how many of `models` are cp:work (your work's Copilot, billed by your tenant)."""
    from halo_harness.providers.copilot_config import REF
    named = [str(m or "").strip() for m in models or []]
    hits = sum(1 for m in named if m == REF)
    return "" if not hits else "all" if hits == len(named) else "some"


def costs_words(dollars: str, tenant: str) -> str:
    """A square's Costs line: its band and cap (`dollars`); "tenant credits" in their place when all of it runs on
    cp:work, and after them when part of it does (a dollar band says nothing about Copilot's cost)."""
    from halo_harness.providers.copilot_catalog import COST_WORDS
    return COST_WORDS if tenant == "all" else dollars + (f" · + {COST_WORDS}" if tenant == "some" else "")


def read(data) -> Contract:
    data = data if isinstance(data, dict) else {}
    budget = data.get("budget") if isinstance(data.get("budget"), dict) else {}
    limits = data.get("limits") if isinstance(data.get("limits"), dict) else {}
    engine = str(data.get("engine") or DEFAULT_ENGINE)
    band = str(budget.get("band") or DEFAULT_BAND)
    depth = _int(limits.get("depth"))
    return Contract(does=str(data.get("does") or data.get("description") or "").strip(),
                    takes=_words(data.get("takes")), gives=_words(data.get("gives")), covers=_words(data.get("covers")),
                    lineup=data.get("lineup") if isinstance(data.get("lineup"), (str, dict)) else None,
                    engine=engine if engine in ENGINES else DEFAULT_ENGINE, band=band if band in BANDS else DEFAULT_BAND,
                    cap_usd=_num(budget.get("cap_usd")), depth=DEFAULT_DEPTH if depth is None else max(0, depth),
                    turns=_int(limits.get("turns")), wall_s=_int(limits.get("wall_s")))


class _Plain:
    def __init__(self):
        self.out: list = []

    def add(self, key: str, msg: str, name: str = "", value=None) -> None:
        self.out.append(f"{key}{msg}")


def _known(L, data: dict, key: str, words: tuple, what: str) -> None:
    raw = data.get(key)
    if raw is None:
        return
    if key == "takes" and isinstance(raw, list) and any(isinstance(x, dict) for x in raw):
        L.add(key, f" at the root is what the square accepts ({', '.join(TAKES)}); a hand-off's "
              "`takes: [{from, take}]` belongs on a stage", key)
        return
    for word in raw if isinstance(raw, list) else []:
        if isinstance(word, str) and word not in words:
            L.add(key, f" {word!r} is not {what} ({', '.join(words)})", key, word)


def contract_lines(L, data) -> None:
    """One line per bad contract value (L: workflow_rules.Lines, or anything with `.add(key, msg, name, value)`)."""
    if not isinstance(data, dict):
        return
    _known(L, data, "takes", TAKES, "a kind a square takes")
    _known(L, data, "gives", GIVES, "a kind a square gives")
    _known(L, data, "covers", COVERS, "a need a square covers")
    if any(data.get(k) is not None for k in CONTRACT_KEYS if k != "gives") and not _words(data.get("gives")):
        L.add("gives", ": a square says what it gives (" + ", ".join(GIVES) + "); without it the router never picks "
              "this workflow", "gives")
    if data.get("engine") is not None and data.get("engine") not in ENGINES:
        L.add("engine", f" {data.get('engine')!r} is not session, orchestra or mission", "engine", data.get("engine"))
    budget = data.get("budget") if isinstance(data.get("budget"), dict) else {}
    if budget.get("band") is not None and budget.get("band") not in BANDS:
        L.add("budget.band", f" {budget.get('band')!r} is not low, mid or high", "band", budget.get("band"))
    if budget.get("cap_usd") is not None and (_num(budget.get("cap_usd")) is None or budget["cap_usd"] < 0):
        L.add("budget.cap_usd", " is dollars, 0 or more", "cap_usd")
    limits = data.get("limits") if isinstance(data.get("limits"), dict) else {}
    for key, least in (("depth", 0), ("turns", 1), ("wall_s", 1)):
        v = limits.get(key)
        if v is not None and (_int(v) is None or v < least):
            L.add(f"limits.{key}", f" is a whole number, {least} or more", key)
    lineup = data.get("lineup")
    if isinstance(lineup, dict):
        lead = lineup.get("lead")
        if not isinstance(lead, dict) or not str(lead.get("bio") or "").strip():
            L.add("lineup.lead", ": a square's lineup names its lead's bio ({lead: {bio, model}}), or is a lineup name",
                  "lead")


def problems(data) -> "list[str]":
    """The contract's lines as a plain list (no file, no line numbers)."""
    L = _Plain()
    contract_lines(L, data)
    return L.out
