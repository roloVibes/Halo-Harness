"""halo_harness.ollama_steward.fingerprint_facts -- Halo 3.3.6.0 R3: crash forensics
(plans/local-model-fit-brief.md D3 item 15). A crash fingerprint (fingerprints.py) carries the load it died in.

    LoadTracker()        the server log's load block line by line (server_context.Rules feeds it):
                         `msg="server config"` and `Listening on ... (version X)` (the startup block in force),
                         `msg="starting llama-server" cmd="..."` (a new load: its window, KV type, flash attention),
                         `offloaded N/N layers`, `graph splits = N`, the `<device> KV buffer size = X MiB` lines;
                         `llama-server started in X seconds` closes it as a `load-result` event
    facts() -> {...}     the load in force now (Rules attaches it to a crash event as `data.load`)
    enrich(fp, ev, state_dir, host, card)   the R3 fields: load_cmd, layers, splits, kv_gpu_mib, kv_cpu_mib,
                         load_s, the KV type and flash attention in force at the crash (the load block's, else the
                         card's), ollama_version (the log's, else the card's), num_ctx_requested (the ledger line
                         nearest the crash), facts_from; `model_from` "the load command" when its `--model` names it
    why_lines(fp)        `halo ollama crashes --why`: each fact with where it came from
    note_new(state_dir, fp)   one plain-language entry in the steward's notes for a new fingerprint
"""

from __future__ import annotations

import re
from typing import Optional

_OFFLOAD = re.compile(r"offloaded (\d+)/(\d+) layers")
_SPLITS = re.compile(r"graph splits\s*=\s*(\d+)")
_KV = re.compile(r"\b(\w+) KV buffer size\s*=\s*([\d.]+) MiB")
_STARTED = re.compile(r"llama-server started in ([\d.]+) seconds")
_VERSION = re.compile(r"\(version ([^)\s]+)\)")
_MODEL_ARG = re.compile(r"--model\s+(\"[^\"]+\"|\S+)")
NEAR_S = 600.0
LOOKBACK_S = 1800.0


def model_of_cmd(cmd: str) -> Optional[str]:
    """The model the load command names, or None for a blob path (Ollama passes `blobs/sha256-...`)."""
    m = _MODEL_ARG.search(cmd or "")
    if not m:
        return None
    base = re.split(r"[\\/]", m.group(1).strip('"'))[-1]
    if not base or base.startswith("sha256-") or base.startswith("sha256:"):
        return None
    return re.sub(r"\.gguf$", "", base, flags=re.IGNORECASE)


def _num(v) -> Optional[int]:
    try:
        return int(str(v))
    except (TypeError, ValueError):
        return None


class LoadTracker:
    """The startup block in force and the load being read (or the last one that finished). A finished load whose
    command names no model waits up to WAIT_LINES for the request's `template selection` line to name it."""

    WAIT_LINES = 25

    def __init__(self) -> None:
        self.server: dict = {}
        self.load: Optional[dict] = None
        self.waiting: Optional[int] = None

    def facts(self) -> dict:
        return {k: v for k, v in (self.load or {}).items() if k != "done"}

    def flush(self) -> list:
        """The finished load still waiting for its model (the end of a read)."""
        if self.waiting is None:
            return []
        self.waiting = None
        return [self._result(self.load.get("done_at"))]

    def feed(self, line: str, at, model: Optional[str]) -> list:
        """One line -> the `load-result` events it closes (none, or one)."""
        from halo_harness.ollama_steward.hardware_sources import parse_env_map, parse_launch, server_settings, slog_fields
        out: list = []
        if self.waiting is not None:
            self.waiting += 1
            if 'msg="template selection"' in line and model:
                self.load["model"] = model
                out += self.flush()
            elif self.waiting > self.WAIT_LINES or 'msg="starting llama-server"' in line:
                out += self.flush()
        if 'msg="server config"' in line:
            s = server_settings(parse_env_map(slog_fields(line).get("env", "")), {}, 1)
            self.server = {"kv_cache_type": s.get("kv_cache_type"), "flash_attention": s.get("flash_attention"),
                           "version": self.server.get("version")}
        elif 'msg="Listening on' in line and (m := _VERSION.search(line)):
            self.server["version"] = m.group(1)
        elif 'msg="starting llama-server"' in line:
            cmd = slog_fields(line).get("cmd", "")
            launch = parse_launch(cmd)
            ctx, slots = _num(launch.get("ctx")), _num(launch.get("parallel")) or 1
            self.load = {"cmd": cmd[:600], "at": at, "model": model_of_cmd(cmd), "window": (ctx // slots) if ctx else None,
                         "kv_cache_type": launch.get("cache_type") or self.server.get("kv_cache_type"),
                         "flash_attention": launch.get("flash_attention") or self.server.get("flash_attention"),
                         "version": self.server.get("version"), "layers": None, "splits": None, "kv_gpu_mib": None,
                         "kv_cpu_mib": None, "load_s": None, "done": False}
        elif self.load is not None and not self.load.get("done"):
            if m := _OFFLOAD.search(line):
                self.load["layers"] = [int(m.group(1)), int(m.group(2))]
            elif m := _SPLITS.search(line):
                self.load["splits"] = int(m.group(1))
            elif m := _KV.search(line):
                key = "kv_cpu_mib" if m.group(1).upper() == "CPU" else "kv_gpu_mib"
                self.load[key] = round((self.load.get(key) or 0.0) + float(m.group(2)), 2)
            elif m := _STARTED.search(line):
                self.load.update(load_s=float(m.group(1)), done=True, done_at=at)
                if self.load.get("model"):
                    return out + [self._result(at)]
                self.waiting = 0
        return out

    def _result(self, at) -> dict:
        from halo_harness.ollama_steward.server_rules import event
        ld = {k: v for k, v in self.facts().items() if k != "done_at"}
        return event("load-result", load_line(ld), f"llama-server started in {ld.get('load_s')} seconds", at=at,
                     model=ld.get("model"), spill=spilled(ld), **{k: v for k, v in ld.items() if k not in ("at", "model")})


def spilled(ld: dict) -> Optional[bool]:
    """True when the load block says part of it is on the CPU; None when it says nothing about placement."""
    lay, splits, cpu = ld.get("layers"), ld.get("splits"), ld.get("kv_cpu_mib")
    if isinstance(lay, list) and len(lay) == 2 and lay[0] < lay[1]:
        return True
    if (isinstance(cpu, (int, float)) and cpu > 0) or (isinstance(splits, int) and splits > 2):
        return True
    return False if (lay or splits is not None or ld.get("kv_gpu_mib")) else None


def load_line(ld: dict) -> str:
    bits = []
    lay = ld.get("layers")
    if isinstance(lay, list) and len(lay) == 2:
        bits.append(f"{lay[0]}/{lay[1]} layers on the GPU")
    if ld.get("splits") is not None:
        bits.append(f"splits = {ld['splits']}")
    if ld.get("kv_gpu_mib"):
        bits.append(f"KV {ld['kv_gpu_mib']:g} MiB on the GPU")
    if ld.get("kv_cpu_mib"):
        bits.append(f"KV {ld['kv_cpu_mib']:g} MiB on the CPU")
    took = f" in {ld['load_s']:.1f} s" if isinstance(ld.get("load_s"), (int, float)) else ""
    tail = " -- part of it runs on the CPU" if spilled(ld) else ""
    return f"{ld.get('model') or 'a model'} loaded{took}: " + (", ".join(bits) or "the log names no placement") + tail


def _t(at) -> float:
    from halo_harness.ollama_steward.ledger import parse_at
    t = at if isinstance(at, (int, float)) else parse_at(at)
    return float(t) if t is not None else 0.0


def newest_load(state_dir, host, model, at: float) -> dict:
    """The newest `load-result` event's data before `at` on this host (this model's when it is known)."""
    from halo_harness.ollama_steward.server_events import read_events
    from halo_harness.providers.ollama import ollama_names_match
    rows = [r for r in read_events(state_dir, kind="load-result", host=host) if at - LOOKBACK_S <= _t(r.get("at")) <= at + 1]
    rows = [r for r in rows if not model or not r.get("model") or ollama_names_match(r.get("model"), model)]
    return dict(rows[-1].get("data") or {}, model=rows[-1].get("model")) if rows else {}


def nearest_num_ctx(state_dir, host, model, at: float) -> Optional[int]:
    """The `num_ctx` the ledger line nearest the crash (within NEAR_S) asked for."""
    from halo_harness.ollama_steward.ledger import read_calls
    from halo_harness.providers.ollama import ollama_names_match
    best = None
    for line in read_calls(state_dir, since=LOOKBACK_S + NEAR_S, host=host):
        if model and line.get("model") and not ollama_names_match(line.get("model"), model):
            continue
        gap = abs(_t(line.get("at")) - at)
        if gap <= NEAR_S and isinstance(line.get("num_ctx_sent"), int) and (best is None or gap < best[0]):
            best = (gap, line["num_ctx_sent"])
    return best[1] if best else None


def enrich(fp: dict, ev: dict, state_dir, host, card) -> dict:
    at = _t(fp.get("at"))
    load = dict((ev.get("data") or {}).get("load") or {})
    if not load and state_dir is not None:
        load = newest_load(state_dir, host, fp.get("model"), at)
    server = (card or {}).get("server") or {}
    if load.get("model") and not ev.get("model") and model_of_cmd(load.get("cmd") or ""):
        fp["model"], fp["model_from"] = load["model"], "the load command"
    elif not fp.get("model") and load.get("model"):
        fp["model"], fp["model_from"] = load["model"], "the newest load before it"
    for k in ("layers", "splits", "kv_gpu_mib", "kv_cpu_mib", "load_s"):
        fp[k] = load.get(k)
    fp["load_cmd"] = (load.get("cmd") or "")[:300] or None
    fp["kv_cache_type"] = load.get("kv_cache_type") or fp.get("kv_cache_type")
    fp["flash_attention"] = load.get("flash_attention") or fp.get("flash_attention")
    fp["ollama_version"] = load.get("version") or server.get("version")
    fp["window_used"] = fp.get("window_used") or load.get("window")
    fp["facts_from"] = "the log's load block" if load else "the host card"
    if fp.get("spill") is None and load:
        fp["spill"] = spilled(load)
    fp["num_ctx_requested"] = nearest_num_ctx(state_dir, host, fp.get("model"), at) if state_dir is not None else None
    return fp


def why_lines(fp: dict) -> list:
    from halo_harness.ollama_steward.fingerprints import WORDS
    out = [f"  signature: {fp.get('signature')} ({WORDS.get(fp.get('signature'), 'a crash')})"]
    ld = {k: fp.get(k) for k in ("layers", "splits", "kv_gpu_mib", "kv_cpu_mib", "load_s")}
    ld["model"] = fp.get("model")
    out.append(f"  the load: {load_line(ld).split(': ', 1)[-1]}")
    fa = fp.get("flash_attention")
    out.append(f"  in force then: KV {fp.get('kv_cache_type') or '?'}, flash attention {fa if fa is not None else '?'}, "
               f"Ollama {fp.get('ollama_version') or '?'} (from {fp.get('facts_from') or 'the host card'})")
    req, used = fp.get("num_ctx_requested"), fp.get("window_used")
    out.append("  the request: " + (f"num_ctx {req:,} (the ledger line nearest the crash)" if isinstance(req, int)
                                    else "no ledger line near the crash") +
               (f"; loaded at {used:,}" if isinstance(used, int) else ""))
    out.append(f"  the model: {fp.get('model') or 'unknown'} (from {fp.get('model_from') or 'unknown'})")
    if fp.get("load_cmd"):
        out.append(f"  the load command: {fp['load_cmd'][:200]}")
    out.extend(f"  evidence: {e[:160]}" for e in (fp.get("evidence") or [])[:4])
    return out


def note_new(state_dir, fp: dict) -> None:
    """One line in the steward's notes for a fingerprint seen for the first time."""
    try:
        from halo_harness.ollama_steward import notes
        from halo_harness.ollama_steward.fingerprints import WORDS
        bits = [b for b in ("after a spill" if fp.get("spill") else "",
                            f"at {fp['window_used']:,}" if isinstance(fp.get("window_used"), int) else "",
                            f"with {fp['kv_cache_type']} KV" if fp.get("kv_cache_type") else "",
                            "flash attention on" if str(fp.get("flash_attention")).lower() in ("on", "true", "1") else "") if b]
        say = (f"{fp.get('model') or 'a model'} crashed on {fp.get('host') or 'a host'}: "
               f"{WORDS.get(fp.get('signature'), 'a crash')}" + (f" {' '.join(bits)}" if bits else "") +
               " (halo ollama crashes --why)")
        notes.append(state_dir, "finding", say, attention=True, model=fp.get("model"),
                     data={"fingerprint": fp.get("signature"), "host": fp.get("host")}, where="fingerprints")
    except Exception:
        pass
