"""tests.test_open_link_token -- fx studio batch 2: the address Halo starts a browser with on Linux carries no Studio
key (halo_harness/studio/open_link.py). Every process's command line is readable by every account on a Linux machine
(/proc/<pid>/cmdline), so the browser gets a one-time link (`?o=<stamp>.<nonce>.<mac>`, signed with the key) and Studio
answers it once, for this account only, with a redirect to the page and its `#t=<key>`. No real browser: a fake
webbrowser module; a real Studio server on loopback.
Run: python -m tests.test_open_link_token
"""
from __future__ import annotations

import http.client
import os
import sys
import tempfile
import threading
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_scoped_state_dir_once  # noqa: E402

ensure_scoped_state_dir_once()

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()

KEY = "k3y-Of-This-Launch_0123456789abcd"


def fake_webbrowser(opened: list):
    class Error(Exception):
        pass

    class GenericBrowser:
        pass

    class Window:
        def open(self, url):
            opened.append(url)
            return True
    return SimpleNamespace(Error=Error, GenericBrowser=GenericBrowser, _tryorder=["firefox"], get=lambda name=None: Window())


@test
def test_the_browser_a_linux_halo_starts_is_never_given_the_key(ctx: Ctx):
    from halo_harness.studio import setup_door as D
    url = f"http://127.0.0.1:43123/?mode=setup&first=1#t={KEY}"
    opened: list = []
    ok = D.open_in_a_window(url, env={"DISPLAY": ":0"}, platform="linux", wb=fake_webbrowser(opened))
    ctx.check(f"opened, the key on no command line, got {ok} {opened}", ok is True and len(opened) == 1
              and KEY not in opened[0] and "#" not in opened[0] and "o=" in opened[0]
              and opened[0].startswith("http://127.0.0.1:43123/?") and "mode=setup" in opened[0] and "first=1" in opened[0])
    for plat in ("win32", "darwin"):  # the URL reaches the browser by a call, not an argv other accounts can read
        opened = []
        D.open_in_a_window(url, env={}, platform=plat, wb=fake_webbrowser(opened))
        ctx.check(f"{plat}: the address as it was, got {opened}", opened == [url])
    opened = []
    D.open_in_a_window("https://github.com/login/device", env={"DISPLAY": ":0"}, platform="linux", wb=fake_webbrowser(opened))
    ctx.check(f"an address with no key is not touched, got {opened}", opened == ["https://github.com/login/device"])


@test
def test_a_link_is_answered_once_with_the_page_and_its_key(ctx: Ctx):
    from halo_harness.studio.open_link import once_link, redeem
    link = once_link(f"http://127.0.0.1:43123/?mode=setup&edit=lineup%3Ateam#t={KEY}", now=1000.0)
    pq = link[len("http://127.0.0.1:43123"):]
    first = redeem(pq, KEY, now=1001.0)
    ctx.check(f"the first use: the page with its key, got {first!r}", first == f"/?mode=setup&edit=lineup%3Ateam#t={KEY}")
    ctx.check("the second use: refused", redeem(pq, KEY, now=1002.0) is None)
    other = once_link(f"http://127.0.0.1:43123/#t={KEY}", now=1000.0)[len("http://127.0.0.1:43123"):]
    ctx.check("signed by another key: refused", redeem(other, "another-key", now=1001.0) is None)
    ctx.check("two minutes old: refused", redeem(other, KEY, now=1000.0 + 121) is None)
    ctx.check("from the future: refused", redeem(other, KEY, now=900.0) is None)
    ctx.check("another account's connection: refused", redeem(other, KEY, now=1001.0, peer_uid=os.getpid() + 7, own_uid=os.getpid()) is None)
    ctx.check("this account's: the page", redeem(other, KEY, now=1001.0, peer_uid=5, own_uid=5) == f"/#t={KEY}")
    ctx.check("a made-up link: refused", redeem("/?o=1000.abc.def", KEY, now=1001.0) is None)


@test
def test_a_windows_browser_through_wsls_relay_still_opens_studio(ctx: Ctx):
    """fx studio batch 2 repair: on WSL2 (NAT networking) a Windows browser reaches a Studio inside WSL through WSL's
    localhost relay, whose Linux end is owned by root (uid 0). Root reads every account's files and processes, the
    key included, so refusing it protects nothing; it only left `halo studio` on a 403 page on WSL."""
    from halo_harness.studio.open_link import once_link, redeem
    link = once_link(f"http://127.0.0.1:43123/?mode=setup#t={KEY}", now=1000.0)[len("http://127.0.0.1:43123"):]
    got = redeem(link, KEY, now=1001.0, peer_uid=0, own_uid=1000)
    ctx.check(f"the relay's root-owned connection: the page, got {got!r}", got == f"/?mode=setup#t={KEY}")
    other = once_link(f"http://127.0.0.1:43123/#t={KEY}", now=1000.0)[len("http://127.0.0.1:43123"):]
    ctx.check("another ordinary account: still refused", redeem(other, KEY, now=1001.0, peer_uid=1001, own_uid=1000) is None)


@test
def test_the_account_of_a_loopback_connection_is_read_from_proc_net_tcp(ctx: Ctx):
    from halo_harness.studio.open_link import peer_uid
    table = ("  sl  local_address rem_address   st tx_queue rx_queue tr tm->when retrnsmt   uid  timeout inode\n"
             "   0: 0100007F:A853 00000000:0000 0A 00000000:00000000 00:00000000 00000000  1000        0 1 1\n"
             "   1: 0100007F:A853 0100007F:D431 01 00000000:00000000 00:00000000 00000000  1000        0 2 1\n"
             "   2: 0100007F:D431 0100007F:A853 01 00000000:00000000 00:00000000 00000000  1001        0 3 1\n")
    ctx.check(f"the client end's owner, got {peer_uid(43091, 54321, table)}", peer_uid(43091, 54321, table) == 1001)
    ctx.check("no such connection: unknown", peer_uid(43091, 1, table) is None)
    ctx.check("no table (macOS, Windows): unknown", peer_uid(43091, 54321, "") is None)


@test
def test_studio_answers_the_link_with_a_redirect_once(ctx: Ctx):
    from halo_harness.studio.open_link import once_link
    from halo_harness.studio.server import start_server, url_for
    root = Path(tempfile.mkdtemp(prefix="halo-openlink-"))
    (root / "home").mkdir()
    server = start_server(port=0, cwd=root, state_dir=root / "home", token=KEY)
    threading.Thread(target=server.serve_forever, daemon=True, name="openlink-studio").start()
    try:
        port = server.server_address[1]
        link = once_link(url_for(server, "setup"))
        pq = link[len(f"http://127.0.0.1:{port}"):]

        def get(path):
            c = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
            c.request("GET", path)
            r = c.getresponse()
            body = r.read()
            c.close()
            return r.status, r.getheader("Location") or "", body
        status, where, _ = get(pq)
        ctx.check(f"302 to the page with its key, got {status} {where!r}", status == 302 and where == f"/?mode=setup#t={KEY}")
        status, where, body = get(pq)
        ctx.check(f"used: refused, the key nowhere, got {status} {where!r}", status == 403 and where == ""
                  and KEY.encode() not in body and b"halo studio" in body)
    finally:
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
