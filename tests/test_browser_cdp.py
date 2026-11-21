"""tests.test_browser_cdp -- Halo's own browser (halo_harness/browser_cdp.py, 3.6.0.6 W entry 2): found on this
machine, started headless by Halo over a DevTools PIPE (no port), driven (open, read, press, type, key, scroll, back,
js, screenshot) and closed with nothing left: no process carries its profile, a clean profile's folder is gone, and
while it ran no process of its tree listened on any socket. The kept profile (Halo's own, the default) serves one
browser at a time and stays. The plain tests run anywhere; the real ones need a Chromium-family browser installed
(every CI leg has Chrome) and take the suite's headless-browser lock. Run: python -m tests.test_browser_cdp
"""
from __future__ import annotations

import os
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("BRIDGE_TEST_HOME", tempfile.mkdtemp(prefix="browser-cdp-home-"))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()

PAGE = """<!doctype html><html><head><title>Halo test page</title></head><body>
<h1>Hello from the W page</h1><p id="state">before</p>
<button id="go" onclick="document.getElementById('state').textContent = 'after click'">Press me</button>
<input id="box" placeholder="your name" onkeydown="if (event.key === 'Enter') document.getElementById('state').textContent = 'sent ' + this.value">
<a href="second.html">Second page</a>
<div style="height: 3000px"></div><p>the end</p></body></html>"""
SECOND = "<!doctype html><title>Second</title><body><p>the second page</p></body>"


def _pages() -> str:
    d = Path(tempfile.mkdtemp(prefix="browser-cdp-pages-"))
    (d / "first.html").write_text(PAGE, encoding="utf-8")
    (d / "second.html").write_text(SECOND, encoding="utf-8")
    return (d / "first.html").as_uri()


def _png_size(data: bytes) -> "tuple[int, int]":
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        return (0, 0)
    return struct.unpack(">II", data[16:24])


def _tree_pids(profile: str) -> list:
    """Every process of this user whose command line carries the profile (tests/helpers/leftovers.scan: Windows,
    Linux and macOS)."""
    from tests.helpers.leftovers import scan
    want = os.path.normpath(profile).lower() if os.name == "nt" else os.path.normpath(profile)
    out = []
    for p in scan(lambda _pid, _start: True).values():
        cmd = (p.cmd or "").replace("/", os.sep) if os.name == "nt" else (p.cmd or "")
        if (want in cmd.lower() if os.name == "nt" else want in cmd) and p.pid != os.getpid():
            out.append(p.pid)
    return out


def _listening(pids: list) -> list:
    """The listening sockets owned by `pids` (Linux: ss; Windows: netstat; macOS: lsof)."""
    pids = {int(p) for p in pids}
    try:
        if sys.platform.startswith("linux"):
            text = subprocess.run(["ss", "-ltnupH"], capture_output=True, text=True, timeout=20).stdout
            return [ln for ln in text.splitlines() if any(f"pid={p}," in ln for p in pids)]
        if os.name == "nt":
            text = subprocess.run(["netstat", "-ano"], capture_output=True, text=True, timeout=60).stdout
            return [ln for ln in text.splitlines() if "LISTENING" in ln and ln.split() and ln.split()[-1].isdigit()
                    and int(ln.split()[-1]) in pids]
        text = subprocess.run(["lsof", "-nP", "-iTCP", "-sTCP:LISTEN"], capture_output=True, text=True,
                              timeout=20).stdout
        return [ln for ln in text.splitlines()[1:] if len(ln.split()) > 1 and ln.split()[1].isdigit()
                and int(ln.split()[1]) in pids]
    except FileNotFoundError as e:
        return [f"cannot look: {e}"]


class _Locked:
    def __enter__(self):
        from tests.helpers.chrome_lock import lock_for
        self.lock = lock_for(None)
        self.lock.acquire()
        return self

    def __exit__(self, *exc):
        self.lock.release()


# -- plain: anywhere, no browser ---------------------------------------------------------------------------------------

@test
def test_key_names_parse_to_real_key_events(ctx: Ctx):
    from halo_harness.browser_cdp import BrowserError, parse_key
    ctx.check("Enter", parse_key("Enter") == ("Enter", "Enter", 13, "\r", 0))
    ctx.check("Control+a: no text, Control bit", parse_key("Control+a") == ("a", "KeyA", 65, "", 2))
    ctx.check("Shift+a: an upper-case A", parse_key("Shift+a")[3] == "A" and parse_key("Shift+a")[4] == 8)
    ctx.check("pagedown in any case", parse_key("pagedown")[0] == "PageDown")
    for bad in ("", "Hyper+a", "F99"):
        try:
            parse_key(bad)
            ctx.check(f"{bad!r} is refused", False)
        except BrowserError as e:
            ctx.check(f"{bad!r}: the line says what to use, got {e}", "Enter" in str(e) and "Control" in str(e))


@test
def test_the_profile_is_matched_whole_never_by_a_prefix(ctx: Ctx):
    from halo_harness.browser_cdp import _carries
    ctx.check("its own profile", _carries(["chrome", "--type=renderer", "--user-data-dir=/h/browser/profile"],
                                          "/h/browser/profile"))
    ctx.check("never a longer name", not _carries(["chrome", "--user-data-dir=/h/browser/profile2"], "/h/browser/profile"))
    ctx.check("never a person's own browser", not _carries(["chrome"], "/h/browser/profile"))


@test
def test_a_clean_profile_left_by_a_gone_session_is_swept_and_a_live_one_kept(ctx: Ctx):
    from unittest import mock
    from halo_harness import browser_cdp as B
    home = Path(tempfile.mkdtemp(prefix="browser-sweep-"))
    gone, live = B.browser_home(home) / "clean-999991-1-1", B.browser_home(home) / "clean-999992-1-1"
    kept = B.browser_home(home) / "profile"
    for p in (gone, live, kept):
        p.mkdir(parents=True)
    with mock.patch("halo_harness.children.pid_running", lambda pid: pid == 999992), \
            mock.patch.object(B, "profile_pids", lambda _p: []):
        B.sweep_clean_profiles(home)
    ctx.check("the gone session's clean profile is removed", not gone.exists())
    ctx.check("a running session's clean profile stays", live.exists())
    ctx.check("Halo's kept profile is never swept", kept.exists())


@test
def test_the_profile_setting_is_kept_by_default(ctx: Ctx):
    from unittest import mock
    from halo_harness import browser_cdp as B
    with mock.patch("halo_harness.theme.get_config_value", lambda k, default=None: default):
        ctx.check("unset: kept", B.profile_setting() == "kept")
    with mock.patch("halo_harness.theme.get_config_value", lambda k, default=None: "clean"):
        ctx.check("clean", B.profile_setting() == "clean")
    with mock.patch("halo_harness.theme.get_config_value", lambda k, default=None: "bogus"):
        ctx.check("a value it does not know: kept", B.profile_setting() == "kept")


@test
def test_no_browser_says_the_one_line_and_starts_nothing(ctx: Ctx):
    from unittest import mock
    from halo_harness import browser_cdp as B
    started = []
    with mock.patch("halo_harness.browser_find.find_browser", lambda **k: None), \
            mock.patch.dict(os.environ, {"HALO_CHROME": ""}):
        b = B.Browser("clean", home=tempfile.mkdtemp(prefix="browser-none-"), popen=lambda *a, **k: started.append(a))
        try:
            b.start()
            ctx.check("start raised", False)
        except B.NoBrowser as e:
            ctx.check(f"the none line, got {e}", str(e).startswith("No browser found: install Google Chrome"))
    ctx.check("nothing was started", not started)


# -- real: a browser installed on this machine -------------------------------------------------------------------------

@test
def test_a_real_browser_over_the_pipe_opens_reads_presses_types_and_closes_clean(ctx: Ctx):
    from halo_harness import browser_cdp as B
    from halo_harness.browser_find import find_browser, none_found
    found = find_browser()
    ctx.check(f"a browser on this machine ({none_found() if not found else found[0]})", found is not None)
    if not found:
        return
    home = Path(tempfile.mkdtemp(prefix="browser-cdp-real-"))
    url = _pages()
    with _Locked():
        b = B.Browser("clean", home=home)
        try:
            b.start()
            profile = b.profile
            ctx.check(f"a clean profile under Halo's home, got {profile}",
                      Path(profile).parent == B.browser_home(home) and Path(profile).name.startswith("clean-"))
            ctx.check("the browser was started over the pipe, with no port",
                      "--remote-debugging-pipe" in " ".join(map(str, b.proc.args))
                      and "--remote-debugging-port" not in " ".join(map(str, b.proc.args)))
            loaded = b.open(url)
            ctx.check("the page loaded", loaded)
            pg = b.page()
            ctx.check(f"title and text, got {pg['title']!r} {pg['text'][:60]!r}",
                      pg["title"] == "Halo test page" and "Hello from the W page" in pg["text"])
            rows, total = b.controls()
            ctx.check(f"the controls, numbered, got {rows}", total == 3 and [r["kind"] for r in rows] ==
                      ["button", "text box", "link"] and rows[0]["words"] == "Press me" and rows[0]["n"] == 1)
            b.press("1")
            ctx.check("a press by number changes the page", "after click" in b.page()["text"])
            b.type_into("your name", "Ada", enter=True)
            ctx.check(f"typed by its words and Enter pressed, got {b.page()['text'][:80]!r}",
                      "sent Ada" in b.page()["text"])
            b.scroll("down")
            ctx.check("a wheel scroll moves the page", (b.js("String(window.scrollY)") or "0") != "0")
            b.scroll("top")
            ctx.check("top", b.js("String(window.scrollY)") == "0")
            ctx.check("js answers as text", b.js("1 + 2") == "3" and b.js("document.title") == "Halo test page")
            b.press("css:a")
            ctx.check("a press on a link opens the next page", b.page()["title"] == "Second")
            b.back()
            ctx.check("back is the page before", b.page()["title"] == "Halo test page")
            b.key("End")
            png = b.screenshot()
            w, h = _png_size(png)
            ctx.check(f"a PNG of the page's size, got {w} x {h}", (w, h) == (B.WIDTH, B.HEIGHT) or (w > 0 and h > 0))
            try:
                b.press("Sign in")
                ctx.check("a missing control is refused", False)
            except B.BrowserError as e:
                ctx.check(f"the line says what to do, got {e}", str(e) == "No control matches 'Sign in'. Call read "
                                                                          "to see the list.")
            pids = _tree_pids(profile)
            ctx.check(f"its processes carry the profile, got {pids}", b.proc.pid in pids or len(pids) > 0)
            ctx.check("no process of its tree listens on a socket", not _listening(pids + [b.proc.pid]))
        finally:
            b.close()
    ctx.check("no process carries the profile afterwards", not _tree_pids(profile))
    ctx.check("the clean profile folder is gone", not os.path.exists(profile))


@test
def test_the_kept_profile_is_halos_own_serves_one_browser_and_stays(ctx: Ctx):
    from halo_harness import browser_cdp as B
    from halo_harness.browser_find import find_browser
    if find_browser() is None:
        ctx.check("a browser on this machine", False)
        return
    home = Path(tempfile.mkdtemp(prefix="browser-cdp-kept-"))
    with _Locked():
        first = B.Browser("kept", home=home)
        second = B.Browser("kept", home=home)
        try:
            first.start()
            ctx.check(f"kept: Halo's own folder, got {first.profile}",
                      first.kind == "kept" and Path(first.profile) == B.browser_home(home) / "profile"
                      and not first.notes)
            first.open("data:text/html,<title>one</title>")
            first.close()
            second.start()
            ctx.check("after the first ended the next one takes the kept profile again", second.kind == "kept")
            third = B.Browser("kept", home=home)
            try:
                third._pick_profile(B.browser_home(home))  # the lock, as a second session's start would meet it
                ctx.check(f"in use: a clean one and the line word for word, got {third.notes}",
                          third.kind == "clean" and third.notes == [
                              "Another session is using Halo's browser profile; this one starts clean (not signed in)."])
            finally:
                if third.profile and third.kind == "clean":
                    import shutil
                    shutil.rmtree(third.profile, ignore_errors=True)
        finally:
            first.close()
            second.close()
    ctx.check("the kept profile stays after the end", (B.browser_home(home) / "profile").is_dir())
    ctx.check("no process carries it", not _tree_pids(str(B.browser_home(home) / "profile")))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
