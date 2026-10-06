"""halo_harness.providers.gateway_routing -- Halo 2.0.5 round 4:
failover between gateway hosts + the lanes rule, on top of the Governor
(the port of the kit's routing.py, wired into Halo's own shapes).

`choose(candidates)` -- the failover half: candidates are MODEL REFS
(the 2.0.1 fallback-model mechanism's own list: the role's model plus
`roles.<name>.fallbacks`), each resolving to a route and therefore a
gateway host/bucket. The first candidate whose bucket `health()` is not
`open` wins; when every host is open, the least-cooled one is chosen and
the Governor paces it. Returns `(model_ref, health, pivoted)` plus the
health that caused a switch, so the notice can name it. A fallback on
the SAME host as the primary cannot help (the gateway throttles per
machine) -- `warn_same_host_fallbacks` says so once per config load.

`lanes.py` logic (the brief's section 4) lives here too: tier defaults
per known family, `roles.lanes` mapping roles to the weakest tier they
may use, and the validator that refuses a configuration where reviewer,
judge or tester resolves to a weaker tier than coder -- one plain line
naming the role to raise. The team-template loader runs the same
validator over a template's assignments.

The Governor paces and fails over; it never declines a request.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

from halo_harness.providers import governor

#: model-ref prefixes -> a default tier (1 strongest .. 3 cheapest).
#: Local models (`ol:`/`hf:` local) default tier 2 or 3 by size; the gym
#: score is the tie-breaker when one exists (read from the gym table by
#: the caller, not here -- this table is only the FAMILY default).
_TIER_FAMILY_DEFAULTS: Tuple[Tuple[Tuple[str, ...], int], ...] = (
    (("cc:", "cx:"), 1),
    (("ant:", "dbx:", "or:"), 2),
    (("oai:", "xp:"), 2),
    (("hf:",), 2),
    (("ol:",), 3),
)

#: The standing lane rule: reviewer/judge/tester must never resolve to a
#: WEAKER (higher-numbered) tier than coder.
VERIFIER_ROLES = ("reviewer", "judge", "tester")

#: Provider -> default gateway host (the gateway each prefix talks to when
#: nothing custom is configured). A custom routes.json entry for the same
#: prefix overrides; providers whose host varies per install (dbx:
#: per-workspace, ol: per-host, hf: local, xp:) get a provider-level
#: bucket instead -- same fallback `governor.key_for` itself uses for
#: keyless kinds.
_PROVIDER_DEFAULT_HOSTS = {
    "openrouter": "openrouter.ai",
    "anthropic": "api.anthropic.com",
    "openai": "api.openai.com",
    "databricks": "",
    "ollama": "",
    "huggingface": "",
    "experiential": "",
    "cc": "",
    "codex": "",
}


def default_tier(model_ref: str) -> int:
    ref = (model_ref or "").lower()
    for prefixes, tier in _TIER_FAMILY_DEFAULTS:
        if ref.startswith(prefixes):
            return tier
    return 2


def _host_of(model_ref: str, routes: Optional[dict]) -> str:
    """The gateway host a model ref resolves to: a custom routes.json
    entry for the prefix wins (its base_url's host), else the provider's
    default gateway host, else "" (the caller keys the bucket on the
    provider instead -- the same fallback `governor.key_for` uses)."""
    from halo_harness.model import parse_model_ref
    try:
        parsed = parse_model_ref(model_ref, routes or {})
    except Exception:
        return ""
    provider = getattr(parsed, "provider", "") or ""
    # a custom route entry (routes.json's own shape: a base_url per
    # custom route name) overrides the default host
    for entry in (routes or {}).values():
        if isinstance(entry, dict) and entry.get("base_url") and entry.get("provider") == provider:
            host = (urlparse(entry["base_url"]).hostname or "").lower()
            if host:
                return host
    return _PROVIDER_DEFAULT_HOSTS.get(provider, "")


def tier_for(model_ref: str, *, model_table: "Optional[Dict[str, dict]]" = None) -> int:
    """The tier of a model: an explicit `tier` in the model table wins
    (set by the catalog or the gym), else the family default."""
    entry = (model_table or {}).get(model_ref) or {}
    t = entry.get("tier")
    if isinstance(t, int) and 1 <= t <= 3:
        return t
    return default_tier(model_ref)


def lane_ok(role: str, model_ref: str, lanes: "Optional[Dict[str, int]]",
            *, model_table: "Optional[Dict[str, dict]]" = None) -> bool:
    """Is `model_ref` allowed for `role`? `roles.lanes` maps a role to
    the WEAKEST tier it may use (e.g. `researcher: 3`); no entry means
    no lane restriction for that role."""
    if not lanes:
        return True
    weakest = lanes.get(role)
    if not isinstance(weakest, int) or not 1 <= weakest <= 3:
        return True
    return tier_for(model_ref, model_table=model_table) <= weakest


def validate_lanes(role_table: "Dict[str, Any]", *, lanes: "Optional[Dict[str, int]]" = None,
                   model_table: "Optional[Dict[str, dict]]" = None) -> "List[str]":
    """One plain line per problem (empty list = fine): a verifier role
    (reviewer, judge, tester) resolving to a WEAKER tier than coder.
    `role_table` is `roles.py`'s persisted table (values bare model refs
    or {"model": ...}); lanes come from `roles.lanes` in config."""
    from halo_harness.roles import role_value_parts
    problems: "List[str]" = []
    coder_ref, _ = role_value_parts(role_table.get("coder")) if role_table.get("coder") else (None, None)
    coder_tier = tier_for(coder_ref, model_table=model_table) if coder_ref else None
    if coder_tier is None:
        return problems
    for role in VERIFIER_ROLES:
        ref, _ = role_value_parts(role_table.get(role)) if role_table.get(role) else (None, None)
        if not ref:
            continue
        t = tier_for(ref, model_table=model_table)
        if t > coder_tier:
            problems.append(f"{role} resolves to tier {t} ({ref}), weaker than coder's tier "
                            f"{coder_tier} ({coder_ref}) -- raise {role} to tier {coder_tier} or better")
    return problems


def warn_same_host_fallbacks(fallbacks: "Optional[Dict[str, List[str]]]", role_table: "Dict[str, Any]",
                             routes: Optional[dict] = None) -> "List[str]":
    """A fallback on the same gateway HOST as the primary cannot help --
    the gateway throttles per machine, so both trip together. Returns
    the warning lines (the config loader prints them; the docs say the
    same thing plainly)."""
    from halo_harness.roles import role_value_parts
    warnings_out: "List[str]" = []
    for role, refs in (fallbacks or {}).items():
        primary, _ = role_value_parts(role_table.get(role)) if role_table.get(role) else (None, None)
        if not primary:
            continue
        p_host = _host_of(primary, routes)
        for fb in refs or []:
            if _host_of(fb, routes) and _host_of(fb, routes) == p_host:
                warnings_out.append(f"{role}: fallback {fb} is on the same gateway host as {primary} "
                                    "-- a host-level overload trips both; put the fallback on another host")
    return warnings_out


def _bucket_key_for(ref: str, routes: Optional[dict]) -> str:
    host = _host_of(ref, routes)
    if host:
        return "host:" + host
    return "provider:" + (ref.split(":", 1)[0] if ":" in ref else ref)


def choose(candidates: "List[str]", *, routes: Optional[dict] = None,
           model_table: "Optional[Dict[str, dict]]" = None) -> Tuple[Optional[str], str, bool]:
    """Failover: `(model_ref, health, pivoted)`. The first candidate on
    a host whose Governor bucket is not `open` wins; `pivoted` is True
    when that is not candidates[0] (the notice names `health` as the
    cause). When every host is open, the least-cooled wins and the
    Governor paces it. `None` for an empty candidate list."""
    if not candidates:
        return None, "unknown", False
    ranked: "List[Tuple[str, str]]" = []
    for ref in candidates:
        ranked.append((ref, governor.health(_bucket_key_for(ref, routes))))
    for ref, h in ranked:
        if h != "open":
            return ref, h, (ref != candidates[0])
    # all open: least-cooled wins
    def cooldown_for(ref: str) -> float:
        st = governor.inspect(_bucket_key_for(ref, routes))
        return st["cooldown_remaining"] if st else 0.0
    ref, h = min(ranked, key=lambda r: cooldown_for(r[0]))
    return ref, h, (ref != candidates[0])
