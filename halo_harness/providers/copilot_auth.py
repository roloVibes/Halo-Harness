"""halo_harness.providers.copilot_auth -- signing in to the user's work Copilot (Halo 3.3.17.0 R1).

The browser is the sign-in (MFA, conditional access and consent happen on Microsoft's page):

* `signin_browser`: the OAuth 2.0 authorization-code flow with PKCE (S256) against
  `https://login.microsoftonline.com/<tenant>/oauth2/v2.0/authorize` and `/token`. The redirect is
  `http://localhost:<free port>` (Entra allows any port on a public client's loopback redirect), served by a
  listener bound to 127.0.0.1 that answers ONE request and closes; the `state` it carries must match. Halo opens
  the browser (`studio.launch._open`, the helper every door uses) and prints the URL too; it waits `WAIT_S`.
* `signin_device`: the device-code flow (`oauth2/v2.0/devicecode`): the code and the verification URL are printed,
  the token endpoint polled at the server's interval. `signin` takes it on its own when no browser can open here
  (SSH, no DISPLAY, HALO_NO_BROWSER: `studio.setup_door.no_browser_reason`).

The refresh token goes to the env file, the access token to memory (copilot_tokens.py); who signed in is noted in
account.json (copilot_account.py). Tests swap `OPEN_BROWSER` and `SLEEP`; no test opens a real browser.
"""

from __future__ import annotations

import base64
import hashlib
import secrets
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Callable, Optional

from halo_harness.providers import copilot_account as A
from halo_harness.providers import copilot_errors as E
from halo_harness.providers import copilot_tokens as T
from halo_harness.providers.copilot_config import CopilotConfig, authority
from halo_harness.providers.copilot_net import CopilotError, request

WAIT_S = 300.0
OPEN_BROWSER: Optional[Callable[[str], bool]] = None  # a test's stand-in for the browser
SLEEP: Callable[[float], None] = time.sleep


def pkce_pair() -> "tuple[str, str]":
    """(verifier, S256 challenge): 43 url-safe characters and the base64url of their SHA-256, no padding."""
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b"=").decode("ascii")
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("ascii")).digest()).rstrip(b"=").decode("ascii")
    return verifier, challenge


def _open(url: str) -> bool:
    if OPEN_BROWSER is not None:
        return bool(OPEN_BROWSER(url))
    from halo_harness.studio.launch import _open as open_url
    return open_url(url)


class Loopback:
    """A one-request listener on 127.0.0.1: the redirect's `code`, `state` and `error` once it has been hit."""

    def __init__(self) -> None:
        self.code = self.state = self.error = None
        self.hits = 0
        self.done = threading.Event()
        owner = self

        class _Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802 (http.server's name)
                owner.hits += 1
                qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
                owner.code = (qs.get("code") or [None])[0]
                owner.state = (qs.get("state") or [None])[0]
                owner.error = (qs.get("error_description") or qs.get("error") or [None])[0]
                body = (b"Halo: signed in to Copilot. You can close this tab." if owner.code
                        else b"Halo: the sign-in did not finish. The terminal says why.")
                self.send_response(200)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                owner.done.set()

            def log_message(self, *args) -> None:  # the query holds the code: never printed
                pass

        self.server = HTTPServer(("127.0.0.1", 0), _Handler)
        self.server.timeout = 0.25
        self.port = self.server.server_address[1]
        self.redirect_uri = f"http://localhost:{self.port}"
        self._closed = False
        self._thread = threading.Thread(target=self._serve_once, daemon=True, name="halo-copilot-loopback")
        self._thread.start()

    def _serve_once(self) -> None:
        try:
            while not self.hits and not self._closed:
                self.server.handle_request()  # one request at most, then the socket closes
        except (OSError, ValueError):
            pass
        finally:
            self.close()

    def close(self) -> None:
        self._closed = True
        try:
            self.server.server_close()
        except OSError:
            pass
        self.done.set()

    def wait(self, timeout: float, abort: Optional[threading.Event] = None) -> bool:
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            if abort is not None and abort.is_set():
                return False
            if self.done.wait(0.2):
                return self.hits > 0
        return False


def authorize_url(cfg: CopilotConfig, api: str, redirect_uri: str, state: str, challenge: str) -> str:
    q = {"client_id": cfg.client_id, "response_type": "code", "redirect_uri": redirect_uri, "response_mode": "query",
         "scope": " ".join(cfg.scope_list(api)), "state": state, "code_challenge": challenge,
         "code_challenge_method": "S256", "prompt": "select_account"}
    return f"{authority(cfg.tenant)}/authorize?{urllib.parse.urlencode(q)}"


def _finish(cfg: CopilotConfig, api: str, tokens: dict) -> dict:
    entry = T.remember(cfg, api, tokens)
    return A.note_signin(tokens.get("id_token"), cfg.tenant, api, entry["expires_at"])


def _token_call(cfg: CopilotConfig, api: str, form: dict) -> dict:
    reply = request("POST", f"{authority(cfg.tenant)}/token", form={"client_id": cfg.client_id, **form})
    if reply.status == 200 and isinstance(reply.data, dict) and reply.data.get("access_token"):
        return reply.data
    raise E.token_error(reply, cfg.consent_scopes(api), refreshing=False)


def signin_browser(cfg: CopilotConfig, api: Optional[str] = None, *, say: Callable[[str], None] = print,
                   wait_s: float = WAIT_S, abort: Optional[threading.Event] = None,
                   on_url: Optional[Callable[[str], None]] = None) -> dict:
    """The loopback flow end to end; the account record, or a CopilotError."""
    api = api or cfg.api
    verifier, challenge = pkce_pair()
    state = secrets.token_urlsafe(16)
    loop = Loopback()
    try:
        url = authorize_url(cfg, api, loop.redirect_uri, state, challenge)
        if on_url is not None:
            on_url(url)
        opened = _open(url)
        say(("Opened the Microsoft sign-in page in your browser." if opened else "Open this page to sign in:")
            + f" Waiting up to {wait_s / 60:.0f} minutes for the sign-in to finish there.")
        say(f"  {url}")
        if not loop.wait(wait_s, abort):
            raise CopilotError("Copilot: the sign-in did not finish in the browser in time -- run `halo copilot "
                               "signin` again (or `--device` to type a code instead).", "signin")
    finally:
        loop.close()
    if loop.error:
        raise E.token_error(_reply_of(loop.error), cfg.consent_scopes(api), refreshing=False)
    if not loop.code or loop.state != state:
        raise CopilotError("Copilot: the redirect did not carry this sign-in's state, so it was not used -- run "
                           "`halo copilot signin` again.", "signin")
    tokens = _token_call(cfg, api, {"grant_type": "authorization_code", "code": loop.code, "redirect_uri": loop.redirect_uri,
                                    "code_verifier": verifier, "scope": " ".join(cfg.scope_list(api))})
    return _finish(cfg, api, tokens)


def _reply_of(text: str):
    from halo_harness.providers.copilot_net import Reply
    return Reply(400, {}, {"error_description": str(text)}, str(text))


def device_start(cfg: CopilotConfig, api: str) -> dict:
    """`{device_code, user_code, verification_uri, interval, expires_in, message}` from the devicecode endpoint."""
    reply = request("POST", f"{authority(cfg.tenant)}/devicecode",
                    form={"client_id": cfg.client_id, "scope": " ".join(cfg.scope_list(api))})
    if reply.status != 200 or not isinstance(reply.data, dict) or not reply.data.get("device_code"):
        raise E.token_error(reply, cfg.consent_scopes(api), refreshing=False)
    return reply.data


def device_poll(cfg: CopilotConfig, api: str, start: dict, *, abort: Optional[threading.Event] = None) -> dict:
    """Poll the token endpoint at the server's interval until the code is used, refused or expires."""
    interval = float(start.get("interval") or 5)
    deadline = time.monotonic() + float(start.get("expires_in") or 900)
    form = {"client_id": cfg.client_id, "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
            "device_code": start["device_code"]}
    while time.monotonic() < deadline:
        if abort is not None and abort.is_set():
            raise CopilotError("Copilot: the sign-in was stopped.", "signin")
        SLEEP(interval)
        reply = request("POST", f"{authority(cfg.tenant)}/token", form=form)
        if reply.status == 200 and isinstance(reply.data, dict) and reply.data.get("access_token"):
            return _finish(cfg, api, reply.data)
        code = str(reply.data.get("error") or "") if isinstance(reply.data, dict) else ""
        if code == "authorization_pending":
            continue
        if code == "slow_down":
            interval += 5
            continue
        raise E.token_error(reply, cfg.consent_scopes(api), refreshing=False)
    raise CopilotError("Copilot: the device code expired before it was used -- run `halo copilot signin --device` "
                       "again.", "signin")


def signin_device(cfg: CopilotConfig, api: Optional[str] = None, *, say: Callable[[str], None] = print,
                  abort: Optional[threading.Event] = None) -> dict:
    api = api or cfg.api
    start = device_start(cfg, api)
    say(f"To sign in, open {start.get('verification_uri') or start.get('verification_url')} and enter the code "
        f"{start.get('user_code')} (it is good for {int(float(start.get('expires_in') or 900)) // 60} minutes).")
    return device_poll(cfg, api, start, abort=abort)


def signin(cfg: CopilotConfig, api: Optional[str] = None, *, device: bool = False,
           say: Callable[[str], None] = print) -> dict:
    """The browser flow, or the device flow when asked or when no browser can open here."""
    if not cfg.configured:
        raise E.not_set_up()
    if not device and OPEN_BROWSER is None:
        from halo_harness.studio.setup_door import no_browser_reason
        why = no_browser_reason()
        if why:
            say(f"No browser opens here ({why}), so the sign-in uses a device code.")
            device = True
    return signin_device(cfg, api, say=say) if device else signin_browser(cfg, api, say=say)
