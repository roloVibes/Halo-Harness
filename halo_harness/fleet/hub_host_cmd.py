"""halo_harness.fleet.hub_host_cmd -- a Studio command sent to a halo host, no member session needed (Halo 3.3.7.0 R2;
docs/HOST.md "Peers act through the host").

Before R2 every hub-to-member command needed a live session there (`hub_commands.send` -> `member.link_for(sid)`).
A machine that runs `halo host` takes the command itself, through the host's typed vocabulary, signed with this
harness's own pair key for that host (fleet.json's `hosts`). Studio's Load / Unload / Probe / Bench / Twin verify /
Pull / Delete map onto the host's operations:

    load -> control/warm {model, num_ctx?, keep_alive?}      unload -> control/unload {model}
    probe -> control/rerun_battery {model, force?}           bench -> control/bench {model, quick?}
    twin-verify -> control/verify_twin {model, window?}      pull -> manage/pull {model}
    delete -> manage/delete {model, force?}                  (copy / rename / twin creation: not in the vocabulary)

    for_member(hub, member_name) -> HostClient | None     the paired host the member announced (fleet/hub_hosts.py)
    member_controls(hub, member_name, who) -> controls | None   a member with no live session: its host, or the line
    send(client, act, fields, *, port) -> (status, answer)  one op; a queued request (fleet.allow_control: ask
                                                            there) answers 202 with the owner's line
"""

from __future__ import annotations

from typing import Optional

ACTS = {"load": ("control", "warm"), "unload": ("control", "unload"), "probe": ("control", "rerun_battery"),
        "bench": ("control", "bench"), "twin-verify": ("control", "verify_twin"), "pull": ("manage", "pull"),
        "delete": ("manage", "delete")}
KEEP = {"warm": ("model", "num_ctx", "keep_alive", "beside"), "unload": ("model",), "rerun_battery": ("model", "force"),
        "bench": ("model", "quick"), "verify_twin": ("model", "window"), "pull": ("model",), "delete": ("model", "force")}
NOT_IN_VOCAB = ("{act} through a halo host is not in its vocabulary (warm, unload, pivot, the profile fields, the "
                "battery, the bench, verify_twin, pull, delete, retire, revert): do it on that machine")


def params_for(op: str, fields: dict, served: Optional[str]) -> dict:
    out = {k: fields[k] for k in KEEP.get(op, ()) if fields.get(k) not in (None, "", False)}
    if served:
        out["host"] = served
    return out


def send(client, act: str, fields: dict, *, port: int) -> "tuple[int, dict]":
    from halo_harness.ollama_steward.host_client import HostError
    pair = ACTS.get(act)
    if pair is None:
        return 409, {"error": NOT_IN_VOCAB.format(act=act.capitalize())}
    grant, op = pair
    if act == "pull" and fields.get("cancel"):
        return 409, {"error": "stopping a pull through a halo host is not in its vocabulary: it runs to its end there"}
    try:
        got = client.act(grant, op, params_for(op, fields, client.served_name(port)))
    except HostError as e:
        return (e.status or 502), {"error": str(e), "via": "host"}
    if got.get("queued"):
        return 202, {**got, "ok": False, "error": got.get("line"), "say": got.get("line"), "via": "host"}
    return 200, {**got, "via": f"halo host at {client.addr}"}


def for_member(hub, member_name: str):
    """The paired halo host a member of this hub announced (its url or fingerprint matched in fleet.json `hosts`)."""
    from halo_harness.fleet import hub_hosts, identity, store
    from halo_harness.ollama_steward.host_client import HostClient
    if hub is None or not member_name:
        return None
    row = next((r for r in hub_hosts.listing(hub.home) if r.get("member") == member_name), None)
    if row is None:
        return None
    for e in store.hosts(hub.home):
        if e.get("state", "joined") != "joined":
            continue
        if (row.get("fingerprint") and e.get("fingerprint") == row["fingerprint"]) or e.get("url") == row.get("url"):
            key = store.key_for(e, hub.home)
            return HostClient(e, key, identity.harness(hub.home)["id"]) if key else None
    return None


def member_controls(hub, member_name: str, who: dict) -> Optional[dict]:
    """A member with no live session: the halo host it announced takes the command when this hub is paired with it
    (studio/local_host_acts.host_controls); else the line that says how; None when it announced none."""
    from halo_harness.fleet import hub_hosts
    row = next((r for r in hub_hosts.listing(hub.home) if r.get("member") == member_name), None) if hub else None
    if row is None:
        return None
    c = for_member(hub, member_name)
    if c is None:
        return {"ok": False, "via": "", "why": f"{member_name} has no live session, and its halo host at {row.get('url')} "
                f"is not paired here: `halo host join {row.get('url')} --code ...` on this machine (a code from `halo host "
                "pair` there) and Load goes through it with no session", **who}
    from halo_harness.studio.local_host_acts import host_controls
    rows = [r for r in c.entry.get("serves") or [] if isinstance(r, dict)]
    url = f"http://{rows[0].get('addr')}:{rows[0].get('port')}" if rows else ""
    got = host_controls(url, member_name) if url else None
    return {**got, **who} if got else None
