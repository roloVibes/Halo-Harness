"""halo_harness.providers.capability_battery -- Halo 3.3.6.0 R1: the battery
(plans/local-model-fit-brief.md Part E1): a short run of one-shot probes
against a local model where its GPU is, and the profile it leaves
(providers/battery_profile.py) in the capability cache
(providers/ollama_capability.py: keyed by the digest, the Ollama version and
the probe set, so any change re-runs it).

    run(host, model, *, client=None, card=None, on_status=None, state_dir=None, force=False, window=None)
        -> the profile, or {ok: False, error, say} when it could not run

The requests, in order: `/api/version`, `/api/tags` (the digest and size),
`/api/show` (the shape), `/api/ps` (was it loaded?), six `/api/chat` turns
(battery_probes.ORDER: the warm-up first, never timed -- Part G4), `/api/ps`
again (did it fit: `size_vram == size` at the window used). About eight
requests to the model, a couple of minutes, no cost; it loads the model.
`card` is the host's hardware card (providers/fit_meter.host_card_of): the
usable window and co-reside / pivot come from it (ollama_steward/fit.py).
`client` answers `call(method, path, body=None, timeout=...) -> dict | None`
(the tests' scripted fake); the default calls the host. Under the test flag
(BRIDGE_TEST_HOME) it runs against a loopback host on a non-default port
only: never a real server from a test.
"""

from __future__ import annotations

import time
import urllib.parse
from typing import Callable, Optional

from halo_harness.providers import battery_probes as B
from halo_harness.providers.battery_profile import finish, resident

COST_LINE = "about 8 requests to {model} on {host}, 1-3 minutes, no cost; it loads the model"
CALL_TIMEOUT_S = 180.0
LOAD_TIMEOUT_S = 600.0
DEFAULT_WINDOW = 32768
FLOOR_WINDOW = 8192


class HostClient:
    def __init__(self, host):
        self.host = host

    def call(self, method: str, path: str, body=None, timeout: float = CALL_TIMEOUT_S):
        from halo_harness.providers.ollama import request_json
        return request_json(self.host, path, method=method, body=body, timeout=timeout).body


def cost_line(model: str, host_name: str) -> str:
    return COST_LINE.format(model=model, host=host_name)


def test_guard(host) -> Optional[str]:
    """Why this host may not be probed from a test run (None: it may): providers/ollama_guard.control_blocked
    under the test flag (the made-up default host, any address but a loopback fake), and the same loopback rule
    whenever BRIDGE_TEST_HOME is set."""
    import os
    from halo_harness.providers.ollama_guard import control_blocked
    why = control_blocked(host)
    if why:
        return why
    if not os.environ.get("BRIDGE_TEST_HOME"):
        return None
    try:
        u = urllib.parse.urlparse(getattr(host, "url", "") or "")
        if u.hostname in ("127.0.0.1", "localhost") and u.port not in (None, 11434):
            return None
    except ValueError:
        pass
    return "a test run probes the scripted fake Ollama only (a loopback host on a test port)"


def _fail(model: str, host_name: str, say: str, **extra) -> dict:
    return {"ok": False, "model": model, "host": host_name, "error": say, "say": say, **extra}


def _row(tags, model: str) -> Optional[dict]:
    from halo_harness.providers.ollama import ollama_names_match
    for r in (tags or {}).get("models") or []:
        if isinstance(r, dict) and (ollama_names_match(r.get("model"), model) or ollama_names_match(r.get("name"), model)):
            return r
    return None


def _trained(info: dict) -> Optional[int]:
    for k, v in (info or {}).items():
        if k.endswith(".context_length") and isinstance(v, int) and v > 0:
            return v
    return None


def _window(host, model: str, info: dict, card, row, asked) -> int:
    if isinstance(asked, int) and asked > 0:
        return asked
    from halo_harness.ollama_steward.profiles import lookup
    w = (lookup(host, model) or {}).get("num_ctx")
    if not isinstance(w, int):
        trained = _trained(info) or DEFAULT_WINDOW
        w = min(trained, DEFAULT_WINDOW)
        if card:
            from halo_harness.ollama_steward.fit import model_window_on_card
            gpu = model_window_on_card(card, {**(row or {}), "model_info": info}, step=4096)
            if isinstance(gpu, int) and gpu > 0:
                w = max(min(w, gpu), min(FLOOR_WINDOW, w))
    return int(w)


def _ps_entry(ps, model: str) -> Optional[dict]:
    from halo_harness.providers.ollama import ollama_names_match
    for e in (ps or {}).get("models") or []:
        if isinstance(e, dict) and (ollama_names_match(e.get("model"), model) or ollama_names_match(e.get("name"), model)):
            return e
    return None


def _fit(card, row: dict, info: dict, used: int, tags, model: str, ps_after) -> dict:
    from halo_harness.providers.ollama_fit import kv_bytes_per_token
    entry = _ps_entry(ps_after, model)
    size, vram = (entry or {}).get("size"), (entry or {}).get("size_vram")
    verified = isinstance(size, int) and isinstance(vram, int) and size > 0 and vram >= size
    out = {"window": {"trained": _trained(info), "used": used, "usable": None, "verified": verified,
                      "loaded_at": (entry or {}).get("context_length"), "on_gpu_pct":
                      round(100.0 * vram / size) if isinstance(size, int) and size and isinstance(vram, int) else None},
           "kv_per_token": None, "resident": {"co_resides_with": [], "pivot_only": None}}
    bpe = 2.0
    if card:
        from halo_harness.ollama_steward.fit import _need, card_budget, model_window_on_card
        b = card_budget(card)
        bpe = b["bpe"]
        full = {**row, "model_info": info}
        out["window"]["usable"] = model_window_on_card(card, full, step=4096)
        mine = _need(b, full, used) if info else None
        others = []
        for r in (tags or {}).get("models") or []:
            if not isinstance(r, dict) or r is row or r.get("digest") == row.get("digest") or not isinstance(r.get("size"), int):
                continue
            need = _need(b, r, FLOOR_WINDOW) if isinstance(r.get("model_info"), dict) and r["model_info"] else \
                r["size"] + 512 * 2 ** 20
            others.append((r.get("model") or r.get("name"), need, r["size"]))
        out["resident"] = resident(mine, others, b["budget"] or None, reserve=457 * 2 ** 20 * b["cards"])
    kv =kv_bytes_per_token(info or {}, bytes_per_elem=bpe)
    out["kv_per_token"] = int(kv) if isinstance(kv, (int, float)) else None
    return out


def run(host, model: str, *, client=None, card=None, on_status: Optional[Callable[[dict], None]] = None,
        state_dir=None, force: bool = False, window: Optional[int] = None, apply: bool = True) -> dict:
    """See the module docstring."""
    name = getattr(host, "name", "") or "this host"
    say = on_status or (lambda _d: None)
    why = test_guard(host)
    if why:
        return _fail(model, name, why)
    client = client or HostClient(host)
    version = ((client.call("GET", "/api/version", timeout=10.0) or {}).get("version"))
    tags = client.call("GET", "/api/tags", timeout=15.0)
    if tags is None:
        return _fail(model, name, f"{name} did not answer (/api/tags): is Ollama running there?")
    row = _row(tags, model)
    if row is None:
        return _fail(model, name, f"no model named {model} on {name}")
    digest = row.get("digest")
    if state_dir is not None and not force:
        from halo_harness.providers.ollama_capability import load_profile
        hit = load_profile(state_dir, digest, name, ollama_version=version)
        if hit is not None:
            say({"step": 0, "of": 0, "probe": "cache", "say": f"probed {time.strftime('%Y-%m-%d', time.localtime(hit.get('probed_at') or 0))}"
                                                              f" (the same digest and Ollama version): the cached profile"})
            return {**hit, "ok": True, "cached": True}
    show = client.call("POST", "/api/show", body={"model": model}, timeout=15.0) or {}
    info = show.get("model_info") if isinstance(show.get("model_info"), dict) else {}
    was_loaded = _ps_entry(client.call("GET", "/api/ps", timeout=10.0), model) is not None
    used = _window(host, model, info, card, row, window)
    keep = getattr(host, "keep_alive", None) or "5m"
    replies, ev, total = {}, {}, len(B.ORDER)
    for i, probe in enumerate(B.ORDER, 1):
        say({"step": i, "of": total, "probe": probe, "say": f"{i}/{total} {B.WORDS[probe]}"})
        reply = client.call("POST", "/api/chat", body=B.body(model, probe, num_ctx=used, keep_alive=keep),
                            timeout=LOAD_TIMEOUT_S if probe == "warmup" else CALL_TIMEOUT_S)
        if not isinstance(reply, dict):
            if probe == "warmup":
                return _fail(model, name, f"{model} did not answer on {name} at {used:,} tokens (it may not load there)",
                             digest=digest)
            reply = {}
        first = None
        if probe != "warmup" and B.thinking_only(reply):
            first = reply
            reply = client.call("POST", "/api/chat", body=B.body(model, probe, num_ctx=used, keep_alive=keep,
                                                               cap=B.THINK_CAP), timeout=CALL_TIMEOUT_S) or {}
        replies[probe], ev[probe] = reply, B.evidence(reply, retried=first)
        if first is not None:
            replies[probe + ":first"] = first
    ps_after = client.call("GET", "/api/ps", timeout=10.0)
    tools, tools_why = B.score_tools(replies["tools"])
    output, output_why = B.score_json(replies["json"])
    ids, ids_why = B.score_reference(replies["reference"])
    thinks = any(B.parts(r)[1].strip() for k, r in replies.items() if k != "warmup")
    sp, warm = B.speed(replies["json"]), B.speed(replies["warmup"])
    p = {"ok": True, "model": model, "host": name, "digest": digest, "ollama_version": version,
         "probe_set": B.PROBE_SET, "probed_at": time.time(), "tools": tools, "tools_why": tools_why,
         "system_role": B.score_system(replies["system"]), "instruction": B.score_instruction(replies["instruction"]),
         "output": output, "output_why": output_why, "identifiers": ids, "identifiers_why": ids_why,
         "reasoning": "thinking" if thinks else "none",
         "size_gb": round(row["size"] / 1e9, 1) if isinstance(row.get("size"), int) else None,
         "speed": {"tok_s": sp["tok_s"], "ttft_ms": sp["ttft_ms"], "at_window": used,
                   "cold_load_s": warm["load_s"] if not was_loaded else None, "warm_at_start": was_loaded},
         "evidence": ev, "capabilities": show.get("capabilities") if isinstance(show.get("capabilities"), list) else None}
    p.update(_fit(card, row, info, used, tags, model, ps_after))
    finish(p)
    if state_dir is not None:
        from halo_harness.providers.ollama_capability import save_profile
        save_profile(state_dir, {k: v for k, v in p.items() if k != "ok"})
        if apply:
            try:
                from halo_harness.providers.placement_apply import apply_profile
                p["applied"] = apply_profile(p, state_dir)
            except Exception:
                p["applied"] = []
    return p
