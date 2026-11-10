"""halo_harness.workflows.router -- which square takes a hand-off, and why (Halo 3.3.16.0 R3,
docs/WORKFLOWS-squares.md "The router").

Auto's rule applied to squares. The gaps: with `need`, that word; with neither `need` nor `name`, the
task's needs (`models_auto.derive_needs` on the task and its files: a PDF, an image, audio, video) minus
what the current model takes (`model_takes.takes_for_ref`, the `/model` takes column: `?` counts as text
only), plus the asks the task names (plan, review, research). The pick: the enabled squares whose
`covers` meet the gaps -- the most gaps covered, then the band nearest the session's, then the enabled
order. One line says why ("handing the PDF to media: your model takes text only"); no square -> one line
saying what could not be read, and the main model goes on.

Bounds, enforced by the tool (tools/workflow.py), worked out here:
- depth: a session's `_square_hops` (None on the main session: it may hand off); a square's child gets
  `limits.depth - 1` (and never more than its caller's hops - 1); at 0 a hand-off is refused;
- the cap: the square's `budget.cap_usd` or the session's remaining lineup budget, whichever is less.

    route(task, files, *, name, need, model_ref, squares, band, hops, remaining, takes) -> Route
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from halo_harness.workflows.contract import BANDS, COVERS

ASKS = (("plan", "plan"), ("review", "review"), ("research", "research"))
_THE = {"pdf": "the PDF", "vision": "the image", "audio": "the audio", "video": "the video", "plan": "the plan",
        "review": "the review", "research": "the research", "code": "the code change", "media": "the media",
        "work-data": "the work data"}
READS = ("vision", "audio", "video", "pdf")


@dataclass
class Route:
    square: Optional[object] = None      # the Workflow picked, None when none (or refused)
    gaps: list = field(default_factory=list)
    takes: list = field(default_factory=list)
    why: str = ""                        # the one line: the hand-off's reason, or what could not start
    refused: bool = False                # a bound said no (depth, cap) or the named square is not enabled
    cap_usd: Optional[float] = None      # the cap the run is held to
    hops: int = 0                        # the hops the square's own agent gets
    rule: str = ""                       # 3.3.16.3: the "when" rule that fired ("when main needs pdf"), "" for today's


def _takes_text(takes: list) -> str:
    words = [w for w in takes if w in ("text",) + READS]
    return "text only" if words in ([], ["text"]) else ", ".join(words)


def model_takes(model_ref: str, state_dir=None) -> list:
    from halo_harness.model_takes import takes_for_ref
    try:
        return list(takes_for_ref(str(model_ref or ""), state_dir)[0])
    except Exception:
        return ["?"]


def gaps(task: str, files=(), *, need: str = "", takes=()) -> "list[str]":
    """The needs the current model cannot meet, plus the asks the task names; `need` alone when given."""
    if need:
        return [need.strip().lower()]
    from halo_harness.models_auto import derive_needs
    found = [n for n, _why in derive_needs((), str(task or ""), list(files or ())) if n in READS]
    out = [n for n in found if n not in set(takes)]
    low = str(task or "").lower()
    out += [cover for word, cover in ASKS if word in low and cover not in out]
    return out


def _band_gap(band: str, session_band: str) -> int:
    a = BANDS.index(band) if band in BANDS else 1
    b = BANDS.index(session_band) if session_band in BANDS else 1
    return abs(a - b)


def pick(gaps_: list, squares: list, session_band: str = "mid", covers=None):
    """The enabled square covering the most gaps, then the nearest band, then the first enabled; None.
    `covers(wf)`: what it covers (3.3.16.3: a rule's `needs` narrow it; default its contract's)."""
    best, key = None, None
    for i, wf in enumerate(squares):
        c = wf.contract
        hit = len(set(covers(wf) if covers else c.covers) & set(gaps_))
        if not hit:
            continue
        k = (-hit, _band_gap(c.band, session_band), i)
        if key is None or k < key:
            best, key = wf, k
    return best


def child_hops(contract, hops: Optional[int]) -> int:
    own = max(0, int(contract.depth) - 1)
    return own if hops is None else max(0, min(own, int(hops) - 1))


def cap_for(contract, remaining: Optional[float]) -> Optional[float]:
    caps = [c for c in (contract.cap_usd, remaining) if c is not None]
    return min(caps) if caps else None


def route(task: str, files=(), *, name: str = "", need: str = "", model_ref: str = "", squares=(),
          band: str = "mid", hops: Optional[int] = None, remaining: Optional[float] = None, takes=None,
          find=None, rules=None) -> Route:
    """The hand-off: a square (or none) and its one line. `squares`: the enabled ones; `find(ref)` resolves
    `name` (defaults to workflows.spec.find); `takes`: what the model takes (default: the takes cache);
    `rules`: 3.3.16.3 {ref: when.Rule} -- the lineup's "when" per square (a ref with none keeps today's rule)."""
    takes = list(takes) if takes is not None else model_takes(model_ref)
    files = [str(f) for f in files or () if str(f).strip()]
    r = Route(takes=takes)
    if hops is not None and hops <= 0:
        r.refused, r.why = True, "no hand-off from here: this square's contract allows no further square (limits.depth)"
        return r
    if need and need.strip().lower() not in COVERS:
        r.refused, r.why = True, f"{need!r} is not a need a square covers ({', '.join(COVERS)})"
        return r
    rules = dict(rules or {})
    mode = lambda wf: rules[wf.ref].mode if wf.ref in rules else "auto"  # noqa: E731
    if name:
        enabled = {wf.ref: wf for wf in squares}
        wf = enabled.get(name.strip())
        if wf is None or mode(wf) == "off":
            r.refused, r.why = True, (f"{name} is not connected: main never uses it (Studio: draw its line, or halo "
                                      f"workflows enable {name} --when auto)" if wf is not None else
                                      f"{name} is not enabled for this lineup: halo workflows enable {name} "
                                      "(or Studio: Agents -> Workflows)")
            return r
        r.square, r.gaps = wf, gaps(task, files, need=need, takes=takes)
        r.rule = "asked for by name"
        r.why = f"handing the task to {wf.ref}: asked for by name"
    else:
        from halo_harness.workflows.when_route import by_rule
        live = [wf for wf in squares if mode(wf) not in ("off", "named")]
        if not need and by_rule(r, task, live, rules):
            r.gaps = gaps(task, files, need=need, takes=takes)
        else:
            r.gaps = gaps(task, files, need=need, takes=takes)
            if not r.gaps:
                r.refused, r.why = True, (f"no hand-off: nothing in the task needs more than your model takes "
                                          f"({_takes_text(takes)})")
                return r
            covers = lambda wf: (rules[wf.ref].needs if wf.ref in rules and rules[wf.ref].needs  # noqa: E731
                                 else ([] if wf.ref in rules and rules[wf.ref].words else wf.contract.covers))
            r.square = pick(r.gaps, live, band, covers)
            what = ", ".join(_THE.get(g, g) for g in r.gaps)
            if r.square is None:
                names = ", ".join(files) or "the task's media"
                r.refused, r.why = True, (f"no enabled square covers {what} (your model takes {_takes_text(takes)}): "
                                          f"could not read {names}; halo workflows enable media")
                return r
            lead = next((g for g in r.gaps if g in covers(r.square)), r.gaps[0])
            if r.square.ref in rules and rules[r.square.ref].needs:
                r.rule = f"when main needs {lead}"
                r.why = f"handing {_THE.get(lead, lead)} to {r.square.ref}: {r.rule}"
            else:
                reason = (f"your model takes {_takes_text(takes)}" if lead in READS else f"the ask names {lead}")
                r.why = f"handing {_THE.get(lead, lead)} to {r.square.ref}: {reason}"
    c = r.square.contract
    r.cap_usd, r.hops = cap_for(c, remaining), child_hops(c, hops)
    if r.cap_usd is not None and r.cap_usd <= 0:
        left = f"${remaining:.2f}" if remaining is not None else "$0.00"
        r.refused, r.why = True, f"{r.square.ref} cannot start: budget hit (the session has {left} left)"
    return r
