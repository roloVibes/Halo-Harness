"""halo_harness.ollama_steward.ledger_call -- Halo 3.3.4.0 R2: the ledger's writer.
`observe_call(session, req, gen, kind=...)` wraps the event stream of one model
call (`agent/loop.py`'s `_stream`, the one place every turn, compaction,
small-model and repair call is dispatched): for a call to a LOCAL server -- an
`ol:` host that is not Ollama's own cloud (native or `dialect: openai`), an
`hf:local/*` / `hf:mlx/*` server -- it passes every event through unchanged and,
once the call's facts are in hand (the final `message_delta`, a wire error, a
phase-1 exception, the caller closing the stream early), writes one ledger line.
Any other call gets its stream back untouched. (`ledger.record_probe` writes a
calibration load's line; 3.3.5.0 R4: ledger_prompt.py adds the prompt's
composition, its prefix, the preflight's decision, warming and the cache.)
`retry` counts the calls of one turn that immediately follow a failed or trimmed one (0 for a first send); a clean
answer resets it. 3.3.6.0 R3: `log_events`, the kinds the server log showed (agent/ollama_log_recovery.py).
"""

from __future__ import annotations

import logging
import re
import time
import urllib.parse
from typing import Optional

from halo_harness.ollama_steward import ledger
from halo_harness.ollama_steward.ledger_prompt import finish as prompt_finish, prompt_fields

log = logging.getLogger("bridge")

_TIMEOUT_RE = re.compile(r"timed out|timeout", re.IGNORECASE)
_HF_CLOUD = ("huggingface.co", "huggingface.cloud", "hf.space")


def _netloc(url: str) -> str:
    try:
        return urllib.parse.urlparse(url or "").netloc or (url or "")
    except ValueError:
        return url or ""


def _hostname(url: str) -> str:
    return (_netloc(url).rsplit("@", 1)[-1].split(":")[0] or "").lower()


def _base(url: str) -> str:
    """A host url without its trailing "/" or "/v1" (an OpenAI-dialect host's chat base adds it)."""
    u = str(url or "").rstrip("/")
    return u[:-3] if u.endswith("/v1") else u


def local_target(session, req) -> Optional[dict]:
    """`{host: {name, url}, dialect}` when `req` goes to a local server, else None."""
    route = getattr(req, "route", None)
    creds = getattr(req, "creds", None)
    url = str(getattr(creds, "base_url", "") or "").rstrip("/")
    provider = getattr(route, "provider", None)
    dialect = "ollama" if getattr(route, "dialect", None) == "ollama" else "openai"
    if provider == "ollama":
        if _hostname(url) == "ollama.com" or _hostname(url).endswith(".ollama.com"):
            return None  # Ollama's own cloud
        from halo_harness.providers.ollama import resolve_ollama_hosts
        env = getattr(getattr(session, "settings", None), "effective_env", None)
        try:
            hosts = resolve_ollama_hosts(env)
        except Exception:
            hosts = []
        host = next((h for h in hosts if _base(h.url) == _base(url)), None)
        name, url = (host.name, str(host.url).rstrip("/")) if host is not None else (_netloc(url), url)
        return {"host": {"name": name, "url": url}, "dialect": dialect}
    if provider == "huggingface" and route is not None and getattr(route, "dialect", None) == "openai-chat":
        hostname = _hostname(url)
        if not hostname or any(hostname == d or hostname.endswith("." + d) for d in _HF_CLOUD):
            return None
        return {"host": {"name": _netloc(url), "url": url}, "dialect": "openai"}
    return None


def _body(req) -> dict:
    for key in ("prebuilt_ollama_body", "prebuilt_oai_body", "body"):
        b = getattr(req, key, None)
        if isinstance(b, dict) and b:
            return b
    return {}


def _images(body: dict) -> int:
    n = 0
    for msg in body.get("messages") or []:
        if isinstance(msg, dict):
            n += len(msg.get("images") or []) if isinstance(msg.get("images"), list) else 0
        if isinstance(msg, dict) and isinstance(msg.get("content"), list):
            n += sum(1 for p in msg["content"] if isinstance(p, dict) and p.get("type") in ("image_url", "image"))
    return n


def body_flags(body: dict) -> dict:
    """3.3.5.0 R0b: what the body asked of the model -- the think value sent (None: no field), a tool catalog,
    images -- so the steward can hold a call against the model's card (rule `called-wrong`)."""
    think = body.get("think")
    if think is None:
        think = body.get("reasoning_effort")
    return {"think": think, "tools": bool(body.get("tools")), "images": _images(body) > 0}


def _window(session, url: str, body: dict) -> dict:
    """The window sent, its source and the estimate `prepare_window` made."""
    opts = body.get("options") if isinstance(body.get("options"), dict) else {}
    num_ctx = opts.get("num_ctx")
    sent = (getattr(session, "_ollama_window_state", None) or {}).get("sent") or {}
    rec = sent.get((url, body.get("model"))) or {}
    if rec:
        source = rec.get("source") if rec.get("num_ctx") == num_ctx else "trim resend"
        return {"num_ctx_sent": num_ctx, "window_source": source, "estimate_tokens": rec.get("estimate"),
                "_reserve": rec.get("reserve") or 1024}
    from halo_harness.providers.ollama_prompt import estimate_request_tokens
    reply = opts.get("num_predict") or body.get("max_tokens") or body.get("max_completion_tokens")
    est = estimate_request_tokens(body.get("messages"), body.get("tools"), "", reply_tokens=reply)
    return {"num_ctx_sent": num_ctx, "window_source": ("request" if num_ctx else "server default"),
            "estimate_tokens": est, "_reserve": max(1024, reply or 0) if isinstance(reply, int) else 1024}


def error_status(exc) -> "tuple[object, str]":
    """(status, one line) for a phase-1 exception."""
    from halo_harness.providers.stream import ContextOverflow
    if isinstance(exc, ContextOverflow):
        return 400, f"the prompt ({exc.prompt_tokens} tokens) is larger than the window ({exc.limit})"
    msg = str(getattr(exc, "message", None) or exc).strip().splitlines()[0][:300] if str(exc).strip() else ""
    from halo_harness.providers.http import is_connect_failure_message
    if is_connect_failure_message(msg):
        return "connection", msg
    if _TIMEOUT_RE.search(msg):
        return "timeout", msg
    status = getattr(exc, "upstream_status", None) or getattr(exc, "status", None)
    return (status if isinstance(status, int) else 500), msg


def _bump_retry(session, kind: str, line: dict) -> int:
    if kind != "turn" or session is None:
        return 0
    box = getattr(session, "_ollama_ledger_resend", None) or {}
    turn = getattr(session, "turn_count", None)
    n = box.get("n", 0) if box.get("turn") == turn else 0
    bad = line.get("status") != 200 or line.get("trimmed") or line.get("done_reason") == "length"
    session._ollama_ledger_resend = {"turn": turn, "n": (n + 1) if bad else 0}
    return n


def _write(session, req, kind: str, target: dict, base: dict, extra: dict) -> None:
    try:
        line = {**base, **extra}
        reserve = line.pop("_reserve", 1024)
        if target["dialect"] == "ollama" and line.get("status") == 200 and not line.get("trimmed"):
            from halo_harness.providers.ollama_prompt import is_trimmed
            line["trimmed"] = bool(is_trimmed(line.get("prompt_eval_count"), line.get("estimate_tokens"), reserve))
        line["retry"] = _bump_retry(session, kind, line)
        prompt_finish(line, reserve)  # 3.3.5.0 R4: warming, cache_reused_pct
        from halo_harness.agent.ollama_log_recovery import ledger_kinds  # 3.3.6.0 R3: what the server log showed
        line["log_events"] = ledger_kinds(session, target, line)
        ledger.record_call(getattr(session, "state_dir", None) or getattr(req, "state_dir", None), line)
    except Exception:
        log.debug("ollama ledger: recording a call failed", exc_info=True)


def observe_call(session, req, gen, *, kind: str = "turn", abort=None):
    """`gen` back unchanged for a call that is not to a local server or
    when the ledger is off; else a generator that records the call."""
    try:
        target = local_target(session, req)
    except Exception:
        target = None
    if target is None or not ledger.enabled():
        return gen
    return _observed(session, req, gen, kind, abort, target)


def _observed(session, req, gen, kind, abort, target):
    from halo_harness.providers.errors import PROMPT_TRIMMED
    from halo_harness.providers.stream import ProviderNotConfigured
    body = _body(req)
    t0 = time.monotonic()
    log_ = getattr(session, "log", None)
    model = body.get("model") or getattr(getattr(req, "route", None), "upstream_model", None)
    own = getattr(session, "model_ref", None)
    base = {"host": target["host"], "model": model,
            "ref": getattr(own, "raw", None) if getattr(own, "model", None) == model else None,
            "dialect": target["dialect"], "kind": kind, "tools_count": len(body.get("tools") or []),
            "images": _images(body), "body_flags": body_flags(body), "session": getattr(log_, "session_id", None),
            "turn": getattr(session, "turn_count", None)}
    base.update(_window(session, target["host"]["url"], body))
    from halo_harness.ollama_steward.ledger_switch import switch_fields  # 3.3.5.0 R0
    base.update(switch_fields(session, model, kind), **prompt_fields(session, kind))  # R4: the prompt budget
    from halo_harness.ollama_steward.ledger_bytes import body_bytes, event_bytes  # 3.3.5.0 R1
    base.update(bytes_in=body_bytes(body), bytes_out=0)
    wall = lambda: round((time.monotonic() - t0) * 1000, 1)  # noqa: E731
    done = False
    answer: dict = {}  # the final message_delta's facts, written when the stream ends (usage may follow it)

    def _answered() -> None:
        extra = {"status": 200, "error": None, **answer}
        if target["dialect"] == "openai":
            usage = answer.get("_usage") or {}
            extra.update(prompt_eval_count=usage.get("input_tokens"), eval_count=usage.get("output_tokens"))
        extra.pop("_usage", None)
        extra["total_ms"] = extra.get("total_ms") or wall()
        _write(session, req, kind, target, base, extra)

    try:
        for ev in gen:
            kind_ev = ev.get("type") if isinstance(ev, dict) else None
            base["bytes_out"] += event_bytes(ev)
            if kind_ev == "message_delta" and not done:
                answer.setdefault("_usage", {}).update(ev.get("usage") or {})
                meta = ev.get("harness_meta") if isinstance(ev.get("harness_meta"), dict) else {}
                if target["dialect"] == "ollama" and meta:
                    answer.update(ledger.timing_fields(meta.get("timing_ns") or {}), done_reason=meta.get("done_reason"))
                stop = (ev.get("delta") or {}).get("stop_reason")
                if target["dialect"] == "openai" and stop:
                    answer["done_reason"] = "length" if stop == "max_tokens" else "stop"
            elif kind_ev == "error" and not done:
                msg = str((ev.get("error") or {}).get("message") or "")[:300]
                status = "connection" if "connection" in msg.lower() else ("timeout" if _TIMEOUT_RE.search(msg) else 500)
                done = True
                _write(session, req, kind, target, base, {"status": status, "error": msg, "total_ms": wall()})
            yield ev
    except GeneratorExit:
        if not done:
            if answer:
                _answered()
            else:
                _write(session, req, kind, target, base, {"status": 499, "total_ms": wall(),
                                                          "error": "Halo closed the call before the reply ended"})
        raise
    except ProviderNotConfigured:
        raise
    except Exception as e:
        if not done:
            status, msg = error_status(e)
            extra = {"status": status, "error": msg, "total_ms": wall()}
            if getattr(e, "err_type", None) == PROMPT_TRIMMED:
                extra["trimmed"] = True
            _write(session, req, kind, target, base, extra)
        raise
    if done:
        return
    if answer:
        _answered()
        return
    stopped = abort is not None and getattr(abort, "is_set", lambda: False)()
    _write(session, req, kind, target, base, {
        "status": 499 if stopped else "connection", "total_ms": wall(),
        "error": "interrupted before the reply ended" if stopped else "the stream ended without a reply"})
