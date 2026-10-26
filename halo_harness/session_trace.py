"""halo_harness.session_trace -- Halo 3.3.0.0 R6: a session as one Markdown
trace file (the owner: "an export button that saves it as an .md file, like
a tracer file so we can save detailed logs of sessions").

`trace_markdown(source, *, model, lineup, totals)` reads a session log (its
path: the main log and every sub-agent log under `<sid>/subagents/`; or the
main log's node list) and returns the trace: a header (the session id, the
model and the lineup, when it started and ended, the totals: turns, tool
calls, tokens in and out, cost), then one `###` entry per row in time order:
the clock, the agent (its tier and model), the kind -- a user prompt, the
assistant's text, a tool call (its name and a one-line argument summary),
the tool's result (fenced, at most 40 lines, then "... (N more lines)"), a
steer and its target, a nudge, a permission answer, the turn-end marker, a
compaction, an error, a rewind. Every text passes the redactor (redact.sanitize_text:
key shapes, `NAME=value` secrets, Bearer headers) and every path under a
user's home becomes `~` (privacy_rules.HOME_PATH_RE), so the file carries
no provider key and no home path. Pure: no network, no clock (the same log
gives the same bytes to `halo session export`, `/export` and Studio's
`GET sessions/<sid>/trace.md`).
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Optional

TRIM_LINES = 40
LINE_MAX = 400
NOT_A_PROMPT = frozenset({"compaction_summary", "compaction_tail", "continuation", "agent_notice", "job_notice",
                          "steer", "nudge"})
_ARG_KEYS = ("command", "file_path", "path", "pattern", "url", "query", "description", "prompt", "notebook_path")


def _scrub(text: str, home: str = "") -> str:
    from halo_harness.privacy_rules import HOME_PATH_RE
    from halo_harness.redact import sanitize_text
    text = sanitize_text(str(text or ""))
    for h in {home, home.replace("\\", "/")} if home else ():
        text = text.replace(h, "~")
    return HOME_PATH_RE.sub("~", text)


def _read(path: Path) -> list:
    out = []
    try:
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                node = json.loads(line) if line.strip() else None
            except ValueError:
                node = None
            if isinstance(node, dict):
                out.append(node)
    except OSError:
        pass
    return out


def _texts(blocks) -> str:
    if isinstance(blocks, str):
        return blocks
    parts = []
    for b in blocks or []:
        if isinstance(b, dict) and b.get("type") == "text":
            parts.append(str(b.get("text") or ""))
        elif isinstance(b, dict) and b.get("type") == "image":
            parts.append("[image]")
    return "".join(parts)


def _one_line(text: str, n: int = 100) -> str:
    text = " ".join(str(text or "").split())
    return text if len(text) <= n else text[: n - 3] + "..."


def arg_summary(inp) -> str:
    """The one line a tool call's input reads as: its command, path, pattern ... else its compact JSON."""
    if not isinstance(inp, dict):
        return _one_line(inp)
    for k in _ARG_KEYS:
        if isinstance(inp.get(k), str) and inp[k].strip():
            return _one_line(inp[k])
    return _one_line(json.dumps(inp, ensure_ascii=False, default=str, sort_keys=True)) if inp else ""


def trim(text: str, n: int = TRIM_LINES) -> str:
    lines = [ln if len(ln) <= LINE_MAX else ln[:LINE_MAX] + "..." for ln in str(text or "").rstrip().split("\n")]
    return "\n".join(lines[:n] + ([f"... ({len(lines) - n} more lines)"] if len(lines) > n else []))


def _fence(text: str) -> str:
    runs = [len(m) for m in re.findall(r"`{3,}", text)]
    return "`" * max([3] + [r + 1 for r in runs])


def _rows(nodes: list, who: str) -> list:
    """(ts, kind, title, body, fenced) per row of one agent's log."""
    rows, calls = [], {}
    for node in nodes:
        t, ts = node.get("type"), float(node.get("ts") or 0)
        if t == "user":
            text, kind = _texts(node.get("content")), node.get("kind")
            if kind is None:
                rows.append((ts, "user prompt", "user prompt", text, False))
            elif kind in ("steer", "nudge"):
                rows.append((ts, kind, f"steer to {who}" if kind == "steer" else "nudge", text, False))
        elif t == "assistant":
            text = _texts(node.get("content"))
            if text.strip():
                rows.append((ts, "assistant text", "assistant text", text, False))
            for b in node.get("content") or []:
                if isinstance(b, dict) and b.get("type") == "tool_use":
                    calls[b.get("id")] = name = str(b.get("name") or "?")
                    arg = arg_summary(b.get("input"))
                    rows.append((ts, "tool call", f"tool call: {name}" + (f" ({arg})" if arg else ""), "", False))
        elif t == "tool_result":
            name = str(node.get("tool") or calls.get(node.get("tool_use_id")) or "?")
            c = node.get("content")
            body = c if isinstance(c, str) else _texts(c) if isinstance(c, list) else json.dumps(c, default=str)
            title = f"tool result: {name}" + (" (error)" if node.get("is_error") else "")
            rows.append((ts, "tool result", title, trim(body), True))
        elif t == "error":
            rows.append((ts, "error", f"error ({node.get('err_type') or 'error'})", str(node.get("message") or ""), False))
        elif t == "interrupted":
            rows.append((ts, "error", "interrupted", "the turn was interrupted", False))
        elif t == "compacted":
            rows.append((ts, "compaction", f"compaction ({node.get('trigger') or 'auto'})",
                         str(node.get("custom_instructions") or ""), False))
        elif t == "rewind":
            rows.append((ts, "rewind", f"rewind ({node.get('verb') or '?'}) to step {node.get('step_id') or '?'}", "", False))
        elif t == "meta" and isinstance(node.get("timeline"), dict):
            rows.extend(_turn_rows(node["timeline"], ts))
    return rows


def _turn_rows(rec: dict, ts: float) -> list:
    """A turn's timeline record: each permission answer, then the turn-end marker."""
    from halo_harness.agent.turn_marker import done_line
    end = rec.get("message_end_ms")
    rows = []
    for w in rec.get("permission_waits") or []:
        if not isinstance(w, dict):
            continue
        at = ts - (end - w["end_ms"]) / 1000 if isinstance(end, (int, float)) and isinstance(w.get("end_ms"), (int, float)) else ts
        took = (w.get("end_ms") or 0) - (w.get("start_ms") or 0)
        rows.append((at, "permission answer", f"permission answer: {w.get('decision') or 'none'}",
                     f"answered after {took / 1000:.1f} s", False))
    marker = rec.get("marker") if isinstance(rec.get("marker"), dict) else {}
    text = str(marker.get("text") or "") or done_line(elapsed_s=(end or 0) / 1000, tools=len(rec.get("tools") or []), cost_usd=None)
    rows.append((ts, "turn end", f"turn end ({marker.get('state') or 'done'})", text, False))
    return rows


def _totals(nodes: list, tool_calls: int) -> dict:
    turns = tin = tout = 0
    cost, priced = 0.0, False
    for node in nodes:
        if node.get("type") == "user" and node.get("kind") not in NOT_A_PROMPT:
            turns += 1
        elif node.get("type") == "usage":
            u = node.get("usage") or {}
            tin += int(u.get("input_tokens") or 0) + int(u.get("cache_read_input_tokens") or 0) + int(u.get("cache_creation_input_tokens") or 0)
            tout += int(u.get("output_tokens") or 0)
            if isinstance(node.get("cost_usd"), (int, float)) and not node.get("estimate"):
                cost, priced = cost + node["cost_usd"], True
    return {"turns": turns, "tool_calls": tool_calls, "tokens_in": tin, "tokens_out": tout, "cost_usd": cost if priced else None}


def _agents(path: Path) -> list:
    """[(info, nodes)] of each sub-agent log under `<sid>/subagents/`, info from its meta.json."""
    out = []
    sub = path.parent / path.stem / "subagents"
    for log in sorted(sub.rglob("agent-*.jsonl")) if sub.is_dir() else []:
        try:
            meta = json.loads(log.with_name(log.stem + ".meta.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            meta = {}
        meta = meta if isinstance(meta, dict) else {}
        name = str(meta.get("role") or meta.get("type") or log.stem)
        out.append(({"name": name, "model": meta.get("model"), "lineup": meta.get("lineup")}, _read(log)))
    return out


def _clock(ts: float, fmt: str = "%H:%M:%S") -> str:
    return time.strftime(fmt, time.localtime(ts)) if ts else "?"


def trace_markdown(source, *, model: Optional[str] = None, lineup: Optional[str] = None, totals: Optional[dict] = None,
                   session_id: Optional[str] = None, tiers: Optional[dict] = None, home: Optional[str] = None) -> str:
    """The trace of `source` (a session log's path, or its node list). `tiers` maps an agent name to its tier."""
    if home is None:
        home = str(Path.home())
    path = Path(source) if isinstance(source, (str, Path)) else None
    nodes = _read(path) if path else list(source or [])
    sid = session_id or (path.stem if path else "?")
    model = model or next((n["model"] for n in reversed(nodes) if n.get("type") == "meta" and n.get("model")), None)
    subs = _agents(path) if path else []
    lineup = lineup or next((i["lineup"] for i, _ in subs if i.get("lineup")), None)
    tiers = tiers or {}
    entries = []
    for i, (info, ns) in enumerate([({"name": "main", "model": model}, nodes)] + subs):
        label = ", ".join(x for x in (f"tier {tiers[info['name']]}" if tiers.get(info["name"]) else "", str(info.get("model") or "")) if x)
        who = info["name"] + (f" ({label})" if label else "")
        entries += [(ts, i, j, who, title, body, fenced, kind) for j, (ts, kind, title, body, fenced) in enumerate(_rows(ns, info["name"]))]
    entries.sort(key=lambda e: (e[0], e[1], e[2]))
    tot = {**_totals(nodes, sum(1 for e in entries if e[7] == "tool call")), **(totals or {})}
    stamps = [float(n.get("ts")) for n in nodes if n.get("ts")]
    cost = tot.get("cost_usd")
    out = [f"# Halo trace: session {sid}", "",
           f"- Session: `{sid}`",
           f"- Model: {model or 'not recorded'} · lineup: {lineup or 'not recorded'}",
           f"- Started: {_clock(min(stamps), '%Y-%m-%d %H:%M:%S') if stamps else '?'} · "
           f"ended: {_clock(max(stamps), '%Y-%m-%d %H:%M:%S') if stamps else '?'}",
           f"- Totals: turns {tot['turns']} · tool calls {tot['tool_calls']} · tokens in {tot['tokens_in']} · "
           f"tokens out {tot['tokens_out']} · cost {'$%.4f' % cost if isinstance(cost, (int, float)) else 'not priced'}",
           f"- Rows: {len(entries)}", ""]
    for ts, _i, _j, who, title, body, fenced, _kind in entries:
        out.append(f"### {_clock(ts)} · {_scrub(who, home)} · {_scrub(_one_line(title, 160), home)}")
        body = _scrub(body, home).rstrip()
        if body:
            f = _fence(body) if fenced else ""
            out += ["", f"{f}text\n{body}\n{f}" if fenced else re.sub(r"(?m)^(#{1,6}\s)", r"\\\1", body)]  # text never opens a heading
        out.append("")
    return "\n".join(out).rstrip() + "\n"
