"""tests.test_copilot_auth -- signing in to the work Copilot (Halo 3.3.17.0 R1, providers/copilot_auth.py,
copilot_tokens.py): the PKCE values; the browser flow against the mock Entra (the code exchanged with its verifier,
who signed in, the refresh token in the env file only); a redirect with another state is refused; the loopback
answers one request and closes; the device flow polls through two `authorization_pending`; a token is refreshed
60 s before it expires and not before; a revoked refresh token says the sign-in expired; consent and offline mode
each say their one line; signout forgets everything; no token in config.json, account.json or any log line.
Mock server only (tests/helpers/mock_copilot.py); no real browser, no Microsoft endpoint.

Run: python -m tests.test_copilot_auth
"""

from __future__ import annotations

import base64
import hashlib
import logging
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.copilot_rig import CopilotRig  # noqa: E402
from tests.helpers.mock_copilot import USER  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


@test
def test_pkce_values(ctx: Ctx):
    from halo_harness.providers.copilot_auth import pkce_pair
    v, c = pkce_pair()
    ctx.check(f"the verifier is 43 url-safe characters, got {len(v)}", len(v) == 43 and re.fullmatch(r"[A-Za-z0-9_-]+", v))
    want = base64.urlsafe_b64encode(hashlib.sha256(v.encode()).digest()).rstrip(b"=").decode()
    ctx.check("the challenge is base64url(SHA-256(verifier)) with no padding", c == want and "=" not in c)
    ctx.check("two pairs differ", pkce_pair()[0] != v)


@test
def test_the_browser_flow_end_to_end(ctx: Ctx):
    records: list = []

    class _Grab(logging.Handler):
        def emit(self, record):
            records.append(record.getMessage())

    root = logging.getLogger()
    grab, old = _Grab(level=logging.DEBUG), root.level
    root.addHandler(grab)
    root.setLevel(logging.DEBUG)
    try:
        with CopilotRig() as r:
            acct = r.signin()
            ctx.check(f"signed in as the mock's account, got {acct.get('username')}", acct.get("username") == USER)
            url = r.opened[0]
            ctx.check("the browser got the authorize URL with S256, the state and the localhost redirect",
                      "/pretend-tenant/oauth2/v2.0/authorize?" in url and "code_challenge_method=S256" in url
                      and "state=" in url and "redirect_uri=http%3A%2F%2Flocalhost%3A" in url)
            tok = [b for m, p, h, b in r.mock.requests if p.endswith("/token")][0]
            ctx.check("the code was exchanged with its verifier and the same redirect",
                      tok["grant_type"] == "authorization_code" and tok.get("code_verifier") and tok["redirect_uri"].startswith("http://localhost:"))
            env_text = r.env_file().read_text(encoding="utf-8")
            ctx.check("the refresh token is in the env file as HALO_SECRET_COPILOT_REFRESH",
                      "HALO_SECRET_COPILOT_REFRESH=rt-1" in env_text)
            others = r.every_file_text()
            ctx.check("no token in config.json, account.json or any other file under the home",
                      "rt-1" not in others and "at-1" not in others and others)
            from halo_harness.providers import copilot_account as A
            ctx.check("account.json holds who and until when, no token", A.load().get("username") == USER
                      and A.load().get("access_expires_at", 0) > time.time() and "token" not in str(A.load().keys()))
    finally:
        root.removeHandler(grab)
        root.setLevel(old)
    joined = "\n".join(records)
    ctx.check("no token or code reached a log line", "rt-1" not in joined and "at-1" not in joined and "code-1" not in joined)


@test
def test_a_redirect_with_another_state_is_refused(ctx: Ctx):
    from halo_harness.providers import copilot_auth
    from halo_harness.providers.copilot_net import CopilotError
    with CopilotRig() as r:
        def wrong_state(url):
            redirect = re.search(r"redirect_uri=([^&]+)", url).group(1)
            target = urllib.request.unquote(redirect)
            urllib.request.build_opener(urllib.request.ProxyHandler({})).open(f"{target}/?code=code-x&state=other", timeout=5).read()
            return True
        copilot_auth.OPEN_BROWSER = wrong_state
        try:
            r.signin()
            ctx.check("refused", False)
        except CopilotError as e:
            ctx.check(f"one line naming the state, got {e.line!r}", e.kind == "signin" and "state" in e.line)
        ctx.check("no token call was made", not r.mock.calls("/token"))


@test
def test_the_loopback_answers_once_then_closes(ctx: Ctx):
    from halo_harness.providers.copilot_auth import Loopback
    lb = Loopback()
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    body = opener.open(f"http://127.0.0.1:{lb.port}/?code=c&state=s", timeout=5).read()
    ctx.check("the one hit is answered", b"signed in" in body and lb.code == "c" and lb.state == "s")
    lb.done.wait(3)
    time.sleep(0.3)
    try:
        opener.open(f"http://127.0.0.1:{lb.port}/?code=d&state=s", timeout=2).read()
        closed = False
    except (urllib.error.URLError, OSError):
        closed = True
    ctx.check("a second request finds the port closed", closed and lb.hits == 1 and lb.code == "c")


@test
def test_the_device_flow(ctx: Ctx):
    from halo_harness.providers import copilot_auth
    with CopilotRig() as r:
        said: list = []
        from halo_harness.providers.copilot_config import load
        acct = copilot_auth.signin(load(), device=True, say=said.append)
        ctx.check(f"the code and the URL are said, got {said}", any("PRETEND1" in s and "devicelogin" in s for s in said))
        ctx.check(f"polled through two pending answers, got {r.mock.device_polls}", r.mock.device_polls == 3)
        ctx.check("signed in", acct.get("username") == USER and not r.opened)


@test
def test_no_browser_here_takes_the_device_flow(ctx: Ctx):
    from halo_harness.providers import copilot_auth
    from halo_harness.providers.copilot_config import load
    with CopilotRig():
        copilot_auth.OPEN_BROWSER = None  # HALO_NO_BROWSER=1 is set by the rig
        said: list = []
        acct = copilot_auth.signin(load(), say=said.append)
        ctx.check(f"it says why and uses the code, got {said[:1]}", "No browser opens here" in said[0] and acct.get("username") == USER)


@test
def test_the_token_is_refreshed_60_s_early(ctx: Ctx):
    from halo_harness.providers import copilot_tokens as T
    from halo_harness.providers.copilot_config import load
    with CopilotRig() as r:
        r.signin()
        cfg, base = load(), time.time()
        calls = lambda: len(r.mock.calls("/token"))  # noqa: E731
        before = calls()
        try:
            T.NOW = lambda: base + 3600 - 61
            ctx.check("61 s left: the one in memory", T.access_token(cfg) == "at-1" and calls() == before)
            T.NOW = lambda: base + 3600 - 59
            ctx.check("59 s left: refreshed", T.access_token(cfg) == "at-2" and calls() == before + 1)
            ref = [b for m, p, h, b in r.mock.requests if p.endswith("/token")][-1]
            ctx.check("a refresh_token grant with the stored one", ref["grant_type"] == "refresh_token" and ref["refresh_token"] == "rt-1")
            ctx.check("the new refresh token replaced the old in the env file",
                      "HALO_SECRET_COPILOT_REFRESH=rt-2" in r.env_file().read_text(encoding="utf-8"))
        finally:
            T.NOW = time.time


@test
def test_a_revoked_refresh_token_says_the_sign_in_expired(ctx: Ctx):
    from halo_harness.providers import copilot_tokens as T
    from halo_harness.providers.copilot_config import load
    from halo_harness.providers.copilot_net import CopilotError
    with CopilotRig() as r:
        r.signin()
        r.mock.revoked.add("rt-1")
        T.forget_access()
        try:
            T.access_token(load())
            ctx.check("refused", False)
        except CopilotError as e:
            ctx.check(f"expired, with the next step, got {e.line!r}", e.kind == "expired" and "halo copilot signin" in e.line
                      and "AADSTS70008" in e.line)
        from halo_harness.providers import copilot_account as A
        ctx.check("the account record notes it", (A.load().get("last_error") or {}).get("kind") == "expired")


@test
def test_consent_and_offline_each_say_one_line(ctx: Ctx):
    from halo_harness.providers.copilot_config import load
    from halo_harness.providers.copilot_net import CopilotError
    with CopilotRig() as r:
        r.mock.scenario["token"] = "consent"
        try:
            r.signin()
            ctx.check("refused", False)
        except CopilotError as e:
            ctx.check(f"consent names the scope and the admin, got {e.line!r}", e.kind == "consent"
                      and "https://workiq.svc.cloud.microsoft/.default" in e.line and "admin" in e.line)
    with CopilotRig() as r:
        for k in ("HALO_COPILOT_AUTHORITY", "HALO_COPILOT_WORKIQ_URL", "HALO_COPILOT_GRAPH_URL"):
            os.environ.pop(k, None)
        os.environ["HALO_OFFLINE"] = "1"
        try:
            r.signin(device=True)
            ctx.check("refused", False)
        except CopilotError as e:
            ctx.check(f"the existing refusal line, got {e.line!r}", e.kind == "offline"
                      and "offline mode: not connecting to login.microsoftonline.com" in e.line)
        ctx.check("nothing reached the mock", not r.mock.requests)
        ctx.check("load() still reads", load().configured)


@test
def test_signout_forgets_everything(ctx: Ctx):
    from halo_harness.providers import copilot_account as A
    from halo_harness.providers import copilot_tokens as T
    from halo_harness.providers.copilot_config import load
    with CopilotRig() as r:
        r.signin()
        lines = T.signout()
        ctx.check(f"it says what went, got {lines}", any("HALO_SECRET_COPILOT_REFRESH" in s for s in lines))
        ctx.check("the env file line is gone", "HALO_SECRET_COPILOT_REFRESH" not in r.env_file().read_text(encoding="utf-8"))
        ctx.check("no refresh token, no access token, no account", not T.refresh_token() and T.cached(load(), "workiq") is None
                  and A.load() == {})


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
