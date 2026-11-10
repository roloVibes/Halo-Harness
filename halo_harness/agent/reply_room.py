"""halo_harness.agent.reply_room -- Halo 3.3.16.1 "the local prompt diet": the reply's room follows the
window (docs/MODELS-prompt-diet.md).

    room(window, requested, *, profile_num_predict=None, explicit=None) -> (tokens, sized_by_window)
    fitted(window, prompt, requested, ...) -> (tokens, window, sized)   the room of the window the call gets
    for_call(session, ref, window, requested, profile, request)   `_build_ollama_body_for_ref`'s room

A first turn to a model with no profile used to ask for the provider profile's 16,384 whatever the window;
prompt + 16,384 then ran past a 32,768 window and the window doubled (the model reloaded at a size its card
may not hold). The room is now never more than a quarter of the window the call gets and never under the
class's floor (`model_switch.class_reserve`). A steward profile's `num_predict` wins, and so does a
`max_tokens` the user set (a model table row's `max_tokens_default`). A reply that runs into a room the
window squeezed takes the trim recovery (`ollama_window_steward.squeezed_cut`), and one that stops at its
own room ends the turn as a max_tokens stop, both as before. The turn says once per session that the
window sized it.
"""

from __future__ import annotations

from typing import Optional

PROVIDER_DEFAULT = 16384  # providers/hooks.py `max_tokens_budget`'s room when a profile names none


def _pos(v) -> Optional[int]:
    return v if isinstance(v, int) and not isinstance(v, bool) and v > 0 else None


def room(window, requested, *, profile_num_predict=None, explicit=None) -> "tuple[int, bool]":
    """(the reply's room, True when the window sized it below `requested`). A steward profile's `num_predict`
    or the user's own `max_tokens` keeps the request as it was (the profile's rule: never under its own)."""
    want = _pos(requested) or PROVIDER_DEFAULT
    if _pos(profile_num_predict) or _pos(explicit):
        return want, False
    if not _pos(window):
        return want, False
    from halo_harness.agent.model_switch import class_reserve
    out = min(want, max(class_reserve(window), window // 4))  # lowered to the limit, never raised
    return out, out < want


def _explicit(session) -> Optional[int]:
    prof = getattr(session, "provider_profile", None)
    return _pos(getattr(prof, "max_tokens_default", None)) or _pos(getattr(prof, "max_tokens_cap", None))


def line(window: int, tokens: int, requested: int) -> str:
    return (f"the reply's room is {tokens:,} tokens, sized by the {window:,} window (a quarter at most; it was "
            f"{requested:,}) so the window does not grow for it")


def fitted(window, prompt, requested, *, ceiling=None, first: bool = False, **kw) -> "tuple[int, int, bool]":
    """(the room, the window it was sized for, sized below `requested`): `window` is the one the call starts
    from; a prompt that will raise it (prompt + room past it, up to `ceiling`) gets the room of the window it
    is raised to, never so much that the room alone raises it again. A session's `first` call starts in a
    window where Halo's own prompt is at most half (a conservative 8,192 default would otherwise hold Halo's
    prompt and little else, and compaction cannot shrink Halo's own prompt)."""
    tokens, sized = room(window, requested, **kw)
    need = (prompt + tokens if not first else max(prompt + tokens, 2 * prompt)) if _pos(prompt) else 0
    if not sized or not _pos(window) or need <= window:
        return tokens, window, sized
    from halo_harness.providers.ollama_fit import power_of_two_ceil
    raised = min(power_of_two_ceil(need), max(window, _pos(ceiling) or 1 << 30))
    more, _s = room(raised, requested, **kw)
    tokens = max(tokens, min(more, raised - prompt))
    return tokens, raised, tokens < (_pos(requested) or PROVIDER_DEFAULT)


def _ceiling(decision, host) -> Optional[int]:
    try:
        from halo_harness.providers.ollama_prompt import window_ceiling
        fit = decision.fit_estimate if _pos(decision.fit_estimate) else None
        return window_ceiling(trained_context=decision.trained_context, fit_estimate=fit,
                              host_max_ctx=getattr(host, "max_ctx", None))
    except Exception:
        return None


def for_call(session, ref, window, requested, decision=None, request=None, host=None) -> "tuple[Optional[int], int]":
    """(the room, the window the call starts from) for a call to the session's own model (`decision`: the
    call's context decision, its profile and its ceiling; `request`: (system, messages, tools), the prompt
    that may raise the window). The start never drops under the window this session last asked of the same
    model (a smaller one reloads it), unless a steward profile names the window. `requested` and `window`
    unchanged for a switch-fitted session (its reserve is the window class's already) and for anything that
    is not the session's model."""
    if ref is not getattr(session, "model_ref", None) or getattr(session, "_switch_reserve", None) or not _pos(window):
        return requested, window
    prompt = None
    if request is not None:
        from halo_harness.providers.ollama_wire_estimate import wire_estimate
        prompt = wire_estimate(*request) - 1024
    first = not getattr(session, "_reply_room_called", False)
    session._reply_room_called = True
    profile = getattr(decision, "profile", None) or {}
    ceiling = _ceiling(decision, host) if decision is not None else None
    kept = (getattr(session, "_reply_room_windows", None) or {}).get(getattr(ref, "model", None))
    if _pos(kept):  # after a call the session's context is the window last sent (a re-send's larger one too)
        kept = max(kept, _pos(getattr(getattr(session, "model_profile", None), "context_tokens", None)) or 0)
    if _pos(kept) and not profile.get("num_ctx"):
        window = min(max(window, kept), max(window, _pos(ceiling) or kept))
    tokens, window, sized = fitted(window, prompt, requested, explicit=_explicit(session), first=first,
                                   ceiling=ceiling, profile_num_predict=profile.get("num_predict"))
    session._reply_room_windows = {**(getattr(session, "_reply_room_windows", None) or {}), getattr(ref, "model", None): window}
    if sized and not getattr(session, "_reply_room_said", False):
        try:
            session._reply_room_said = True
            from halo_harness.agent.prompt_wire import _queue_line
            _queue_line(session, line(window, tokens, _pos(requested) or PROVIDER_DEFAULT))
        except Exception:
            pass
    return tokens, window
