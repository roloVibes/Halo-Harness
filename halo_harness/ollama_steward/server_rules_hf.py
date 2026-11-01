"""halo_harness.ollama_steward.server_rules_hf -- Halo 3.3.8.0 R2: what llama-server, LM Studio and mlx_lm.server print,
turned into the same events as Ollama's log (server_rules.KINDS; server_context_hf.Rules adds what needs the lines
around a line).

    classify(line, at=None, runtime=None) -> event | None
    line_time(line) -> epoch seconds of the line's own timestamp, or None (llama-server prints none by default)
    SAYS[runtime] -> the kinds that runtime's log can state; can_say(runtime, kind); not_asked(runtime) -> the rest

llama-server (llama.cpp's server: Halo's own `halo local serve` log, or a `--log-file`) -- the llama.cpp lines Ollama
embeds are read by server_rules.classify (offloaded a/b layers -> cpu-spill, out of memory / cudaMalloc failed / CUDA
error -> gpu-memory, print_timing -> timing); here: `input truncated` and `context shift` (prompt-trimmed), `the request
exceeds the available context size` (prompt-trimmed, refused), `stopped by limit` (reply-cut: the server's n_predict),
`context shift is disabled` (window-full), `failed to load model` / `error loading model` (load-failed), GGML_ASSERT,
3.3.8.0 R4: a pool's RPC lines -- "Remote RPC server crashed or returned malformed response" (the abort),
"Failed to connect to <addr>", "RPC server version mismatch" -> `rpc-lost` {addr} (ollama_steward/rules_pool.py),
`terminate called`, a segfault (a crash: other-error, the death line), the request lines' 500s. LM Studio (its
server-logs file): `[timestamp][LEVEL]` lines -- the context-overflow error (prompt-trimmed), `"finish_reason": "length"`
(reply-cut), a failed load, out of memory, `The model has crashed` (the death line), any other [ERROR]. mlx_lm.server
(Python's http.server and logging): a 500 request line, a Metal out-of-memory, a Traceback's last line, libc++abi.
"""

from __future__ import annotations

import datetime as _dt
import re
from typing import Optional

from halo_harness.ollama_steward.server_rules import classify as classify_llama, event

SAYS = {"llama-server": ("prompt-trimmed", "reply-cut", "window-full", "cpu-spill", "gpu-memory", "load-failed",
                         "slow-load", "http-500", "other-error", "timing", "load-result", "rpc-lost"),
        "lmstudio": ("prompt-trimmed", "reply-cut", "gpu-memory", "load-failed", "other-error"),
        "mlx": ("http-500", "gpu-memory", "load-failed", "other-error")}
ASKED = ("prompt-trimmed", "reply-cut", "window-full", "cpu-spill", "gpu-memory", "load-failed", "slow-load",
         "http-500", "other-error")

_LMS_TIME = re.compile(r"^\[(\d{4}-\d\d-\d\d)[ T](\d\d:\d\d:\d\d)(?:\.\d+)?\]")
_PY_TIME = re.compile(r"^(\d{4}-\d\d-\d\d) (\d\d:\d\d:\d\d)(?:,\d+)?\b")
_HTTPD = re.compile(r'\[(\d\d/[A-Z][a-z]{2}/\d{4}) (\d\d:\d\d:\d\d)\] "(\w+) (\S+)[^"]*" (\d{3})')
_LLAMA_REQ = re.compile(r"request: (\w+) (\S+) \S+ (\d{3})\b")
_TRUNC = re.compile(r"input truncated.*?n_ctx\s*=\s*(\d+).*?n_keep\s*=\s*(\d+).*?n_left\s*=\s*(\d+)"
                    r"(?:.*?n_prompt_tokens\s*=\s*(\d+))?")
_SHIFT = re.compile(r"context shift, n_keep\s*=\s*(\d+), n_left\s*=\s*(\d+), n_discard\s*=\s*(\d+)")
_LIMIT = re.compile(r"stopped by limit.*?n_predict\s*=\s*(-?\d+)")  # also "n_decoded = N, n_predict = N"
_LMS_OVER = re.compile(r"context length of only (\d+) tokens", re.I)
_LMS_KEEP = re.compile(r"keep the first (\d+) tokens", re.I)
_RPC_LOST = re.compile(r"Remote RPC server crashed or returned malformed response|Failed to connect to (\S+)|"
                       r"RPC server version mismatch|ggml_backend_rpc\S*: .*(?:failed|error|closed)|"
                       r"RPC\[([^\]]+)\].*(?:connection (?:closed|lost|refused)|failed to (?:send|recv))", re.I)
_DEATH = re.compile(r"GGML_ASSERT|terminate called after throwing|Segmentation fault|libc\+\+abi: terminating|"
                    r"model has crashed|exited with code|Aborted \(core dumped\)", re.I)


def line_time(line: str) -> Optional[float]:
    text = str(line or "")
    try:
        if m := _LMS_TIME.search(text) or _PY_TIME.search(text):
            return _dt.datetime.strptime(f"{m.group(1)} {m.group(2)}", "%Y-%m-%d %H:%M:%S").timestamp()
        if m := _HTTPD.search(text):
            return _dt.datetime.strptime(f"{m.group(1)} {m.group(2)}", "%d/%b/%Y %H:%M:%S").timestamp()
    except ValueError:
        return None
    return None


def can_say(runtime: Optional[str], kind: str) -> bool:
    return kind in SAYS.get(runtime or "llama-server", SAYS["llama-server"])


def not_asked(runtime: Optional[str]) -> list:
    """The kinds this runtime's log never prints: a rule says "not asked" for them, never "nothing wrong"."""
    return [k for k in ASKED if not can_say(runtime, k)]


def _ev(kind: str, say: str, line: str, at, runtime, **data) -> dict:
    return event(kind, say, line, at=at, runtime=runtime, **data)


def _status(line: str, at, runtime) -> Optional[dict]:
    m = _LLAMA_REQ.search(line) or _HTTPD.search(line)
    if not m:
        return None
    status = int(m.groups()[-1])
    if status == 500:
        return _ev("http-500", f"a request failed with HTTP 500 ({runtime or 'the server'}): read the lines around it",
                   line, at, runtime, status=500)
    return None


def _llama(line: str, at, rt) -> Optional[dict]:
    if m := _TRUNC.search(line):
        n_ctx, keep, left = (int(x) for x in m.groups()[:3])
        prompt = int(m.group(4)) if m.group(4) else None
        return _ev("prompt-trimmed", f"llama-server cut the prompt to fit its slot window of {n_ctx:,}" +
                   (f" ({prompt:,} tokens sent)" if prompt else "") + ": a smaller prompt (compact) or a bigger "
                   "--ctx-size", line, at, rt, window_sent=n_ctx, limit=n_ctx, keep=keep, n_left=left, prompt=prompt)
    if m := _SHIFT.search(line):
        return _ev("prompt-trimmed", f"llama-server shifted its context: {int(m.group(3)):,} tokens of the conversation "
                   "dropped to make room (the window filled)", line, at, rt, keep=int(m.group(1)),
                   n_left=int(m.group(2)), discarded=int(m.group(3)), shift=True)
    if "exceeds the available context size" in line:
        return _ev("prompt-trimmed", "llama-server refused a prompt larger than its slot window (HTTP 400): compact "
                   "before the call, or start it with a bigger --ctx-size", line, at, rt, refused=True)
    if m := _LIMIT.search(line):
        n = int(m.group(1))
        return _ev("reply-cut", f"a reply stopped at the server's own n_predict ({n:,} tokens): its -n / --n-predict, "
                   "or the request's max_tokens", line, at, rt, n_predict=n)
    if "context shift is disabled" in line:
        return _ev("window-full", "the window filled mid-reply and llama-server stopped (context shift is off): keep "
                   "a reply reserve and compact", line, at, rt)
    if "failed to load model" in line or "error loading model" in line or "exiting due to model loading error" in line:
        return _ev("load-failed", f"llama-server failed to load the model: {line.strip()[-160:]}", line, at, rt)
    if "ggml_cuda_init" in line or "found 1 CUDA devices" in line:
        return None  # the device list at start, not an error
    return None


def _lmstudio(line: str, at, rt) -> Optional[dict]:
    low = line.lower()
    if _LMS_OVER.search(line) or "context the overflows" in low or "context overflow" in low:
        w, keep = _LMS_OVER.search(line), _LMS_KEEP.search(line)
        n = int(w.group(1)) if w else None
        return _ev("prompt-trimmed", "LM Studio could not fit the prompt in the model's loaded context" +
                   (f" of {n:,} tokens" if n else "") + ": load it with a larger Context Length, or compact first",
                   line, at, rt, window_sent=n, limit=n, keep=int(keep.group(1)) if keep else None)
    if '"finish_reason": "length"' in line or '"finish_reason":"length"' in line:
        return _ev("reply-cut", "a reply stopped at its length limit (finish_reason length)", line, at, rt)
    if "failed to load" in low or "error loading model" in low:
        return _ev("load-failed", f"LM Studio failed to load the model: {line.strip()[-160:]}", line, at, rt)
    return None


def _mlx(line: str, at, rt) -> Optional[dict]:
    low = line.lower()
    if "insufficient memory" in low or "outofmemory" in low.replace(" ", ""):
        return _ev("gpu-memory", "Metal ran out of memory (the unified memory the model, its cache and the rest of the "
                   "Mac share)", line, at, rt)
    if re.match(r"^\w*(Error|Exception): ", line.strip()):
        return _ev("other-error", f"mlx_lm.server raised {line.strip()[:160]}", line, at, rt)
    return None


def classify(line: str, at=None, runtime: Optional[str] = None) -> Optional[dict]:
    """One line of a local server's log -> an event, or None."""
    text = str(line or "").rstrip("\r\n")
    if not text.strip() or text.startswith("--- halo starts:"):
        return None
    at = at if at is not None else line_time(text)
    rt = runtime or "llama-server"
    if rt == "llama-server" and "allocate" not in text and (m := _RPC_LOST.search(text)):  # 3.3.8.0 R4: a pool's RPC backend (rules_pool.py)
        addr = next((g for g in m.groups() if g), None)
        abort = "crashed or returned malformed" in text
        return _ev("rpc-lost", "an RPC backend of the pool was lost" + (f" ({addr})" if addr else "") +
                   (": llama-server aborted the request" if abort else ""), text, at, rt, addr=addr,
                   death=abort or None, mismatch="version mismatch" in text.lower() or None)
    if _DEATH.search(text):
        return _ev("other-error", f"{'LM Studio' if rt == 'lmstudio' else rt} died: {text.strip()[:160]}", text, at, rt,
                   death=True)
    got = _status(text, at, rt)
    if got is None:
        got = {"llama-server": _llama, "lmstudio": _lmstudio, "mlx": _mlx}.get(rt, _llama)(text, at, rt)
    if got is None and rt != "mlx":
        got = classify_llama(text, at=at)  # the llama.cpp lines Ollama embeds: spills, CUDA, print_timing
        if got is not None:
            if got["kind"] in ("startup", "client-gave-up", "queue-full", "cancel-task", "no-user-query", "spec-decode"):
                return None  # Ollama's own vocabulary ([GIN], its scheduler): not this server's
            got["data"]["runtime"] = rt
    if got is None and "[ERROR]" in text:
        got = _ev("other-error", f"the server logged an error: {text.strip()[-160:]}", text, at, rt)
    return got
