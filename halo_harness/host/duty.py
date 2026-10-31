"""halo_harness.host.duty -- the duty steward's pass (Halo 3.3.7.0 R2; plans/local-model-fit-brief.md H10.5c / H10.9;
the command is host_steward_cli.py).

The duty steward is **not** in the host process: it is its own process (`halo host steward run`), a peer of the host
like any other with its own identity and grant (`control` by default; its peers.json record carries `duty: true`, so
fleet.allow_control: ask does not queue it -- the owner turned it on; `none` still keeps the host a monitor). Each
pass reads the host's `GET findings` and `GET card`, asks the 3.3.4.0 steward's model (ollama_steward/agent.py,
through the host's own Ollama like any other client) for a note and any extra proposal, and lands each `where: host`
fix through the same typed operations, the finding cited (`evidence.finding`): the host's guards and verify judge it
like any other. A note per pass goes to the host's steward notes (the stream's `note` frames).

    identity(home) / make_identity(home, grants) / drop_identity(home)   the steward's peer record and key file
    client(home) -> HostClient | None   signed as the duty steward, to the host this machine runs (serve.json)
    pass_once(home, model, *, caller=None, client_=None, now=None) -> {findings, sent, note, skipped}
"""

from __future__ import annotations

import json
import secrets
import time
from typing import Callable, Optional

from halo_harness.host import state as S

STATE_FILE, KEY_FILE = "steward.json", "steward.key"
NAME = "duty steward"
FIELD_OPS = {"num_ctx": "set_num_ctx", "num_predict": "set_num_predict", "keep_alive": "set_keep_alive",
             "tools_max": "set_tools_max"}
MAX_SENDS = 2


def _key_path(home):
    return S.host_dir(home) / KEY_FILE


def read_state(home) -> dict:
    try:
        got = json.loads((S.host_dir(home) / STATE_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return got if isinstance(got, dict) else {}


def write_state(home, data: dict) -> None:
    from halo_harness.privateio import write_private_atomic
    S.host_dir(home).mkdir(parents=True, exist_ok=True)
    write_private_atomic(S.host_dir(home) / STATE_FILE, json.dumps(data, indent=2))


def drop_state(home) -> None:
    try:
        (S.host_dir(home) / STATE_FILE).unlink()
    except OSError:
        pass


def identity(home) -> "tuple[Optional[str], Optional[bytes]]":
    st = read_state(home)
    try:
        key = bytes.fromhex(_key_path(home).read_text(encoding="ascii").strip())
    except (OSError, ValueError):
        key = None
    return st.get("peer"), key


def make_identity(home, grants=("view", "control")) -> str:
    """The duty steward's peer record on this host (made once; its grants as given)."""
    from halo_harness.privateio import write_private_atomic
    pairing = S.HostPairing(home)
    pid, key = identity(home)
    if pid and key and pairing.member(pid):
        pairing.update_member(pid, grants=list(grants), duty=True)
        return pid
    pid, key = f"duty-{secrets.token_hex(6)}", secrets.token_bytes(32)
    pairing.add_member({"id": pid, "name": NAME, "host": "this machine", "duty": True, "grants": list(grants)}, key)
    S.host_dir(home).mkdir(parents=True, exist_ok=True)
    write_private_atomic(_key_path(home), key.hex())
    write_state(home, {**read_state(home), "peer": pid})
    return pid


def drop_identity(home) -> None:
    pid, _key = identity(home)
    if pid:
        S.HostPairing(home).remove(pid, kicked=False)
    try:
        _key_path(home).unlink()
    except OSError:
        pass


def client(home):
    from halo_harness.ollama_steward.host_client import HostClient
    info = S.read_info(home)
    pid, key = identity(home)
    if not info or not pid or not key:
        return None
    scheme = "https" if info.get("tls") else "http"
    entry = {"url": f"{scheme}://127.0.0.1:{info['port']}", "tls": bool(info.get("tls")),
             "fingerprint": info.get("fingerprint"), "name": info.get("name")}
    return HostClient(entry, key, pid, timeout=10.0)


def _text(findings: list, card: dict) -> str:
    from halo_harness.ollama_steward.rules import format_finding
    out = ["The host's card:"]
    for r in card.get("hosts") or []:
        out.append(f"- {r.get('name')}: {r.get('footprint')}; loaded: "
                   + (", ".join(str(m.get("model")) for m in (r.get("card") or {}).get("loaded") or []) or "nothing"))
    out.append("The host's findings (where: host = a fix the host applies; client = one a harness performs):")
    for f in findings:
        out += [f"{x} (where: {f.get('where')})" if i == 0 else x for i, x in enumerate(format_finding(f))]
    return "\n".join(out) if findings else "\n".join(out + ["- none"])


def _sends(findings: list, props: list) -> list:
    """(finding, field, to, why) for each rules proposal on the host's side, then each model proposal that names a
    finding's key (it cites that finding)."""
    out = []
    for f in findings:
        p = f.get("proposal") or {}
        if f.get("where") == "host" and p.get("field") in FIELD_OPS:
            out.append((f, p["field"], p["to"], p.get("why") or f.get("finding")))
    by_key = {f.get("key"): f for f in findings}
    for p in props:
        f = by_key.get(p.get("key"))
        if f is not None and p.get("field") in FIELD_OPS and not any(s[0] is f and s[1] == p["field"] for s in out):
            out.append((f, p["field"], p.get("to"), str(p.get("why") or "the duty steward's model proposes it")))
    return out[:MAX_SENDS]


def pass_once(home, model: Optional[str], *, caller: Optional[Callable] = None, client_=None,
              now: Optional[float] = None) -> dict:
    from halo_harness.ollama_steward import agent, agent_prompt, notes
    from halo_harness.ollama_steward.host_client import HostError
    now = time.time() if now is None else now
    c = client_ or client(home)
    if c is None:
        return {"findings": 0, "sent": [], "note": None, "skipped": "halo host is not running here (halo host serve)"}
    try:
        findings = [f for f in c.get("findings").get("findings") or [] if isinstance(f, dict)]
        card = c.card(fresh=True)
    except HostError as e:
        return {"findings": 0, "sent": [], "note": None, "skipped": f"the host did not answer: {e}"}
    lines, props = [], []
    if model and findings:
        try:
            reply = (caller or agent.live_call)(model, agent_prompt.guide(), _text(findings, card), state_dir=home)
            lines, props, _why = agent.parse((reply or {}).get("text"))
        except Exception as e:
            lines = [f"duty steward {model}: no note ({type(e).__name__}: {str(e)[:160]})"]
    sent = []
    for f, field, to, why in _sends(findings, props):
        params = {"model": f.get("model"), "value": to, "host": f.get("host")}
        try:
            got = c.act("control", FIELD_OPS[field], params, evidence={"finding": f["id"], "lines": [f.get("finding")]},
                        why=str(why)[:200])
            sent.append({"finding": f["id"], "op": FIELD_OPS[field], "to": to, "ok": bool(got.get("ok")),
                         "say": got.get("say") or got.get("line"), "change": got.get("change_id")})
        except HostError as e:
            sent.append({"finding": f["id"], "op": FIELD_OPS[field], "to": to, "ok": False, "say": str(e)})
    head = lines[0] if lines else (f"duty steward: {len(findings)} findings, {len(sent)} fixes sent" if findings
                                   else "duty steward: nothing to fix on this host")
    body = lines + [f"{s['op']} {s['to']} citing {s['finding']}: {s['say']}" for s in sent]
    note = notes.append(home, "note", head, lines=body or [head], cost="local, free" if model else None,
                        model=model, where="duty steward", attention=any(s["ok"] for s in sent), now=now,
                        data={"findings": [f["id"] for f in findings], "sent": sent})
    return {"findings": len(findings), "sent": sent, "note": note, "skipped": ""}
