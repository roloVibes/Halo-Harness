"""halo_harness.ollama_steward.tuner -- Halo 3.6.0.25 T: "Tune with <model>", a tuner model of the person's choice
reading what Halo measured about one local model. A role, not a brand: `ollama.tuner.model` (Settings, Local; EMPTY by
default; any reference Halo can call, picked with the model picker). With none set, nothing here runs and no request
is ever made.

    tuner_model() -> ref or None
    offer(state_dir, host, model) -> {tuner, sends, cost, writes, rounds}     said before a start
    facts(host, model, state_dir, *, client=None, card=None) -> the facts sent (scrubbed)
    scrub(text, host=None) -> text   no file path, no host name, no address, no user name
    run(state_dir, host, model, *, caller=None, stop=None, on_line=None, card=None, client=None, memory=None,
        send=None) -> {ok, tuner, rounds, cost, measured, kept, refused, dropped, texts, say}

It runs in the steward chat's FIXED-TOOL pattern (ollama_steward/chat.py): each round the model answers one JSON
object, at most ROUNDS rounds; the tools are Halo's own code (TOOLS): read the facts, read the sweep, ask Halo to
measure one more window (providers/local_sweep_run.sweep(only=), under the sweep's six-load cap; it becomes the pick
only by the sweep's own rule), and write the three texts (ollama_steward/tuner_notes.py: a diagnosis, server advice
from an allow-list, the model's guide). No shell, no file, no network tool. A proposal above the model's trained
window, or an option that does not exist, is refused and counted.
"""

from __future__ import annotations

import getpass
import json
import os
import re
import socket
import time
from typing import Callable, Optional

ROUNDS = 8
OUT_TOKENS = 600
SENDS = ("the model's facts from its header, the server's version and settings, the sweep's table and the card's "
         "size: no file path, no host name, no address, no user name")
WRITES = ("nothing to the Ollama store; up to three texts in Halo's notes (a diagnosis, server advice, a guide), each "
          "shown as written by {tuner}; a window it proposes is measured by Halo (the sweep's load cap) and becomes the "
          "pick only if it measures better")

HEAD = """You tune one local model on one Ollama server. Halo measured it and gives you the facts. Each reply is ONE \
JSON object and nothing else:
  {"tool": "<name>", "args": {...}}   to read or do one thing (you see its answer, then reply again)
  {"done": "<one line>"}              when you are finished
Use only the numbers you are given or a tool returns. You never run anything: Halo measures, and a person decides. \
The tools:"""

TOOLS = {
    "facts": ("{}", "the model's header facts, the server's version and settings, the card's size"),
    "sweep": ("{}", "the windows Halo measured: on the card / spilled / slow, free MiB, prompt and reply tok/s, the pick"),
    "measure": ('{"window": N}', "ask Halo to measure one more window (at most the model's trained window; the loads "
                                 "are capped); it becomes the pick only if it is larger and wholly on the card, before "
                                 "the speed cliff"),
    "write": ('{"kind": "diagnosis", "text": "..."} | {"kind": "advice", "settings": [{"key", "value", "why"}]} | '
              '{"kind": "guide", "best_at": [...], "avoid": [...], "text": "..."}',
              "a diagnosis (only when it does not load or spills at its start), server advice (settings: "
              "OLLAMA_KV_CACHE_TYPE, OLLAMA_FLASH_ATTENTION, OLLAMA_NUM_PARALLEL, OLLAMA_MAX_LOADED_MODELS, "
              "OLLAMA_CONTEXT_LENGTH, OLLAMA_KEEP_ALIVE, OLLAMA_ORIGINS, each with why), the guide (a few lines)"),
}


def tuner_model() -> Optional[str]:
    try:
        from halo_harness.theme import get_config_value
        v = get_config_value("ollama.tuner.model", default=None)
    except Exception:
        return None
    return v.strip() if isinstance(v, str) and v.strip() and v.strip().lower() not in ("none", "off") else None


def guide() -> str:
    return HEAD + "\n" + "\n".join(f"  {n} {a}: {w}" for n, (a, w) in TOOLS.items())


# ---- the scrub ----------------------------------------------------------------------------------------------------

_URL = re.compile(r"\b[a-z][a-z0-9+.-]*://[^\s\"'<>]+", re.I)
_IP4 = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}(?::\d+)?\b")
_IP6 = re.compile(r"(?<![\w:])(?=[0-9a-f:]*(?:::|[a-f]))(?:[0-9a-f]{0,4}:){2,7}[0-9a-f]{0,4}(?![\w:])", re.I)
_WIN = re.compile(r"\b[A-Za-z]:[\\/][^\s\"'<>]*")
_UNC = re.compile(r"\\\\[^\s\"'<>]+")
_POSIX = re.compile(r"(?<![\w.])(?:~|/(?:home|Users|root|mnt|media|opt|var|tmp|usr|etc|srv|private|Volumes))"
                    r"(?:/[^\s\"'<>]*)?")


def _names(host) -> list:
    out = set()
    for v in (os.environ.get("USERNAME"), os.environ.get("USER"), _safe(getpass.getuser), _safe(socket.gethostname),
              os.environ.get("COMPUTERNAME"), getattr(host, "name", None)):
        if isinstance(v, str) and len(v.strip()) >= 2:
            out.add(v.strip())
    try:
        from urllib.parse import urlparse
        h = urlparse(str(getattr(host, "url", "") or "")).hostname
        if h:
            out.add(h)
    except Exception:
        pass
    try:
        from halo_harness.providers.ollama import resolve_ollama_hosts
        for h in resolve_ollama_hosts():
            if isinstance(h.name, str) and len(h.name) >= 2:
                out.add(h.name)
    except Exception:
        pass
    return sorted(out, key=len, reverse=True)


def _safe(fn) -> Optional[str]:
    try:
        return fn()
    except Exception:
        return None


def scrub(text: str, host=None) -> str:
    s = _URL.sub("<address>", str(text))
    s = _UNC.sub("<path>", s)
    s = _WIN.sub("<path>", s)
    s = _POSIX.sub("<path>", s)
    s = _IP4.sub("<address>", s)
    s = _IP6.sub("<address>", s)
    for n in _names(host):
        s = re.sub(rf"(?<![\w-]){re.escape(n)}(?![\w-])", "<name>", s, flags=re.I)
    return s


# ---- the facts ----------------------------------------------------------------------------------------------------

_INFO = (".context_length", ".block_count", ".embedding_length", ".attention.head_count", ".attention.head_count_kv",
         ".expert_count", ".expert_used_count")


def facts(host, model: str, state_dir, *, client=None, card=None) -> dict:
    from halo_harness.providers import capability_battery as CB
    from halo_harness.providers import local_sweep as S
    from halo_harness.providers.ollama_hw import host_fit_settings, load_server
    client = client or CB.HostClient(host)
    version = (client.call("GET", "/api/version", timeout=10.0) or {}).get("version")
    row = CB._row(client.call("GET", "/api/tags", timeout=15.0), model) or {}
    show = client.call("POST", "/api/show", body={"model": model}, timeout=15.0) or {}
    info = show.get("model_info") or {}
    head = {k.split(".", 1)[-1]: v for k, v in info.items() if k.endswith(_INFO) and isinstance(v, (int, float))}
    d = row.get("details") or show.get("details") or {}
    settings = host_fit_settings(host)
    total = None
    if card:
        try:
            from halo_harness.ollama_steward.fit import card_budget
            total = card_budget(card).get("total")
        except Exception:
            total = None
    rec = S.load(state_dir, host.url, model, digest=row.get("digest"), server=load_server(host, version)) or {}
    table = [{k: r.get(k) for k in ("window", "state", "free_mib", "used_mib", "prompt_tok_s", "tok_s", "timed")}
             for r in sorted(rec.get("windows") or [], key=lambda r: r["window"])]
    return {"model": model, "family": d.get("family"), "parameter_size": d.get("parameter_size"),
            "quantization": d.get("quantization_level"), "format": d.get("format"), "size_bytes": row.get("size"),
            "header": head, "capabilities": show.get("capabilities") or [],
            "server": {"ollama_version": version, "kv_cache_type": settings.get("kv_cache_type"),
                       "parallel": settings.get("parallel")},
            "card_total_gib": round(total / 2 ** 30, 1) if isinstance(total, (int, float)) and total else "unknown",
            "sweep": {"windows": table, "pick": rec.get("pick"), "why": rec.get("why"), "loads_used": len(table),
                      "loads_cap": S.MAX_LOADS}}


def _text(obj, host) -> str:
    return scrub(json.dumps(obj, ensure_ascii=False, default=str), host)


def offer(state_dir, host, model: str, *, tuner: Optional[str] = None, card=None, client=None) -> dict:
    from halo_harness.checks.run import call_price
    from halo_harness.ollama_steward.agent_prompt import tokens
    tuner = tuner or tuner_model()
    if not tuner:
        return {"tuner": None, "line": "a tuner model of your choice could read Halo's measurements of this model and "
                "write a diagnosis, server advice and a guide; pick one in Settings (Tuner model) to offer it"}
    try:
        n = tokens(guide()) + tokens(_text(facts(host, model, state_dir, client=client, card=card), host))
    except Exception:
        n = tokens(guide()) + 1500
    tin = sum(n + i * 400 for i in range(ROUNDS))  # each round resends the context and the tools' answers so far
    return {"tuner": tuner, "sends": SENDS, "cost": call_price(tuner, tin, OUT_TOKENS * ROUNDS) + f" (at most {ROUNDS} rounds)",
            "writes": WRITES.format(tuner=tuner), "rounds": ROUNDS}


# ---- the job ------------------------------------------------------------------------------------------------------

def _parse(text: str) -> dict:
    from halo_harness.ollama_steward.chat import parse
    raw = str(text or "")
    try:
        from halo_harness.ollama_steward.chat import _FENCE, _THINK
        body = _THINK.sub("", raw)
        m = _FENCE.search(body)
        j = json.loads(m.group(1) if m else body[body.find("{"):body.rfind("}") + 1])
        if isinstance(j, dict) and isinstance(j.get("done"), str):
            return {"answer": j["done"]}
    except Exception:
        pass
    return parse(raw)


def run(state_dir, host, model: str, *, tuner: Optional[str] = None, caller: Optional[Callable] = None, stop=None,
        on_line: Optional[Callable[[str], None]] = None, card=None, client=None, memory=None, send=None,
        check_busy: bool = False) -> dict:
    from halo_harness.ollama_steward import tuner_notes as N
    from halo_harness.ollama_steward.chat import cost_words
    from halo_harness.ollama_steward.tune_lines import os_of
    from halo_harness.providers import capability_battery as CB
    from halo_harness.providers import local_sweep_run as SR
    say = on_line or (lambda _s: None)
    tuner = tuner or tuner_model()
    name = getattr(host, "name", "") or "this host"
    out = {"ok": False, "tuner": tuner, "model": model, "host": name, "rounds": 0, "measured": 0, "kept": 0,
           "refused": 0, "dropped": 0, "texts": {}, "cost": "", "cost_usd": None, "stopped": False}
    if not tuner:
        return {**out, "say": "no tuner model is set (Settings: Tuner model): nothing was sent"}
    if caller is None:
        from halo_harness.ollama_steward.agent import live_call
        caller = live_call
    why = CB.test_guard(host)
    if why:
        return {**out, "say": why}
    client = client or CB.HostClient(host)
    f = facts(host, model, state_dir, client=client, card=card)
    digest = (CB._row(client.call("GET", "/api/tags", timeout=15.0), model) or {}).get("digest")
    trained = (f.get("header") or {}).get("context_length")
    text = "The facts:\n" + _text(f, host)
    usage = {"input_tokens": 0, "output_tokens": 0, "cost_usd": None, "local": None}
    t0, end = time.monotonic(), ""
    for i in range(ROUNDS):
        if stop is not None and stop.is_set():
            out["stopped"] = True
            break
        out["rounds"] = i + 1
        try:
            reply = caller(tuner, guide(), text, state_dir=state_dir) or {}
        except Exception as e:
            end = f"the tuner did not answer ({type(e).__name__}: {str(e)[:160]})"
            break
        for k in ("input_tokens", "output_tokens"):
            usage[k] += int(reply.get(k) or 0)
        if isinstance(reply.get("cost_usd"), (int, float)):
            usage["cost_usd"] = (usage["cost_usd"] or 0.0) + reply["cost_usd"]
        usage["local"] = reply.get("local")
        p = _parse(reply.get("text"))
        if "tool" not in p:
            end = p.get("answer") or ""
            break
        tool, args = p["tool"], p["args"]
        if tool == "facts":
            ans = _text(facts(host, model, state_dir, client=client, card=card), host)
        elif tool == "sweep":
            ans = _text(facts(host, model, state_dir, client=client, card=card)["sweep"], host)
        elif tool == "measure":
            ans = _measure(state_dir, host, model, args, trained, out, card=card, client=client, memory=memory,
                           send=send, say=say)
        elif tool == "write":
            ans = _write(state_dir, host, model, args, out, tuner=tuner, digest=digest, trained=trained,
                         first=(f["sweep"]["windows"] or [{}])[0], os_name=os_of(host, card), N=N)
        else:
            out["refused"] += 1
            ans = f"no tool {tool!r}: the tools are {', '.join(TOOLS)}"
        say(f"round {i + 1}: {tool}: {ans[:200]}")
        text += f"\n\nTOOL {tool} {scrub(json.dumps(args, default=str), host)}:\n{scrub(ans, host)}"
    secs = time.monotonic() - t0
    out.update(ok=True, cost=cost_words(usage, tuner, secs), cost_usd=usage["cost_usd"], usage=usage, end=end)
    out["say"] = (f"{tuner} ran {out['rounds']} round{'s' if out['rounds'] != 1 else ''}"
                  + (" (stopped)" if out["stopped"] else "") + f", cost {out['cost']}; proposals: {out['measured']} "
                  f"measured, {out['kept']} kept, {out['refused']} refused; settings dropped: {out['dropped']}; "
                  f"wrote: {', '.join(out['texts']) or 'nothing'}")
    say(out["say"])
    return out


def _measure(state_dir, host, model, args: dict, trained, out: dict, **kw) -> str:
    from halo_harness.providers import local_sweep as S
    from halo_harness.providers import local_sweep_run as SR
    w = args.get("window")
    extra = sorted(set(args) - {"window"})
    if extra or not isinstance(w, int) or isinstance(w, bool) or w < S.FLOOR or (trained and w > trained):
        out["refused"] += 1
        return ("refused: " + (f"no option {', '.join(extra)}" if extra else f"{w!r} is not a window from {S.FLOOR:,} up to "
                f"the model's trained window ({trained or '?'})"))
    got = SR.sweep(host, model, state_dir=state_dir, only=w, check_busy=False, card=kw.get("card"), client=kw.get("client"),
                   memory=kw.get("memory"), send=kw.get("send"), on_line=kw.get("say"))
    if got.get("refused") or not got.get("ok"):
        out["refused"] += 1
        return f"refused: {got.get('say')}"
    if got.get("capped"):
        out["refused"] += 1
        return f"refused: {got.get('say')}"
    out["measured"] += 1
    rec = got["record"]
    if rec.get("pick") == w:
        out["kept"] += 1
    row = got.get("row") or {}
    return f"{S.row_line(row)}; the pick is now {rec.get('why') or 'none'}"


def _write(state_dir, host, model, args: dict, out: dict, *, tuner, digest, trained, first, os_name, N) -> str:
    from halo_harness.providers import local_sweep as S
    kind = str(args.get("kind") or "")
    if kind == "diagnosis":
        if first and S.good(first):
            out["refused"] += 1
            return "refused: the sweep shows the model loads wholly on the card at its start; no diagnosis is kept"
        txt = str(args.get("text") or "").strip()[:600]
        if not txt:
            out["refused"] += 1
            return "refused: a diagnosis needs its text"
        out["texts"]["diagnosis"] = N.put(state_dir, host.name, model, "diagnosis", {"text": txt}, by=tuner, digest=digest)
        return "kept: the diagnosis"
    if kind == "advice":
        kept, dropped = N.advice(args.get("settings"), trained=trained, os_name=os_name)
        out["dropped"] += dropped
        if not kept:
            return f"nothing kept: {dropped} setting{'s' if dropped != 1 else ''} not on the list (or without a reason)"
        out["texts"]["advice"] = N.put(state_dir, host.name, model, "advice", {"settings": kept, "dropped": dropped},
                                       by=tuner, digest=digest)
        return f"kept: {len(kept)} setting{'s' if len(kept) != 1 else ''} (shown with set / revert lines, never run); dropped {dropped}"
    if kind == "guide":
        lst = lambda v: [str(x).strip()[:160] for x in v][:6] if isinstance(v, list) else []  # noqa: E731
        g = {"text": str(args.get("text") or "").strip()[:800], "best_at": lst(args.get("best_at")),
             "avoid": lst(args.get("avoid"))}
        if not (g["text"] or g["best_at"] or g["avoid"]):
            out["refused"] += 1
            return "refused: a guide needs a text, best_at or avoid"
        out["texts"]["guide"] = N.put(state_dir, host.name, model, "guide", g, by=tuner, digest=digest)
        return "kept: the guide"
    out["refused"] += 1
    return f"refused: no kind {kind!r} (diagnosis, advice, guide)"
