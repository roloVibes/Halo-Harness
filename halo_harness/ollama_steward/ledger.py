"""halo_harness.ollama_steward.ledger -- Halo 3.3.4.0 R2: every call to a
local model server leaves one line in `<state>/ollama/traffic.jsonl`.

    record_call(state_dir, line)  one JSON line, appended under a file lock;
                                  the file rotates to `traffic.1.jsonl` at 20 MB
    read_calls(state_dir, since=None, host=None, model=None)
                                  the lines back, oldest first (the rotated
                                  file, then the current one)
    record_probe(host, model, ...) a calibration load's line (kind "calibrate",
                                  providers/ollama_calibrate_steps.measure_step);
                                  ledger_call.py writes every other call's

A line (`blank_line` has every field, `None` when unknown):

    at, host {name, url}, model, ref, dialect ("ollama" | "openai"), kind
    ("turn" | "compaction" | "calibrate" | "small" | "repair"), num_ctx_sent,
    window_source, estimate_tokens, prompt_eval_count, eval_count,
    done_reason, total_ms, load_ms, prompt_eval_ms, eval_ms, eval_tok_s,
    trimmed, status (200 | 400 | 499 | 500 | 503 | ... | "timeout" |
    "connection"), error, retry, session, turn, tools_count, images, from,
    switched_from (3.3.5.0 R0: the previous call's model in this session when
    it differs), fitted (a switch step ran before this call), body_flags
    (3.3.5.0 R0b: {think, tools, images} -- the think value the body sent,
    None when it sent none; whether it carried a tool catalog and images)

`from` is this machine's fleet name while it has joined a hub (None
otherwise); the hub sets it to the member's name on the lines a member
forwards (fleet/ollama_share.py). `ollama.ledger: false` turns recording
off. A write that fails is logged at DEBUG and never fails the call.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Optional

log = logging.getLogger("bridge")

TRAFFIC_FILE = "traffic.jsonl"
ROTATED_FILE = "traffic.1.jsonl"
ROTATE_BYTES = 20 * 2 ** 20
KINDS = ("turn", "compaction", "calibrate", "small", "repair")
FIELDS = ("at", "host", "model", "ref", "dialect", "kind", "num_ctx_sent", "window_source", "estimate_tokens",
          "prompt_eval_count", "eval_count", "done_reason", "total_ms", "load_ms", "prompt_eval_ms", "eval_ms",
          "eval_tok_s", "trimmed", "status", "error", "retry", "session", "turn", "tools_count", "images", "from",
          "switched_from", "fitted", "body_flags")
_SINCE_RE = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*([smhdw]?)\s*$", re.IGNORECASE)
_UNIT_S = {"": 3600, "s": 1, "m": 60, "h": 3600, "d": 86400, "w": 7 * 86400}


def ledger_dir(state_dir) -> Path:
    return Path(state_dir) / "ollama"


def traffic_path(state_dir) -> Path:
    return ledger_dir(state_dir) / TRAFFIC_FILE


def enabled() -> bool:
    """`ollama.ledger` (default true); anything but a plain `false` keeps it on."""
    try:
        from halo_harness.theme import get_config_value
        return get_config_value("ollama.ledger", default=True) is not False
    except Exception:
        return True


def this_machine() -> Optional[str]:
    """This machine's fleet name while it has joined a hub, else None."""
    try:
        from halo_harness.fleet import identity, store
        return identity.fleet_name() if store.has_hubs() else None
    except Exception:
        return None


def now_iso(ts: Optional[float] = None) -> str:
    import datetime as _dt
    t = _dt.datetime.fromtimestamp(time.time() if ts is None else ts, _dt.timezone.utc)
    return t.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def parse_at(text) -> Optional[float]:
    """An `at` value back to epoch seconds (None when it does not parse)."""
    import datetime as _dt
    try:
        return _dt.datetime.fromisoformat(str(text).replace("Z", "+00:00")).timestamp()
    except (TypeError, ValueError):
        return None


def parse_since(text) -> Optional[float]:
    """"1h" / "24h" / "7d" / "30m" / "90s" / a bare number of hours -> seconds."""
    if text is None or text == "":
        return None
    m = _SINCE_RE.match(str(text))
    if not m:
        raise ValueError(f"--since takes a span such as 1h, 24h or 7d, got {text!r}")
    return float(m.group(1)) * _UNIT_S[m.group(2).lower()]


def blank_line(**values) -> dict:
    """A line with every field, the defaults filled (`kind` "turn", `retry`
    0, `trimmed` False, `images` 0, `at` now, `from` this machine)."""
    line = {k: None for k in FIELDS}
    line.update(kind="turn", retry=0, trimmed=False, images=0, fitted=False)
    line.update(values)
    if not line.get("at"):
        line["at"] = now_iso()
    if "from" not in values:
        line["from"] = this_machine()
    return line


def _ms(ns) -> Optional[float]:
    return round(ns / 1e6, 1) if isinstance(ns, (int, float)) and not isinstance(ns, bool) else None


def timing_fields(t: dict) -> dict:
    """Ollama's nanosecond fields -> the line's milliseconds and the eval rate."""
    t = t or {}
    ev, ev_ns = t.get("eval_count"), t.get("eval_duration")
    rate = round(ev / (ev_ns / 1e9), 2) if isinstance(ev, int) and isinstance(ev_ns, (int, float)) and ev_ns > 0 \
        else None
    return {"prompt_eval_count": t.get("prompt_eval_count"), "eval_count": ev, "total_ms": _ms(t.get("total_duration")),
            "load_ms": _ms(t.get("load_duration")), "prompt_eval_ms": _ms(t.get("prompt_eval_duration")),
            "eval_ms": _ms(ev_ns), "eval_tok_s": rate}


def same_file(saved_head: str, head: str) -> bool:
    """Is a file whose first bytes are `head` the one whose first bytes were
    `saved_head`? (A short file grows, so one may be a prefix of the other.)"""
    return head.startswith(saved_head) or saved_head.startswith(head)


def _rotate(path: Path) -> None:
    try:
        if path.stat().st_size >= ROTATE_BYTES:
            os.replace(path, path.with_name(ROTATED_FILE))
    except OSError:
        pass


def append_lines(state_dir, lines: "list[dict]") -> int:
    """Append whole lines (the hub's side, and `record_call`'s); returns how
    many were written."""
    if not lines:
        return 0
    from halo_harness.filelock import file_lock
    path = traffic_path(state_dir)
    data = "".join(json.dumps(x, ensure_ascii=False, default=str) + "\n" for x in lines)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with file_lock(path, timeout=2.0):
            _rotate(path)
            with open(path, "a", encoding="utf-8", newline="\n") as f:
                f.write(data)
        return len(lines)
    except OSError:
        log.debug("ollama ledger: could not write %s", path, exc_info=True)
        return 0


def record_call(state_dir, line: dict) -> Optional[Path]:
    """Append one call's line (missing fields filled by `blank_line`); None
    when the ledger is off, the state dir is unknown or the write failed."""
    if state_dir is None or not enabled():
        return None
    full = blank_line(**{k: v for k, v in (line or {}).items()})
    return traffic_path(state_dir) if append_lines(state_dir, [full]) else None


def _iter_file(path: Path):
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            for raw in f:
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    obj = json.loads(raw)
                except ValueError:
                    continue
                if isinstance(obj, dict):
                    yield obj
    except OSError:
        return


def host_matches(line: dict, host: Optional[str]) -> bool:
    if not host:
        return True
    h = line.get("host") or {}
    want = host.lower()
    return isinstance(h, dict) and want in (str(h.get("name") or "").lower(), str(h.get("url") or "").lower())


def model_matches(line: dict, model: Optional[str]) -> bool:
    if not model:
        return True
    have = str(line.get("model") or "").lower()
    want = model.lower()
    return have == want or have == f"{want}:latest" or have.split(":")[0] == want


def read_calls(state_dir, since=None, host: Optional[str] = None, model: Optional[str] = None,
               kind: Optional[str] = None) -> "list[dict]":
    """Every line, oldest first; `since` is seconds back from now (or a
    span such as "1h"), `host` a host name or url, `model` a model name."""
    if isinstance(since, str):
        since = parse_since(since)
    cutoff = time.time() - since if isinstance(since, (int, float)) else None
    d = ledger_dir(state_dir)
    out = []
    for path in (d / ROTATED_FILE, d / TRAFFIC_FILE):
        for line in _iter_file(path):
            if cutoff is not None:
                t = parse_at(line.get("at"))
                if t is None or t < cutoff:
                    continue
            if host_matches(line, host) and model_matches(line, model) and (not kind or line.get("kind") == kind):
                out.append(line)
    return out


def record_probe(host, model: str, *, num_ctx: int, reply, elapsed_s: float, state_dir=None) -> None:
    """One calibration load (`/api/chat` with `num_predict: 1`) as a line of kind `calibrate`."""
    try:
        if state_dir is None:
            from halo_harness.config.paths import bridge_home
            state_dir = bridge_home()
        failure = getattr(reply, "failure", None)
        status = {None: 200, "timeout": "timeout", "unreachable": "connection"}.get(
            failure, getattr(reply, "status", None) or 500)
        body = getattr(reply, "body", None) if isinstance(getattr(reply, "body", None), dict) else {}
        line = {"host": {"name": getattr(host, "name", None), "url": getattr(host, "url", None)}, "model": model,
                "dialect": "ollama", "kind": "calibrate", "num_ctx_sent": num_ctx, "window_source": "calibration step",
                "estimate_tokens": None, "status": status, "done_reason": body.get("done_reason"),
                "error": None if failure is None else f"calibration load {failure} after {elapsed_s:.1f} s",
                **timing_fields(body)}
        line["total_ms"] = line.get("total_ms") or round(elapsed_s * 1000, 1)
        record_call(state_dir, line)
    except Exception:
        log.debug("ollama ledger: recording a calibration load failed", exc_info=True)
