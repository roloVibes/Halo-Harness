"""halo_harness.ollama_steward.profiles -- Halo 3.3.4.0 R3: one profile per
host and model, what every halo reads before each call to that model.

    ollama.profiles["<host>|<model>"] = {num_ctx, num_predict, keep_alive,
        tools_max, host_for, compact_at, note, by ("steward" | "user" |
        "hub"), at}

in `~/.halo/config.json`. `<host>` is the host's name on this machine (a
line from another machine is mapped by `traffic.canonical_host`, so the
hub's key names its own host). How a call reads it
(`providers.ollama_hw.resolve_context_decision`, `agent/loop.py`):

- `num_ctx`: the window, sent on every call to that model (one window per
  host and model: two windows reload the model every call); it wins over
  the memory estimate, never over the learned cap (`~/.halo/ollama-fit.json`)
  or the host's `max_ctx`, and it is the most the call gets
- `num_predict`: the reply's room, never squeezed below it (the prompt
  compacts first)
- `keep_alive`, `host_for` (ask this model on that host instead),
  `tools_max`, `compact_at` (compact before a call whose prompt passes this
  share of the window; 0.8 when unset)

The hub hands its profiles to each member in the answer to the member's
`POST /fleet/v1/ollama` (fleet/ollama_share.py), keyed by the member's own
host names; the member keeps them with `by: "hub"`, never over its own
`by: "user"` entry.
"""

from __future__ import annotations

import time
from typing import Optional

FIELDS = ("num_ctx", "num_predict", "keep_alive", "tools_max", "host_for", "compact_at", "note", "by", "at")
CHANGEABLE = ("num_ctx", "num_predict", "keep_alive", "tools_max", "host_for", "compact_at")
COMPACT_AT = 0.8
CONFIG_KEY = "ollama.profiles"


def short_model(model) -> str:
    m = str(model or "").strip()
    return m[:-len(":latest")] if m.endswith(":latest") else m


def key_for(host_name, model) -> str:
    return f"{host_name}|{short_model(model)}"


def split_key(key: str) -> "tuple[str, str]":
    host, _, model = str(key).partition("|")
    return host, model


def _config_of(home) -> dict:
    import json
    from pathlib import Path
    try:
        data = json.loads((Path(home) / "config.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def all_profiles(home=None) -> dict:
    """Every profile in config.json ({} when none); entries that are not
    dicts are skipped. `home`: another state dir's config (the hub's)."""
    try:
        if home is not None:
            raw = (_config_of(home).get("ollama") or {}).get("profiles") or {}
        else:
            from halo_harness.theme import get_config_value
            raw = get_config_value(CONFIG_KEY, default={})
    except Exception:
        return {}
    return {k: v for k, v in raw.items() if isinstance(k, str) and isinstance(v, dict)} if isinstance(raw, dict) \
        else {}


def lookup(host, model) -> Optional[dict]:
    """The profile for `host` (an OllamaHost or a host name) and `model`, or None."""
    name = getattr(host, "name", host)
    if not name or not model:
        return None
    return all_profiles().get(key_for(name, model))


def _save(profiles: dict) -> None:
    from halo_harness.theme import set_config_value, unset_config_value
    if profiles:
        set_config_value(CONFIG_KEY, profiles)
    else:
        unset_config_value(CONFIG_KEY)


def _pos(v) -> Optional[int]:
    return v if isinstance(v, int) and not isinstance(v, bool) and v > 0 else None


def clean(entry: dict) -> dict:
    """Only the known fields, each of its own type (a typo never breaks a call)."""
    out: dict = {}
    for k in ("num_ctx", "num_predict", "tools_max"):
        if _pos(entry.get(k)):
            out[k] = entry[k]
    ka = entry.get("keep_alive")
    if isinstance(ka, (str, int)) and not isinstance(ka, bool) and str(ka).strip():
        out["keep_alive"] = ka
    if isinstance(entry.get("host_for"), str) and entry["host_for"].strip():
        out["host_for"] = entry["host_for"].strip()
    ca = entry.get("compact_at")
    if isinstance(ca, (int, float)) and not isinstance(ca, bool) and 0.3 <= ca <= 0.95:
        out["compact_at"] = float(ca)
    for k in ("note", "by", "at"):
        if isinstance(entry.get(k), str) and entry[k]:
            out[k] = entry[k]
    return out


def set_field(key: str, field: str, value, *, by: str = "steward", note: Optional[str] = None) -> dict:
    """One field of one profile set (None removes the field; an empty profile goes). Returns the profile."""
    from halo_harness.ollama_steward.ledger import now_iso
    profiles = all_profiles()
    entry = dict(profiles.get(key) or {})
    if value is None:
        entry.pop(field, None)
    else:
        entry[field] = value
    entry.update(by=by, at=now_iso())
    if note:
        entry["note"] = note
    entry = clean(entry)
    if any(k in entry for k in CHANGEABLE):
        profiles[key] = entry
    else:
        profiles.pop(key, None)
    _save(profiles)
    return entry


def clamp_window(num_ctx, *, learned_cap=None, host_max_ctx=None, trained=None) -> Optional[int]:
    """A profile window held under the learned cap, the host's max_ctx and the trained context."""
    v = _pos(num_ctx)
    if v is None:
        return None
    for cap in (learned_cap, host_max_ctx, trained):
        if _pos(cap):
            v = min(v, cap)
    return v


def compact_at(profile: Optional[dict]) -> float:
    ca = (profile or {}).get("compact_at")
    return float(ca) if isinstance(ca, (int, float)) and not isinstance(ca, bool) and 0.3 <= ca <= 0.95 \
        else COMPACT_AT


# ---- the hub hands its profiles to a member ---------------------------------------------------

def _hosts_of(home) -> list:
    from halo_harness.providers.ollama import _host_from_dict, resolve_ollama_hosts
    raw = (_config_of(home).get("ollama") or {}).get("hosts")
    hosts = [h for h in (_host_from_dict(d) for d in raw if isinstance(d, dict)) if h] if isinstance(raw, list) else []
    return hosts or resolve_ollama_hosts()


def payload_for_member(home, member: str, *, since_s: float = 7 * 86400) -> dict:
    """The hub's profiles (its own `home`) keyed by `member`'s own host
    names: the member's forwarded ledger lines say which name it uses for
    which of the hub's hosts (the Mac's `lan` is the PC's `default`)."""
    profiles = all_profiles(home)
    if not profiles or not member:
        return {}
    from halo_harness.ollama_steward.ledger import read_calls
    from halo_harness.ollama_steward.traffic import canonical_host
    hosts = _hosts_of(home)
    names: dict = {}
    for line in read_calls(home, since=since_s):
        if line.get("from") != member:
            continue
        here, _h = canonical_host(line.get("host") or {}, hosts)
        theirs = (line.get("host") or {}).get("name")
        if theirs:
            names[here] = theirs
    out = {}
    for key, entry in profiles.items():
        host, model = split_key(key)
        if host in names and entry.get("by") != "hub":
            out[key_for(names[host], model)] = {k: v for k, v in entry.items() if k in FIELDS}
    return out


def merge_from_hub(payload, *, now: Optional[float] = None) -> int:
    """A member keeps the hub's profiles with by "hub"; its own "user"
    entries stay. Returns how many entries changed."""
    if not isinstance(payload, dict) or not payload:
        return 0
    from halo_harness.ollama_steward.ledger import now_iso
    profiles = all_profiles()
    changed = 0
    for key, entry in payload.items():
        if not isinstance(key, str) or "|" not in key or not isinstance(entry, dict):
            continue
        mine = profiles.get(key) or {}
        if mine.get("by") == "user":
            continue
        new = clean({**entry, "by": "hub", "at": entry.get("at") or now_iso(now or time.time())})
        if {k: mine.get(k) for k in CHANGEABLE} != {k: new.get(k) for k in CHANGEABLE}:
            profiles[key] = new
            changed += 1
    if changed:
        _save(profiles)
    return changed
