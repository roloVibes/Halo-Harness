"""halo_harness.voice.ensure -- the speech servers the voice loop needs (Halo 3.3.9.0 R2; docs/VOICE.md "The servers"):

    picks(state_dir=None) -> {"stt": (model, device), "tts": (model, device), "bundle": id | None, "budget_ms": int|None,
        "reserved": the claim's model as a ref (ol:<model>@<host>) | None}
        a voice bundle that is on (a claim in <state>/ollama/claims.json whose bundle needs stt / tts: voice-local,
        meta-glasses) picks with the verdict's rule (local_sched/bundle_voice.pick: a present model of its any_of, on
        the device the need allows); else voice.stt_model / voice.tts_model on voice.device
    running(kind, state_dir=None) -> the base url of a live `stt` / `tts` server, or None
    cost_line(kind, model, device) -> "starting stt: faster-whisper:small.en on the CPU: 0.9 GB RAM ... -- ~5 s to load"
    ensure(state_dir=None, say=print) -> (urls {stt, tts} | None, started [kind], lines)
        a kind with no live server is started through R1's launch.serve (`halo local serve --stt | --tts`), the cost
        line said first; a failure stops what this call started and says the one line (not present: the download
        command; the extra: the install line)
    stop(started, state_dir=None) -> [line]  `/voice off` stops the servers the loop started, never one it found

A bundle never starts a process (a claim is a claim): the loop starts what it needs and stops what it started.
"""

from __future__ import annotations

from typing import Callable, Optional

LOAD_S_PER_GB = {"cpu": 4.0, "cuda": 2.0}
_DEVICE = {"cpu": "cpu", "gpu": "cuda", "cpu-or-gpu": "auto"}


def _state(state_dir):
    if state_dir is not None:
        return state_dir
    from halo_harness.config.paths import bridge_home
    return bridge_home()


def _setting(key: str, default):
    from halo_harness.theme import get_config_value
    v = get_config_value(key, default=None)
    return v if isinstance(v, str) and v.strip() else default


def on_bundle(state_dir=None) -> Optional[dict]:
    """The voice bundle that is on here (the newest claim of a bundle with speech needs), as packs.bundles.find."""
    try:
        from halo_harness.local_sched.claims_file import local_file, read
        from halo_harness.packs.bundles import find
        for row in reversed(read(local_file(_state(state_dir)))):
            e = find(str(row.get("bundle") or ""), state_dir=state_dir)
            needs = ((e or {}).get("block") or {}).get("needs") or {}
            if "stt" in needs or "tts" in needs:
                return {**e, "claim": row}
    except Exception:
        return None
    return None


def picks(state_dir=None) -> dict:
    out = {"stt": (_setting("voice.stt_model", "faster-whisper:small.en"), None),
           "tts": (_setting("voice.tts_model", "kokoro-82m"), None), "bundle": None, "budget_ms": None, "reserved": None}
    e = on_bundle(state_dir)
    if e is None:
        return out
    from halo_harness.local_sched.bundle_voice import pick
    block = e["block"]
    out["bundle"], out["budget_ms"] = e["id"], block.get("latency_budget_ms")
    c = e.get("claim") or {}
    if c.get("model"):
        out["reserved"] = f"ol:{c['model']}@{c['host']}" if c.get("host") else f"ol:{c['model']}"
    for kind in ("stt", "tts"):
        need = (block.get("needs") or {}).get(kind)
        if need and need.get("any_of"):
            p = pick(kind, need)
            if p.get("model"):
                out[kind] = (p["model"], _DEVICE.get(need.get("device") or "cpu", "cpu"))
    return out


def running(kind: str, state_dir=None) -> Optional[str]:
    from halo_harness.bg_run import pid_alive
    from halo_harness.providers.local_server import _entry
    from halo_harness.voice.launch import entry
    row = _entry(_state(state_dir), kind)
    if row is not None and pid_alive(row.get("pid")) and row.get("base_url"):
        return str(row["base_url"])
    e = entry(kind)
    if e and e.get("voice") is True and e.get("url") and not e.get("pid"):
        return str(e["url"])  # a speech server started elsewhere and written here by hand
    return None


def cost_line(kind: str, model: str, device: Optional[str]) -> str:
    from halo_harness.voice.catalog import get
    from halo_harness.voice.device import choose
    row = get(model)
    if row is None:
        return f"starting {kind}: {model} (not in the speech catalog: halo voice models)"
    d = choose(row, device)
    gb = row.cpu_gb if d["device"] == "cpu" else row.gpu_gb
    secs = max(1, int(round(1 + gb * LOAD_S_PER_GB[d["device"]])))
    return f"starting {kind}: {d['line']} -- ~{secs} s to load (halo local serve --{kind} {model} --device {d['device']})"


def ensure(state_dir=None, say: Callable = print) -> "tuple[Optional[dict], list, list]":
    from halo_harness.voice.launch import serve
    state = _state(state_dir)
    got, started, lines = {}, [], []
    pk = picks(state_dir)
    if pk["bundle"]:
        lines.append(f"the {pk['bundle']} bundle is on: its speech picks")
    for kind in ("stt", "tts"):
        url = running(kind, state)
        if url:
            got[kind] = url
            continue
        model, device = pk[kind]
        first = cost_line(kind, model, device)
        say(first)
        lines.append(first)
        code, said, reg = serve(kind, model, device=device, state_dir=state)
        if code != 0 or reg is None:
            lines += [ln for ln in said if not ln.startswith("  ")][-2:] or said
            lines += stop(started, state)
            return None, [], lines
        started.append(kind)
        got[kind] = str(reg["base_url"])
        lines.append(f"{kind}: {model} on {reg['base_url']} ({reg['device']})")
    return got, started, lines


def stop(started: list, state_dir=None) -> list:
    from halo_harness.providers.local_server import stop as stop_server
    out = []
    for kind in started:
        r = stop_server(kind, state_dir=_state(state_dir))
        out.append(r.get("say") or f"stopped {kind}")
    return out
