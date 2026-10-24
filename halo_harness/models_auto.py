"""halo_harness.models_auto -- the `auto` model reference (Halo 3.1.9.0 R2,
"the Auto lineup").

A bio whose `models.preference` is `auto` (the auto lineup's pool,
templates/agents/auto-*.yaml) names no model: `pick` chooses one when the
agent spawns, from R1's best-at index (`models_best_at.index`) and what the
task needs:

* the needs: the bio's `models.needs`, plus what the task carries -- an image
  path (or an attached image) asks for `vision`, an audio / video / PDF one
  for `audio` / `video` / `pdf`; a planner, reviewer or judge asks for
  `reasoning`; a task longer than `LONG_INPUT_CHARS` asks for `long-context`;
  a media agent whose task names no modality asks for `vision`;
* the candidates: the index's rows that state every need (an unstated fact
  is not a yes), answer in text and do not state "no tool calls" (every
  agent works through its tools); a video need no model has falls back to
  vision (the Media tool turns a video into frames);
* the band (the lineup's `budget.band`): `low` the cheapest candidate, `mid`
  the best one within `MID_WINDOW` x the cheapest paid one (free and local
  ones always count), `high` the strongest. "Best" is the mean of the index's
  scores for the kinds behind the needs (`NEED_KINDS`; reasoning takes the
  better of code and research); with no needs it is cheap and fast (bulk and
  measured speed);
* a tie goes to the session's own model, then (band low) to a local one,
  then the cheaper, then the ref's name; no candidate -> main's model.

The reason is one line naming the deciding need and the price ("an image in
the task, the cheapest vision model ($0.30/$1.20 per 1M)"); `Pick.line()` is
what Studio and the child's first note show. Deterministic given the index.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import NamedTuple, Optional

AUTO = "auto"
BANDS = ("low", "mid", "high")
DEFAULT_BAND = "mid"
NEEDS = ("vision", "audio", "video", "pdf", "reasoning", "tools", "long-context")
NEED_KINDS = {"vision": "visual", "audio": "audio", "video": "video", "pdf": "pdf", "tools": "code",
              "long-context": "research"}
DECIDE_ORDER = ("vision", "audio", "video", "pdf", "long-context", "reasoning", "tools")
MID_WINDOW = 3.0
LONG_CONTEXT_TOKENS = 128_000
LONG_INPUT_CHARS = 100_000
REASONING_WORDS = (("plan", "planning"), ("review", "review"), ("judge", "judging"))
_EXTS = {
    "vision": ("png", "jpg", "jpeg", "gif", "webp", "bmp", "tif", "tiff", "heic", "heif"),
    "audio": ("mp3", "wav", "flac", "m4a", "ogg", "opus", "aac", "wma"),
    "video": ("mp4", "mov", "mkv", "webm", "avi", "m4v", "wmv"),
    "pdf": ("pdf",),
}
_EXT_RE = {need: re.compile(r"\.(?:" + "|".join(exts) + r")\b", re.IGNORECASE) for need, exts in _EXTS.items()}
_WHAT = {"vision": "an image", "audio": "audio", "video": "a video", "pdf": "a PDF"}
_MODALITIES = ("vision", "audio", "video", "pdf")


@dataclass
class Pick:
    ref: str                                          # the model (main's when `fallback`)
    reason: str                                       # one line: the deciding need and the price
    kinds: list = field(default_factory=list)         # the needs the pick was made for
    alternatives: list = field(default_factory=list)  # the next candidates, best first
    fallback: bool = False                            # True: no candidate, main's model runs it

    def line(self) -> str:
        return f"auto: {self.ref or 'main'} -- {self.reason}"

    def fall_back(self, main_ref: str, why: str) -> None:
        self.ref, self.reason, self.fallback = main_ref, f"{why}; using main's", True


def is_auto(value) -> bool:
    return isinstance(value, str) and value.strip().lower() == AUTO


def _attachment_need(item) -> Optional[str]:
    if isinstance(item, dict):
        kind = str(item.get("type") or item.get("media_type") or "").lower()
        for prefix, need in (("image", "vision"), ("audio", "audio"), ("input_audio", "audio"), ("video", "video"),
                             ("document", "pdf"), ("application/pdf", "pdf")):
            if kind.startswith(prefix):
                return need
        item = item.get("path") or item.get("image_path") or ""
    text = str(item or "")
    return next((need for need in _MODALITIES if _EXT_RE[need].search(text)), None)


def derive_needs(needs=(), task_text: str = "", attachments=(), role: str = "") -> list:
    """`[(need, why), ...]` in NEEDS order, each need once; `why` says where
    it came from ("an image in the task", "planning needs reasoning")."""
    found: dict = {}
    for item in attachments or ():
        need = _attachment_need(item)
        if need:
            found.setdefault(need, f"{_WHAT[need]} attached")
    for need in _MODALITIES:
        if _EXT_RE[need].search(task_text or ""):
            found.setdefault(need, f"{_WHAT[need]} in the task")
    words = (role or "").lower()
    for word, what in REASONING_WORDS:
        if word in words:
            found.setdefault("reasoning", f"{what} needs reasoning")
            break
    for need in needs or ():
        need = str(need).strip().lower()
        if need in NEEDS:
            found.setdefault(need, f"the bio asks for {need}")
    if len(task_text or "") > LONG_INPUT_CHARS:
        found.setdefault("long-context", "a long input")
    if "media" in words and not any(n in found for n in _MODALITIES):
        found["vision"] = "media work naming no modality"
    return [(need, found[need]) for need in NEEDS if need in found]


def has(facts: dict, need: str) -> bool:
    """True when the row STATES the need (None / unstated is not a yes)."""
    mi = facts.get("modalities_in") if isinstance(facts.get("modalities_in"), list) else []
    if need == "vision":
        return "image" in mi
    if need in ("audio", "video"):
        return need in mi
    if need == "pdf":
        return "pdf" in mi or "file" in mi
    if need == "reasoning":
        r = facts.get("reasoning")
        return isinstance(r, dict) and r.get("kind") in ("native", "openai")
    if need == "tools":
        return facts.get("tools") is True
    if need == "long-context":
        ctx = facts.get("context_tokens")
        return isinstance(ctx, (int, float)) and not isinstance(ctx, bool) and ctx >= LONG_CONTEXT_TOKENS
    return False


def strength(entry: dict, needs: list) -> float:
    s = entry.get("scores") or {}
    num = lambda k: float(s.get(k) or 0)
    if not needs:
        return round(0.7 * num("bulk") + 0.3 * num("fast"), 3)
    parts = [max(num("code"), num("research")) if n == "reasoning" else num(NEED_KINDS[n]) for n in needs]
    return round(sum(parts) / len(parts), 3)


def price_words(facts: dict) -> str:
    if facts.get("local"):
        return "free, local"
    pin, pout = facts.get("price_in_per_m"), facts.get("price_out_per_m")
    if not isinstance(pin, (int, float)) or isinstance(pin, bool):
        return "price unknown"
    pout = pout if isinstance(pout, (int, float)) and not isinstance(pout, bool) else pin
    return "free" if pin <= 0 and pout <= 0 else f"${pin:.2f}/${pout:.2f} per 1M"


class _Cand(NamedTuple):
    ref: str
    score: float
    price: Optional[float]
    local: bool
    facts: dict


def _candidates(entries: dict, needs: list, main_ref: str) -> list:
    from halo_harness.capabilities_strengths import blended_price
    out = []
    for ref in sorted(entries):
        e = entries[ref] if isinstance(entries[ref], dict) else {}
        f = e.get("facts") if isinstance(e.get("facts"), dict) else {}
        mo = f.get("modalities_out")
        if f.get("tools") is False or (isinstance(mo, list) and "text" not in mo):
            continue
        if all(has(f, n) for n in needs):
            out.append(_Cand(ref, strength(e, needs), blended_price({**f, "ref": ref}), f.get("local") is True, f))
    return out


def _choose(cands: list, needs: list, band: str, main_ref: str) -> tuple:
    """`(chosen, ordered, rule, tie)` -- the band's rule over the candidates."""
    inf, label = float("inf"), ("+".join(needs) + " model") if needs else ""
    priced = [c for c in cands if c.price is not None]
    by_score = lambda c: (-c.score, c.ref != main_ref, c.price if c.price is not None else inf, c.ref)
    if band == "low":
        pool = priced or cands
        ordered = sorted(pool, key=lambda c: (c.price if c.price is not None else inf, c.ref != main_ref,
                                              not c.local, -c.score, c.ref))
        primary = lambda c: c.price
        rule = f"the cheapest {label or 'model'}"
    elif band == "mid":
        paid = [c.price for c in priced if c.price > 0]
        cap = min(paid) * MID_WINDOW if paid else 0.0
        pool = [c for c in priced if c.price <= cap + 1e-9] or cands
        ordered, primary = sorted(pool, key=by_score), (lambda c: c.score)
        rule = f"the best {label or 'cheap, fast model'} within {MID_WINDOW:g}x the cheapest"
    else:
        ordered, primary = sorted(cands, key=by_score), (lambda c: c.score)
        rule = f"the strongest {label}" if label else "the best cheap, fast model"
    if not priced and band != "high":
        rule += " (no candidate states a price: by score)"
    best = ordered[0]
    tied, tie = len([c for c in ordered if primary(c) == primary(best)]) > 1, ""
    if tied and best.ref == main_ref:
        tie = "; a tie, so main's own model"
    elif tied and band == "low" and best.local:
        tie = "; a tie, so the local one"
    return best, ordered, rule, tie


def load_rows(state_dir) -> dict:
    """The best-at index's rows: a stale index answers at once (rebuilt behind
    it), a missing one is waited for at most `FIRST_BUILD_WAIT_S`; {} when
    none. `HALO_AUTO_INDEX_BUILD=0` (the test suite) reads the file only."""
    if state_dir is None:
        return {}
    try:
        import os
        from halo_harness.models_best_at import index, load
        cache = load(state_dir) if os.environ.get("HALO_AUTO_INDEX_BUILD") == "0" else index(state_dir, stale_ok=True)
    except Exception:
        return {}
    rows = cache.get("rows") if isinstance(cache, dict) else None
    return rows if isinstance(rows, dict) else {}


def pick(state_dir, *, needs=(), task_text: str = "", attachments=(), band: str = DEFAULT_BAND,
         main_ref: str = "", role: str = "", rows: Optional[dict] = None) -> Pick:
    """The model an `auto` agent runs on, and why (see the module docstring).
    `role`: the words naming the agent (its alias, its bio's kind); `rows`:
    the index's rows (default: read from `state_dir`)."""
    found = derive_needs(needs, task_text, attachments, role)
    wanted, why = [n for n, _w in found], dict(found)
    band = band if band in BANDS else DEFAULT_BAND
    entries = load_rows(state_dir) if rows is None else rows
    if not entries:
        return Pick(main_ref, "no model index yet (`halo models analyze` builds it); using main's", wanted, [], True)
    cands, note = _candidates(entries, wanted, main_ref), ""
    if not cands and "video" in wanted:
        relaxed = [n for n in wanted if n != "video"] + ([] if "vision" in wanted else ["vision"])
        relaxed = [n for n in NEEDS if n in relaxed]
        cands = _candidates(entries, relaxed, main_ref)
        if cands:
            wanted, note = relaxed, "no model takes video, so vision reads the Media tool's frames: "
    if not cands:
        return Pick(main_ref, f"no model in the catalog has {'+'.join(wanted)}; using main's", wanted, [], True)
    best, ordered, rule, tie = _choose(cands, wanted, band, main_ref)
    deciding = next((why[n] for n in DECIDE_ORDER if n in why), "no special needs")
    reason = f"{deciding}, {note}{rule} ({price_words(best.facts)}){tie}"
    return Pick(best.ref, reason, wanted, [c.ref for c in ordered[1:4]])
