"""halo_harness.models_library.truth_rules -- Halo 3.3.6.0 R2: one rule per capability of the F2 list
(models_library/truths.py says what the three truths mean).

    RULES[cap](row, card, profile) -> {value, truth, why} | None (nothing says)
    needs_probe(cap, row, card) -> the fact of a verified-only capability before a probe

Where each one is read: the battery's profile first (verified), then what the metadata says -- the card's `sources`
(`/api/show`, the library's chips, the hub's pipeline tag), the hub's tags, a projector in the files (declared) --
then the family, size and name rules (expected). The hub's tags are a weak signal for security / pentest: the why
says so.
"""

from __future__ import annotations

import re
from typing import Optional

from halo_harness.models_library.truths import DECLARED as D, EXPECTED as E, TITLES, VERIFIED as V, fact, source_truth

BULK_PARAMS = 9.0
PLANNER_PARAMS = 14.0
LONG = 65536
TOOL_NAMES = ("llama3.1", "llama3.2", "llama3.3", "llama4", "qwen2.5", "qwen3", "mistral-nemo", "mistral-small",
              "mistral-large", "gpt-oss", "devstral", "command-r", "granite3", "granite4", "hermes", "firefunction",
              "glm4", "glm-4", "kimi", "deepseek-v3")
_TOOL_TAGS = ("function-calling", "tool-use", "tools", "function calling", "tool-calling")
_SEC_NAME = re.compile(r"(?:^|[-_/.:])(?:sec|security|pentest|hack|hacker|cyber|redteam|red-team)(?:$|[-_/.:\d])")
_LANG = re.compile(r"^[a-z]{2}$")


def _tags(row: dict) -> list:
    return [str(t).lower() for t in (row.get("tags") or [])]


def _name(row: dict, card: dict) -> str:
    return str(row.get("name") or row.get("id") or card.get("name") or "").lower()


def _date(p: dict) -> str:
    from halo_harness.providers.battery_profile import date_of
    return date_of(p)


def _tag_hit(row: dict, words) -> Optional[str]:
    return next((t for t in _tags(row) if t in words), None)


def tools(row, card, p):
    if p and p.get("tools") in ("yes", "no"):
        ok = p["tools"] == "yes"
        return fact(ok, V, f"the battery {'made a tool call' if ok else 'got no tool call'} (probed {_date(p)})")
    t, src = card.get("tools"), (card.get("sources") or {}).get("tools")
    if t == "probed":
        return fact(True, V, src or "the tool-call probe made a call")
    if t in ("declared", "none") and source_truth(src):
        return fact(t == "declared", source_truth(src), src)
    if hit := _tag_hit(row, _TOOL_TAGS):
        return fact(True, D, f"the hub's tags: {hit}")
    name = _name(row, card)
    if any(n in name for n in TOOL_NAMES):
        return fact(True, E, "a family that calls tools (a family rule, not probed)")
    return None


def thinking(row, card, p):
    if p and p.get("reasoning") in ("thinking", "none"):
        ok = p["reasoning"] == "thinking"
        return fact(ok, V, f"the battery: {'it answers in thinking' if ok else 'no thinking in its answers'} (probed {_date(p)})")
    t, src = card.get("thinks"), str((card.get("sources") or {}).get("thinks") or "")
    if t in ("yes", "default-on") and src.startswith("the name"):
        return fact(True, E, src.split(":")[0])
    if t in ("yes", "default-on", "no") and source_truth(src):
        return fact(t != "no", source_truth(src), src)
    if hit := _tag_hit(row, ("reasoning", "thinking", "chain-of-thought")):
        return fact(True, D, f"the hub's tags: {hit}")
    return None


def coder(row, card, p):
    if hit := _tag_hit(row, ("code", "coding", "code-generation", "coder")):
        return fact(True, D, f"the hub's tags: {hit} (a code probe is not in the battery)")
    if card.get("purpose") == "coder":
        src = str((card.get("sources") or {}).get("purpose") or "the name")
        return fact(True, source_truth(src) or E, f"{src} (a code probe is not in the battery)")
    return None


def agentic(row, card, p):
    if not p or p.get("tools") not in ("yes", "no"):
        return None
    ok = bool(p.get("agentic_ready"))
    miss = [w for w, bad in (("tool calls", p.get("tools") != "yes"), ("the system role", p.get("system_role") == "weak"),
                             ("strict instructions", p.get("instruction") != "strict"),
                             ("JSON", p.get("output") not in ("json", "fenced-json"))) if bad]
    return fact(ok, V, (f"tools + system role + instruction + JSON (probed {_date(p)})" if ok else
                        f"misses {', '.join(miss) or 'a gate'} (probed {_date(p)})"))


def _window(row, card) -> Optional[int]:
    for n in (row.get("context"), (card.get("window") or {}).get("tokens"), (card.get("window") or {}).get("ceiling")):
        if isinstance(n, int) and n > 0:
            return n
    return None


def planner(row, card, p):
    if p and p.get("tools") in ("yes", "no"):
        from halo_harness.providers.placement import verdict
        v = verdict(p, "orchestrator")
        ok = bool(v["ok"]) and p.get("instruction") == "strict" and p.get("output") in ("json", "fenced-json")
        return fact(ok, V, (f"long window, strict instructions and JSON (probed {_date(p)})" if ok else
                            (v["why"] or "it misses strict instructions or JSON") + f" (probed {_date(p)})"))
    if card.get("tools") == "none" and source_truth((card.get("sources") or {}).get("tools")):
        return fact(False, D, "no tool calls declared: a planner acts through its tools")
    params, w = row.get("params") or card.get("params"), _window(row, card)
    if card.get("purpose") == "reasoning":
        return fact(True, E, "a reasoning model (the name): planning and review (not probed)")
    if isinstance(params, (int, float)) and isinstance(w, int):
        ok = params >= PLANNER_PARAMS and w >= 32768
        return fact(ok, E, f"{params:g}B with a {w:,} window: {'big enough' if ok else 'small'} for planning (a size heuristic)")
    return None


def verifier(row, card, p):
    if not p or p.get("tools") not in ("yes", "no"):
        return None
    ok = p.get("identifiers") == "trusted" and p.get("output") in ("json", "fenced-json")
    return fact(ok, V, (f"trustworthy reference ids and a structured verdict (probed {_date(p)})" if ok else
                        f"{'it invents reference ids' if p.get('identifiers') != 'trusted' else 'no JSON verdict'} (probed {_date(p)})"))


def compactor(row, card, p):
    if p and (p.get("window") or {}).get("usable"):
        from halo_harness.providers.placement import verdict
        v = verdict(p, "compaction")
        return fact(bool(v["ok"]), V, (v["why"] or f"a {(p['window']['usable']) // 1024}k window here") + f" (probed {_date(p)})")
    w = _window(row, card)
    if card.get("embedding_only"):
        return fact(False, D, "an embedding model: it does not write text")
    if isinstance(w, int):
        return fact(w >= LONG, E, f"a {w:,} window claimed: {'long input fits' if w >= LONG else 'chunk its input'} "
                                   "(a compression probe is not in the battery)")
    return None


def _active(row, card) -> Optional[float]:
    from halo_harness.models_library.search_cost import active_params
    return active_params(row.get("name") or card.get("name") or "", row.get("params") or card.get("params"))


def bulk(row, card, p):
    from halo_harness.providers.battery_profile import BULK_TOK_S
    tok = ((p or {}).get("speed") or {}).get("tok_s")
    if isinstance(tok, (int, float)):
        return fact(tok >= BULK_TOK_S, V, f"{tok:g} tok/s measured here (bulk needs {BULK_TOK_S:g})")
    if card.get("embedding_only") or card.get("purpose") == "embedding":
        return fact(False, E, "an embedding model: it writes no text")
    a = _active(row, card)
    if isinstance(a, (int, float)):
        return fact(a <= BULK_PARAMS, E, f"{a:g}B active: {'fast' if a <= BULK_PARAMS else 'slow'} for bulk (params x arch, not measured)")
    return None


def abliterated(row, card, p):
    if hit := _tag_hit(row, ("abliterated", "uncensored")):
        return fact(True, D, f"the hub's tags: {hit}")
    if any(w in _name(row, card) for w in ("abliterated", "uncensored")):
        return fact(True, E, "the name says so (a refusal probe is not in the battery)")
    return None


def vision(row, card, p):
    from halo_harness.providers.vision_fact import vision_of  # 3.3.6.0 R6: the one source (the probe, then metadata)
    f = vision_of(card, row, p)
    return None if f["value"] is None else fact(f["value"], f["truth"], f["source"])


def audio(row, card, p):
    if "audio" in [str(c).lower() for c in row.get("capabilities") or []]:
        return fact(True, D, "the library's chips: audio")
    if hit := _tag_hit(row, ("automatic-speech-recognition", "text-to-speech", "audio", "speech", "audio-text-to-text")):
        return fact(True, D, f"the hub's tags: {hit}")
    if any(w in _name(row, card) for w in ("whisper", "voxtral", "-tts", "speech", "audio")):
        return fact(True, E, "the name (whisper / voxtral / tts / speech)")
    return None


def embedding(row, card, p):
    if hit := _tag_hit(row, ("sentence-similarity", "feature-extraction", "text-ranking", "reranker", "sentence-transformers")):
        return fact(True, D, f"the hub's tags: {hit}")
    if row.get("source") == "ollama" and "embedding" in [str(c).lower() for c in row.get("capabilities") or []]:
        return fact(True, D, "the library's chips: embedding")
    if card.get("purpose") == "embedding" or card.get("embedding_only"):
        src = str((card.get("sources") or {}).get("purpose") or "")
        return fact(True, source_truth(src) or E, src or "the name")
    if "rerank" in _name(row, card):
        return fact(True, E, "the name (rerank): a cross-encoder")
    return None


def security(row, card, p):
    if hit := _tag_hit(row, ("security", "cybersecurity", "pentest", "infosec", "red-team", "redteam")):
        return fact(True, D, f"the hub's tags: {hit} (a weak signal: anyone can tag a repo)")
    if _SEC_NAME.search(_name(row, card)):
        return fact(True, E, "the name (sec / pentest / cyber): a weak signal (a task probe is not in the battery)")
    return None


def math(row, card, p):
    if _tag_hit(row, ("math", "mathematics")):
        return fact(True, D, "the hub's tags: math")
    if "math" in _name(row, card):
        return fact(True, E, "the name (math)")
    return None


def multilingual(row, card, p):
    tags = _tags(row)
    langs = [t for t in tags if _LANG.match(t)]
    if "multilingual" in tags or len(langs) >= 5:
        return fact(True, D, "the hub's tags: " + ("multilingual" if "multilingual" in tags else f"{len(langs)} languages"))
    if "multilingual" in str(row.get("description") or "").lower():
        return fact(True, D, "the listing's description: multilingual")
    return None


def long_context(row, card, p):
    w = _window(row, card)
    if not isinstance(w, int):
        return None
    return fact(w >= LONG, E, f"claims {w:,} (claimed is not recalled: a needle probe is not in the battery)")


def needs_probe(cap: str, row: dict, card: dict) -> dict:
    why = {"tool-accuracy": "the battery's multi-tool probe has not run on it"}.get(cap, f"nothing reliable declares {TITLES[cap]}")
    after = "halo models probe <ref>" if row.get("installed") else "download and verify"
    return fact(None, None, f"needs a probe: {why} ({after})", probe=True)


RULES = {"tools": tools, "thinking": thinking, "coder": coder, "agentic-ready": agentic, "planner": planner,
         "verifier": verifier, "compactor": compactor, "bulk": bulk, "abliterated": abliterated, "vision": vision,
         "audio": audio, "embedding": embedding, "security": security, "math": math, "multilingual": multilingual,
         "long-context": long_context, "tool-accuracy": lambda row, card, p: None if not isinstance((p or {}).get(
             "tool_call_accuracy"), (int, float)) else fact(p["tool_call_accuracy"] >= 0.75, V, f"the multi-tool probe: "
             f"{p['tool_call_accuracy']:.0%} ({p.get('tool_call_why') or 'scored'}, probed {_date(p)})")}  # 3.3.6.0 R4
