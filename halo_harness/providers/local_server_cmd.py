"""halo_harness.providers.local_server_cmd -- Halo 3.3.5.0 R5: the command line of a local server Halo starts for a
file on disk (providers/local_server.py runs it), and where each of its numbers comes from.

    binary(runtime, *, state_dir) -> (argv prefix | None, source line)
        llama-server: `huggingface.llama_server_bin` (a path, or a list: the program and its first arguments), else
        PATH, else a runtime `halo local serve` fetched (~/.halo/runtimes); mlx: `python -m mlx_lm.server` on a Mac
        with mlx-lm installed. Under BRIDGE_TEST_NO_BACKGROUND_NET only a configured llama_server_bin runs (the
        tests' fake, tests/helpers/fake_llama_server.py): a real llama-server or mlx_lm is never started by a test.
    plan_flags(path, fmt, *, window=None, parallel=None, state_dir=None) -> {window, ngl, parallel, kv_type,
        flash_attn, num_predict, layers, host, sources {flag: why}, notes}
        the window and -ngl from the fit planner on this machine's hardware card (ollama_steward/fit.
        model_window_on_card: the largest window with every layer on the GPU), capped by the file's trained context;
        the card's kv_cache_type; a steward profile's num_predict for this model; one slot unless asked
    llama_argv(prefix, *, path, model, port, flags) -> [...]   llama-server -m <path> --alias <model> -c <window>
        -ngl <ngl> -np <parallel> --port <p> --host 127.0.0.1 [--cache-type-k/v <kv>] [--flash-attn on] [-n <n>]
    mlx_argv(prefix, *, path, port) -> [...]                   python -m mlx_lm.server --model <path> --port <p>
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

STOP_GRACE_S = 10.0
FLOOR = 8192
KV_QUANT = ("q8_0", "q4_0")
GIB = 2 ** 30


def binary(runtime: str, *, state_dir=None) -> "tuple[Optional[list], str]":
    from halo_harness.config.paths import background_net_disabled
    from halo_harness.theme import get_config_value
    if runtime == "mlx":
        if sys.platform != "darwin":
            return None, f"mlx_lm.server runs on a Mac with Apple Silicon; this machine is {sys.platform}: serve a GGUF with llama-server"
        if background_net_disabled():
            return None, "under the test flag (BRIDGE_TEST_NO_BACKGROUND_NET) mlx_lm.server is not started"
        import importlib.util
        if importlib.util.find_spec("mlx_lm") is None:
            return None, 'mlx-lm is not installed: uv tool install "halo-harness[mlx]" (or pip install mlx-lm)'
        return [sys.executable, "-m", "mlx_lm.server"], "python -m mlx_lm.server (mlx-lm in this Python)"
    conf = get_config_value("huggingface.llama_server_bin", default=None)
    if isinstance(conf, list) and conf and all(isinstance(x, str) for x in conf):
        return list(conf), "huggingface.llama_server_bin"
    if isinstance(conf, str) and conf.strip():
        p = Path(conf).expanduser()
        return ([str(p)], "huggingface.llama_server_bin") if p.exists() else (None, f"huggingface.llama_server_bin names {p}, which is not there")
    if background_net_disabled():
        return None, "under the test flag (BRIDGE_TEST_NO_BACKGROUND_NET) only a configured huggingface.llama_server_bin runs"
    found = shutil.which("llama-server")
    if found:
        return [found], f"llama-server on PATH ({found})"
    from halo_harness.providers.local_runtime import find_runtime_binary
    got = find_runtime_binary("llama-server", state_dir=state_dir)
    if got:
        return got, f"the runtime Halo fetched ({got[0]})"
    from halo_harness.providers.local_use import install_hint
    return None, ("llama-server is not on PATH and huggingface.llama_server_bin is not set: " + install_hint()
                  + " (or halo local serve <file> fetches one)")


def this_machine_card() -> "tuple[Optional[dict], str]":
    """The hardware card of the first host this machine serves that has one (the Ollama panel's cache)."""
    try:
        from halo_harness.fleet.ollama_share import served_here
        from halo_harness.ollama_steward.fit import card_budget
        from halo_harness.providers.ollama import resolve_ollama_hosts
        from halo_harness.providers.ollama_guard import skip_default
        from halo_harness.studio.ollama_hosts_view import card_of
        for h in resolve_ollama_hosts():
            if skip_default(h) or not served_here(h.url):
                continue
            card = card_of(h)
            if card and card_budget(card)["budget"] > 0:
                return card, h.name
    except Exception:
        pass
    return None, ""


def _profile_num_predict(model: str) -> "tuple[Optional[int], str]":
    try:
        from halo_harness.ollama_steward.profiles import all_profiles, split_key
        for k, p in sorted(all_profiles().items()):
            if split_key(k)[1].lower() == model.lower() and isinstance((p or {}).get("num_predict"), int):
                return p["num_predict"], f"the steward profile {k}"
    except Exception:
        pass
    return None, ""


def plan_flags(path, fmt: str, *, model: str = "", window: Optional[int] = None, parallel: Optional[int] = None) -> dict:
    from halo_harness.ollama_steward.fit import card_budget, model_window_on_card
    from halo_harness.providers.local_fit import read_fit_inputs_for_path, trained_context_from_model_info
    from halo_harness.providers.ollama import HARD_CONTEXT_CAP
    info, _quant, weights = read_fit_inputs_for_path(path, fmt=fmt)
    trained = trained_context_from_model_info(info)
    layers = next((v for k, v in (info or {}).items() if k.endswith(".block_count") and isinstance(v, int)), None)
    card, host = this_machine_card()
    src, notes = {}, []
    row = {"size": weights, "model_info": info or {}}
    on_gpu = model_window_on_card(card, row) if card and isinstance(weights, int) and info else None
    cap = min(v for v in (trained, HARD_CONTEXT_CAP) if isinstance(v, int) and v > 0)
    if isinstance(window, int) and window > 0:
        win, src["window"] = window, "asked"
        if on_gpu and window > on_gpu:
            notes.append(f"{window:,} is past the {on_gpu:,} that stays on the GPU here: llama-server may not allocate it")
    elif on_gpu:
        win = min(on_gpu, cap)
        src["window"] = (f"the fit planner on {host}'s card: every layer on the GPU up to {on_gpu:,}"
                         + (f", the file's trained context {trained:,}" if trained and trained < on_gpu else ""))
    else:
        win = min(FLOOR, cap)
        src["window"] = (f"{'no hardware card read for this machine yet (Local -> Hosts reads it)' if not card else 'the weights do not fit the card whole'}"
                         f": the planner's floor {FLOOR:,}" + (f" (the trained context is {trained:,})" if trained else ""))
    b = card_budget(card) if card else None
    if card and on_gpu:
        ngl, src["ngl"] = (layers + 1 if layers else 999), f"every layer{f' ({layers} + the output)' if layers else ''} on the GPU: the window holds there"
    elif card and isinstance(weights, int) and weights > 0 and layers and b and b["budget"]:
        share = max(0, min(layers, int(layers * (b["budget"] - 2 * GIB) / weights)))
        ngl, src["ngl"] = share, f"about {share} of {layers} layers fit {host}'s {b['budget'] / GIB:.1f} GiB with the KV cache; the rest run on the CPU"
    else:
        ngl, src["ngl"] = 999, "every layer (no hardware card for this machine to work it out from)"
    np_ = int(parallel) if isinstance(parallel, int) and parallel > 0 else 1
    src["parallel"] = "asked" if np_ != 1 or parallel else "one slot: one request at a time keeps the whole window for it"
    kv = ((card or {}).get("server") or {}).get("kv_cache_type")
    kv = kv if kv in KV_QUANT else None
    src["kv_type"] = f"the card's kv_cache_type ({host})" if kv else "f16, llama-server's default (the card names no quantized KV)"
    fa = bool(kv)
    src["flash_attn"] = "on: a quantized V cache needs flash attention" if fa else "llama-server's default (auto)"
    npred, src["num_predict"] = _profile_num_predict(model) if model else (None, "")
    if npred is None:
        src["num_predict"] = "llama-server's default (no steward profile for this model)"
    return {"window": win, "ngl": ngl, "parallel": np_, "kv_type": kv, "flash_attn": fa, "num_predict": npred,
            "layers": layers, "trained": trained, "host": host or None, "sources": src, "notes": notes}


def llama_argv(prefix: list, *, path, model: str, port: int, flags: dict) -> list:
    argv = list(prefix) + ["-m", str(path), "--alias", model, "-c", str(flags["window"]), "-ngl", str(flags["ngl"]),
                           "-np", str(flags["parallel"]), "--port", str(port), "--host", "127.0.0.1"]
    if flags.get("kv_type"):
        argv += ["--cache-type-k", flags["kv_type"], "--cache-type-v", flags["kv_type"]]
    if flags.get("flash_attn"):
        argv += ["--flash-attn", "on"]
    if isinstance(flags.get("num_predict"), int):
        argv += ["-n", str(flags["num_predict"])]
    return argv


def mlx_argv(prefix: list, *, path, port: int) -> list:
    return list(prefix) + ["--model", str(path), "--port", str(port)]


def runtime_of(fmt: str, asked: Optional[str] = None) -> str:
    a = (asked or "").strip().lower()
    if a in ("mlx", "mlx_lm", "mlx-lm"):
        return "mlx"
    if a in ("llama-server", "llama", "llama.cpp"):
        return "llama-server"
    return "llama-server" if fmt == "gguf" else "mlx"


# Process and loopback helpers providers/local_server.py uses.

def get(url: str, timeout: float = 2.0):
    """(status, parsed JSON or text) of one loopback GET through providers/http.open_upstream; (0, why) when nothing
    answers."""
    import http.client
    import urllib.parse
    from halo_harness.providers.http import UpstreamConnectError, open_upstream
    u = urllib.parse.urlparse(url)
    conn = None
    try:
        conn = open_upstream(u.hostname or "127.0.0.1", u.port or 80, u.scheme == "https", connect_timeout=max(1, int(timeout)))
        if conn.sock:
            conn.sock.settimeout(timeout)
        conn.request("GET", u.path or "/", headers={"Accept-Encoding": "identity"})
        resp = conn.getresponse()
        code, body = resp.status, resp.read().decode("utf-8", "replace")
    except (UpstreamConnectError, OSError, http.client.HTTPException, ValueError) as e:
        return 0, str(e) or type(e).__name__
    finally:
        if conn is not None:
            conn.close()
    try:
        return code, json.loads(body)
    except ValueError:
        return code, body


def tail_lines(path, n: int = 40) -> list:
    try:
        data = Path(path).read_bytes()[-max(4096, n * 400):]
    except OSError:
        return []
    return data.decode("utf-8", "replace").splitlines()[-n:]


def _gone(pid) -> bool:
    from halo_harness.bg_run import pid_alive
    from halo_harness.providers.local_runtime import _posix_proc_state
    return not pid_alive(pid) or (sys.platform != "win32" and _posix_proc_state(pid) == "Z")


def halt(pid: int, grace: float = STOP_GRACE_S) -> str:
    """Terminate, then kill after `grace` seconds; how it ended."""
    import signal
    from halo_harness.providers.local_runtime import _forget_popen
    proc = _forget_popen(pid)
    if proc is not None:
        proc.terminate()
        try:
            proc.wait(timeout=grace)
            return "terminated"
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)
            return f"killed after {grace:.0f} s"
    try:
        os.kill(pid, signal.SIGTERM)
    except (OSError, TypeError):
        return "already gone"
    end = time.monotonic() + grace
    while time.monotonic() < end:
        if _gone(pid):
            return "terminated"
        time.sleep(0.2)
    try:
        os.kill(pid, getattr(signal, "SIGKILL", signal.SIGTERM))
    except OSError:
        pass
    return f"killed after {grace:.0f} s"


__all__ = ["binary", "get", "halt", "llama_argv", "mlx_argv", "plan_flags", "runtime_of", "tail_lines", "this_machine_card"]
