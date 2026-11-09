"""halo_signal.pairing_trust -- the queued `trust` steps of pairing.py, run on the bridge's tick (a step over a
failing link backs off 2 s .. 60 s, TRUST_TRIES times, then gives up with a notice).

    run_ops(pairing, transport) -> [op]   the steps that finished

An `invite` step trusts a new phone's current key while a pairing phrase is open (signal-cli then hands over the
message it held, which must be the phrase); the step is kept in pending.json's `trusted` list (the newest 20) so the
pairing records the safety number it trusted. A `reverify` step trusts a paired phone's confirmed new key.
"""

from __future__ import annotations

from halo_signal import files
from halo_signal.errors import IOFailure, SignalError

TRUST_TRIES = 12
KEEP_TRUSTED = 20


def _digits(sn) -> str:
    return "".join(str(sn).split())


def run_ops(pairing, tr) -> list:
    done: list = []
    if tr is None:
        return done
    with pairing._mu:
        for op in list(files.read_json(pairing.pending_path).get("ops", [])):
            key = (op.get("kind"), op.get("aci"), op.get("safety_number"))
            if pairing._retry.get(key, (0, 0.0))[1] > pairing.clock():
                continue
            try:
                tr.trust(op["aci"], _digits(op["safety_number"]))
            except IOFailure as e:
                n = pairing._retry.get(key, (0, 0.0))[0] + 1
                if n < TRUST_TRIES:
                    pairing._retry[key] = (n, pairing.clock() + min(60.0, 2.0 ** n))
                    continue
                _finish(pairing, op, ok=False, why=f"signal-cli unreachable ({e.message or 'I/O error'})")
            except SignalError as e:
                _finish(pairing, op, ok=False, why=e.message or f"trust refused (code {e.code})")
            else:
                _finish(pairing, op, ok=True)
            pairing._retry.pop(key, None)
            done.append(op)
    return done


def _finish(pairing, op: dict, *, ok: bool, why: str = "") -> None:
    aci = op["aci"]
    with pairing._pending_edit() as q:
        q["ops"] = [o for o in q.get("ops", []) if o != op]
        if ok and op.get("kind") == "invite":
            q["trusted"] = (q.get("trusted") or [])[-(KEEP_TRUSTED - 1):] + [op]
    if op.get("kind") == "reverify" and ok:
        with pairing._edit_peers() as d:
            p = d.setdefault("peers", {}).get(aci)
            if p is not None:
                p.update(safety_number=op["safety_number"], blocked_until_reverified=False, pending_safety_number=None)
    if not ok:
        pairing.add_notice("trust_failed", aci, f"trust step failed: {why}")
