"""halo_harness.agent.preflight -- Halo 3.3.5.0 R4: a local request that will
not fit its window is a decision the user sees before it is sent, never a
silent cut.

    check(session) -> {prompt, window, usable, reserve, cut, line} | None
    bigger_model(session, need) -> "ol:<model>@<host>" | None
    run(session, turn_no)   a generator of events; returns "compact" | "switch" | "send" | "stop" | None

Ollama's rule: a prompt over the window sent is cut to `window / 2 + 2`
tokens, 4 from the start and the rest from the tail (measured on 0.40.13).
Before an Ollama call whose request (its prompt plus the reply's room) is
larger than the largest window the call can get, the turn says one line --
"prompt 30,756 tokens · window 32,768 · usable 16,386 · this will be cut" --
and offers [compact] [bigger-window model: <the best fit on the host>]
[send anyway]. The TUI shows the three as keys with compact on Enter;
Studio's Live composer shows three buttons (`preflight-compact`,
`preflight-switch`, `preflight-send`) answering the same card. In `-p`, a
non-interactive run or a sub-agent the default applies: `prompt.preflight`
(ask | compact | send; ask means compact when nobody can answer). The choice
goes on the next ledger line (`preflight`: "compact" | "switch" | "sent")
and into the session log (a `preflight` node); "send anyway" orders the
payload so the tail Ollama keeps holds the task (`agent/prompt_wire.py`).
"""

from __future__ import annotations

import logging
import threading
import uuid
from typing import Optional

from halo_harness import events

log = logging.getLogger("bridge")

ACTIONS = {"compact": "compact", "accept": "compact", "switch": "switch", "edit": "switch", "send": "send",
           "stop": "stop"}
WORDS = {"compact": "compacting first", "switch": "switching to {to}", "send": "sending anyway (the tail is kept)",
         "stop": "stopped before sending"}
LEDGER = {"compact": "compact", "switch": "switch", "send": "sent"}


def check(session) -> Optional[dict]:
    from halo_harness.agent.ollama_window import _state
    last = _state(session).get("last")
    if not last or last["choice"].fits:
        return None
    reserve = int(last.get("reserve") or 1024)
    prompt = max(1, int(last["estimate"]) - reserve)
    window = int(last["choice"].ceiling or 0)
    if window <= 0:
        return None
    usable = window // 2 + 2
    cut = prompt > window
    tail = "this will be cut" if cut else f"no room left for the reply ({reserve:,})"
    line = f"prompt {prompt:,} tokens · window {window:,} · usable {usable:,} · {tail}"
    return {"prompt": prompt, "window": window, "usable": usable, "reserve": reserve, "cut": cut, "line": line,
            "model": last.get("model"), "host": last.get("host_name")}


def bigger_model(session, need: int) -> Optional[str]:
    """The model on the session's Ollama host with the smallest window that
    holds `need` tokens (a model that takes tools when the session sends them)."""
    ref = getattr(session, "model_ref", None)
    if getattr(ref, "provider", "") != "ollama":
        return None
    try:
        from halo_harness.agent.model_window import window_on_host
        from halo_harness.providers.local_models_cached import cached_catalog
        from halo_harness.providers.ollama import ollama_names_match, resolve_ollama_host
        env = getattr(getattr(session, "settings", None), "effective_env", None)
        host = resolve_ollama_host(ref.host, env)
        catalog = cached_catalog(host) if host is not None else None
        best = None
        for row in (catalog or {}).get("models") or []:
            name = row.get("model") or row.get("name") if isinstance(row, dict) else None
            if not name or ollama_names_match(name, ref.model):
                continue
            caps = row.get("capabilities") if isinstance(row.get("capabilities"), list) else None
            if caps is not None and ("embedding" in caps or (caps and "completion" not in caps and "tools" not in caps)):
                continue
            if caps is not None and "tools" not in caps and getattr(session, "session_catalog", None) is not None:
                continue
            w = window_on_host(name, host, state_dir=getattr(session, "state_dir", None), catalog_row=row)
            tokens = w.get("tokens")
            if isinstance(tokens, int) and tokens >= need and (best is None or tokens < best[0]):
                best = (tokens, name)
        if best is None:
            return None
        return f"ol:{best[1]}@{host.name}"
    except Exception:
        log.debug("preflight: no bigger-window model could be read", exc_info=True)
        return None


def _ask(session, info: dict, alt: Optional[str], turn_no: int):
    rid = f"preflight-{uuid.uuid4().hex[:8]}"
    session._approval_waiters[rid] = {"event": threading.Event(), "decision": None}
    session._preflight_pending = {"id": rid, "line": info["line"], "switch_to": alt, "default": "compact"}
    choices = [{"id": "compact", "label": "compact", "default": True},
               {"id": "switch", "label": f"bigger-window model: {alt}" if alt else "bigger-window model: none fits here",
                "disabled": alt is None},
               {"id": "send", "label": "send anyway"}]
    yield events.Event("approval_request", {"id": rid, "position": "preflight", "text": info["line"], "is_error": False,
                                            "choices": choices, "switch_to": alt, "default": "compact"}, turn=turn_no)
    try:
        answer = session._await_reply(session._approval_waiters, rid)
    finally:
        session._preflight_pending = None
    if answer is None:
        return "stop" if session.abort.is_set() else "compact"
    return ACTIONS.get(str((answer or {}).get("action") or ""), "compact")


def _record(session, info: dict, choice: str, alt: Optional[str], asked: bool) -> None:
    session._preflight_decision = LEDGER.get(choice)
    try:
        session.log._append({"type": "preflight", "line": info["line"], "choice": choice, "asked": asked,
                             "switch_to": alt if choice == "switch" else None, "prompt": info["prompt"],
                             "window": info["window"]})
    except Exception:
        log.debug("preflight: the log node could not be written", exc_info=True)
    log.info("preflight: %s -> %s", info["line"], choice)


def _switch(session, alt: str, turn_no: int):
    from halo_harness.headless import _resolve_creds
    from halo_harness.model import parse_model_ref, resolve_model_profile
    from halo_harness.agent.model_switch import run_switch
    target = parse_model_ref(alt, getattr(getattr(session, "agent_runtime", None), "routes", None) or {})
    profile = resolve_model_profile(target, session.state_dir, getattr(session.agent_runtime, "routes", None) or {})
    creds = _resolve_creds(target, session.settings) or session.creds
    yield from run_switch(session, target, profile, creds, why="preflight")
    # a standing choice, like /model: the turn's end never switches it back
    session._primary_model_snapshot = (session.model_ref, session.model_profile, session.creds,
                                       session.effort, session.effort_source)


def run(session, turn_no: int):
    from halo_harness.agent.prompt_lean import knobs
    session._preflight_sent_now = False
    info = check(session)
    if info is None:
        return None
    mode = knobs()["preflight"]
    alt = bigger_model(session, info["prompt"] + info["reserve"])
    asked = mode == "ask" and bool(getattr(session, "interactive", False)) and getattr(session, "agent_id", None) is None
    if asked:
        choice = yield from _ask(session, info, alt, turn_no)
    else:
        choice = "send" if mode == "send" else "compact"
    if choice == "switch" and not alt:
        choice = "compact"
    how = "" if asked else f" (prompt.preflight: {mode})"
    yield events.turn_marker("preflight", f"↳ {info['line']}: {WORDS[choice].format(to=alt)}{how}", turn=turn_no,
                             preflight={**info, "choice": choice, "switch_to": alt, "asked": asked})
    _record(session, info, choice, alt, asked)
    if choice == "switch":
        try:
            yield from _switch(session, alt, turn_no)
        except Exception:
            log.warning("preflight: the switch to %s failed; compacting instead", alt, exc_info=True)
            session._preflight_decision = "compact"
            return "compact"
    elif choice == "send":
        session._preflight_sent_now = True
    return choice
