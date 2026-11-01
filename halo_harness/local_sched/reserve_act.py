"""halo_harness.local_sched.reserve_act -- turning a bundle on and off: the claim, its keep_alive, the release (Halo
3.3.7.0 R5; plans/local-model-fit-brief.md L2; `halo pack on | off`, the Pack Manager's tick).

    claim(bundle_id, *, host=None, holder="keep", cwd=None, state_dir=None) -> (ok, lines, verdict)
        the verdict first (local_sched/bundle_fit.py): only a ready bundle is turned on -- "needs N downloads" and
        "won't work" are its own lines and nothing is written. Then the bundle is installed and enabled (a shipped one),
        the claim recorded -- through the paired halo host's `control/claim` when one serves the card, else in this
        machine's `<state>/ollama/claims.json` -- and the reserved model's profile gets keep_alive -1, Halo-side, as a
        change (ollama_steward/changes.py) scoped to the bundle's life: `keep` from the CLI (until `halo pack off`),
        `until-restart` when a halo process holds it (Studio's tick: undone when the bundle is unticked or that halo
        exits). A bundle with no reservation is recorded with 0 GB: its routing holds (offline-only: no cloud rung).
    release(bundle_id, *, state_dir=None, cwd=None, disable=True) -> (ok, lines)   the claim taken back, the keep_alive
        change reverted, the pack disabled
    at_exit() -> lines    the bundles this process holds released (atexit, for holder="process")
3.3.8.0 R3: a claim a halo process holds (holder="process") carries a lease (claims_file `until`, pool.claim_lease_s)
here and on the host, renewed by this process's heartbeat (local_sched/lease.py): a killed Studio's claim expires.
Nothing downloads and nothing loads here: the reserved model loads on its first call (or `halo local warm <model>`).
"""

from __future__ import annotations

import os
import time

from halo_harness.local_sched import claims_file as CF

_HOOKED = [False]
_MINE: dict = {}  # bundle id -> the state dir it was claimed in (this process holds it)


def _state(state_dir=None):
    from halo_harness.local_sched.reserve import _state as s
    return s(state_dir)


def _host_act(host, op: str, params: dict) -> "tuple[bool, str]":
    from halo_harness.local_sched.pivot import _client
    from halo_harness.ollama_steward.host_client import HostError, _addr_port
    c = _client(host)
    if c is None:
        return False, ""
    served = c.served_name(_addr_port(str(getattr(host, "url", "")))[1])
    if served:
        params = {**params, "host": served}
    try:
        got = c.act("control", op, params, why="a bundle's reservation")
    except HostError as e:
        return False, str(e)
    if got.get("queued"):
        return False, got.get("line") or "queued for the host's owner (fleet.allow_control: ask there)"
    return bool(got.get("ok", True)), str(got.get("say") or "")


def _keep_alive(state, host_name: str, model: str, bundle_id: str, holder: str) -> "tuple[str, str]":
    from halo_harness.ollama_steward.agent_proposals import land_user
    from halo_harness.ollama_steward.profiles import key_for
    scope = "until-restart" if holder == "process" else "keep"
    got = land_user(state, {"key": key_for(host_name, model), "field": "keep_alive", "to": -1}, scope=scope, by="bundle",
                    why=f"the {bundle_id} bundle reserves it")
    return (got.get("id") or ""), got["line"]


def claim(bundle_id: str, *, host=None, holder: str = "keep", cwd=None, state_dir=None) -> "tuple[bool, list, dict]":
    from halo_harness.local_sched.bundle_fit import verdict
    from halo_harness.local_sched.facts import host_named
    from halo_harness.local_sched.reserve import forget, free_after_claims
    from halo_harness.packs.bundles import ensure_installed, find
    state = _state(state_dir)
    entry = find(bundle_id, cwd=cwd, state_dir=state_dir)
    if entry is None or entry["block"] is None:
        return False, [f"no bundle {bundle_id!r} here (halo pack list --bundles)"], {}
    h = host if host is not None and not isinstance(host, str) else host_named(host)
    v = verdict(entry["block"], h, state_dir=state)
    if v["state"] != "ready":
        tail = [f"  - {o['says']}" for o in v["options"] if o["kind"] != "warn"]
        if v.get("button"):
            tail.append(f"  {v['button']['label']}: " + "; ".join(f"halo models pull {t} --host {v['host']}"
                                                                    for t in v["button"]["tags"]))
        return False, [f"{bundle_id} is not turned on: {v['says']}"] + tail, v
    ok, lines, _pack = ensure_installed(entry, cwd=cwd, state_dir=state_dir)
    if not ok:
        return False, lines, v
    b, res = entry["block"], v.get("reserved")
    row = {"bundle": bundle_id, "name": entry.get("name"), "host": v["host"], "model": None, "gb": 0.0, "window": None,
           "priority": None, "keep_alive": None, "at": round(time.time(), 3), "by": "halo", "holder": holder,
           "holder_pid": os.getpid() if holder == "process" else None, "scope": "until-restart" if holder == "process"
           else "keep", "change_id": None, "escalation": b["routing"]["escalation"], "task_work": b["routing"]["task_work"],
           "via": "local", "until": round(time.time() + CF.lease_s(), 3) if holder == "process" else None}
    if res:
        row.update(model=res["model"], gb=round(float(res["gb"]), 2), window=res["window"], priority=res["priority"], keep_alive=-1)
        landed, say = _host_act(h, "claim", {"model": res["model"], "gb": round(float(res["gb"]), 2), "bundle": bundle_id,
                                             "window": int(res["window"]), "priority": res["priority"],
                                             **({"lease_s": CF.lease_s()} if holder == "process" else {})})
        if say and not landed:
            return False, lines + [f"{bundle_id}: the halo host did not take the claim: {say}"], v
        row["via"] = "host" if landed else "local"
        row["change_id"], ka = _keep_alive(state, v["host"], res["model"], bundle_id, holder)
        lines.append(f"reserved {res['model']} on {v['host']} for {bundle_id}: {float(res['gb']):.1f} GB held"
                     + (" by the halo host" if landed else "") + f"; {ka}")
    else:
        lines.append(f"{bundle_id} is on: nothing reserved")
    CF.put(CF.local_file(state), row)
    forget()
    if holder == "process":
        _hold(bundle_id, state)
        _lease(bundle_id, state, h if row["via"] == "host" else None)
    fac = free_after_claims(h, int((v.get("usable_gb") or 0) * 2 ** 30), state_dir=state)
    lines.append(fac["line"] + f" on {v['host']}")
    lines.append(_routing_line(b, v))
    return True, lines, v


def _routing_line(b: dict, v: dict) -> str:
    from halo_harness.local_sched.reserve import cloud_target
    r = b["routing"]
    if r["escalation"] == "off":
        return "while it is on: no cloud rung (routing.escalation is off for every session here)"
    c = v.get("coder") or {}
    if r["task_work"] == "coder-or-cloud" and c and not c.get("beside"):
        return f"while it is on: task work goes to {cloud_target() or 'a cloud model (routing.escalation.to names it)'}"
    if c:
        return f"while it is on: task work stays on the coder ({c['model']}), beside the reservation"
    return "while it is on: nothing else is evicted for it"


def _hold(bundle_id: str, state) -> None:
    _MINE[bundle_id] = str(state)
    if not _HOOKED[0]:
        import atexit
        atexit.register(at_exit)
        _HOOKED[0] = True


def _lease(bundle_id: str, state, host) -> None:
    """The heartbeat renews this bundle's claim here and on the host while this process lives (3.3.8.0 R3)."""
    from halo_harness.local_sched import lease

    def renew(until: float) -> list:
        from pathlib import Path
        if not Path(state).is_dir():  # that home is gone (a test's scratch home): nothing to renew
            return []
        out = [f"{len(CF.renew(CF.local_file(state), bundle_id, until))} local"]
        if host is not None:
            ok, say = _host_act(host, "renew", {"bundle": bundle_id, "lease_s": CF.lease_s()})
            out.append(say if ok else f"the host did not renew it ({say or 'no answer'})")
        return out
    lease.hold(f"bundle:{bundle_id}", renew)


def release(bundle_id: str, *, state_dir=None, cwd=None, disable: bool = True) -> "tuple[bool, list]":
    from halo_harness.local_sched.facts import host_named
    from halo_harness.local_sched.reserve import forget
    from halo_harness.ollama_steward import changes
    state = _state(state_dir)
    rows = CF.drop(CF.local_file(state), bundle_id)
    lines = []
    for r in rows:
        if r.get("via") == "host":
            ok, say = _host_act(host_named(r.get("host")), "release", {"bundle": bundle_id})
            lines.append(say if ok else f"the halo host did not answer the release ({say or 'no answer'}); its claim "
                                        "stays there until it does")
        if r.get("change_id"):
            lines += changes.revert(state, r["change_id"], f"the {bundle_id} bundle was turned off")
        if r.get("model"):
            lines.append(f"released {r['model']} on {r.get('host')} ({float(r.get('gb') or 0):g} GB)")
    _MINE.pop(bundle_id, None)
    from halo_harness.local_sched import lease
    lease.release(f"bundle:{bundle_id}")
    forget()
    if disable:
        from halo_harness.packs import grants as G
        from halo_harness.packs import state as S
        if S.entry(bundle_id, state_dir) is not None:
            lines += G.disable(bundle_id, state_dir=state_dir)[1]
    return True, lines or [f"{bundle_id} was not on"]


def at_exit() -> list:
    """Only while that home is still this process's home (a test's scratch home that moved on is left alone)."""
    from pathlib import Path
    out: list = []
    try:
        from halo_harness.config.paths import bridge_home
        here = Path(bridge_home()).resolve()
    except Exception:
        return out
    for bundle_id, state in sorted(_MINE.items()):
        try:
            if Path(state).resolve() == here:
                out += release(bundle_id, state_dir=state, disable=False)[1]
        except Exception:
            continue
    return out
