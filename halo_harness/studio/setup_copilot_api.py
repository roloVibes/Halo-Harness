"""halo_harness.studio.setup_copilot_api -- the Copilot card of Setup -> Providers (Halo 3.3.17.0 R2;
docs/PROVIDERS-copilot.md, docs/STUDIO-setup.md). Same loopback / origin / token guard as every Studio route; the
answers carry no token, ever (the card says who signed in, as `halo copilot status` does).

    GET  setup/copilot                  the card's state (below)
    POST setup/copilot/config {tenant?, client_id?, api?, web?}
                                        `copilot.*` through set_config_value -> 200 {...state, lines}; 422 {problems}
    POST setup/copilot/signin {device?} starts the sign-in on the machine Studio runs on -> 202 {...state}:
                                        a browser can open here: the loopback flow (Microsoft's page opens in a new
                                        tab; the card says "finish in the browser tab that opened"); no browser here
                                        (SSH, no DISPLAY, HALO_NO_BROWSER: a remote Studio) or `device`: the device
                                        code and its URL, shown on the card; 409 while one is waiting
    POST setup/copilot/signout          copilot_tokens.signout -> 200 {...state, lines}

    state = {configured, signed_in, tenant, client_id, api, apis, web, timezone, status: [line], consent_scopes,
             signin: {state: idle|waiting|done|failed, flow, line, user_code, verification_uri}}
"""

from __future__ import annotations

import re
import threading
import time

_LOCK = threading.Lock()
_JOB: dict = {"state": "idle", "flow": "", "line": "", "user_code": "", "verification_uri": "", "at": 0.0}
_ID = re.compile(r"^[A-Za-z0-9._-]{1,200}$")


def _body(req) -> dict:
    return req.body if isinstance(req.body, dict) else {}


def job() -> dict:
    with _LOCK:
        return {k: v for k, v in _JOB.items() if k != "at"}


def _set_job(**fields) -> None:
    with _LOCK:
        _JOB.update(fields, at=time.time())


def state() -> dict:
    from halo_harness.copilot_cli import status_lines
    from halo_harness.providers.copilot_config import APIS, load
    from halo_harness.providers.copilot_route import signed_in
    cfg = load()
    return {"configured": cfg.configured, "signed_in": signed_in(), "tenant": cfg.tenant, "client_id": cfg.client_id,
            "api": cfg.api, "apis": list(APIS), "web": cfg.web, "timezone": cfg.timezone, "status": status_lines(cfg),
            "consent_scopes": cfg.consent_scopes(), "signin": job()}


def post_config(req):
    from halo_harness.providers.copilot_config import APIS
    from halo_harness.theme import set_config_value
    body, problems, writes = _body(req), [], []
    for key in ("tenant", "client_id"):
        if key in body:
            v = str(body.get(key) or "").strip()
            if v and not _ID.match(v):
                problems.append(f"copilot.{key}: {v!r} is not a tenant id, domain or app id (letters, digits, . _ -)")
            elif v:
                writes.append((f"copilot.{key}", v))
    if "api" in body:
        api = str(body.get("api") or "")
        if api in APIS:
            writes.append(("copilot.api", api))
        else:
            problems.append(f"copilot.api: one of {', '.join(APIS)}")
    if "web" in body:
        writes.append(("copilot.web", bool(body.get("web"))))
    if problems or not writes:
        return 422, {"error": (problems or ["nothing to save"])[0], "problems": problems or ["nothing to save"]}
    for key, value in writes:
        set_config_value(key, value)
    return 200, {**state(), "lines": [f"{k} = {v}" for k, v in writes]}


def _run(fn) -> None:
    from halo_harness.providers.copilot_net import CopilotError
    try:
        acct = fn()
        who = acct.get("username") or acct.get("name") or "your account"
        _set_job(state="done", line=f"Signed in as {who}.")
    except CopilotError as e:
        _set_job(state="failed", line=e.line)
    except Exception as e:  # one line on the card, never a traceback
        _set_job(state="failed", line=f"Copilot: the sign-in failed ({type(e).__name__}: {e})")


def post_signin(req):
    from halo_harness.providers import copilot_auth as AU
    from halo_harness.providers import copilot_errors as E
    from halo_harness.providers.copilot_config import load
    from halo_harness.providers.copilot_net import CopilotError
    cfg = load()
    if not cfg.configured:
        err = E.not_set_up()
        return 422, {"error": err.line, "problems": [err.line]}
    if job()["state"] == "waiting":
        return 409, {"error": "a sign-in is already waiting: finish it, or wait for it to end", "problems": []}
    from halo_harness.studio.setup_door import no_browser_reason
    device = bool(_body(req).get("device")) or (AU.OPEN_BROWSER is None and bool(no_browser_reason()))
    if device:
        try:
            start = AU.device_start(cfg, cfg.api)
        except CopilotError as e:
            return 422, {"error": e.line, "problems": [e.line]}
        uri = str(start.get("verification_uri") or start.get("verification_url") or "")
        _set_job(state="waiting", flow="device", user_code=str(start.get("user_code") or ""), verification_uri=uri,
                 line=f"Open {uri} on any device and enter the code {start.get('user_code')}.")
        target = lambda: AU.device_poll(cfg, cfg.api, start)  # noqa: E731
    else:
        _set_job(state="waiting", flow="browser", user_code="", verification_uri="",
                 line="Finish in the browser tab that opened (Microsoft's sign-in page); this card updates when you do.")
        target = lambda: AU.signin_browser(cfg, cfg.api, say=lambda _line: None)  # noqa: E731
    threading.Thread(target=_run, args=(target,), daemon=True, name="halo-copilot-signin").start()
    return 202, state()


def post_signout(req):
    from halo_harness.providers.copilot_tokens import signout
    lines = signout()
    _set_job(state="idle", flow="", line="", user_code="", verification_uri="")
    return 200, {**state(), "lines": ["Signed out: " + "; ".join(lines) + "."]}


ROUTES = {"setup/copilot": ("GET", lambda req: (200, state())), "setup/copilot/config": ("POST", post_config),
          "setup/copilot/signin": ("POST", post_signin), "setup/copilot/signout": ("POST", post_signout)}


def dispatch_setup_copilot(req):
    if req.path not in ROUTES:
        return None
    method, fn = ROUTES[req.path]
    return fn(req) if req.method == method else (405, {"error": "method not allowed"})
