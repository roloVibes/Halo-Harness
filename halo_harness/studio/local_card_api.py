"""halo_harness.studio.local_card_api -- Halo 3.3.6.0 R4: the card's measured facts and its dialect record in
Studio (dispatched by studio/local_api.dispatch_local; docs/STUDIO-local.md). No request to any server.

    GET  local/host/<name>/measured?model=      providers/measured.measured_for + its lines: {measured, lines, cli}
    GET  local/host/<name>/dialect?model=       providers/dialect.record + view: {record, view, cli}
    POST local/host/<name>/dialect {model, set?: {field: value}, reset?: FIELD | "" (every field)}
                                                your edit (marked `user`: it wins over the battery and the ledger);
                                                422 with the problems when a value does not fit its field
Every answer carries `cli`, the `halo models measured | dialect` line that does the same.
"""

from __future__ import annotations

import re
import urllib.parse

_CARD = re.compile(r"^local/host/(?P<name>[^/]+)/(?P<act>measured|dialect)$")


def _host(name: str):
    from halo_harness.providers.ollama import resolve_ollama_hosts
    return next((h for h in resolve_ollama_hosts() if h.name.lower() == name.lower()), None)


def _model(req) -> str:
    body = req.body if isinstance(req.body, dict) else {}
    return str(body.get("model") or (req.query or {}).get("model") or "").strip()


def _dialect(req, host, model: str):
    from halo_harness.providers.dialect import record, reset, set_fields, view
    cli = f"halo models dialect {model} --host {host.name}"
    if req.method == "POST":
        body = req.body if isinstance(req.body, dict) else {}
        if body.get("reset") is not None:
            reset(host, model, str(body["reset"]) or None)
            cli += " --reset" + (f" {body['reset']}" if body["reset"] else "")
        sets = body.get("set") if isinstance(body.get("set"), dict) else {}
        if sets:
            _stored, bad = set_fields(host, model, sets, by="user")
            if bad:
                return 422, {"error": bad[0], "problems": bad, "cli": cli}
            cli += "".join(f" --set {k}={_cli_value(v)}" for k, v in sets.items())
    rec = record(host, model, state_dir=req.state_dir)
    return 200, {"record": rec, "view": view(rec), "cli": cli}


def _cli_value(v) -> str:
    if isinstance(v, dict):
        return ("on" if v.get("on") else "off") + f":{v.get('attempts', v.get('window'))}"
    if isinstance(v, list):
        return ",".join(v)
    if isinstance(v, bool):
        return "on" if v else "off"
    return "auto" if v is None else str(v)


def dispatch_card(req):
    """The answer for a route of this file, else None."""
    m = _CARD.match(req.path)
    if not m:
        return None
    act = m.group("act")
    if req.method not in (("GET",) if act == "measured" else ("GET", "POST")):
        return 405, {"error": "method not allowed"}
    host = _host(urllib.parse.unquote(m.group("name")))
    if host is None:
        return 404, {"error": f"no configured Ollama host named {m.group('name')!r}"}
    model = _model(req)
    if not model:
        return 422, {"error": "say which model: ?model=<name>", "problems": ["model is required"]}
    if act == "dialect":
        return _dialect(req, host, model)
    from halo_harness.providers.measured import lines, measured_for
    got = measured_for(host, model, state_dir=req.state_dir)
    return 200, {"measured": got, "lines": lines(got), "cli": f"halo models measured {model} --host {host.name}"}
