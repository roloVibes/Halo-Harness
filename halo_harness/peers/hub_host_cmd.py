"""halo_harness.peers.hub_host_cmd -- a Studio command sent to a halo host, no member session needed (Halo 3.3.7.0 R2;
docs/HOST.md "Peers act through the host").

A machine that runs `halo host` takes the command itself, through the host's typed vocabulary, signed with this
harness's own pair key for that host (fleet.json's `hosts`). Studio's Load / Unload / Probe / Bench / Twin verify /
Pull / Delete map onto the host's operations:

    load -> control/warm {model, num_ctx?, keep_alive?}      unload -> control/unload {model}
    probe -> control/rerun_battery {model, force?}           bench -> control/bench {model, quick?}
    twin-verify -> control/verify_twin {model, window?}      pull -> manage/pull {model}
    delete -> manage/delete {model, force?}                  (copy / rename / twin creation: not in the vocabulary)

    send(client, act, fields, *, port) -> (status, answer)  one op; a queued request (host.allow_control: ask
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
