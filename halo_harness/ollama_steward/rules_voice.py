"""halo_harness.ollama_steward.rules_voice -- the steward watches a speech server like a llama-server (Halo 3.3.9.0 R1;
docs/MODELS-steward-servers.md "Speech servers"; knowledge/local-servers.md "## Speech servers"). The events are the
speech server's own log lines (server_log_voice.py); one finding per rule and group, keyed `stt|<model>` /
`tts|<model>`, each with `server`, `runtime` (voice-stt | voice-tts) and a stated fix line -- never applied by itself.

    stt-slow           the newest transcriptions run under SLOW_RTF x realtime (median): the CPU -> `--device cuda`
                       when the GPU has the model's footprint free, else a smaller built model
    tts-slow           the newest replies' first audio comes later than FIRST_MS (median): the same two ways out
    voice-cpu          the newest load put the model on the CPU while the GPU had its footprint free (the launcher's
                       read, on the load line): `--device cuda` frees the CPU, at that many GB of VRAM (info)
    voice-load-failed  the load failed: the error line, and the install line when the extra was the cause

    voice_rules(ctx) -> [finding]
"""

from __future__ import annotations

from statistics import median
from typing import Optional

from halo_harness.ollama_steward.rules import finding, hint

SLOW_RTF = 2.0
FIRST_MS = 400
RECENT = 8
MIB = 2 ** 20


def _voice(g: dict) -> Optional[str]:
    rt = str(g.get("runtime") or "")
    return rt[len("voice-"):] if rt in ("voice-stt", "voice-tts") else None


def _tag(f: dict, g: dict) -> dict:
    f.update(server=g.get("server") or g["host"], runtime=g["runtime"], not_asked=[], applied=False)
    return f


def _last_load(g: dict) -> dict:
    rows = [e.get("data") or {} for e in g["events"] if e.get("kind") == "load-result"]
    return rows[-1] if rows else {}


def _need_mib(model: str) -> Optional[int]:
    from halo_harness.voice.catalog import get
    row = get(model)
    return int(round(row.gpu_gb * 1e9 / MIB)) if row and row.gpu_gb else None


def _smaller(model: str) -> Optional[str]:
    from halo_harness.voice.catalog import get, of_kind
    row = get(model)
    if row is None:
        return None
    down = [r for r in of_kind(row.kind) if r.built and r.cpu_gb < row.cpu_gb]
    return max(down, key=lambda r: r.cpu_gb).name if down else None


def _cuda_room(g: dict) -> bool:
    ld, need = _last_load(g), _need_mib(g["model"])
    return ld.get("device") == "cpu" and isinstance(ld.get("gpu_free_mib"), int) and bool(need) \
        and ld["gpu_free_mib"] >= need


def _fix(g: dict, kind: str) -> "tuple[str, str]":
    """(the stated line, its cost)."""
    from halo_harness.voice.catalog import get
    model = g["model"]
    if _cuda_room(g):
        row = get(model)
        return (f"halo local stop {kind} && halo local serve --{kind} {model} --device cuda",
                f"{row.gpu_gb:g} GB of VRAM beside the chat model, a restart of the speech server (seconds)")
    small = _smaller(model)
    if small:
        return (f"halo local stop {kind} && halo local serve --{kind} {small}",
                f"a smaller model (less accurate), a restart of the speech server (seconds)")
    return ("", "")


def slow(g: dict, kind: str) -> list:
    rows = [e.get("data") or {} for e in g["events"] if e.get("kind") == "timing"
            and (e.get("data") or {}).get("voice") == kind][-RECENT:]
    if not rows:
        return []
    if kind == "stt":
        got = median(float(r["rtf"]) for r in rows if isinstance(r.get("rtf"), (int, float)))
        if got >= SLOW_RTF:
            return []
        text = (f"{g['model']} on {g.get('server') or g['host']} transcribes at {got:.1f}x realtime (the newest "
                f"{len(rows)}): under {SLOW_RTF:g}x a reply waits on the transcript")
        nums = {"rtf": round(got, 2), "requests": len(rows), "device": rows[-1].get("device")}
    else:
        got = median(int(r["first_ms"]) for r in rows if isinstance(r.get("first_ms"), int))
        if got <= FIRST_MS:
            return []
        text = (f"{g['model']} on {g.get('server') or g['host']} starts speaking after {got:.0f} ms (the newest "
                f"{len(rows)}): over {FIRST_MS} ms the reply feels late")
        nums = {"first_ms": int(got), "requests": len(rows), "device": rows[-1].get("device")}
    line, cost = _fix(g, kind)
    if line:
        text += f"; {line.split(' && ')[-1]}"
    return [_tag(finding(f"{kind}-slow", g, "warn", text, numbers=nums,
                         server_hint=hint(None, line, cost) if line else None), g)]


def on_cpu(g: dict, kind: str) -> list:
    if not _cuda_room(g):
        return []
    ld = _last_load(g)
    line, cost = _fix(g, kind)
    text = (f"{g['model']} runs on the CPU while the GPU has {ld['gpu_free_mib']:,} MiB free (it needs "
            f"{_need_mib(g['model']):,} MiB there): --device cuda moves it, said, never done by itself")
    return [_tag(finding("voice-cpu", g, "info", text, numbers={"gpu_free_mib": ld["gpu_free_mib"],
                                                              "need_mib": _need_mib(g["model"])},
                         server_hint=hint(None, line, cost)), g)]


def load_failed(g: dict, kind: str) -> list:
    bad = [e for e in g["events"] if e.get("kind") == "load-failed"]
    if not bad:
        return []
    d = bad[-1].get("data") or {}
    from halo_harness.voice import INSTALL_LINE
    if d.get("extra"):
        line, cost = INSTALL_LINE, "the engines' packages in Halo's tool environment (a few hundred MB)"
    elif d.get("device") == "cuda":
        line, cost = f"halo local serve --{kind} {g['model']} --device cpu", "the CPU's time instead of the GPU's"
    else:
        line, cost = f"halo voice download {g['model']}", "the model's files again"
    text = (f"{g['model']} did not load on {g.get('server') or g['host']} ({d.get('device') or '?'}): "
            f"{str(d.get('error') or '')[:160]}")
    return [_tag(finding("voice-load-failed", g, "error", text, events=bad, numbers={"failures": len(bad)},
                         server_hint=hint(None, line, cost)), g)]


def voice_rules(ctx: dict) -> list:
    out: list = []
    for g in ctx.get("groups") or []:
        kind = _voice(g)
        if kind:
            out += load_failed(g, kind) + slow(g, kind) + on_cpu(g, kind)
    return out
