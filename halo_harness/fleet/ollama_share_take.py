"""halo_harness.fleet.ollama_share_take -- the member's side of the hub's
answer to a ledger push (fleet/ollama_share.py; split out in 3.3.5.0 R1): the
hub's steward profiles and its newest steward note; 3.3.7.0 R2: the fleet's crash fingerprints (`take_reply`).
"""

from __future__ import annotations

from halo_harness.fleet import identity


def take_profiles(reply) -> int:
    """A member keeps the profiles the hub's answer carries (ollama_steward/profiles.py)."""
    try:
        from halo_harness.ollama_steward.profiles import merge_from_hub
        return merge_from_hub((reply or {}).get("profiles") if isinstance(reply, dict) else None)
    except Exception:
        return 0


def take_note(reply, home=None) -> bool:
    """A member keeps the hub's newest steward note (3.3.4.0 R4); True when it is a new one."""
    try:
        from halo_harness.ollama_steward.notes import take_hub_note
        payload = (reply or {}).get("steward_note") if isinstance(reply, dict) else None
        return take_hub_note(home if home is not None else identity.home(), payload)
    except Exception:
        return False


def take_reply(reply, home=None) -> None:
    """3.3.7.0 R2: everything a member keeps from the hub's answer: its profiles, its note, the fleet's fingerprints."""
    take_profiles(reply)
    take_note(reply, home)
    try:
        from halo_harness.fleet.ollama_share_cards import take_fleet
        take_fleet(reply, home if home is not None else identity.home())
    except Exception:
        pass
