"""tests.helpers.studio_copilot -- the Copilot card of Setup -> Providers in headless Chrome (Halo 3.3.17.0 R2),
real keys and clicks through the driver base over a scratch home (capture_studio's seeded_home), Studio served in a
thread of this process, the Copilot mock (tests/helpers/mock_copilot.py) standing in for Entra and Work IQ. The
"browser" the sign-in opens is a stub that follows the authorize redirect to the loopback after a pause (never a
real browser: `HALO_NO_BROWSER=1` stays set):

1. the Providers page opens with nothing popped up; the card is there, its status "not set up", the scopes listed
   and the "Register the app" disclosure closed;
2. the tenant and the app id saved through the card's form: config.json has them, the status names the tenant;
3. Sign in (the browser flow): the card says "Finish in the browser tab that opened", then "signed in as" and the mark
   "signed in"; the refresh token is in the env file and nowhere in the page;
4. Sign out: the mark says "set up", the status "not signed in";
5. Sign in on a Studio with no browser (the device flow): the code is shown, then signed in;
6. density: each status row is one line (an ellipsis when cut, its full text in the tooltip); no horizontal scroll.
The last stdout line is the JSON of what it saw (exit 2: no Chrome)."""
from __future__ import annotations

import json
import os
import shutil
import sys
import threading
import time
from contextlib import contextmanager
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tools"))

from tests.helpers.chrome_driver import Driver  # noqa: E402
from tests.helpers.studio_packs_steps import q, qa  # noqa: E402
from tests.helpers.studio_setup_pages import OPEN, goto  # noqa: E402
from tests.helpers.studio_setup_providers import fill, press  # noqa: E402

CARD = "[data-testid=setup-copilot]"
MARK = f"({q('[data-testid=setup-copilot-mark]')}?.textContent || '')"
STATUS = qa("[data-testid=setup-copilot-status]") + ".map((r) => r.textContent).join('\\n')"
LINE = f"({q('[data-testid=setup-copilot-signin-line]')}?.textContent || '')"


def _click(c, sel: str, done: str) -> str:
    btn = q(sel)
    c.wait(f"!!{btn} && !{btn}.disabled", 15)
    c.js(f"{btn}.scrollIntoView({{block: 'center'}}); 1")
    time.sleep(0.2)
    c.click_on(btn)
    try:
        c.wait(done, 6)
        return "pointer"
    except TimeoutError:
        c.js(f"{btn}?.click(); 1")
        c.wait(done, 15)
        return "element"


def first_look(c, url, ctx) -> dict:
    c.go(url)
    goto(c, "providers")
    c.wait(f"!!{q(CARD)}", 30)
    time.sleep(1.0)
    return {"popups": c.js(OPEN), "status0": c.js(STATUS), "mark0": c.js(MARK),
            "scopes": c.js(f"({q('[data-testid=setup-copilot-scopes]')}?.textContent || '')"),
            "register_open": c.js(f"{q('[data-testid=setup-copilot-register]')}.open"),
            "provider_cards": c.js(f"{qa('[data-testid=setup-provider]')}.length")}


def configure(c, url, ctx) -> dict:
    from tests.helpers.mock_copilot import CLIENT_ID, TENANT
    out = {"tenant_by": fill(c, "copilot", "tenant", TENANT), "app_by": fill(c, "copilot", "client_id", CLIENT_ID)}
    out["save_by"] = press(c, "copilot", f"{STATUS}.includes('tenant: {TENANT}')")
    out["status1"] = c.js(STATUS)
    cfg = json.loads((ctx["state"] / "config.json").read_text(encoding="utf-8"))
    out["config"] = cfg.get("copilot")
    return out


def browser_signin(c, url, ctx) -> dict:
    out = {"signin_by": _click(c, "[data-testid=setup-copilot-signin]", f"{LINE}.startsWith('Finish in the browser tab')")}
    out["waiting_line"] = c.js(LINE)
    out["signed_mark"] = c.wait(f"{MARK} === 'signed in' && {MARK}", 30)
    out["status2"] = c.js(STATUS)
    out["opened"] = len(ctx["opened"])
    env = ctx["env_file"].read_text(encoding="utf-8") if ctx["env_file"].is_file() else ""
    out["env_has_refresh"] = "HALO_SECRET_COPILOT_REFRESH=rt-" in env
    out["token_in_page"] = c.js("document.documentElement.outerHTML.includes('rt-1') || document.documentElement.outerHTML.includes('at-1')")
    return out


def signout(c, url, ctx) -> dict:
    out = {"signout_by": _click(c, "[data-testid=setup-copilot-signout]", f"{MARK} === 'set up'")}
    out["status3"] = c.js(STATUS)
    out["lines3"] = c.js(f"({q('[data-testid=setup-copilot-lines]')}?.textContent || '')")
    return out


def device_signin(c, url, ctx) -> dict:
    from halo_harness.providers import copilot_auth
    copilot_auth.OPEN_BROWSER = None  # a Studio with no browser here (HALO_NO_BROWSER=1): the device code
    code = f"({q('[data-testid=setup-copilot-code]')}?.textContent || '')"
    out = {"device_by": _click(c, "[data-testid=setup-copilot-signin]", f"{code} === 'PRETEND1'")}
    out["device_line"] = c.js(LINE)
    out["device_mark"] = c.wait(f"{MARK} === 'signed in' && {MARK}", 30)
    return out


def density(c, url, ctx) -> dict:
    rows = qa(f"{CARD} [data-testid=setup-copilot-status]")
    js = (f"{rows}.map((r) => {{ const s = getComputedStyle(r); return [r.title === r.textContent, s.whiteSpace, s.textOverflow,"
          " r.getBoundingClientRect().height < 24]; })")
    return {"rows": c.js(js), "hscroll": c.js("document.documentElement.scrollWidth > document.documentElement.clientWidth + 1")}


class CopilotDriver(Driver):
    no_chrome = {"skip": "no Chrome found"}

    @contextmanager
    def session(self, c):
        from capture_studio import seeded_home, serve
        from tests.helpers.copilot_rig import follow
        from tests.helpers.mock_copilot import MockCopilot
        from halo_harness.providers import copilot_auth
        state = seeded_home()
        os.environ["HALO_ENV_FILE"] = str(state.parent / "halo-env")
        os.environ["HALO_NO_BROWSER"] = "1"
        mock = MockCopilot().__enter__()
        os.environ.update(mock.env())
        opened: list = []

        def browser(target: str) -> bool:  # the user takes a moment in the tab, then the redirect lands
            opened.append(target)
            threading.Timer(2.5, follow, [target]).start()
            return True
        copilot_auth.OPEN_BROWSER = browser
        copilot_auth.SLEEP = lambda s: time.sleep(1.0)  # the device code stays on screen for a few polls
        srv, url = serve(state, True)
        url = url.replace("mode=orchestra&feed=off", "mode=setup&tour=off")
        ctx = {"state": state, "env_file": state.parent / "halo-env", "opened": opened}
        try:
            yield tuple((fn, (c, url, ctx)) for fn in (first_look, configure, browser_signin, signout, device_signin, density))
        finally:
            copilot_auth.OPEN_BROWSER, copilot_auth.SLEEP = None, time.sleep
            mock.__exit__(None, None, None)
            srv.shutdown()
            srv.server_close()
            shutil.rmtree(state.parent, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(CopilotDriver(sys.argv[1:]).main())
