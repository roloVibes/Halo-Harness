"""tests.helpers.mock_ollama_battery -- Halo 3.3.6.0 R1: scripted answers to
the battery's probes (halo_harness/providers/battery_probes.py) per model
kind, for tests/helpers/mock_ollama.MockUpstream (non-streamed `/api/chat`,
one JSON answer each). The kinds mirror the owner's measured run
(plans/local-model-fit-brief.md E7):

    bt-coder:30b     passes everything: a tool call, BANANA in the system and the user turn, plain JSON, 284
    bt-mute:24b      answers EMPTY with a tool schema attached (no tool call), ignores the system role,
                     fenced JSON, CWE-20, very fast
    bt-thinker:27b   answers in `thinking`: with a small num_predict `content` is empty, with 600 it answers;
                     prose instead of JSON, 284
    bt-fence:14b     JSON in a ``` fence, the rest like the coder
    bt-wrongid:8b    ignores the system role, answers CWE-601

`install(mock)` puts the scenarios, the `/api/tags` rows and the `/api/show`
answers on a MockUpstream; `ps_full(mock, name)` / `ps_spill(...)` script
`/api/ps` after the run. Never a literal LAN address (tests/test_privacy_scan.py).
"""

from __future__ import annotations

import json

from tests.helpers.mock_ollama import send_json
from tests.helpers.steward_seed import CODER30, QWEN27, QWEN9

GOOD_JSON = json.dumps({"severity": "high", "cwe": "CWE-284", "why": "no object-level authorization check",
                        "fix": "check the tenant on every object read"})
MISTRAL = {"llama.block_count": 40, "llama.attention.head_count_kv": 8, "llama.attention.key_length": 128,
           "llama.attention.value_length": 128, "llama.embedding_length": 5120, "llama.context_length": 131072}
KINDS = {
    "bt-coder:30b": {"size": 18554258719, "info": {**CODER30, "qwen3moe.context_length": 262144}, "family": "qwen3moe",
                     "caps": ["completion", "tools"], "tok": (300, 1.6e9)},
    "bt-mute:24b": {"size": 14300000000, "info": MISTRAL, "family": "llama", "caps": ["completion", "tools"],
                    "tok": (300, 1.0e9)},
    "bt-thinker:27b": {"size": 16804059546, "info": {**QWEN27, "qwen35.context_length": 262144}, "family": "qwen35",
                       "caps": ["completion", "tools", "thinking"], "tok": (96, 1.0e9)},
    "bt-fence:14b": {"size": 9000000000, "info": {**QWEN9, "qwen35.context_length": 32768}, "family": "qwen35",
                     "caps": ["completion", "tools"], "tok": (120, 1.0e9)},
    "bt-wrongid:8b": {"size": 5200000000, "info": {**QWEN9, "qwen35.context_length": 131072}, "family": "qwen35",
                      "caps": ["completion", "tools", "thinking"], "tok": (50, 1.0e9)},
}


def probe_of(body: dict) -> str:
    msgs = (body or {}).get("messages") or []
    text = " ".join(str(m.get("content") or "") for m in msgs if isinstance(m, dict))
    if body.get("tools"):
        return "tools"
    if any(m.get("role") == "system" and "BANANA" in str(m.get("content")) for m in msgs if isinstance(m, dict)):
        return "system"
    if "Reply with exactly one word" in text:
        return "instruction"
    if "triaging pentest findings" in text:
        return "json"
    if "CWE identifier" in text:
        return "reference"
    if "Reply with the word ready" in text:
        return "warmup"
    return "other"


def _answer(name: str, probe: str, body: dict) -> dict:
    """{content, thinking?, tool_calls?} for one probe of one kind."""
    cap = ((body.get("options") or {}).get("num_predict")) or 0
    coder = {"warmup": "ready", "tools": "", "system": "BANANA", "instruction": "BANANA", "json": GOOD_JSON,
             "reference": "284", "other": "ok"}
    if name == "bt-coder:30b":
        out = {"content": coder[probe]}
    elif name == "bt-mute:24b":
        out = {"content": {"tools": "", "system": "4", "instruction": "BANANA\n\n2+2 = 4",
                           "json": "```json\n" + GOOD_JSON + "\n```", "reference": "CWE-20"}.get(probe, "ok")}
    elif name == "bt-thinker:27b":
        if probe in ("warmup", "other"):
            return {"content": "ready", "thinking": "a short thought"}
        if cap < 600:
            return {"content": "", "thinking": "Let me think about this carefully. " * 4}
        out = {"content": {"tools": "", "system": "BANANA", "instruction": "BANANA. 2+2 is 4.",
                           "json": "The finding is an IDOR: severity high, CWE-284; add an object check.",
                           "reference": "284"}[probe], "thinking": "reasoned it through"}
    elif name == "bt-fence:14b":
        out = {"content": "```json\n" + GOOD_JSON + "\n```" if probe == "json" else coder[probe]}
    else:  # bt-wrongid:8b
        out = {"content": {"system": "2+2 = 4", "instruction": "BANANA 4", "reference": "601"}.get(probe, coder[probe]),
               "thinking": "hmm"}
    if probe == "tools" and name != "bt-mute:24b":
        out["tool_calls"] = [{"function": {"name": "get_weather", "arguments": {"city": "Paris"}}}]
    return out


def scenario(name: str):
    def fn(h, body):
        mock = h.server.mock
        probe = probe_of(body)
        with mock._lock:
            mock.battery_calls = getattr(mock, "battery_calls", []) + [(name, probe)]
            first = not getattr(mock, "battery_loaded", {}).get(name)
            mock.battery_loaded = {**getattr(mock, "battery_loaded", {}), name: True}
        if first:  # loaded now: /api/ps lists it, on the GPU or spilled (`mock.battery_fit`)
            window = int(((body.get("options") or {}).get("num_ctx")) or 32768)
            (ps_spill if getattr(mock, "battery_fit", {}).get(name) == "spill" else ps_full)(mock, name, window)
        ev, dur = KINDS[name]["tok"]
        if probe == "warmup":  # the first call after a load: graph capture, slow (never timed)
            ev, dur = 8, 1.4e9
        msg = {"role": "assistant", **_answer(name, probe, body)}
        send_json(h, 200, {"model": name, "created_at": "2026-10-30T00:00:00Z", "message": msg, "done": True,
                           "done_reason": "stop", "total_duration": int(dur + 2e8),
                           "load_duration": int(6.5e9 if first else 1e6), "prompt_eval_count": 40,
                           "prompt_eval_duration": int(1.2e8), "eval_count": ev, "eval_duration": int(dur)})
    return fn


def row(name: str) -> dict:
    k = KINDS[name]
    return {"name": name, "model": name, "modified_at": "2026-10-01T00:00:00Z", "size": k["size"],
            "digest": "sha256:" + name.replace(":", "-"),
            "details": {"family": k["family"], "families": [k["family"]], "parameter_size": name.split(":")[1].upper(),
                        "quantization_level": "Q4_K_M", "format": "gguf"}}


def install(mock, names=None, *, version: str = "0.40.13") -> None:
    names = list(names or KINDS)
    mock.version_response = {"version": version}
    mock.tags_response = {"models": [row(n) for n in names]}
    for n in names:
        mock.show_responses[n] = {"modelfile": "", "parameters": "", "template": "", "capabilities": KINDS[n]["caps"],
                                  "details": row(n)["details"], "model_info": KINDS[n]["info"]}
        mock.scenarios[n] = scenario(n)


def _put(mock, name: str, size: int, vram: int, window: int) -> None:
    rest = [e for e in (mock.ps_response or {}).get("models") or [] if e.get("model") != name]
    mock.ps_response = {"models": rest + [{"model": name, "name": name, "size": size, "size_vram": vram,
                                           "context_length": window, "expires_at": "2026-10-30T01:00:00Z"}]}


def ps_full(mock, name: str, window: int = 32768) -> None:
    size = KINDS[name]["size"] + 2 * 2 ** 30 if name in KINDS else 20 * 2 ** 30
    _put(mock, name, size, size, window)


def ps_spill(mock, name: str, window: int = 32768, share: float = 0.8) -> None:
    size = KINDS[name]["size"] + 2 * 2 ** 30 if name in KINDS else 20 * 2 ** 30
    _put(mock, name, size, int(size * share), window)


def chats(mock) -> list:
    return [b for m, p, b in ((r.get("method"), r.get("path"), r.get("body")) for r in mock.requests)
            if p == "/api/chat"]
