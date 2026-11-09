"""halo_harness.ollama_steward.agent_quiet -- Halo 3.3.13.1 (the steward hotfix, plans/ROADMAP.md F1): the steward
is quiet when nothing changed. The owner's PC held 664 of the steward's own ten-minute sessions in 30 days: a note
was due whenever a finding's id was new, and the ids moved with every growing proposal.

A note (agent.due) is due only when, since the last note, a finding came or went (its rule, host and model and
severity: not the proposal's number), a server changed (the configured hosts and the local servers the rules saw),
a profile changed (the profile fields a call reads), or a server event fired. Else nothing: no model call, no
session, no note. The signature is kept in the note's data (`sig`), so the next pass compares with it.
"""

from __future__ import annotations

import hashlib
import json
from typing import Optional

FIELDS = ("num_ctx", "num_predict", "keep_alive", "tools_max", "host_for", "compact_at")


def _digest(obj) -> str:
    return hashlib.sha1(json.dumps(obj, sort_keys=True, default=str).encode("utf-8")).hexdigest()[:12]


def findings_part(done: dict) -> list:
    return sorted({f"{f.get('rule')}|{f.get('key')}|{f.get('severity')}" for f in done.get("findings") or []})


def servers_part(ctx: Optional[dict]) -> list:
    ctx = ctx or {}
    hosts = [f"{getattr(h, 'name', '')}|{getattr(h, 'url', '')}" for h in ctx.get("hosts") or []]
    servers = [str(g.get("key")) for g in ctx.get("groups") or [] if g.get("server")]
    return sorted(set(hosts + servers))


def profiles_part() -> str:
    try:
        from halo_harness.ollama_steward.profiles import all_profiles
        return _digest({k: {f: v.get(f) for f in FIELDS if f in v} for k, v in all_profiles().items()})
    except Exception:
        return ""


def signature(ctx: Optional[dict], done: dict) -> dict:
    return {"findings": _digest(findings_part(done)), "servers": _digest(servers_part(ctx)),
            "profiles": profiles_part()}


def what_changed(last_sig, sig: dict) -> list:
    """The parts that differ from the last note's signature ([] = nothing changed)."""
    if not isinstance(last_sig, dict):
        return ["no signature on the last note"]
    names = {"findings": "a finding", "servers": "a server", "profiles": "a profile"}
    return [names[k] for k in ("findings", "servers", "profiles") if last_sig.get(k) != sig.get(k)]
