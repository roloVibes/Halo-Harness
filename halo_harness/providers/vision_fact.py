"""halo_harness.providers.vision_fact -- Halo 3.3.6.0 R6: can this model see images? One fact with one of the three
truths (models_library/truths.py), and the one source every home that says it reads: the card (`vision`,
`vision_truth`, `sources.vision`; providers/model_card.py), the search's truth (models_library/truth_rules.vision),
the placement rule for the `eyes` role (providers/placement.verdict), the measured card's modality
(providers/measured._modality) and the card chip (providers/model_card_words.chips).

    vision_of(card=None, row=None, profile=None) -> {value: True | False | None, truth, source}
    hf_config_vision(config) -> (True | False, why) | None      a Hugging Face config.json (None: it says nothing)
    word(f) -> "sees" | "no eyes" | "eyes?"                     the eye chip
    line(f) -> "reads images (verified: ...)" | "cannot see images (declared: ...)" | "eyes? ..."
    of_ref(ref, state_dir=None) -> the fact for a model ref (its card; no request)

The order, the first that says wins:
  1. the battery's image probe (profile `vision` yes / no; providers/battery_probes.vision_turn)   verified
  2. the server's own row: `/api/show` capabilities (vision listed; a list without it says no), a projector
     (`projector_info`, `projector_bytes`)                                                            declared
  3. a Hugging Face config (`vision_config`, an image processor, a vision architecture)            declared
  4. the cloud catalog's modalities (`modalities_in` / `input_modalities` has image)                declared
  5. what the card already carries from metadata (the library's chips, the hub's pipeline tag)      declared
  6. the family rule (llava, -vl, vision, moondream, minicpm-v, gemma3 past 1b, llama4, pixtral ...)  expected
  7. nothing: None (unknown; `halo models probe <ref>` settles it on a local model)
An expected fact is only ever a yes: a name that names no vision is not a no.
"""

from __future__ import annotations

import re
import time
from typing import Optional

VERIFIED, DECLARED, EXPECTED = "verified", "declared", "expected"
_FAMILY = re.compile(r"llava|bakllava|moondream|minicpm-v|(?:^|[-_/.:])vision|(?:-|\d)vl(?:$|[-_:.])|qwen\d?(?:\.\d)?-?vl|"
                     r"llama4|pixtral|mistral-small3\.[12]|granite[\d.]*-vision|internvl|cogvlm|smolvlm|paligemma|"
                     r"idefics|molmo|florence|gemma3(?!:(?:1b|270m))(?:n)?(?:$|[:-])", re.IGNORECASE)
_ARCH = re.compile(r"vl|vision|llava|pixtral|idefics|mllama|paligemma|internvl|minicpmv|molmo|florence|smolvlm|blip|"
                   r"imagetext|gemma3forconditional", re.IGNORECASE)
_IMAGE_KEYS = ("vision_config", "image_processor", "image_processor_type", "preprocessor_config", "vision_tower",
               "mm_vision_tower", "image_token_index", "image_token_id")


def fact(value, truth, source: str) -> dict:
    return {"value": value, "truth": truth if value is not None else None, "source": source}


def _date(p: dict) -> str:
    at = p.get("probed_at")
    return time.strftime("%Y-%m-%d", time.localtime(at)) if isinstance(at, (int, float)) else "never"


def hf_config_vision(config) -> "Optional[tuple]":
    """(True, why) when a config.json names an image part, (False, why) when it names a text-only architecture."""
    if not isinstance(config, dict) or not config:
        return None
    hit = next((k for k in _IMAGE_KEYS if config.get(k)), None)
    if hit:
        return True, f"the Hugging Face config ({hit})"
    archs = [str(a) for a in config.get("architectures") or [] if isinstance(a, str)]
    if any(_ARCH.search(a) for a in archs):
        return True, f"the Hugging Face config (architectures {', '.join(archs)[:60]})"
    if archs:
        return False, f"the Hugging Face config (architectures {', '.join(archs)[:60]}: text only)"
    return None


def _from_row(row: dict) -> Optional[dict]:
    for key in ("modalities_in", "input_modalities"):  # a cloud row (an Ollama row derives the same from its caps)
        mods = row.get(key)
        if isinstance(mods, list) and mods:
            sees = "image" in [str(m).lower() for m in mods]
            return fact(sees, DECLARED, "the catalog's modalities" + ("" if sees else ": text only"))
    caps = row.get("capabilities") if isinstance(row.get("capabilities"), list) and row.get("capabilities") else None
    if caps is not None and row.get("source") in (None, "ollama", "local"):
        low = [str(c).lower() for c in caps]
        src = "the library's chips" if row.get("source") == "ollama" else "/api/show capabilities"
        if "vision" in low:
            return fact(True, DECLARED, src)
    if row.get("projector_info") or int(row.get("projector_bytes") or 0) > 0:
        return fact(True, DECLARED, "a projector (mmproj) in its files" if row.get("projector_bytes") else
                    "/api/show projector_info")
    if caps is not None and row.get("source") in (None, "ollama", "local"):
        return fact(False, DECLARED, f"{src}: no vision")
    for key in ("config", "hf_config"):
        got = hf_config_vision(row.get(key))
        if got:
            return fact(got[0], DECLARED, got[1])
    return None


def _from_card(card: dict) -> Optional[dict]:
    from halo_harness.models_library.truths import source_truth
    src = str((card.get("sources") or {}).get("vision") or "")
    v = card.get("vision")
    truth = card.get("vision_truth") or source_truth(src)
    if v is True and truth in (VERIFIED, DECLARED):
        return fact(True, truth, src)
    if v is False and truth in (VERIFIED, DECLARED):
        return fact(False, truth, src)
    return None


def family_rule(name: str) -> Optional[dict]:
    m = _FAMILY.search(str(name or ""))
    return fact(True, EXPECTED, f"the family ({m.group(0).strip('-_/.:')}: a vision family, not probed)") if m else None


def vision_of(card: Optional[dict] = None, row: Optional[dict] = None, profile: Optional[dict] = None) -> dict:
    """See the module docstring."""
    card, row, p = card or {}, row or {}, profile if isinstance(profile, dict) else {}
    if p.get("vision") in ("yes", "no"):
        ok = p["vision"] == "yes"
        why = p.get("vision_why") or ("it named the colour" if ok else "it could not see the image")
        return fact(ok, VERIFIED, f"the battery's image probe, probed {_date(p)} ({why})")
    for got in (_from_row(row), _from_card(card)):
        if got is not None:
            return got
    name = card.get("name") or row.get("name") or row.get("model") or row.get("id") or ""
    if card.get("vision") is True and not str((card.get("sources") or {}).get("vision") or "").startswith("unknown"):
        return fact(True, EXPECTED, str((card.get("sources") or {}).get("vision") or "the name"))
    return family_rule(name) or fact(None, None, "nothing says whether it reads images")


def word(f: Optional[dict]) -> str:
    v = (f or {}).get("value")
    return "sees" if v is True else "no eyes" if v is False else "eyes?"


def line(f: Optional[dict], ref: str = "") -> str:
    f = f or {}
    v, truth, src = f.get("value"), f.get("truth"), f.get("source") or ""
    if v is True:
        return f"reads images ({truth}: {src})"
    if v is False:
        return f"cannot see images ({truth}: {src})"
    return f"eyes? nothing says whether it reads images ({'halo models probe ' + ref if ref else 'a probe'} settles it)"


def apply(card: dict, row: Optional[dict], profile: Optional[dict]) -> dict:
    """The card's `vision`, `vision_truth` and `sources.vision` set from the fact (model_card.card_of)."""
    f = vision_of(card, row, profile)
    card["vision"], card["vision_truth"] = f["value"], f["truth"]
    card["sources"] = {**(card.get("sources") or {}), "vision": f["source"]}
    return card


def of_ref(ref, state_dir=None) -> dict:
    """The fact for a model ref from its card (no request: the cached catalog and the capability cache)."""
    try:
        from halo_harness.providers.model_card import card_of
        card = card_of(ref, state_dir=state_dir)
        return {"value": card.get("vision"), "truth": card.get("vision_truth"),
                "source": (card.get("sources") or {}).get("vision") or ""}
    except Exception:
        return fact(None, None, "nothing says whether it reads images (no card)")
