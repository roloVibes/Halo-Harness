"""halo_harness.ollama_steward.agent_proposals -- Halo 3.3.4.0 R4: a
change the steward's model proposes, checked before it lands.

`check(state_dir, p, ctx)` -> (a finding with the proposal, "") or (None, why):

- `key` names a host and model the rules read this run (`<host>|<model>`)
- `field` is a profile field (profiles.CHANGEABLE) and `to` a value of its
  type (`profiles.clean` keeps it); `host_for` names another configured host
- `num_ctx`: never above the rules' cap (the learned cap, else what the card
  fits with every layer on, else the host's `max_ctx`), never past the fit
  planner's window for the model alone on its card, and never smaller than the
  window sent for a model whose prompts were trimmed or whose replies were cut
  (a conversation that outgrew its window is answered by compaction)
- `num_predict`: at most half the window

`land(...)` sends each that passes through `steward.check` (one change per
model per ten minutes) and the mode: `auto` -> `steward.apply_change`,
`review` -> a proposal line (`halo ollama steward apply <id>`), `off` ->
reported only. Every outcome says one line.
"""

from __future__ import annotations

import time
from typing import Callable, Optional

FLOOR_CTX = 2048


def _group(ctx: dict, key: str) -> Optional[dict]:
    from halo_harness.ollama_steward.profiles import key_for, split_key
    host, model = split_key(key)
    want = key_for(host, model)
    return next((g for g in ctx.get("groups") or [] if g["key"] == want or g["key"].lower() == want.lower()), None)


def _num_ctx_bound(state_dir, g: dict, ctx: dict) -> "tuple[Optional[int], str]":
    from halo_harness.ollama_steward.rules import card_fit
    names = {"learned cap": "the learned cap", "the card": "the card's fit", "max_ctx": "the host's max_ctx"}
    caps = []
    if g.get("cap"):
        caps.append((g["cap"], names.get(g.get("cap_source"), "the measured cap")))
    fit = card_fit(g, ctx)
    if fit:
        caps.append((fit, "the card's fit"))
    return min(caps) if caps else (None, "")


def check(state_dir, p: dict, ctx: dict) -> "tuple[Optional[dict], str]":
    from halo_harness.ollama_steward.profiles import CHANGEABLE, clean
    from halo_harness.ollama_steward.rules import finding, proposal
    key, field, to = str(p.get("key") or ""), str(p.get("field") or ""), p.get("to")
    why = str(p.get("why") or "the steward's model proposes it")[:200]
    g = _group(ctx, key)
    if g is None:
        return None, f"{key or '(no key)'} is no host and model the steward read"
    if field not in CHANGEABLE:
        return None, f"{field or '(no field)'} is not a profile field ({', '.join(CHANGEABLE)})"
    if isinstance(to, float) and to.is_integer() and field in ("num_ctx", "num_predict", "tools_max"):
        to = int(to)
    if field not in clean({field: to}):
        return None, f"{to!r} is not a value {field} takes"
    if field == "host_for" and (to == g["host"] or to not in {h.name for h in ctx.get("hosts") or []}):
        return None, f"{to!r} is not another configured host"
    s, current = g.get("stats") or {}, (g.get("profile") or {}).get(field)
    window = (g.get("profile") or {}).get("num_ctx") or s.get("window")
    if field == "num_ctx":
        bound, source = _num_ctx_bound(state_dir, g, ctx)
        if bound and to > bound:
            return None, f"num_ctx {to} is above {source} ({bound})"
        if to < FLOOR_CTX:
            return None, f"num_ctx {to} is under {FLOOR_CTX}"
        if window and to < window and (s.get("trims") or s.get("cuts")):
            return None, (f"num_ctx {to} is smaller than the window sent ({window}) for a model whose prompts "
                          "outgrew it: that is compaction's to answer")
    if field == "num_predict" and window and to > window // 2:
        return None, f"num_predict {to} is more than half the window ({window})"
    f = finding("agent", g, "info", f"the steward's model proposes {field} {to}: {why}",
                numbers={"window": window, "p95": s.get("p95")}, proposal=proposal(field, current, to, why))
    return f, ""


def land(state_dir, props: list, ctx: dict, *, mode_name: str, say: Callable = lambda _s: None,
         now: Optional[float] = None, scope: str = "until-restart") -> list:
    """Each proposal checked and landed under the mode; the outcomes, in order (3.3.4.0 R5: under the
    steward's profile lock, so a pass running beside this one cannot land the same change twice). 3.3.6.0 R5:
    each landed change carries `scope` (ollama_steward/changes.py; the steward's own default: until-restart)."""
    from halo_harness.ollama_steward import steward
    with steward.profile_lock(state_dir):
        return _land(state_dir, props, ctx, mode_name=mode_name, say=say, now=now, scope=scope)


def _land(state_dir, props: list, ctx: dict, *, mode_name: str, say: Callable, now: Optional[float],
          scope: str = "until-restart") -> list:
    from halo_harness.ollama_steward import steward
    now = time.time() if now is None else now
    out = []
    journal = steward.read_journal(state_dir)
    for p in props[:4]:
        row = {k: p.get(k) for k in ("key", "field", "to", "why")}
        f, why = check(state_dir, p, ctx)
        change = None
        if f is not None:
            change, why = steward.check(state_dir, f, hosts=ctx.get("hosts") or [], now=now, journal=journal)
        if change is None:
            say(f"steward model's proposal dropped: {row['field']} {row['to']} for {row['key']} ({why})")
            out.append({**row, "landed": False, "kind": "dropped", "reason": why})
            continue
        if mode_name == "auto":
            r = steward.apply_change(state_dir, f, change, mode_name="auto", now=now, scope=scope)
            journal.append(r)
            say(r["say"])
            out.append({**row, "to": change["to"], "landed": True, "kind": "apply", "id": r["id"]})
        elif mode_name == "review":
            r = steward.propose(state_dir, f, change, now=now)
            say(f"steward proposes: {change['field']} {change.get('from')} -> {change['to']} for {f['model']} on "
                f"{f['host']} ({change['why']}); halo ollama steward apply {f['id']}")
            out.append({**row, "to": change["to"], "landed": False, "kind": "proposal", "id": r["id"]})
        else:
            say(f"steward model proposes {change['field']} {change['to']} for {f['key']} (mode off: not applied)")
            out.append({**row, "landed": False, "kind": "reported"})
    return out


def land_user(state_dir, change: dict, *, scope: str = "keep", by: str = "user", why: str = "",
              session_id: Optional[str] = None, session_pid: Optional[int] = None) -> dict:
    """3.3.6.0 R5: a change you apply (the tuning report, the KV dial, Settings, the bench's trial settings):
    checked like a proposal (a profile field, a value of its type, num_ctx at least FLOOR_CTX, num_predict at most
    half the window, host_for another configured host), written as yours, and its row in changes.jsonl carries
    `scope` (keep unless you pick another). -> {ok, line, id?}"""
    from halo_harness.ollama_steward import changes, steward
    from halo_harness.ollama_steward.profiles import CHANGEABLE, all_profiles, clean, set_field, split_key
    key, field, to = str(change.get("key") or ""), str(change.get("field") or ""), change.get("to")
    host, model = split_key(key)
    if not host or not model:
        return {"ok": False, "line": f"{key or '(no key)'} names no host and model (<host>|<model>)"}
    if field not in CHANGEABLE or (to is not None and field not in clean({field: to})):
        return {"ok": False, "line": f"{field} {to!r} is not a profile change ({', '.join(CHANGEABLE)})"}
    if scope == "session" and not session_id:
        return {"ok": False, "line": "session needs a session to end with: open one (or name it), or pick "
                                     "until-restart or keep"}
    old = all_profiles().get(key) or {}
    window = old.get("num_ctx")
    if field == "num_ctx" and isinstance(to, int) and to < FLOOR_CTX:
        return {"ok": False, "line": f"num_ctx {to} is under {FLOOR_CTX}"}
    if field == "num_predict" and isinstance(to, int) and window and to > window // 2:
        return {"ok": False, "line": f"num_predict {to} is more than half the window ({window})"}
    if field == "host_for" and to is not None:
        from halo_harness.providers.ollama import resolve_ollama_hosts
        if to == host or to not in {h.name for h in resolve_ollama_hosts()}:
            return {"ok": False, "line": f"{to!r} is not another configured host"}
    with steward.profile_lock(state_dir):
        note = f"{by}: {field} {to} ({why})" if why else f"{by}: {field} {to}"
        set_field(key, field, to, by="user", note=note[:300])
        row = changes.record(state_dir, by=by, key=key, field=field, before=old.get(field), after=to, scope=scope,
                             why=why, session_id=session_id, session_pid=session_pid, before_by=old.get("by"))
    return {"ok": True, "id": row["id"], "line": f"{field} {changes.fmt(old.get(field))} -> {changes.fmt(to)} on "
                                                 f"{key} ({changes.WORDS[row['scope']]})"}
