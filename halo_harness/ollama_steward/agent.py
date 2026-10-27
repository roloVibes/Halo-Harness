"""halo_harness.ollama_steward.agent -- Halo 3.3.4.0 R4: the steward's
model, selectable and cheap. One call per note writes what the rules found
in plain words (agent_prompt.py builds what it reads) and may propose a
profile change the rules did not make.

The model (`choose_model`): `ollama.steward.model` (any model ref; a cloud
model only when it names one), else the configured `compactionModel` when it
is a local model, else the smallest local model this machine lists (by its
size on disk), else none: the job runs the rules only and `status` says "no
steward model: set ollama.steward.model".

When (`due`): a run that found something the last note did not name, or made
a change, or saw a server event that passed its quiet period -- and at most
once per `ollama.steward.note_every_s` (600 s). Never a call when nothing is
new.

The answer: at most NOTE_LINES lines (the first is the TUI status line's
text) and an optional fenced `proposals` block, `[{key, field, to, why}]`.
Each proposal goes through `proposals.check` (agent_proposals.py): a known
host and model, a profile field, a value of its type, never above the
measured cap or past the card's fit, never a smaller window for a model whose
prompts outgrew it, then `steward.check` (ten minutes per model) -- and lands
under the mode: `auto` applies it, `review` writes a proposal line, `off`
only reports it. A dropped one says why. The note's cost line: "local, free"
for a local model, else the tokens and the dollars when priced.
"""

from __future__ import annotations

import json
import re
import time
from typing import Callable, Optional

NOTE_LINES = 6
NOTE_EVERY_S = 600.0
MAX_TOKENS = 700
NO_MODEL = "no steward model: set ollama.steward.model"
_BLOCK = re.compile(r"```\s*proposals\s*\n(.*?)```", re.S | re.I)
_THINK = re.compile(r"<think>.*?</think>", re.S | re.I)


def _cfg(key: str, default=None):
    try:
        from halo_harness.theme import get_config_value
        return get_config_value(key, default=default)
    except Exception:
        return default


def note_every_s() -> float:
    v = _cfg("ollama.steward.note_every_s", NOTE_EVERY_S)
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) and v >= 0 else NOTE_EVERY_S


def _is_local(ref: str) -> bool:
    try:
        from halo_harness.model import is_local_ref_string
        return bool(is_local_ref_string(ref))
    except Exception:
        return str(ref).startswith(("ol:", "hf:local/", "hf:mlx/"))


def local_models(state_dir=None) -> "list[tuple[str, int]]":
    """(ref, size in bytes) of the local models this machine lists, from the cached views (no host is probed)."""
    try:
        from halo_harness.providers.local_models import build_local_view
        rows = build_local_view(state_dir=state_dir, cached=True)
    except Exception:
        return []
    return [(r.ref, r.size_bytes) for r in rows if getattr(r, "ref", None) and isinstance(r.size_bytes, int)
            and r.size_bytes > 0 and "not served" not in str(getattr(r, "group", ""))]


def choose_model(*, configured=None, compaction=None, local=None, state_dir=None) -> "tuple[Optional[str], str]":
    """(the model ref or None, where it came from)."""
    configured = _cfg("ollama.steward.model") if configured is None else configured
    if isinstance(configured, str) and configured.strip():
        return configured.strip(), "ollama.steward.model"
    compaction = _cfg("compactionModel") if compaction is None else compaction
    if isinstance(compaction, str) and compaction.strip() and _is_local(compaction.strip()):
        return compaction.strip(), "compactionModel"
    rows = local_models(state_dir) if local is None else list(local)
    if rows:
        ref, size = min(rows, key=lambda t: (t[1], t[0]))
        return ref, f"the smallest local model ({size / 2 ** 30:.1f} GiB)"
    return None, NO_MODEL


def _last_agent_note(state_dir, now: float) -> Optional[dict]:
    from halo_harness.ollama_steward import notes
    rows = notes.read(state_dir, stage="note", since_s=7 * 86400, now=now)
    return rows[-1] if rows else None


def due(state_dir, done: dict, *, notify: int = 0, now: Optional[float] = None,
        every_s: Optional[float] = None) -> "tuple[bool, str]":
    """(call the model now?, why)."""
    from halo_harness.ollama_steward.ledger import parse_at
    now = time.time() if now is None else now
    every_s = note_every_s() if every_s is None else every_s
    last = _last_agent_note(state_dir, now)
    named = set(((last or {}).get("data") or {}).get("findings") or [])
    new = [f["id"] for f in done.get("findings") or [] if f["id"] not in named]
    changes = len(done.get("applied") or []) + len(done.get("rolled_back") or []) + len(done.get("proposed") or [])
    if not new and not changes and not notify:
        return False, "nothing new since the last note"
    if last is not None and now - (parse_at(last.get("at")) or 0) < every_s:
        return False, f"a note was written less than {int(every_s)} s ago"
    return True, f"{len(new)} new findings, {changes} changes, {notify} server events"


def parse(text: str) -> "tuple[list[str], list[dict], str]":
    """(the note's lines, the proposals, why the block was dropped or "")."""
    text = _THINK.sub("", str(text or ""))
    props, why = [], ""
    m = _BLOCK.search(text)
    if m:
        try:
            got = json.loads(m.group(1))
            props = [p for p in (got if isinstance(got, list) else [got]) if isinstance(p, dict)]
        except ValueError:
            why = "the proposals block is not JSON"
        text = text[:m.start()] + text[m.end():]
    lines = []
    for raw in text.splitlines():
        t = raw.strip().lstrip("#").strip()
        if t and not t.startswith("```"):
            lines.append(t[:300])
    return lines[:NOTE_LINES], props, why


def cost_line(reply: dict, model: str) -> str:
    if reply.get("local") or _is_local(model):
        return "local, free"
    tin, tout = reply.get("input_tokens"), reply.get("output_tokens")
    toks = f"{tin or '?'} in / {tout or '?'} out tokens"
    usd = reply.get("cost_usd")
    return f"{toks}, ${usd:.4f}" if isinstance(usd, (int, float)) else f"{toks}, no price known"


def write_note(state_dir, ctx: dict, done: dict, *, model: str, caller: Optional[Callable] = None,
               events: Optional[list] = None, say: Callable = lambda _s: None, where: Optional[str] = None,
               now: Optional[float] = None) -> "tuple[Optional[dict], list]":
    """ONE model call -> (the note line written or None, the proposals' outcomes)."""
    from halo_harness.ollama_steward import agent_prompt, agent_proposals, notes
    now = time.time() if now is None else now
    caller = caller or live_call
    try:
        reply = caller(model, agent_prompt.guide(), agent_prompt.context(ctx, done, events=events), state_dir=state_dir)
    except Exception as e:
        say(f"steward model {model}: no note ({type(e).__name__}: {str(e)[:160]})")
        return None, []
    lines, props, why = parse((reply or {}).get("text"))
    if why:
        say(f"steward model {model}: {why}, no proposal taken")
    outcomes = agent_proposals.land(state_dir, props, ctx, mode_name=done.get("mode") or "auto", say=say, now=now)
    if not lines:
        say(f"steward model {model}: the answer held no note")
        return None, outcomes
    cost = cost_line(reply or {}, model)
    severe = any(f.get("severity") == "error" for f in done.get("findings") or [])
    changed = bool(done.get("applied") or done.get("rolled_back") or any(o.get("landed") for o in outcomes))
    row = notes.append(state_dir, "note", lines[0], lines=lines + [f"(steward model {model}: {cost})"], cost=cost,
                       attention=severe or changed, model=model, where=where, now=now,
                       data={"findings": [f["id"] for f in done.get("findings") or []], "proposals": outcomes,
                             "usage": {k: (reply or {}).get(k) for k in ("input_tokens", "output_tokens", "cost_usd")}})
    return row, outcomes


def live_call(model: str, system_text: str, user_text: str, *, state_dir=None, timeout_s: float = 120.0) -> dict:
    """The one call: a bare session for `model` (the live pong's builder, init_cli), one `call_small_model`
    request that never enters a session log -> {text, input_tokens, output_tokens, cost_usd, local}."""
    from pathlib import Path
    from halo_harness import headless
    from halo_harness.model import is_local_model_ref
    build = headless.build_session(cwd=Path(state_dir) if state_dir else Path.cwd(), model_ref_raw=model, bare=True,
                                   print_mode=True, max_turns=1)
    session = build.session
    usage: dict = {}
    try:
        text = session.call_small_model(system_text=system_text, user_text=user_text, max_tokens=MAX_TOKENS,
                                        timeout_s=timeout_s, model_ref=build.model_ref, usage_out=usage)
    finally:
        if build.mcp_manager is not None:
            try:
                build.mcp_manager.close_all()
            except Exception:
                pass
    tin, tout = usage.get("input_tokens"), usage.get("output_tokens")
    prof = getattr(session, "model_profile", None)
    pin, pout = getattr(prof, "price_in", None), getattr(prof, "price_out", None)
    cost = (tin * pin + tout * pout) if all(isinstance(x, (int, float)) for x in (tin, tout, pin, pout)) else None
    return {"text": text, "input_tokens": tin, "output_tokens": tout, "cost_usd": cost,
            "local": is_local_model_ref(build.model_ref)}
