"""halo_harness.agent.prompt_measure -- Halo 3.3.16.1 "the local prompt diet": what a model's first turn
costs before anything is sent (`halo local prompt`, `/status`, `halo doctor`, Studio's model card, the
steward's fit plan, tests/test_prompt_budget_pins.py).

    first_turn(ref, *, window=None, platform=None, cwd=None, text="hi", control=None, builder=False,
               one_shot=False) -> Measure
    new_session(ref, *, window=, platform=, cwd=, control=None, builder=False, one_shot=False, helpers_off=False)
                                         the stub it measures: a NEW top session in `cwd` (crew/session_start.py;
                                         3.6.0.10 M1b); `one_shot`: as `halo -p` with one prompt marks it (many_turns
                                         False); `helpers_off`: the gym's "before" (halo_harness/gym_handout.py)
    one_shot_first_ask(ref, *, cap, platform=None, cwd=None, text="hi", control=None, rename=None) -> dict
                                         a one-shot's first ask through the product's own ladder (3.6.0.12 OS:
                                         start_window, then reply_room.for_call; tests/test_prompt_budget_pins.py)
    first_turn_line(m) -> "Halo's own first turn: 9,150 tokens of 32,768 (28 %)"
    composition_text(session, first=)   `/cost`, `/status` (first: the line above on a local model)
    doctor_note(ref, cwd)                `halo doctor`'s default-model row
    card_line(ref, window)               Studio's model card row (a measure per window, five minutes)
    first_turn_floor()                   the steward's fit plan floor (ollama_steward/fit.py)

Built from the functions the loop uses: the session's system prompt and snapshots
(`agent/assemble.SessionContext`: CLAUDE.md, the memory, the environment; the roster), the built-in tool
catalog (`tools/registry.default_tools`, for `platform`), `derive_request`, the wire shaping
(`prompt_wire.shape`: the memory's placement, the lean profile, the tool diet), the composition, the reply's
room (`agent/reply_room`) and the window the call would be sent at (`ollama_prompt.window_for` over the
wire's own estimate, `providers/ollama_wire_estimate`). Nothing is sent, nothing is logged.

Measure = {ref, platform, lean, window, sent_window, reply_room, prompt, total, system_message, share,
composition, line, tools: [{name, tokens, offered, why}], left_out: [names]}. `prompt` is Halo's own first
turn (everything but the reply's room, as the wire carries it), `total` that plus the room,
`system_message` the system message's tokens (memory included on a local model), `share` prompt / sent
window.
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Optional


class _Nodes:
    def __init__(self):
        self._nodes: list = []

    def nodes(self, upto=None) -> list:
        return list(self._nodes if upto is None else self._nodes[:upto])

    def add(self, **node) -> None:
        self._nodes.append({**node, "seq": len(self._nodes)})


def _window_for_ref(ref, env=None) -> Optional[int]:
    """The window a call to `ref` starts from: an `ol:` model's resolved num_ctx (catalog, host, profile)."""
    if getattr(ref, "provider", "") != "ollama":
        return None
    try:
        from halo_harness.providers.ollama_hw import resolve_context_decision
        return resolve_context_decision(ref, env).num_ctx
    except Exception:
        return None


def _rows(full: list, sent: list, dropped: list, why_kept: dict) -> list:
    from halo_harness.agent.prompt_diet import ALIASES, wire_tokens
    from halo_harness.tools.lean_descriptions import lean_definition
    sent_by = {t.get("name"): t for t in sent}
    names = {t.get("name") for t in full}
    rows = []
    for t in full:
        n = t.get("name")
        if n in sent_by:
            rows.append({"name": n, "tokens": wire_tokens(sent_by[n]), "offered": True, "why": why_kept.get(n, "offered")})
        elif ALIASES.get(n) in names:
            rows.append({"name": n, "tokens": 0, "offered": False, "why": f"the same tool as {ALIASES[n]} (sent once)"})
        else:
            why = "the other shell (prompt.shell)" if n in ("Bash", "PowerShell") else "left out to fit the window"
            rows.append({"name": n, "tokens": wire_tokens(lean_definition(t)), "offered": False,
                         "why": why + "; callable by name, ToolSearch shows it"})
    return rows


def _why_kept(session, sent: list) -> dict:
    from halo_harness.agent.prompt_diet import lean_shell, workflow_needed
    from halo_harness.providers.ollama_fit import CORE_TOOL_NAMES
    shell = lean_shell(getattr(session, "_measure_platform", None))
    core = set(CORE_TOOL_NAMES) | ({shell} if shell else set())
    out = {}
    for t in sent:
        n = t.get("name")
        out[n] = ("core" if n in core else "the lineup's square" if n == "Workflow" and workflow_needed(session)
                  else "built-in")
    return out


def new_session(ref, *, window: Optional[int] = None, platform: Optional[str] = None, cwd=None,
                control: Optional[str] = None, builder: bool = False, one_shot: bool = False,
                helpers_off: bool = False):
    """The session a measure runs on: a NEW top session in `cwd` (3.6.0.10 M1b): the built-in tools of `platform`,
    the Builder when `builder` (as headless.build_session adds it for a session someone answers), and the state a
    start sets (crew/session_start.new_session_state: `control` is what `--map` would name, None the folder's own).
    `helpers_off` (3.6.0.13 GM, the gym's "before"): the helpers words turned off BEFORE the start, so the tools'
    words and the Builder's sentence are today's line's (agent/helpers_words.on_auto)."""
    from halo_harness.agent.assemble import SessionContext
    from halo_harness.config.paths import bridge_home
    from halo_harness.crew.session_start import new_session_state
    from halo_harness.model import parse_model_ref
    from halo_harness.providers.profiles import model_family
    from halo_harness.tools.registry import ToolRegistry, default_tools
    ref = parse_model_ref(ref) if isinstance(ref, str) else ref
    plat = platform or sys.platform
    cwd = Path(cwd or Path.cwd())
    registry = ToolRegistry(default_tools(platform=plat))
    if builder and registry.get("Builder") is None:
        from halo_harness.tools.builder_tool import BuilderTool
        registry.add_tool(BuilderTool())
    ctx = SessionContext(cwd=cwd, model_label=ref.raw, model_family=model_family(ref.model), tool_registry=registry)
    window = window or _window_for_ref(ref, getattr(ctx.settings, "effective_env", None))
    session = SimpleNamespace(model_ref=ref, model_profile=SimpleNamespace(context_tokens=window), log=_Nodes(),
                              session_context=ctx, tool_registry=registry, state_dir=bridge_home(),
                              settings=ctx.settings, route=None, role_name=None, _measure_window=window,
                              _measure_platform=plat)
    # the measured session is one a person works in (the terminal app marks its session `interactive`); `one_shot`:
    # as headless.run_print_mode marks `-p` with one prompt (agent/helpers_words.one_shot asks the ladder's own rule)
    session.interactive = not one_shot
    if one_shot:
        session.many_turns = False
    if helpers_off:
        session._helpers_off = True
    return new_session_state(session, cwd=cwd, control=control)


def _first_request(ref, **kw) -> tuple:
    """(session, the full tool list, system text, messages, the tools sent): a new session's first request, shaped
    for the wire as the loop shapes it (`kw`: new_session's own, `text`, and `mode`: the permission mode line a
    turn's start logs after the user node, agent/mode_notice.sync; None logs none)."""
    from halo_harness.agent.derive import derive_request
    from halo_harness.agent.prompt_wire import shape
    from halo_harness.config.paths import bridge_home
    text = kw.pop("text", "hi")
    mode = kw.pop("mode", None)
    session = new_session(ref, **kw)
    ref = session.model_ref
    ctx, registry, log = session.session_context, session.tool_registry, session.log
    log.add(type="meta", model=ref.raw, tools=registry.definitions())
    log.add(type="system", text=ctx.system_prompt)
    try:
        from halo_harness.providers.roster import roster_snapshot_text
        roster = roster_snapshot_text(bridge_home(), current_ref=ref.raw)
    except Exception:
        roster = ""
    for kind, snap in (("claude_md", ctx.claude_md_text()), ("memory_index", ctx.memory_snapshot_text()),
                       ("environment", ctx.environment_snapshot_text(ref.raw)), ("roster", roster)):
        if snap:
            log.add(type="snapshot", kind=kind, content=[{"type": "text", "text": snap}])
    log.add(type="user", content=[{"type": "text", "text": text}])
    if mode:
        from halo_harness.agent.mode_notice import mode_line
        log.add(type="snapshot", kind="permission_mode", content=[{"type": "text", "text": mode_line(mode)}])
    system_text, messages, tools = derive_request(log)
    full = list(tools or [])
    session._measure_raw = (system_text, messages, full)  # what a one-shot's ask shapes again (one_shot_first_ask)
    system_text, messages, sent = shape(session, system_text, messages, full, purpose="measure")
    return session, full, system_text, messages, list(sent or [])


def first_turn(ref, *, window: Optional[int] = None, platform: Optional[str] = None, cwd=None,
               text: str = "hi", control: Optional[str] = None, builder: bool = False, one_shot: bool = False) -> dict:
    from halo_harness.agent import prompt_lean as L
    from halo_harness.agent.prompt_composition import compose, composition_line, known_texts
    from halo_harness.agent.prompt_wire import placement_for
    from halo_harness.agent.reply_room import PROVIDER_DEFAULT, fitted
    from halo_harness.providers.ollama_prompt import window_for
    from halo_harness.providers.ollama_wire_estimate import wire_estimate
    session, full, system_text, messages, sent = _first_request(
        ref, window=window, platform=platform, cwd=cwd, control=control, builder=builder, one_shot=one_shot, text=text)
    ref, plat, window = session.model_ref, session._measure_platform, session._measure_window
    comp = compose(session, messages, sent, system_text, placement=placement_for(session), known=known_texts(session))
    prompt = wire_estimate(system_text, messages, sent) - 1024  # the reply's room counted below, not here
    named = comp["system"]["tokens"] + comp["user"]["tokens"]  # the wire's total; its JSON framing in history
    comp = {**comp, "total": prompt, "history": {**comp["history"], "tokens": max(0, prompt - named)}}
    reply, _w, _sized = fitted(window, prompt, PROVIDER_DEFAULT, first=True)
    sent_window = window_for(prompt + reply, base=window, base_source="measure").num_ctx if window else None
    dropped = list(getattr(session, "_diet_dropped", None) or [])
    from halo_harness.agent.prompt_composition import tokens_of
    return {"ref": ref.raw, "platform": plat, "lean": L.active(session), "window": window, "sent_window": sent_window,
            "reply_room": reply, "prompt": prompt, "total": prompt + reply, "system_message": tokens_of(system_text),
            "share": round(100.0 * prompt / sent_window, 1) if sent_window else None, "composition": comp,
            "line": composition_line(comp), "tools": _rows(full, sent, dropped, _why_kept(session, sent)),
            "left_out": dropped}


MEASURE_HOST = "http://measure.invalid"  # a name no call reaches: the one-shot's ask is measured, never sent


def _renamed(value, rename: dict):
    if isinstance(value, str):
        for old, new in rename.items():
            value = value.replace(old, new)
        return value
    if isinstance(value, list):
        return [_renamed(v, rename) for v in value]
    if isinstance(value, dict):
        return {k: _renamed(v, rename) for k, v in value.items()}
    return value


def one_shot_first_ask(ref, *, cap: int, platform: Optional[str] = None, cwd=None, text: str = "hi",
                       control: Optional[str] = None, rename: Optional[dict] = None) -> dict:
    """3.6.0.12 OS: a one-shot's (`halo -p`, one prompt) first ask of a local model with nothing loaded, through the
    product's own ladder: the request `first_turn` measures, its window from `ollama_window_truth.start_window` under
    `cap` (the host's max_ctx) and its reply's room from `reply_room.for_call`, called as agent/loop.py calls them.
    `rename`: strings replaced in the request first (a pin's fixed paths). Nothing is sent and nothing is kept: the
    window the ask notes for this process is taken back. Each step is measured with its own tool block and the block of
    the step asked is the one measured (prompt_wire.one_shot_shaper). Returns {prompt, asked, source, reply_room,
    window, sent_window, tools: [names sent], tool_tokens, system: the system text sent}."""
    from types import SimpleNamespace as NS
    from halo_harness.agent import ollama_window_truth as T
    from halo_harness.agent.reply_room import PROVIDER_DEFAULT, for_call
    from halo_harness.providers.ollama_prompt import window_for
    session, _full, system_text, messages, sent = _first_request(ref, window=cap, platform=platform, cwd=cwd,
                                                                 control=control, one_shot=True, text=text)
    from halo_harness.agent.prompt_wire import one_shot_shaper

    def _fixed(req: tuple) -> tuple:
        return tuple(_renamed(list(part) if isinstance(part, tuple) else part, rename) for part in req) \
            if rename else tuple(req)
    request = _fixed((system_text, messages, sent))
    ref = session.model_ref
    host = NS(name="measure", url=MEASURE_HOST, max_ctx=cap)
    decision = NS(profile={}, trained_context=None, fit_estimate=None)
    key = T._key(host.url, ref.model)
    with T._ASKED_LOCK:
        was = T._ASKED.get(key)
    try:
        # 3.6.0.12 OS: each step measured with its own tool block, and the block of the step asked is the one sent
        reshape = one_shot_shaper(session, ref, request, raw=session._measure_raw, post=_fixed, purpose="measure")
        asked, source, hold = T.start_window(session, host=host, ref=ref, decision=decision, cap=cap,
                                             cap_source="host max_ctx", request=request, requested=PROVIDER_DEFAULT,
                                             reshape=reshape)
        if reshape is not None:
            request = reshape(None)
        reply, window = for_call(session, ref, asked, PROVIDER_DEFAULT, decision, request, host, hold=hold)
    finally:
        with T._ASKED_LOCK:
            if was is None:
                T._ASKED.pop(key, None)
            else:
                T._ASKED[key] = was
    from halo_harness.agent.prompt_diet import wire_tokens
    prompt = T.prompt_estimate(session.state_dir, host.url, ref.model, *request)[1]
    return {"prompt": prompt, "asked": asked, "source": source, "reply_room": reply, "window": window,
            "sent_window": window_for(prompt + reply, base=window, base_source="measure").num_ctx,
            "tools": [t.get("name") for t in request[2] or []],
            "tool_tokens": sum(wire_tokens(t) for t in request[2] or []), "system": request[0]}


def _local(ref) -> bool:
    from halo_harness.agent.prompt_lean import is_local
    return is_local(ref)


def for_session(session) -> Optional[dict]:
    """The session's own model measured once per window (`/status`), None for a cloud model or on a failure."""
    ref = getattr(session, "model_ref", None)
    if ref is None or not _local(ref):
        return None
    from halo_harness.agent.prompt_diet import call_window
    window = call_window(session)
    cache = getattr(session, "_first_turn_measure", None) or {}
    key = (getattr(ref, "raw", None), window)
    if key not in cache:
        try:
            cache = {key: first_turn(ref, window=window, cwd=getattr(session, "cwd", None))}
        except Exception:
            cache = {key: None}
        session._first_turn_measure = cache
    return cache[key]


def composition_text(session, *, first: bool = False) -> str:
    """`/cost` and `/status`: the composition line; `/status` (`first`) adds Halo's own first turn on a local model."""
    from halo_harness.agent.prompt_composition import composition_line
    from halo_harness.agent.prompt_wire import composition_now
    text = composition_line(composition_now(session))
    m = for_session(session) if first else None
    return text + ("\n" + first_turn_line(m) if m else "")


_CARD: dict = {}
CARD_TTL_S = 300.0


def card_line(ref_raw: str, window) -> Optional[str]:
    """Studio's model card row (studio/model_card_api.py): "Halo's first turn: N tokens (P % of the window)" for
    a local model with a known window, measured once per window and platform for five minutes; None otherwise."""
    try:
        ref = _parse(ref_raw)
        if not _local(ref) or not isinstance(window, int) or window <= 0:
            return None
        m = _cached(ref, window)
        return f"Halo's first turn: {m['prompt']:,} tokens ({round(100.0 * m['prompt'] / window):.0f} % of the window)"
    except Exception:
        return None


def _cached(ref, window: int) -> dict:
    import time
    key = (window, sys.platform, str(Path.cwd()))
    hit = _CARD.get(key)
    if hit is None or time.time() - hit[0] > CARD_TTL_S:
        hit = _CARD[key] = (time.time(), first_turn(ref, window=window))
    return hit[1]


def first_turn_floor(*, step: int = 4096, reply: int = 4096, fallback: int = 8192) -> int:
    """The steward's fit plan (ollama_steward/fit.py): the smallest window that holds Halo's own leanest first
    turn (a 16,384 window's) and a reply, rounded up to `step`; never under `fallback`, which it is when the
    measure fails."""
    try:
        m = _cached(_parse("ol:model"), 16384)
        return max(fallback, -(-(int(m["prompt"]) + reply) // step) * step)
    except Exception:
        return fallback


def _parse(raw: str):
    from halo_harness.model import parse_model_ref
    return parse_model_ref(raw)


def doctor_note(ref, cwd=None) -> str:
    """`halo doctor`'s default-model row on a local model: " · Halo's own first turn: N tokens of W (P %)"."""
    try:
        return f" · {first_turn_line(first_turn(ref, cwd=cwd))}" if _local(ref) else ""
    except Exception:
        return ""


def first_turn_line(m: Optional[dict]) -> str:
    if not m:
        return "Halo's own first turn: not measured"
    w = m.get("sent_window")
    if not w:
        return f"Halo's own first turn: {m['prompt']:,} tokens"
    return f"Halo's own first turn: {m['prompt']:,} tokens of {w:,} ({m['share']:.0f} %)"
