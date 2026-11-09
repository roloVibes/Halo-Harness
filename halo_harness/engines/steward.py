"""halo_harness.engines.steward -- the steward reads an engine's server through its descriptor: one log reader for every
engine (server_rules_hf.classify and server_context_hf.Rules hand an engine's lines here), the queue read where the
descriptor has `stats`, and one rule that turns the events into findings with the descriptor's sentence and fix.

    classify(line, at=None, runtime=..., model=None) -> event | None   the first descriptor pattern that matches (and
        whose conditions hold): kind = descriptors.WORDS[word] (loaded -> load-result, error -> other-error, timing ->
        timing, the rest engine-<word>), say = the descriptor's sentence with the line's numbers
    EngineRules(runtime).feed(line, at=None) -> [event]   the model from Halo's start line, the load timed from it, a
        slow-load past three minutes
    stats(server, *, timeout=1.0) -> [event]   an `engine-waiting` event when the /health `live` block or /metrics say
        requests wait
    findings(ctx) -> [finding]   one per engine group and word (slots, waiting, backend-fallback, disk-bound, loading),
        keyed `<server>|<model>`, the newest event's sentence and the descriptor's fix line -- never applied by itself
"""

from __future__ import annotations

import datetime as _dt
import json
import re
from typing import Optional

from halo_harness.engines.descriptors import SEVERITY, WORDS, get
from halo_harness.ollama_steward.server_rules import SLOW_LOAD_S, event

_ANSI = re.compile(r"\x1b(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
_NAME = re.compile(r"(?:--served-model-name|--name|--alias|--model)\s+(\S+)")
_SAMPLE = re.compile(r"^([A-Za-z_:][\w:]*)(?:\{[^}]*\})?\s+([-+0-9.eE]+|NaN)\s*$")
FINDS = ("slots", "waiting", "backend-fallback", "disk-bound", "loading")


def _num(v):
    try:
        return int(v) if re.fullmatch(r"-?\d+", str(v)) else float(v)
    except (TypeError, ValueError):
        return v


def _holds(cond: tuple, groups: dict, model) -> bool:
    key, op, want = cond
    got = str(model or "").lower() if key == "model" else _num(groups.get(key))
    if op == "has":
        return str(want) in str(got)
    if not isinstance(got, (int, float)):
        return False
    return got < want if op == "<" else got >= want if op == ">=" else want[0] <= got <= want[1]


def line_time(d: dict, text: str) -> "tuple[Optional[float], str]":
    """The line's own stamp (epoch seconds) and the line without it."""
    rx = d["log"].get("stamp")
    m = re.match(rx, text) if rx else None
    if not m:
        return None, text
    try:
        t = _dt.datetime.strptime(f"{m.group(1)} {m.group(2)}", "%Y-%m-%d %H:%M:%S")
        return (t.replace(tzinfo=_dt.timezone.utc) if d["log"].get("utc") else t).timestamp(), text[m.end():]
    except (ValueError, OSError, OverflowError):
        return None, text[m.end():]


def classify(line: str, at=None, runtime: Optional[str] = None, model=None) -> Optional[dict]:
    d = get(runtime)
    text = _ANSI.sub("", str(line or "")).rstrip("\r\n")
    if d is None or not text.strip() or text.startswith("--- halo starts:"):
        return None
    t, body = line_time(d, text)
    for word, rx, sentence, *conds in d["log"]["patterns"]:
        m = re.search(rx, body)
        if m is None or not all(_holds(c, m.groupdict(), model) for c in conds):
            continue
        groups = {k: v for k, v in m.groupdict().items() if v is not None}
        say = sentence.format_map({**{k: "?" for k in re.findall(r"\{(\w+)\}", sentence)}, **groups})
        data = {k: _num(v) for k, v in groups.items()}
        if word == "timing":
            data["phase"] = "prefill" if "prefill" in sentence else "decode"
            if data["phase"] == "decode":
                data["eval_tok_s"] = data.get("tok_s")
        ev = event(WORDS[word], say, text, at=t if t is not None else at, runtime=d["id"], word=word,
                   notable=bool(conds) or None, **{k: v for k, v in data.items() if k not in ("runtime", "word")})
        ev["severity"] = SEVERITY[word]
        return ev
    return None


class EngineRules:
    """server_context_hf.Rules for an engine's server: the model from Halo's start line, the load timed from it."""

    def __init__(self, runtime: str) -> None:
        self.runtime, self.d = runtime, get(runtime)
        self.model: Optional[str] = None
        self.load_at: Optional[float] = None
        self.clock: Optional[float] = None

    def feed(self, raw: str, at=None) -> list:
        text = _ANSI.sub("", str(raw or "")).rstrip("\r\n")
        t, _body = line_time(self.d, text)
        self.clock = t if t is not None else (at if at is not None else self.clock)
        if text.startswith("--- halo starts:"):
            m = _NAME.search(text)
            if m and self.d["log"].get("names_model", True):
                self.model = m.group(1).rstrip("/\\").replace("\\", "/").rsplit("/", 1)[-1]
            self.load_at = self.clock
            return []
        ev = classify(text, at=at, runtime=self.runtime, model=self.model)
        if ev is None:
            return []
        ev["model"] = ev.get("model") or self.model
        out = [ev]
        if ev["kind"] == "load-result":
            took = ev["data"].get("load_s")
            if not isinstance(took, (int, float)) and isinstance(self.clock, (int, float)) and isinstance(
                    self.load_at, (int, float)):
                took = ev["data"]["load_s"] = max(0.0, self.clock - self.load_at)
            if isinstance(took, (int, float)) and took > SLOW_LOAD_S:
                out.append(event("slow-load", f"a load took {took:.0f} s (over 3 minutes): {self.d['label']} reads the "
                                 "model into memory first", text, at=ev["at"], model=self.model, runtime=self.runtime,
                                 seconds=took))
        return out

    def flush(self) -> list:
        return []


def _get(url: str, key: Optional[str], timeout: float) -> "tuple[int, str]":
    import http.client
    import urllib.parse
    from halo_harness.providers.http import UpstreamConnectError, open_upstream
    u, conn = urllib.parse.urlparse(url), None
    try:
        conn = open_upstream(u.hostname or "127.0.0.1", u.port or 80, u.scheme == "https", connect_timeout=max(1, int(timeout)))
        if conn.sock:
            conn.sock.settimeout(timeout)
        conn.request("GET", u.path or "/", headers={"Accept-Encoding": "identity",
                                                    **({"Authorization": f"Bearer {key}"} if key else {})})
        resp = conn.getresponse()
        return resp.status, resp.read().decode("utf-8", "replace")
    except (UpstreamConnectError, OSError, http.client.HTTPException, ValueError):
        return 0, ""
    finally:
        if conn is not None:
            conn.close()


def stats(server, *, timeout: float = 1.0) -> list:
    d = get(getattr(server, "runtime", None))
    st = (d or {}).get("stats")
    if not st:
        return []
    from halo_harness.ollama_steward.servers_hf import base
    root = base(getattr(server, "url", ""))
    code, body = _get(f"{root}{d['health']}", None, timeout)
    try:
        live = (json.loads(body) or {}).get(st["live"]) if code == 200 else None
    except (ValueError, AttributeError):
        live = None
    if isinstance(live, dict):
        waiting, conns = int(live.get("waiting") or 0), int(live.get("connections") or 0)
        nums = {"running": conns - waiting, "waiting": waiting, "source": d["health"]}
    else:
        from halo_harness.engines.adapter import key
        mine = str(getattr(server, "name", "")).lower() == d["id"]
        code, text = _get(f"{root}{st['metrics']}", key(d["id"]) if mine else None, timeout)
        m = {g.group(1): float(g.group(2)) for x in text.splitlines() if (g := _SAMPLE.match(x.strip()))} if code == 200 else {}
        if st["waiting"] not in m:
            return []
        nums = {"running": int(m.get(st["running"]) or 0), "waiting": int(m[st["waiting"]]),
                "lanes": int(m[st["lanes"]]) if st["lanes"] in m else None, "source": st["metrics"]}
    if nums["waiting"] <= 0:
        return []
    say = f"{nums['waiting']} requests waiting, {nums['running']} running ({nums['source']})"
    ev = event("engine-waiting", say, f"GET {root}{nums['source']}: {json.dumps(nums)}", model=getattr(server, "model", None),
               runtime=d["id"], word="waiting", **nums)
    ev["severity"] = "warn"
    return [ev]


def findings(ctx: dict) -> list:
    from halo_harness.ollama_steward.ledger import parse_at
    from halo_harness.ollama_steward.rules import finding, hint
    from halo_harness.ollama_steward.server_rules_hf import not_asked
    out: list = []
    for g in ctx.get("groups") or []:
        d = get(g.get("runtime"))
        if d is None:
            continue
        who = g.get("server") or g["host"]
        loads = [parse_at(e.get("at")) or 0 for e in g["events"] if e.get("kind") == "load-result"]
        for word in FINDS:
            evs = [e for e in g["events"] if e.get("kind") == WORDS[word]]
            if word == "loading":  # past once the server is up, unless the line crossed a threshold (a slow stage)
                evs = [e for e in evs if (e.get("data") or {}).get("notable") or (parse_at(e.get("at")) or 0) > max(loads, default=-1)]
            if not evs:
                continue
            last = evs[-1]
            fix, cost = d["fixes"].get(word, (None, None))
            text = (f"{g['model']} on {who}: {last.get('say')}" + (f" ({len(evs)} lines)" if len(evs) > 1 else "")
                    + (f" -- {fix}" if fix else ""))
            f = finding(WORDS[word], g, SEVERITY[word], text, events=evs[-8:], numbers=dict(last.get("data") or {}),
                        server_hint=hint(None, f"{fix} on {who}", cost) if fix else None)
            f.update(server=who, runtime=d["id"], not_asked=not_asked(d["id"]), applied=False, verified=d["verified"])
            out.append(f)
    return out
