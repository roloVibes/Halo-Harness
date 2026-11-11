"""halo_harness.workflows.when -- a block's "when": the rule that says when main hands work to a square
(Halo 3.3.16.3 "Blocks", docs/WORKFLOWS-squares.md "When").

A lineup's `workflows:` item is a plain ref (today's meaning: the square's `covers` against the gaps) or

    {ref: <ref>, when: {needs: [pdf, audio], words: [review, audit], mode: auto}}

- `mode: auto` (the default): the square takes a hand-off when main needs one of `needs` (the square's
  `covers`, narrowed; none given = its covers) or the task says one of `words`;
- `named`: only when main asks for it by name;
- `always`: first -- a hand-off that names no need goes to it before any other (the Workflow tool's
  description tells main to hand it the task before it answers);
- `off`: not connected -- main never uses it; the block stays on the board, drawn dashed.

The auto lineup keeps its rules in config `workflows.when.<ref>` (when_store.py reads and writes both).

    read(raw) -> Rule | None        None for a plain ref (or no `when`)
    problems(raw) -> [line]         one line per bad value
    item_ref(item) -> str           a `workflows:` item's ref
    label(rule, covers) -> str      the line's label: "needs pdf, audio" | "says review" | "by name only" | ...
    sentence(rule, ref, covers)     the hover card's sentence: "main hands media work when it needs a PDF or audio"
    parse(text) -> (raw | None, problem)   the CLI's --when: needs=pdf,audio | words=review,audit | named | always | off | auto
    word_hit(rule, task) -> str     the first of the rule's words the task says ("" when none)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from halo_harness.workflows.contract import COVERS

MODES = ("auto", "named", "always", "off")
ALIASES = {"images": "vision", "image": "vision", "work data": "work-data", "a plan": "plan", "a review": "review"}
# the words the When page ticks, in its order, with what each is called in plain words
NEEDS = (("pdf", "pdf"), ("vision", "images"), ("audio", "audio"), ("video", "video"), ("code", "code"),
         ("plan", "a plan"), ("research", "research"), ("review", "a review"), ("work-data", "work data"))
_SAY = dict(NEEDS) | {"media": "media"}
_THE = {"pdf": "a PDF", "vision": "an image", "audio": "audio", "video": "video", "code": "code", "plan": "a plan",
        "research": "research", "review": "a review", "work-data": "work data", "media": "media"}


@dataclass
class Rule:
    needs: list = field(default_factory=list)
    words: list = field(default_factory=list)
    mode: str = "auto"

    def to_json(self) -> dict:
        out: dict = {}
        if self.needs:
            out["needs"] = list(self.needs)
        if self.words:
            out["words"] = list(self.words)
        if self.mode != "auto":
            out["mode"] = self.mode
        return out

    @property
    def plain(self) -> bool:
        """The rule a plain ref has: auto, no needs, no words."""
        return self.mode == "auto" and not self.needs and not self.words


def _need(word) -> str:
    w = str(word or "").strip().lower()
    return ALIASES.get(w, w)


def _list(v) -> list:
    if isinstance(v, str):
        v = [x for x in re.split(r"[,\s]+", v) if x]
    return [str(x).strip() for x in v if isinstance(x, (str, int)) and str(x).strip()] if isinstance(v, list) else []


def _mode(v) -> str:
    """YAML reads a bare `mode: off` as false: that is `off`."""
    return "off" if v is False else str(v or "auto").strip().lower()


def read(raw) -> Optional[Rule]:
    """The rule of a `when:` mapping (or of a whole `{ref, when}` item); None when it has none."""
    if isinstance(raw, dict) and "ref" in raw:
        raw = raw.get("when")
    if not isinstance(raw, dict):
        return None
    mode = _mode(raw.get("mode"))
    needs = list(dict.fromkeys(_need(n) for n in _list(raw.get("needs"))))
    words = list(dict.fromkeys(w.lower() for w in _list(raw.get("words"))))
    return Rule(needs=[n for n in needs if n in COVERS], words=words, mode=mode if mode in MODES else "auto")


def problems(raw) -> "list[str]":
    """One line per bad value of a `when:` mapping."""
    if raw is None:
        return []
    if not isinstance(raw, dict):
        return ['"when" is a mapping: {needs: [...], words: [...], mode: auto|named|always|off}']
    out = []
    for k in raw:
        if k not in ("needs", "words", "mode"):
            out.append(f'"when.{k}" is not read (needs, words, mode)')
    if raw.get("mode") is not None and _mode(raw.get("mode")) not in MODES:
        out.append(f'"when.mode" {raw.get("mode")!r} is not one of {", ".join(MODES)}')
    for n in _list(raw.get("needs")):
        if _need(n) not in COVERS:
            out.append(f'"when.needs" {n!r} is not a need a square covers ({", ".join(COVERS)})')
    if raw.get("needs") is not None and not isinstance(raw.get("needs"), (list, str)):
        out.append('"when.needs" is a list of needs')
    if raw.get("words") is not None and not isinstance(raw.get("words"), (list, str)):
        out.append('"when.words" is a list of words')
    return out


def item_ref(item) -> str:
    if isinstance(item, str):
        return item.strip()
    if isinstance(item, dict) and isinstance(item.get("ref"), str):
        return item["ref"].strip()
    return ""


def _join(words: list, last: str = "or") -> str:
    return words[0] if len(words) == 1 else ", ".join(words[:-1]) + f" {last} {words[-1]}"


def label(rule: Optional[Rule], covers=()) -> str:
    """The line's label, a few plain words."""
    rule = rule or Rule()
    if rule.mode == "off":
        return "not connected"
    if rule.mode == "named":
        return "by name only"
    if rule.mode == "always":
        return "always first"
    bits = []
    needs = rule.needs or ([c for c in covers if c != "media"] if not rule.words else [])
    if needs:
        bits.append("needs " + ", ".join(_SAY.get(n, n) for n in needs))
    if rule.words:
        bits.append("says " + ", ".join(rule.words))
    return " · ".join(bits) or "asked by name"


def when_line(rule: Optional[Rule], covers=()) -> str:
    """ "when needs pdf" | "not connected" -- the label as a CLI line says it."""
    got = label(rule, covers)
    return got if got == "not connected" else f"when {got}"


def sentence(rule: Optional[Rule], ref: str, covers=()) -> str:
    """The rule in a sentence (a line's hover card, `halo workflows when`)."""
    rule = rule or Rule()
    if rule.mode == "off":
        return f"{ref} is not connected: main never uses it"
    if rule.mode == "named":
        return f"main hands {ref} work only when it asks for {ref} by name"
    if rule.mode == "always":
        return f"main hands {ref} every task first, before it answers"
    bits = []
    needs = rule.needs or ([c for c in covers if c != "media"] if not rule.words else [])
    if needs:
        bits.append("it needs " + _join([_THE.get(n, n) for n in needs]))
    if rule.words:
        bits.append("the task says " + _join([f'"{w}"' for w in rule.words]))
    tail = " or when ".join(bits) if bits else "it asks for it by name"
    return f"main hands {ref} work when {tail}" + ("" if rule.needs or rule.words else " (its covers)")


def parse(text: str) -> "tuple[Optional[dict], str]":
    """`--when`: needs=pdf,audio | words=review,audit | needs=pdf;words=scan | named | always | off | auto.
    (raw `when` mapping, "") or (None, the problem); auto answers {} (the plain rule)."""
    t = str(text or "").strip()
    if t.lower() in MODES:
        return ({} if t.lower() == "auto" else {"mode": t.lower()}), ""
    out: dict = {}
    for part in [p for p in re.split(r"[;&]", t) if p.strip()]:
        key, eq, val = part.partition("=")
        key = key.strip().lower()
        if not eq or key not in ("needs", "words"):
            return None, f"{part.strip()!r}: --when takes needs=pdf,audio | words=review,audit | named | always | off"
        out[key] = [v for v in re.split(r"[,\s]+", val.strip()) if v]
    bad = problems(out)
    return (None, bad[0]) if bad else (out, "")


def word_hit(rule: Optional[Rule], task: str) -> str:
    low = str(task or "").lower()
    for w in (rule.words if rule else ()):
        if re.search(r"(?<![a-z0-9])" + re.escape(w) + r"(?![a-z0-9])", low):
            return w
    return ""
