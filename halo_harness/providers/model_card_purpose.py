"""halo_harness.providers.model_card_purpose -- Halo 3.3.5.0 R0b: the family
rules of docs/MODELS-families.md as code -- what a local model is FOR, whether
it thinks, its size and its quantization -- each answer with its source.

    purpose_of(name, caps=None, family="")  -> (purpose, source)
    thinks_of(name, caps=None, family="")   -> (thinks, source)
    params_of(name, details, model_info)    -> (billions | None, source)
    quant_of(name, details)                 -> (quant | "", source)

Purpose words, in the order they are tried on the model's name (the namespace
and the host stripped): `embed` / `bge` / `nomic` / `e5-` / `gte-` / `mxbai`
-> embedding; `-coder` / `coder` / `codestral` / `devstral` / `codellama` /
`starcoder` / `codegemma` -> coder; `r1` / `-think` / `thinking` / `qwq` /
`gpt-oss` / `magistral` -> reasoning; `-vl` / `llava` / `vision` /
`moondream` / `minicpm-v` -> vision; `-instruct` / `-it` / `-chat` -> instruct.
No word in the name: Ollama's `/api/show` capabilities decide (embedding
alone -> embedding, vision without completion -> vision), then a chat model
with no purpose word is `instruct` -- a hybrid model that can think (Qwen3's
`thinking` capability) stays `instruct`, its thinking is the card's `thinks`;
`unknown` only when nothing at all is known. Pure: no I/O.
"""

from __future__ import annotations

import re
from types import SimpleNamespace
from typing import Optional

PURPOSES = ("coder", "instruct", "reasoning", "vision", "embedding", "unknown")
_SEP = r"(?:^|[-_:/.\s])"
_END = r"(?:$|[-_:/.\s])"
RULES = (
    ("embedding", re.compile(r"embed|" + _SEP + r"(?:bge|e5|gte|mxbai)" + _END + r"|nomic-embed|bge-")),
    ("coder", re.compile(r"coder|codestral|devstral|codellama|starcoder|codegemma|codeqwen")),
    ("reasoning", re.compile(_SEP + r"r1" + _END + r"|-think|thinking|qwq|gpt-oss|magistral|" + _SEP + r"o[134]" + _END)),
    ("vision", re.compile(r"(?:-|\d)vl" + _END + r"|llava|vision|moondream|minicpm-v")),
    ("instruct", re.compile(r"-instruct|-it" + _END + r"|-chat" + _END)),
)
RULE_WORDS = {"embedding": "embed / bge / nomic", "coder": "-coder", "reasoning": "r1 / -think / qwq / gpt-oss",
              "vision": "-vl / llava / vision", "instruct": "-instruct / -it"}
# families whose thinking is on until a call turns it off (Ollama's own template default)
THINK_DEFAULT_ON = ("qwen3", "qwen35", "qwen3moe", "qwen3next", "deepseek", "deepseek2", "gptoss", "gpt-oss", "qwq",
                    "magistral")


def bare(name: str) -> str:
    """The model id without its provider prefix, host suffix and namespace, lowercased."""
    raw = str(name or "")
    if ":" in raw.split("/", 1)[0] and raw.split(":", 1)[0] in ("ol", "hf", "local", "or", "dbx", "ant", "oai", "xp"):
        raw = raw.split(":", 1)[1]
    raw = raw.split("@", 1)[0]
    for prefix in ("local/", "mlx/"):
        if raw.startswith(prefix):
            raw = raw[len(prefix):]
    return raw.rsplit("/", 1)[-1].lower()


def _caps(caps) -> Optional[set]:
    if isinstance(caps, (list, tuple, set)) and caps:
        return {str(c).lower() for c in caps}
    return None


def name_rule(name: str) -> Optional[str]:
    low = bare(name)
    for purpose, rx in RULES:
        if rx.search(low):
            return purpose
    return None


def purpose_of(name: str, caps=None, family: str = "") -> "tuple[str, str]":
    by_name = name_rule(name)
    c = _caps(caps)
    if by_name == "embedding" or (c and "embedding" in c and "completion" not in c):
        return "embedding", (f"the name ({RULE_WORDS['embedding']})" if by_name == "embedding"
                             else "/api/show capabilities: embedding only")
    if by_name:
        return by_name, f"the name ({RULE_WORDS[by_name]})"
    if c and "vision" in c and "completion" not in c:
        return "vision", "/api/show capabilities: vision"
    if c and "thinking" in c:
        return "instruct", "a chat model that can think (no purpose word in its name)"
    if c or family:
        return "instruct", "a chat model (no purpose word in its name)"
    return "unknown", "nothing says (no capabilities, no family)"


def thinks_of(name: str, caps=None, family: str = "") -> "tuple[str, str]":
    """"yes" | "no" | "default-on"."""
    c = _caps(caps)
    fam = str(family or "").lower()
    low = bare(name)
    on_by_rule = name_rule(name) == "reasoning" or any(f in low for f in ("qwen3", "deepseek")) or fam in THINK_DEFAULT_ON
    if c is not None:
        if "thinking" not in c:
            return "no", "/api/show capabilities: no thinking"
        if on_by_rule:
            return "default-on", "/api/show capabilities: thinking; the family thinks unless told not to"
        return "yes", "/api/show capabilities: thinking"
    if name_rule(name) == "reasoning":
        return "default-on", f"the name ({RULE_WORDS['reasoning']}): the server does not say"
    return "no", "the name (no thinking word): the server does not say"


_SIZE = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*([bmk])\s*$", re.IGNORECASE)
_NAME_SIZE = re.compile(r"(?:^|[-_:/.])(?:\d+x)?(\d+(?:\.\d+)?)b(?:$|[-_:/.])", re.IGNORECASE)


def _billions(text) -> Optional[float]:
    m = _SIZE.match(str(text or ""))
    if not m:
        return None
    n, unit = float(m.group(1)), m.group(2).lower()
    return round(n if unit == "b" else n / 1000.0 if unit == "m" else n / 1e6, 3)


def params_of(name: str, details=None, model_info=None) -> "tuple[Optional[float], str]":
    d = details if isinstance(details, dict) else {}
    got = _billions(d.get("parameter_size"))
    if got:
        return got, "/api/show details.parameter_size"
    info = model_info if isinstance(model_info, dict) else {}
    count = info.get("general.parameter_count")
    if isinstance(count, (int, float)) and not isinstance(count, bool) and count > 0:
        return round(count / 1e9, 3), "/api/show model_info general.parameter_count"
    m = _NAME_SIZE.search(bare(name))
    if m:
        return float(m.group(1)), "the name"
    return None, "unknown"


_QUANT = re.compile(r"(?:^|[-_:/.])(q\d(?:_k)?(?:_[msl0-9])?|iq\d_[a-z]+|f16|fp16|bf16|fp8|mxfp4|[48]bit)(?:$|[-_:/.])",
                    re.IGNORECASE)


def quant_of(name: str, details=None) -> "tuple[str, str]":
    d = details if isinstance(details, dict) else {}
    q = d.get("quantization_level")
    if isinstance(q, str) and q.strip():
        return q.strip(), "/api/show details.quantization_level"
    m = _QUANT.search(bare(name))
    if m:
        return m.group(1).upper() if m.group(1).lower().startswith(("q", "iq")) else m.group(1), "the name"
    return "", "unknown"


def family_of(name: str, details=None) -> "tuple[str, str]":
    d = details if isinstance(details, dict) else {}
    if isinstance(d.get("family"), str) and d["family"]:
        return d["family"], "/api/show details.family"
    try:
        from halo_harness.providers.profiles import model_family
        fam = model_family(bare(name))
    except Exception:
        fam = ""
    return (fam, "the name") if fam and fam != "generic" else ("", "unknown")


def parse_ref(ref) -> SimpleNamespace:
    """A ref string (or a ModelRef) as {provider, model, host, local, mlx, raw}; no lookup."""
    if not isinstance(ref, str):
        return ref
    raw = ref.strip()
    head, _, rest = raw.partition(":")
    model, _, host = rest.partition("@")
    provider, local, mlx = {"ol": ("ollama", False, False), "local": ("local", True, False)}.get(head, ("", False, False))
    if head == "hf" and rest.startswith(("local/", "mlx/")):
        provider, local, mlx = "huggingface", True, rest.startswith("mlx/")
        model = model.split("/", 1)[1]
    if not provider:
        provider, model, host = head or "cloud", rest or raw, ""
    return SimpleNamespace(provider=provider, model=model, host=host or None, local=local, mlx=mlx, raw=raw,
                           dialect="ollama" if provider == "ollama" else "")
