"""halo_harness.ollama_steward.rules_voice_loop -- the steward's `voice-slow` (Halo 3.3.9.0 R2; docs/VOICE.md "The
latency card"; knowledge/local-servers.md "## Speech servers"): the voice loop's own cards in <state>/voice/turns.jsonl
(voice/latency.py), read the way rules_voice.py reads a speech server's log.

    voice-slow   one stage of the newest STREAK turns ran over its share of the budget each time (heard 20 %, text 25 %,
                 token 40 %, audio 15 % of latency_budget_ms): one finding per stage, keyed `voice|<stage>`, on the
                 Ollama host served here (the Steward page's row), with the stated fix -- never applied by itself:
                   heard  the end of speech waits on the VAD -> halo voice download silero-vad (a level gate stands in)
                   text   the transcript is slow (stt on the CPU) -> --device cuda, or faster-whisper:small.en
                   token  the chat model is loading -> a voice bundle's reservation keeps it resident (halo pack on ...)
                   audio  Kokoro on the CPU is ~100 ms to first audio -> check tts-slow

    voice_slow(ctx) -> [finding]
"""

from __future__ import annotations

from halo_harness.ollama_steward.rules import finding, hint

STREAK = 3


def _stt() -> "tuple[str, str]":
    from halo_harness.voice.launch import entry
    e = entry("stt") or {}
    return str(e.get("model") or "faster-whisper:small.en"), str(e.get("device") or "cpu")


def fix(stage: str) -> "tuple[str, str, str]":
    """(why, the stated line, its cost)."""
    if stage == "heard":
        return ("the end of speech waits on the VAD", "halo voice download silero-vad",
                "2 MB; the level gate that stands in without it waits on loud silence")
    if stage == "text":
        model, device = _stt()
        if device == "cpu":
            return (f"stt ({model}) runs on the CPU", f"halo local stop stt && halo local serve --stt {model} --device cuda",
                    "its GPU footprint beside the chat model (0.2 to 1.5 GB), a restart of the speech server (seconds); "
                    "or a smaller model: halo local serve --stt faster-whisper:small.en")
        return (f"stt ({model}) is slow on {device}", "halo local stop stt && halo local serve --stt faster-whisper:small.en",
                "some accuracy, a restart of the speech server (seconds)")
    if stage == "token":
        return ("the chat model is loading before it answers", "halo pack on voice-local",
                "its reservation keeps the chat model resident (about 1.2 GB of VRAM held)")
    return ("the first audio comes late (Kokoro on the CPU is ~100 ms)", "halo ollama steward findings",
            "nothing: see tts-slow for the speech server's own figure")


def _here(ctx: dict) -> str:
    """The Ollama host served on this machine (the voice loop's chat model's, the Steward page's row), else words."""
    try:
        from halo_harness.peers.ollama_share import served_here
        return next((h.name for h in ctx.get("hosts") or [] if served_here(h.url)), "this machine")
    except Exception:
        return "this machine"


def voice_slow(ctx: dict) -> list:
    state = ctx.get("state_dir")
    if state is None:
        return []
    from halo_harness.voice.latency import SHARE, STAGES, rows
    recent = rows(state, STREAK)
    if len(recent) < STREAK:
        return []
    out = []
    for stage in STAGES:
        b = [int(r.get("budget_ms") or 1500) for r in recent]
        got = [(r.get("stages") or {}).get(stage) for r in recent]
        if not all(isinstance(ms, int) and ms > SHARE[stage] * bb for ms, bb in zip(got, b)):
            continue
        share = int(SHARE[stage] * b[-1])
        why, line, cost = fix(stage)
        g = {"key": f"voice|{stage}", "host": _here(ctx), "model": "voice loop"}
        text = (f"the voice loop's {stage} stage ran over its {share:,} ms share of the {b[-1]:,} ms budget "
                f"{STREAK} turns running ({', '.join(f'{ms:,}' for ms in got)} ms): {why}; {line.split(' && ')[-1]}")
        out.append(finding("voice-slow", g, "warn", text, numbers={"stage": stage, "share_ms": share, "turns_ms": got,
                                                                     "budget_ms": b[-1]},
                           server_hint=hint(None, line, cost), stage=stage, not_asked=[], applied=False))
    return out
