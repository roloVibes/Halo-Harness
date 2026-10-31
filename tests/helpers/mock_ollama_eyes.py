"""tests.helpers.mock_ollama_eyes -- Halo 3.3.6.0 R6: models for the battery's vision probe
(halo_harness/providers/battery_probes.vision_turn) on the scripted fake Ollama of
tests/helpers/mock_ollama_battery.py. Every probe but the image one answers like the coder there; the image
turn (a message with `images`) answers per kind:

    ey-sees:7b     /api/show lists vision; answers "Red."                         -> verified yes
    ey-blind:7b    lists vision; answers "I'm sorry, I cannot see images."        -> verified no
    ey-refuse:7b   lists vision; the server answers HTTP 500 naming image input   -> verified no
    ey-odd:7b      lists vision; answers "Blue"                                   -> unverified
    ey-think:7b    lists vision + thinking; thinking only under 600 tokens, then "red" -> yes (re-asked)
    ey-text:7b     lists completion + tools, no vision                            -> not asked (declared no)
    ey-old:7b      /api/show has no capabilities list at all                       -> asked, "red" -> yes

`add(mock)` installs them beside the battery kinds; `images_sent(mock)` counts the image turns. Never a LAN
address, never a real server.
"""

from __future__ import annotations

from tests.helpers import mock_ollama_battery as MB
from tests.helpers.mock_ollama import send_json
from tests.helpers.steward_seed import QWEN9

EYES = {
    "ey-sees:7b": (["completion", "vision"], "Red."),
    "ey-blind:7b": (["completion", "vision"], "I'm sorry, I cannot see images; I am a text model."),
    "ey-refuse:7b": (["completion", "vision"], None),
    "ey-odd:7b": (["completion", "vision"], "Blue"),
    "ey-think:7b": (["completion", "vision", "thinking"], "red"),
    "ey-text:7b": (["completion", "tools"], "red"),
    "ey-old:7b": (None, "red"),
}


def _has_image(body: dict) -> bool:
    return any(isinstance(m, dict) and m.get("images") for m in (body or {}).get("messages") or [])


def scenario(name: str):
    caps, said = EYES[name]

    def fn(h, body):
        mock = h.server.mock
        cap = ((body.get("options") or {}).get("num_predict")) or 0
        if _has_image(body):
            with mock._lock:
                mock.eyes_calls = getattr(mock, "eyes_calls", []) + [(name, cap)]
            if said is None:
                send_json(h, 500, {"error": "this model is missing data required for image input"})
                return
            if name == "ey-think:7b" and cap < 600:
                msg = {"role": "assistant", "content": "", "thinking": "A single pixel. What colour is it? " * 3}
            else:
                msg = {"role": "assistant", "content": said}
        else:
            msg = {"role": "assistant", **MB._answer("bt-coder:30b", MB.probe_of(body), body)}
        send_json(h, 200, {"model": name, "message": msg, "done": True, "done_reason": "stop", "eval_count": 40,
                           "eval_duration": int(4e8), "prompt_eval_count": 30, "prompt_eval_duration": int(1e8),
                           "load_duration": int(1e6)})
    return fn


def row(name: str) -> dict:
    return {"name": name, "model": name, "modified_at": "2026-10-01T00:00:00Z", "size": 5_000_000_000,
            "digest": "sha256:" + name.replace(":", "-"),
            "details": {"family": "qwen35", "families": ["qwen35"], "parameter_size": "7B", "quantization_level": "Q4_K_M",
                        "format": "gguf"}}


def add(mock, names=None) -> None:
    names = list(names or EYES)
    rows = list((getattr(mock, "tags_response", None) or {}).get("models") or [])
    mock.tags_response = {"models": rows + [row(n) for n in names]}
    for n in names:
        caps = EYES[n][0]
        show = {"modelfile": "", "parameters": "", "template": "", "details": row(n)["details"],
                "model_info": {**QWEN9, "qwen35.context_length": 32768}}
        if caps is not None:
            show["capabilities"] = caps
        mock.show_responses[n] = show
        mock.scenarios[n] = scenario(n)


def images_sent(mock) -> list:
    return list(getattr(mock, "eyes_calls", []))
