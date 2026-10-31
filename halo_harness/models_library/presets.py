"""halo_harness.models_library.presets -- Halo 3.3.6.0 R2: presets first, checkboxes second (plans/local-model-
fit-brief.md F3) and the inverse flow, "find a model for this role" (F4).

    PRESETS                       Coder, Reasoner / planner, Bulk worker, Compactor, Verifier, Security / pentest,
                                  Multimodal, Embeddings, Offline-only: each a filter bundle {needs, fit, supply,
                                  role, intent} the page shows expanded and editable
    bundle(preset, **overrides) -> the bundle (a copy) with its title and why
    preset_for_role(role) -> preset id     a lineup role ("verify", "coder", "planner", ...) -> its preset
    parse_sentence(text) -> {preset, needs, fit, supply, understood [words]}
                                  "a local coder that can use tools" -> Coder + tools verified-or-declared
    for_role(role_or_sentence, *, state_dir, host="", window=None) -> {preset, bundle, rows, ...}  ranked rows
    save_template(preset, *, state_dir, model="", lineup="", bundle=None) -> (ok, lines, name)
                                  Save as role template: a `local-<preset>` lineup (main + the preset's role,
                                  its `search` block = the bundle), or the role entry in the lineup named

The role a preset fills is a placement role (providers/placement.py), so a row's role-ready verdict is the
battery's; an embedding model fills no lineup role (its template keeps the filters only).
"""

from __future__ import annotations

import copy
import re
from typing import Optional

TOOLS = {"tools": "declared"}
PRESETS = {
    "coder": {"title": "Coder", "role": "coder", "agent": "auto-coder", "intent": "code",
              "needs": {"coder": "expected", **TOOLS}, "fit": {"fits_at": True}, "supply": {"runs_here": True},
              "why": "code-specialised, calls tools, fits this card at the window"},
    "reasoner": {"title": "Reasoner / planner", "role": "orchestrator", "agent": "auto-planner", "intent": "chat",
                 "needs": {"planner": "expected", **TOOLS}, "fit": {"fits_at": True}, "supply": {"runs_here": True},
                 "why": "a long window, instruction and JSON: plans, delegates, reviews"},
    "bulk": {"title": "Bulk worker", "role": "bulk", "agent": "local-small", "intent": "",
             "needs": {"bulk": "expected"}, "fit": {"fully_on_gpu": True, "params_max": 14}, "supply": {"runs_here": True},
             "why": "fast single-shot steps: small, fully on the GPU"},
    "compactor": {"title": "Compactor", "role": "compaction", "agent": "auto-writer", "intent": "long",
                  "needs": {"compactor": "expected"}, "fit": {"fits_at": True}, "supply": {"runs_here": True},
                  "why": "long input, short output: a 65k window or more"},
    "verifier": {"title": "Verifier", "role": "reviewer", "agent": "verifier", "intent": "chat",
                 "needs": {"verifier": "any", **TOOLS}, "fit": {"fits_at": True}, "supply": {"runs_here": True},
                 "why": "reasons and keeps reference ids right: only a probe says so (download and verify)"},
    "security": {"title": "Security / pentest", "role": "researcher", "agent": "auto-researcher", "intent": "chat",
                 "needs": {"security": "expected", **TOOLS}, "fit": {"fits_at": True}, "supply": {"runs_here": True},
                 "why": "security-flavoured (a weak signal: tags and names) and calls tools"},
    "multimodal": {"title": "Multimodal", "role": "eyes", "agent": "auto-media", "intent": "images",
                   "needs": {"vision": "declared"}, "fit": {"fits_at": True}, "supply": {"runs_here": True},
                   "why": "reads images: a projector or a declared vision capability"},
    "embeddings": {"title": "Embeddings", "role": "", "agent": "", "intent": "embed",
                   "needs": {"embedding": "declared"}, "fit": {"fits_at": True}, "supply": {"runs_here": True},
                   "why": "vectors for search and recall (no lineup role: the template keeps the filters)"},
    "offline": {"title": "Offline-only", "role": "main", "agent": "default-model", "intent": "",
                "needs": {**TOOLS}, "fit": {"fits_at": True},
                "supply": {"runs_here": True, "ollama_supports": True, "gated": False},
                "why": "runs here with no network: fits, loads on this Ollama, not gated"},
}
ORDER = tuple(PRESETS)
ROLE_PRESET = {"coder": "coder", "implement": "coder", "implementer": "coder", "tester": "coder", "worker": "coder",
               "reviewer": "verifier", "verify": "verifier", "verifier": "verifier", "judge": "verifier",
               "planner": "reasoner", "orchestrator": "reasoner", "lead": "reasoner", "main": "reasoner",
               "researcher": "reasoner", "small": "bulk", "bulk": "bulk", "writer": "bulk", "compaction": "compactor",
               "compactor": "compactor", "summarize": "compactor", "eyes": "multimodal", "vision": "multimodal",
               "media": "multimodal", "security": "security", "pentest": "security", "embed": "embeddings",
               "embeddings": "embeddings", "embedding": "embeddings", "offline": "offline"}
WORDS = (("coder", r"\bcod(?:e|er|ing)\b|programm"), ("reasoner", r"\breason|\bplan(?:ner|ning)?\b|orchestrat"),
         ("verifier", r"\bverif|\bjudge|\breview"), ("compactor", r"\bcompact|\bsummar"),
         ("bulk", r"\bbulk\b|\bbatch\b|\bcheap\b|\bfast\b"), ("security", r"\bsecurity\b|\bpentest|\bhack|\bcve\b"),
         ("multimodal", r"\bimages?\b|\bvision\b|\bmultimodal\b|\bscreenshots?\b|\bsee\b"),
         ("embeddings", r"\bembed|\bvectors?\b"), ("offline", r"\boffline\b|air.?gapped|no internet"))
EXTRAS = (("tools", r"\btools?\b|tool.?call|function.?call", "declared"), ("thinking", r"\bthink|\breasons\b", "expected"),
          ("vision", r"\bsee images\b|\bvision\b", "declared"), ("long-context", r"long (?:context|documents?)", "expected"),
          ("abliterated", r"\buncensored\b|\babliterated\b", "expected"), ("math", r"\bmath", "expected"),
          ("multilingual", r"multilingual|many languages", "declared"))


def bundle(preset: str, **over) -> dict:
    """The preset's filter bundle (a copy, `id` and its words included); `over` replaces needs / fit / supply keys."""
    b = copy.deepcopy(PRESETS.get(preset) or {"title": "Any", "role": "", "agent": "", "intent": "", "needs": {},
                                              "fit": {}, "supply": {}, "why": "no preset"})
    b["id"] = preset if preset in PRESETS else ""
    from halo_harness.models_library.presets_save import LINEUP_ROLE
    b["lineup_role"] = LINEUP_ROLE.get(preset, "")  # the role Save as role template and the offer fill
    for k in ("needs", "fit", "supply"):
        b[k].update({kk: vv for kk, vv in (over.get(k) or {}).items() if vv is not None})
    return b


def all_bundles() -> list:
    return [bundle(p) for p in ORDER]


def preset_for_role(role: str) -> str:
    r = str(role or "").strip().lower()
    return ROLE_PRESET.get(r) or ROLE_PRESET.get(r.split("-")[-1], "") or ("coder" if "cod" in r else "")


def parse_sentence(text: str) -> dict:
    t = str(text or "").lower()
    preset = next((p for p, rx in WORDS if re.search(rx, t)), "")
    needs, fit, supply, understood = {}, {}, {}, [PRESETS[preset]["title"]] if preset else []
    for cap, rx, floor in EXTRAS:
        if re.search(rx, t) and not (cap == "thinking" and preset == "reasoner"):
            needs[cap] = floor
            understood.append(f"{cap} {floor if floor != 'declared' else 'verified or declared'}")
    if re.search(r"\bfits?\b|my card|my gpu", t):
        fit["fits_at"] = True
        understood.append("fits this host")
    if m := re.search(r"(?:under|at most|below|<=?)\s*(\d+(?:\.\d+)?)\s*gb", t):
        fit["disk_max_gb"] = float(m.group(1))
        understood.append(f"at most {m.group(1)} GB")
    if m := re.search(r"(\d+(?:\.\d+)?)\s*b\b(?: or (?:smaller|less))?", t):
        fit["params_max"] = float(m.group(1))
        understood.append(f"at most {m.group(1)}B")
    if re.search(r"apache|\bmit\b|permissive|open licen", t):
        supply["licence"] = "permissive"
        understood.append("a permissive licence")
    return {"preset": preset, "needs": needs, "fit": fit, "supply": supply, "understood": understood}


def resolve(spec: dict) -> dict:
    """A query's search spec -> {bundle, role, understood}: a preset, a lineup role or a sentence, then the
    explicit needs / fit / supply on top (`replace`: instead of it, the page's edited bundle)."""
    spec = dict(spec or {})
    understood: list = []
    preset = str(spec.get("preset") or "")
    extra = {"needs": {}, "fit": {}, "supply": {}}
    if spec.get("for_role") and not preset:
        preset = preset_for_role(spec["for_role"])
        understood.append(f"the role {spec['for_role']} -> {PRESETS[preset]['title'] if preset else 'no preset'}")
    if spec.get("sentence") and not preset:
        got = parse_sentence(spec["sentence"])
        preset, understood = got["preset"], understood + got["understood"]
        for k in extra:
            extra[k].update(got[k])
    b = bundle(preset, **extra)
    for k in ("needs", "fit", "supply"):  # `replace`: the page's edited bundle is the whole of it
        b[k] = dict(spec.get(k) or {}) if spec.get("replace") else {**b[k], **(spec.get(k) or {})}
    return {"bundle": b, "role": spec.get("role") or b.get("role") or "", "understood": understood}


def for_role(role_or_sentence: str, *, state_dir, host: str = "", window: Optional[int] = None, source: str = "all") -> dict:
    """The inverse flow: a lineup role or a plain sentence -> the ranked rows (browse.library with the bundle)."""
    from halo_harness.models_library.browse import library
    key = "for_role" if preset_for_role(role_or_sentence) and " " not in role_or_sentence.strip() else "sentence"
    return library(state_dir, source=source, host=host, window=window, search={key: role_or_sentence}, per=2000)


def save_template(preset: str, *, state_dir=None, cwd=None, model: str = "", lineup: str = "",
                  bundle_over: Optional[dict] = None) -> "tuple[bool, list, str]":
    from halo_harness.models_library.presets_save import save
    return save(preset, state_dir=state_dir, cwd=cwd, model=model, lineup=lineup, bundle_over=bundle_over)
