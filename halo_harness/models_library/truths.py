"""halo_harness.models_library.truths -- Halo 3.3.6.0 R2: the three truths (plans/local-model-fit-brief.md F1).

Every capability and fit fact on a library row is one of three, never blurred:

    declared  read from metadata: `/api/show` capabilities, the library's chips, the hub's pipeline tag and tags,
              GGUF metadata, a registry config (cheap, there before a download, sometimes wrong)
    expected  inferred from the family rules, the size or the name (a heuristic: it says so)
    verified  probed on this host by the battery (providers/capability_battery.py): the only one that may gate a role

    source_truth(text) -> truth | None      a card `sources` line -> its truth (None: nothing says)
    truth_of(fact, card, profile, row=None) -> "declared" | "expected" | "verified" | None
    facts_for_row(row, card, profile) -> {cap: {value, truth, why}}   the F2 capability list (CAPS)

A capability with no source at all is absent from `facts_for_row`, never guessed. `agentic-ready`, `verifier` and
`tool-accuracy` are verified-only (nothing reliable declares them): without a profile they are there with
`truth: None, probe: True` and "needs a probe". The rules per capability are truth_rules.py.
"""

from __future__ import annotations

from typing import Optional

DECLARED, EXPECTED, VERIFIED = "declared", "expected", "verified"
RANK = {VERIFIED: 3, DECLARED: 2, EXPECTED: 1, None: 0}
CAPS = ("tools", "thinking", "coder", "agentic-ready", "planner", "verifier", "compactor", "bulk", "abliterated",
        "vision", "audio", "embedding", "security", "math", "multilingual", "long-context", "tool-accuracy")
VERIFIED_ONLY = ("agentic-ready", "verifier", "tool-accuracy")
TITLES = {"tools": "tool calls", "thinking": "thinking", "coder": "coder", "agentic-ready": "agentic-ready",
          "planner": "planner / orchestrator", "verifier": "verifier / judge", "compactor": "compactor",
          "bulk": "bulk worker", "abliterated": "abliterated", "vision": "vision", "audio": "audio",
          "embedding": "embedding / reranker", "security": "security / pentest", "math": "math",
          "multilingual": "multilingual", "long-context": "long-context recall", "tool-accuracy": "tool-call accuracy"}
FIT_FIELDS = ("window", "params", "quant", "size", "fits", "speed")
GLYPH = {VERIFIED: "✓", DECLARED: "◇", EXPECTED: "≈"}

_VERIFIED_WORDS = ("the battery", "the tool-call probe", "probed on")
_ABSENT_WORDS = ("does not say", "nothing says", "unknown", "not known", "no source")
_DECLARED_STRONG = ("/api/show", "the library's chips", "pipeline tag", "registry", "config", "gguf metadata",
                    "tags page", "the listing", "manifest", "size chip", "the repo's tags", "the repo's card", "the repo's")
_EXPECTED_WORDS = ("the name", "family", "estimate", "a chat model", "typical", "rule", "heuristic")
_DECLARED_WEAK = ("library", "snapshot", "the catalog", "huggingface.co", "ollama.com", "the server")


def source_truth(text) -> Optional[str]:
    """A card `sources` line ("/api/show capabilities", "the name (-coder)", "the battery made a call") -> its truth."""
    t = str(text or "").lower().strip()
    if not t:
        return None
    if any(w in t for w in _VERIFIED_WORDS):
        return VERIFIED
    if any(t.startswith(w) or f": {w}" in t for w in _ABSENT_WORDS) or "does not say" in t:
        return None
    if any(w in t for w in _DECLARED_STRONG):
        return DECLARED
    if any(w in t for w in _EXPECTED_WORDS):
        return EXPECTED
    if any(w in t for w in _DECLARED_WEAK):
        return DECLARED
    return None


def at_least(truth: Optional[str], floor: str) -> bool:
    """True when `truth` is as strong as `floor` ("verified" > "declared" > "expected"; floor "any": anything)."""
    if floor == "any":
        return True
    return RANK.get(truth, 0) >= RANK.get(floor, 1)


def mark_of(card: dict, field: str) -> str:
    """The block mark of a card field before a probe: declared when metadata said it, else expected."""
    return DECLARED if source_truth((card.get("sources") or {}).get(field)) == DECLARED else EXPECTED


def _fit_truth(fact: str, card: dict, profile: Optional[dict], row: Optional[dict]) -> Optional[str]:
    src = dict(card.get("sources") or {})
    rsrc = dict((row or {}).get("sources") or {})
    p = profile or {}
    if fact == "window":
        if (p.get("window") or {}).get("verified"):
            return VERIFIED
        return source_truth(rsrc.get("context") or src.get("window"))
    if fact == "params":
        return source_truth(rsrc.get("params") or src.get("params"))
    if fact == "quant":
        return source_truth(rsrc.get("quant") or src.get("quant"))
    if fact == "size":
        if p.get("size_gb"):
            return VERIFIED
        return source_truth(rsrc.get("size_bytes")) or (EXPECTED if (row or {}).get("estimate") else None)
    if fact == "fits":
        if (p.get("window") or {}).get("verified"):
            return VERIFIED
        fit = (row or {}).get("fit") or {}
        if fit.get("level") in (None, "unknown", "cloud"):
            return None
        return EXPECTED if fit.get("estimate", True) else DECLARED
    if fact == "speed":
        return VERIFIED if (p.get("speed") or {}).get("tok_s") else EXPECTED
    return None


def truth_of(fact: str, card: dict, profile: Optional[dict] = None, row: Optional[dict] = None) -> Optional[str]:
    """The truth of one capability (CAPS) or fit field (FIT_FIELDS) of this card; None when nothing says."""
    if fact in FIT_FIELDS:
        return _fit_truth(fact, card or {}, profile, row)
    got = facts_for_row(row or {}, card or {}, profile).get(fact)
    return got.get("truth") if got else None


def facts_for_row(row: dict, card: dict, profile: Optional[dict] = None) -> dict:
    """{cap: {value, truth, why}} for every capability something says (CAPS order); verified-only ones unprobed:
    {value: None, truth: None, probe: True, why: "needs a probe ..."}."""
    from halo_harness.models_library.truth_rules import RULES, needs_probe
    out: dict = {}
    for cap in CAPS:
        got = RULES[cap](row or {}, card or {}, profile if isinstance(profile, dict) else None)
        if got is None and cap in VERIFIED_ONLY:
            got = needs_probe(cap, row or {}, card or {})
        if got is not None:
            out[cap] = got
    return out


def fact(value, truth: Optional[str], why: str, **more) -> dict:
    return {"value": value, "truth": truth, "why": why, **more}


def chips(facts: dict) -> list:
    """The row's capability chips: {cap, title, value, truth, glyph, why} for each fact that holds or needs a probe."""
    out = []
    for cap, f in facts.items():
        if f.get("value") is False:
            continue
        out.append({"cap": cap, "title": TITLES.get(cap, cap), "value": f.get("value"), "truth": f.get("truth"),
                    "glyph": GLYPH.get(f.get("truth"), "?"), "why": f.get("why") or "", "probe": bool(f.get("probe"))})
    return out
