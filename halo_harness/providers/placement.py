"""halo_harness.providers.placement -- Halo 3.3.6.0 R1: the placement rules
(plans/local-model-fit-brief.md Part E3): where a probed local model may
go, read off its battery profile (providers/battery_profile.py).

    verdict(profile, role) -> {ok, why, fix, notes, source}
        ok None: no profile (the declared facts decide, marked "expected")
    profile_for_ref(ref, state_dir) -> the newest profile of an `ol:` ref, or None (no request)
    ref_verdict(ref, role, state_dir) -> verdict, or None when the ref has no profile
    spawn_gate(ref, tool_names, state_dir, *, role) -> None | the line a tool-using child on it gets
    with_tools(state_dir, exclude="") -> the probed local models that call tools, agentic-ready first

The rules: no tools -> never a tool-using sub-agent (compaction, bulk and
small single-shot steps stay open); a weak system role moves the
instruction to the user turn (agent/prompt_wire.py); thinking raises the
reply reserve (placement_apply.py); fenced JSON is stripped before parsing;
unverified identifiers are never authoritative; a 32k window chunks its
inputs and never receives whole sessions (compaction); pivot-only flags a
lineup that names it beside another big model (placement_apply.lineup_pivots);
not interactive -> not a main / `/model` target.
"""

from __future__ import annotations

from typing import Optional

ROLES = ("main", "orchestrator", "coder", "reviewer", "researcher", "small", "compaction", "bulk", "eyes")
TOOL_ROLES = ("main", "orchestrator", "coder", "reviewer", "researcher")
SINGLE_SHOT = ("small", "compaction", "bulk")
ALIASES = {"planner": "orchestrator", "judge": "reviewer", "tester": "coder", "subagent_default": "coder",
           "lead": "orchestrator", "worker": "coder", "visual": "eyes", "vision": "eyes"}  # 3.3.6.0 R6: the visual lane
SESSION_WINDOW = 32768
FIX_TOOLS = "route this step to {better}, or run it as a single-shot step without tools"


class NoToolCalling(ValueError):
    """A tool-using sub-agent asked of a model the battery found with no tool calling (agent/subagent.py)."""


def role_of(role: str) -> str:
    r = str(role or "").strip().lower()
    return r if r in ROLES else ALIASES.get(r, "coder")


def _date(p) -> str:
    from halo_harness.providers.battery_profile import date_of
    return date_of(p)


def with_tools(state_dir, exclude: str = "") -> list:
    """`ol:<model>@<host>` of every probed model that calls tools, agentic-ready first, then the faster."""
    from halo_harness.providers.ollama_capability import all_profiles
    from halo_harness.providers.ollama import ollama_names_match
    seen, out = set(), []
    rows = [p for p in all_profiles(state_dir) if p.get("tools") == "yes" and p.get("model")]
    rows.sort(key=lambda p: (not p.get("agentic_ready"), -float((p.get("speed") or {}).get("tok_s") or 0)))
    for p in rows:
        ref = f"ol:{p['model']}@{p.get('host')}"
        if ref in seen or (exclude and ollama_names_match(p["model"], exclude.split(":", 1)[-1].split("@")[0])):
            continue
        seen.add(ref)
        out.append(ref)
    return out


def _better(state_dir, model: str) -> str:
    got = with_tools(state_dir, exclude=f"ol:{model}") if state_dir is not None else []
    return got[0] if got else "a model with tools"


def usable_window(profile: dict, state_dir=None) -> Optional[int]:
    """3.3.6.0 R5: the largest window the bench saw stay on the GPU (the speed card) over the planner's estimate."""
    if state_dir is not None:
        try:
            from halo_harness.providers.local_bench_runs import load
            sc = load(state_dir, profile.get("host") or "", profile.get("model") or "", profile.get("digest"))
            if sc and isinstance(sc.get("max_gpu_window"), int):
                return sc["max_gpu_window"]
        except Exception:
            pass
    return (profile.get("window") or {}).get("usable")


def verdict(profile: Optional[dict], role: str, *, state_dir=None) -> dict:
    """See the module docstring. `state_dir` names a better model in the fix when one is probed."""
    if not isinstance(profile, dict) or profile.get("tools") not in ("yes", "no"):
        return {"ok": None, "why": "not probed yet", "fix": "halo models probe <ref>", "notes": [], "source": "expected"}
    r = role_of(role)
    model, date = profile.get("model") or "this model", _date(profile)
    notes: list = []
    if profile.get("system_role") == "weak":
        notes.append("its system role is weak: Halo moves the instruction into the user turn")
    if profile.get("reasoning") == "thinking":
        notes.append("it answers in thinking: the reply reserve is raised")
    if profile.get("output") == "fenced-json":
        notes.append("it fences its JSON: the fence is stripped before parsing")
    if profile.get("identifiers") == "unverified":
        notes.append("never let it emit authoritative IDs: resolve with a tool or a stronger model")
    out = {"ok": True, "why": "", "fix": "", "notes": notes, "source": "verified"}
    usable = usable_window(profile, state_dir)
    if profile.get("tools") == "no" and r in TOOL_ROLES:
        out.update(ok=False, why=f"no tool calling on this model (probed {date}): it can't run agentic steps",
                   fix=FIX_TOOLS.format(better=_better(state_dir, model)))
    elif r in ("main", "orchestrator") and profile.get("interactive") == "no":
        out.update(ok=False, why=f"not interactive (probed {date}): a step model, not one to talk to",
                   fix="use it as a step model (bulk, compaction); keep a model with tools as main")
    elif r == "compaction" and isinstance(usable, int) and 0 < usable <= SESSION_WINDOW:
        out.update(ok=False, why=f"a {usable // 1024}k window here: chunk inputs; never a role that receives whole "
                               "sessions", fix="give compaction a model with a 65k window or more")
    elif r == "eyes" and _sees(profile) is False:  # 3.3.6.0 R6: the vision probe said no
        out.update(ok=False, why=f"cannot see images (verified: the battery's image probe, probed {date})",
                   fix="give the visual lane a model that sees (halo models --vision)")
    elif r in ("main", "orchestrator") and isinstance(usable, int) and 0 < usable < SESSION_WINDOW:
        out.update(ok=False, why=f"its window here is {usable:,}, under the {SESSION_WINDOW:,} a main agent needs",
                   fix="lower other loads on the card, or use a smaller model")
    return out


def _sees(profile: dict) -> Optional[bool]:
    from halo_harness.providers.vision_fact import vision_of
    f = vision_of(None, None, profile)
    return f["value"] if f["truth"] == "verified" else None


def profile_for_ref(ref, state_dir) -> Optional[dict]:
    """The newest profile of an `ol:` ref (its host when the ref names one, else any host)."""
    if state_dir is None:
        return None
    try:
        from halo_harness.providers.model_card_purpose import parse_ref
        r = parse_ref(ref)
        if getattr(r, "provider", "") != "ollama":
            return None
        from halo_harness.providers.ollama_capability import profile_for
        host = getattr(r, "host", None)
        if not host:
            from halo_harness.providers.ollama import resolve_ollama_host
            h = resolve_ollama_host(None)
            host = h.name if h is not None else None
        return profile_for(state_dir, r.model, host) or (profile_for(state_dir, r.model) if not getattr(r, "host", None)
                                                          else None)
    except Exception:
        return None


def ref_verdict(ref, role: str, state_dir) -> Optional[dict]:
    p = profile_for_ref(ref, state_dir)
    return verdict(p, role, state_dir=state_dir) if p else None


def role_warning(ref, role: str, state_dir) -> Optional[str]:
    """One line when the role's model fails the role's gate ("<why>: <fix>"), else None (roles.py, doctor)."""
    if not str(getattr(ref, "raw", ref) or "").startswith("ol:"):
        return None
    v = ref_verdict(ref, role, state_dir)
    return f"{v['why']}: {v['fix']}" if v and v["ok"] is False else None


def spawn_gate(ref, tool_names, state_dir, *, role: str = "") -> Optional[str]:
    """The line a tool-using child on a no-tools model gets instead of a start (None: it may start)."""
    if not tool_names:
        return None
    p = profile_for_ref(ref, state_dir)
    if not p or p.get("tools") != "no":
        return None
    raw = getattr(ref, "raw", ref)
    better = _better(state_dir, p.get("model") or "")
    return (f"{raw} has no tool calling (probed {_date(p)}): a tool-using sub-agent{f' ({role})' if role else ''} "
            f"can't run on it. Route this step to {better} (Agent model=...), or run it as a single-shot step "
            "without tools (an agent with tools: [])")


def auto_gate(cands: list, state_dir) -> "tuple[list, list]":
    """models_auto.pick's gate: (the candidates left, a line per local model left out). Every auto agent works
    through its tools, so a model the battery found with no tool calling is never picked."""
    if state_dir is None:
        return cands, []
    keep, said = [], []
    for c in cands:
        p = profile_for_ref(c.ref, state_dir) if str(c.ref).startswith("ol:") else None
        if p and p.get("tools") == "no":
            said.append(f"skipped {c.ref}: no tool calling (probed {_date(p)}), so it can't run an agent")
        else:
            keep.append(c)
    return keep, said


def interactive_note(ref, state_dir) -> Optional[str]:
    """Why the `/model` picker greys this model (None: it is a chat target)."""
    p = profile_for_ref(ref, state_dir)
    if not p:
        return None
    v = verdict(p, "main", state_dir=state_dir)
    return None if v["ok"] else v["why"]
