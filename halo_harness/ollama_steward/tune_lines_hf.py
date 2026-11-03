"""halo_harness.ollama_steward.tune_lines_hf -- Halo 3.3.8.0 R2: the server-side lines for a local server (llama-server,
LM Studio, mlx_lm.server), the sibling of tune_lines.py's Ollama lines. Each is a stated action -- the exact flag or
setting, the line that reverts it, `applied: false` -- that the person runs where the server runs; Halo never starts,
restarts or configures a server.

    line(server, change, value, *, was=None) -> {change, runtime, set, revert, how, cost, applied: False} | None
        change: "ctx-size" | "n-gpu-layers" | "cache-type" | "n-predict" | "flash-attn"
        None: that runtime has no such setting (mlx_lm.server keeps no fixed window and offloads nothing)
    hint(stated) -> the finding's server_hint {env, line, cost}
    crash_fixes(fp) -> [{side, line, cost}]   a repeated crash in a local server's log (rules_crash.py)

For a server Halo started, `how` is the restart through Halo (`halo local stop <id>` then `halo local serve ...
--window N`): still a line for the person, never run by the steward.
"""

from __future__ import annotations

from typing import Optional

COSTS = {"ctx-size": "more memory for the KV cache per slot: fewer layers may fit on the GPU",
         "n-gpu-layers": "more VRAM for the weights: a smaller --ctx-size or a q8_0 KV cache makes room",
         "cache-type": "a q8_0 KV cache takes half the memory of f16; quality drops a little on long contexts",
         "n-predict": "a reply can run until the window ends",
         "flash-attn": "flash attention on saves memory per token; off is slower and needs more"}


def _llama(change: str, value, was) -> Optional[tuple]:
    if change == "ctx-size":
        return f"--ctx-size {value}", f"--ctx-size {was}" if was else "drop --ctx-size (the model's trained context)"
    if change == "n-gpu-layers":
        return f"--n-gpu-layers {value}", f"--n-gpu-layers {was}" if was is not None else "drop --n-gpu-layers"
    if change == "cache-type":
        return f"--cache-type-k {value} --cache-type-v {value}", f"--cache-type-k {was or 'f16'} --cache-type-v {was or 'f16'}"
    if change == "n-predict":
        return f"--n-predict {value}", f"--n-predict {was}" if was is not None else "drop --n-predict"
    if change == "flash-attn":
        return f"--flash-attn {value}", f"--flash-attn {was or 'auto'}"
    return None


def _lmstudio(change: str, value, was) -> Optional[tuple]:
    names = {"ctx-size": "Context Length", "n-gpu-layers": "GPU Offload", "cache-type": "K Cache Quantization Type",
             "flash-attn": "Flash Attention"}
    if change not in names:
        return None
    where = "LM Studio -> My Models -> the model's load settings -> "
    return (f"{where}{names[change]}: {value} (then reload the model)",
            f"{where}{names[change]}: {was if was is not None else 'its default'} (then reload the model)")


def _mlx(change: str, value, was) -> Optional[tuple]:
    if change == "n-predict":
        return f"mlx_lm.server ... --max-tokens {value}", f"--max-tokens {was}" if was else "drop --max-tokens"
    return None  # no fixed window, no layer offload on unified memory, no KV type flag


def _ft(change: str, value, was) -> Optional[tuple]:
    """3.3.9.1: `ft serve`'s flags (docs/cli.md, from the source, unverified); FreeToken sizes its own cache and layers."""
    if change == "ctx-size":
        return f"--max-seq-len-override {value}", f"--max-seq-len-override {was}" if was else "drop --max-seq-len-override"
    if change == "n-predict":
        return "--max-output-tokens 32768", f"--max-output-tokens {was}" if was else "drop --max-output-tokens"
    return None


def _st(change: str, value, was) -> Optional[tuple]:
    """3.3.9.2: `strata launch`'s flags (docs/TERMINAL_LAUNCH.md, from the source, unverified); a new launch applies them."""
    if change == "ctx-size":
        return f"--context {value}", f"--context {was}" if was else "drop --context"
    if change == "cache-type":
        return "--kv q4_0" if str(value).startswith("q4") else "--kv int8", f"--kv {was}" if was else "drop --kv"
    return None


def line(server, change: str, value, *, was=None) -> Optional[dict]:
    rt = getattr(server, "runtime", None) or "llama-server"
    got = {"llama-server": _llama, "lmstudio": _lmstudio, "mlx": _mlx, "freetoken": _ft, "strata": _st}.get(
        rt, _llama)(change, value, was)
    if got is None:
        return None
    set_, revert = got
    name = getattr(server, "name", "the server")
    if rt == "lmstudio":
        how = f"on {name}: {set_}"
    elif getattr(server, "source", "") == "halo" or getattr(server, "id", None):
        sid = getattr(server, "id", None) or name
        how = (f"halo local stop {sid}, then halo local serve <the model> --window {value}" if change == "ctx-size" else
               f"halo local stop {sid}, then start it again with {set_}")
    else:
        how = f"restart {rt} on {name} with {set_} (where it was started)"
    return {"change": change, "runtime": rt, "set": set_, "revert": revert, "how": how,
            "cost": COSTS.get(change, ""), "applied": False}


def hint(stated: Optional[dict]) -> Optional[dict]:
    if not stated:
        return None
    return {"env": None, "line": f"{stated['how']} (revert: {stated['revert']})", "cost": stated["cost"],
            "applied": False, "runtime": stated["runtime"]}


def crash_fixes(fp: dict, server=None) -> list:
    """Every fix for a repeated crash in a local server's log: Halo's side first, then the server's (stated)."""
    from halo_harness.ollama_steward.rules_crash import _smaller
    model, name = fp.get("model") or "the model", fp.get("host") or "the server"
    out = []
    to = _smaller(fp, None)
    if to:
        out.append({"side": "halo", "line": f"a {to:,} window for {model} on {name} (the profile's num_ctx): the crash "
                    "window", "cost": "a shorter context; compaction runs sooner"})
    from types import SimpleNamespace
    srv = server or SimpleNamespace(name=name, runtime=fp.get("runtime"), source="", id=None)
    kv = "f16" if str(fp.get("kv_cache_type") or "").lower() == "q8_0" else "q8_0"  # the measured IMA was q8_0 + FA
    for change, value in (("ctx-size", to), ("cache-type", kv)):
        if value is None:
            continue
        st = line(srv, change, value, was=fp.get("window_used") if change == "ctx-size" else fp.get("kv_cache_type"))
        if st:
            out.append({"side": "host", "line": f"{st['how']} (revert: {st['revert']})", "cost": st["cost"],
                        "applied": False})
    return out
