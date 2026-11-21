"""tests.test_browser_cdp -- Halo's own browser (halo_harness/browser_cdp.py, 3.6.0.6 W entry 2): found on this
machine, started headless by Halo over a DevTools PIPE (no port), driven (open, read, press, type, key, scroll, back,
js, screenshot) and closed with nothing left: no process carries its profile, a clean profile's folder is gone, and
while it ran no process of its tree listened on any socket. The kept profile (Halo's own, the default) serves one
browser at a time and stays. The plain tests run anywhere; the real ones need a Chromium-family browser installed
(every CI leg has Chrome) and take the suite's headless-browser lock. Run: python -m tests.test_browser_cdp
"""
from __future__ import annotations

import atexit
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
_SCRATCH: "list[str]" = []


def _scratch(prefix: str) -> str:
    """A temp folder this run removes when it exits (a real browser's profile in it is 5 to 90 MB)."""
    d = tempfile.mkdtemp(prefix=prefix)
    _SCRATCH.append(d)
    return d


@atexit.register
def _remove_scratch() -> None:
    for d in reversed(_SCRATCH):
        for _ in range(30):  # Windows lets go of a folder a moment after a browser's processes end
            shutil.rmtree(d, ignore_errors=True)
            if not os.path.exists(d):
                break
            time.sleep(0.1)


if not os.environ.get("BRIDGE_TEST_HOME"):
    os.environ["BRIDGE_TEST_HOME"] = _scratch("browser-cdp-home-")

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
    d = Path(_scratch("browser-cdp-pages-"))
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


SITE = {
    "/tabs.html": "<!doctype html><title>Tabs</title><body><a href='/second.html' target='_blank'>New tab</a>"
                  "<button onclick=\"window.close()\">Close me</button></body>",
    "/second.html": SECOND,
    "/boxes.html": "<!doctype html><title>Boxes</title><body><p id='s'>no box yet</p>"
                   "<button onclick=\"alert('Saved!'); document.getElementById('s').textContent = 'after alert'\">"
                   "Alert</button><button onclick=\"document.getElementById('s').textContent = 'confirm said ' + "
                   "confirm('Delete it?')\">Confirm</button><button onclick=\"document.getElementById('s')"
                   ".textContent = 'prompt said ' + prompt('Your name?', 'Ada')\">Prompt</button></body>",
    "/slow.html": "<!doctype html><title>Slow</title><body><p>the text that is there</p><img src='/never.png'>"
                  "</body>",
    "/dl.html": "<!doctype html><title>Files</title><body><a href='/report.txt'>Get the report</a></body>",
    "/opens-box.html": "<!doctype html><title>Opens</title><body><a href='/box-first.html' target='_blank'>Box tab</a>"
                       "</body>",
    "/box-first.html": "<!doctype html><html><head><script>alert('Hello at once');</script><title>Box first</title>"
                       "</head><body><p>after the first box</p></body></html>",
}
BROWSER_WORDS = ("chrome", "chromium", "edge", "msedge", "brave", "scoped_dir", "url_fetcher")
REPORT = b"the report, " * 100


class _Site:
    """The pages above on 127.0.0.1 (port 0) for as long as the `with` lasts; /never.png never answers (until the
    site ends), /report.txt is a download."""

    def __enter__(self) -> str:
        import http.server
        import threading
        self.stop = stop = threading.Event()

        class Page(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                path = self.path.split("?", 1)[0]
                if path == "/never.png":
                    stop.wait(120)
                    return
                if path == "/report.txt":
                    body, ctype, extra = REPORT, "text/plain", {"Content-Disposition": 'attachment; filename="report.txt"'}
                elif path in SITE:
                    body, ctype, extra = SITE[path].encode("utf-8"), "text/html; charset=utf-8", {}
                else:
                    self.send_error(404)
                    return
                self.send_response(200)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(body)))
                for k, v in extra.items():
                    self.send_header(k, v)
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *a):
                pass

        self.srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Page)
        self.srv.daemon_threads = True
        self.th = threading.Thread(target=self.srv.serve_forever, name="w-site", daemon=True)
        self.th.start()
        return f"http://127.0.0.1:{self.srv.server_address[1]}"

    def __exit__(self, *exc):
        self.stop.set()
        self.srv.shutdown()
        self.srv.server_close()
        self.th.join(10)


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
def test_the_ps_path_matches_the_profile_whole_too(ctx: Ctx):
    """macOS (and Linux under HALO_TEST_NO_PROC) reads `ps`, where a command line is one text: the profile is matched
    whole there too, never as the start of a longer folder name."""
    from types import SimpleNamespace
    from unittest import mock
    from halo_harness import browser_cdp as B
    prof = os.path.normpath("/h/browser/profile")
    text = "\n".join([f"  11 /opt/chrome --user-data-dir={prof} about:blank",
                      f"  12 /opt/chrome --type=renderer --user-data-dir={prof}2 --lang=en",
                      f"  13 /opt/chrome --type=gpu-process --user-data-dir={prof}",
                      f"  14 /opt/chrome --user-data-dir={prof}-old about:blank",
                      f"  {os.getpid()} python --user-data-dir={prof}"])
    with mock.patch.object(B.subprocess, "run", lambda *a, **k: SimpleNamespace(stdout=text)):
        got = B._ps_pids(prof)
    ctx.check(f"only the processes that carry exactly this profile, got {got}", got == [11, 13])


@test
def test_a_clean_profile_left_by_a_gone_session_is_swept_and_a_live_one_kept(ctx: Ctx):
    from unittest import mock
    from halo_harness import browser_cdp as B
    home = Path(_scratch("browser-sweep-"))
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
    # Windows lets go of a folder a moment after its processes end (a start right after a hard end, on a slow machine):
    # a removal that does nothing at first is tried again, as the normal end's is
    late = B.browser_home(home) / "clean-999993-1-1"
    late.mkdir(parents=True)
    real_rmtree, tries = shutil.rmtree, []

    def rmtree(path, *a, **k):
        tries.append(str(path))
        return None if len(tries) < 3 else real_rmtree(path, *a, **k)
    with mock.patch("halo_harness.children.pid_running", lambda pid: pid == 999992), \
            mock.patch.object(B, "profile_pids", lambda _p: []), mock.patch.object(B.shutil, "rmtree", rmtree):
        B.sweep_clean_profiles(home)
    ctx.check(f"a folder the system lets go of late is removed at this start too, tries {tries}",
              not late.exists() and tries == [str(late)] * 3)
    ctx.check("and the running session's still stays", live.exists())


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
        b = B.Browser("clean", home=_scratch("browser-none-"), popen=lambda *a, **k: started.append(a))
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
    home = Path(_scratch("browser-cdp-real-"))
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
            size = b.js("[innerWidth, innerHeight, devicePixelRatio].join(' ')").split()
            want = (round(int(size[0]) * float(size[2])), round(int(size[1]) * float(size[2])))
            ctx.check(f"a PNG of the page's size {want}, got {w} x {h}", (w, h) == want)
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
def test_real_pages_a_new_tab_a_box_an_endless_load_and_a_download(ctx: Ctx):
    """W batch 2 entry 1, a real browser on pages this test serves on 127.0.0.1: (a) a link with target=_blank: the
    browser goes on in the new tab and says so; a tab that closes hands back to the one before; (b) alert, confirm
    and prompt are answered at once (the action returns, the page went on) and each is said; (c) a page whose load
    never ends: open returns within the limit with what is there; (d) a download lands in the download folder only,
    under its own name, and is said."""
    from halo_harness import browser_cdp as B
    from halo_harness.browser_find import find_browser
    if find_browser() is None:
        ctx.check("a browser on this machine", False)
        return
    home, dl = Path(_scratch("browser-cdp-pages2-")), Path(_scratch("browser-cdp-dl-"))
    their_dl = Path.home() / "Downloads" / "report.txt"
    before = their_dl.stat().st_mtime if their_dl.exists() else None
    with _Locked(), _Site() as site:
        b = B.Browser("clean", home=home)
        b.download_dir = dl
        try:
            b.start()
            b.take_notes()
            ctx.check("(a) the page with the link", b.open(site + "/tabs.html") and b.page()["title"] == "Tabs")
            b.press("New tab")
            notes = b.take_notes()
            ctx.check(f"(a) on the new tab, said, got {notes} {b.page()['title']!r}",
                      notes == [B.NEW_TAB] and b.page()["title"] == "Second" and len(b.tabs) == 2)
            b.js("window.close(); 'closing'")
            notes = b.take_notes()
            ctx.check(f"(a) it closed: back on the one before, got {b.page()['title']!r} {notes}",
                      b.page()["title"] == "Tabs" and len(b.tabs) == 1 and B.NEW_TAB not in notes)
            b.press("New tab")
            ctx.check("(a) the line word for word", b.take_notes() == ["A new tab opened; now on it."])
            b.open(site + "/boxes.html")
            b.take_notes()
            t = time.monotonic()
            b.press("Alert")
            ctx.check(f"(b) an alert: answered at once, said, the page went on, got {b.page()['text'][:60]!r}",
                      b.take_notes() == ["The page showed a box: 'Saved!' (accepted)."] and "after alert" in
                      b.page()["text"] and time.monotonic() - t < 10)
            b.press("Confirm")
            ctx.check("(b) a confirm: accepted", b.take_notes() == ["The page showed a box: 'Delete it?' (accepted)."]
                      and "confirm said true" in b.page()["text"])
            b.press("Prompt")
            ctx.check("(b) a prompt: its default text", "prompt said Ada" in b.page()["text"] and len(b.take_notes()) == 1)
            t = time.monotonic()
            loaded = b.open(site + "/slow.html")
            took = time.monotonic() - t
            ctx.check(f"(c) an endless load returns within the limit with what is there, got {loaded} in {took:.1f}s",
                      loaded is False and took < B.LOAD_WAIT_S + 5 and "the text that is there" in b.page()["text"])
            # W batch 3 entry 4: a box raised by the first line of a tab that has just opened is answered too (before
            # (d), so a fault in (d) never hides this one)
            b.open(site + "/opens-box.html")
            b.take_notes()
            t = time.monotonic()
            b.press("Box tab")
            took, notes = time.monotonic() - t, b.take_notes()
            ctx.check(f"(e) a box in a new tab's first moment: answered, said after the new tab, the page went on, "
                      f"got {notes} {took:.1f}s {b.page()['text'][:60]!r}",
                      notes == [B.NEW_TAB, "The page showed a box: 'Hello at once' (accepted)."]
                      and "after the first box" in b.page()["text"] and took < B.LOAD_WAIT_S)
            b.open(site + "/dl.html")
            b.take_notes()
            b.press("Get the report")
            notes = b.take_notes()
            got = dl / "report.txt"
            ctx.check(f"(d) the download is said, got {notes}", notes == [f"Downloaded: {got} (1 KiB)."])
            ctx.check(f"(d) only the file, under its own name, got {sorted(p.name for p in dl.iterdir())}",
                      got.is_file() and got.read_bytes() == REPORT and [p.name for p in dl.iterdir()] == ["report.txt"])
            after = their_dl.stat().st_mtime if their_dl.exists() else None
            ctx.check("(d) nothing written to the person's own Downloads", after == before)
            # W batch 3 entry 3: the folder a person reads holds a download only when it is whole
            b.press("Get the report")
            seen, end = set(), time.monotonic() + 8.0
            while time.monotonic() < end:
                seen |= {p.name for p in dl.iterdir()}
                time.sleep(0.5)
            half = sorted(n for n in seen if n.lower().endswith((".crdownload", ".tmp")) or len(n) == 36)
            ctx.check(f"(d) never a half-written file in the session's folder, saw {sorted(seen)}", not half)
            second = dl / "report (2).txt"
            ctx.check(f"(d) a taken name gets ' (2)', whole, got {sorted(p.name for p in dl.iterdir())}",
                      sorted(p.name for p in dl.iterdir()) == ["report (2).txt", "report.txt"]
                      and second.read_bytes() == REPORT)
            staging = getattr(b, "stage", None)
            ctx.check(f"(d) the staging folder is Halo's own, under Halo's home (one rename away), got {staging}",
                      staging is not None and (Path(staging) / "downloads").is_dir()
                      and Path(staging).parent == B.browser_home(home) / "tmp")
            ctx.check("(d) and it is empty once the file moved",
                      staging is not None and not any((Path(staging) / "downloads").iterdir()))
        finally:
            b.close()
        ctx.check("the staging folder went with the browser", staging is None or not os.path.exists(staging))


def _browser_entries(folder) -> "list[str]":
    try:
        names = os.listdir(folder)
    except OSError:
        return []
    return sorted(n for n in names if any(w in n.lower() for w in BROWSER_WORDS))


@test
def test_a_temp_folder_a_hard_end_left_is_swept_and_a_live_ones_kept(ctx: Ctx):
    """W batch 3 entry 1: the browser's own temp folder (`<halo home>/browser/tmp/<pid>-...`) that a hard end left is
    removed by the next start: only one whose owner (the pid in its name) is no longer alive; never one in use."""
    from unittest import mock
    from halo_harness import browser_cdp as B
    home = Path(_scratch("browser-tmp-sweep-"))
    root = B.browser_home(home) / "tmp"
    gone, live, mine = root / "999991-1", root / "999992-1", root / f"{os.getpid()}-1"
    short = getattr(B, "short_root", lambda: None)()
    deep_gone = [short / "999991-7"] if short is not None else []
    for p in (gone, live, mine, *deep_gone):
        (p / "downloads").mkdir(parents=True)
    read: list = []
    real_iterdir = Path.iterdir

    def iterdir(self):
        read.append(str(self))
        return real_iterdir(self)
    with mock.patch("halo_harness.children.pid_running", lambda pid: pid == 999992), \
            mock.patch.object(Path, "iterdir", iterdir):
        B.sweep_temps(home)
    ctx.check("the gone session's temp folder is removed", not gone.exists())
    ctx.check("and one it had in the short root (a POSIX home too deep for the browser's socket)",
              not any(p.exists() for p in deep_gone))
    ctx.check("a running session's temp folder stays", live.exists())
    ctx.check("this process's own stays", mine.exists())
    # the checker: reading the whole system temp cost 18 s on a real Windows TEMP of 450,000 entries
    allowed = {str(root)} | ({str(short)} if short is not None else set())
    ctx.check(f"the sweep reads Halo's own folders only, never the system's temp, read {read}",
              set(read) <= allowed and str(Path(tempfile.gettempdir())) not in read)
    ctx.check("an empty short root goes with the sweep", short is None or not short.exists() or any(short.iterdir()))
    late = root / "999993-1"  # Windows lets go of a folder late: the removal is tried again (as the clean profile's)
    (late / "downloads").mkdir(parents=True)
    real_rmtree, tries = shutil.rmtree, []

    def rmtree(path, *a, **k):
        tries.append(str(path))
        return None if len(tries) < 3 else real_rmtree(path, *a, **k)
    with mock.patch("halo_harness.children.pid_running", lambda pid: pid == 999992), \
            mock.patch.object(B.shutil, "rmtree", rmtree):
        B.sweep_temps(home)
    ctx.check(f"a temp folder the system lets go of late is removed at this start too, tries {tries[:3]}",
              not late.exists() and tries[:3] == [str(late)] * 3)
    ctx.check("and the running session's and this process's own still stay", live.exists() and mine.exists())
    own, tmp = B.temp_folders(Path("/h/.halo/browser"))
    ctx.check(f"a home that fits: under Halo's home, got {own} {tmp}",
              own.parent == Path("/h/.halo/browser/tmp") and tmp == own)
    own, tmp = B.temp_folders(Path("/h/" + "d" * 80 + "/.halo/browser"))
    ctx.check(f"a home too deep: downloads still staged under Halo's home, got {own}", own.parent.name == "tmp"
              and str(own).startswith("/h/" if os.name != "nt" else str(Path("/h/"))))
    ctx.check(f"and on POSIX the browser's temp in the short root, within the socket's limit, got {tmp}",
              (tmp is not None and tmp.parent == short and len(str(tmp)) + B.SOCKET_TAIL <= B.SOCKET_MAX)
              if os.name != "nt" else tmp == own)
    # macOS: TMPDIR alone is about 48 characters; the short root never comes from it
    with mock.patch.dict(os.environ, {"TMPDIR": "/var/folders/xy/" + "z" * 30 + "/T/"}):
        own, tmp = B.temp_folders(Path("/h/" + "d" * 80 + "/.halo/browser"))
    ctx.check(f"a long TMPDIR (macOS) never makes the socket path too long, got {tmp}",
              os.name == "nt" or (tmp is not None and len(str(tmp)) + B.SOCKET_TAIL <= B.SOCKET_MAX))


@test
def test_a_whole_download_a_moment_held_still_reaches_the_session(ctx: Ctx):
    """W batch 3 repair (the checker): a move that fails a moment (Windows holds a file it has just written) is tried
    again; the download reaches the session's folder instead of going with the staging folder at the close."""
    from unittest import mock
    from halo_harness import browser_cdp as B
    home, dl = Path(_scratch("browser-dl-held-")), Path(_scratch("browser-dl-held-to-"))
    b = B.Browser("clean", home=home)
    b.stage = b.tmp = home / "stage"
    b.download_dir = dl
    (b.stage / "downloads").mkdir(parents=True)
    (b.stage / "downloads" / "g-1").write_bytes(REPORT)
    real_move, tries = B.shutil.move, []

    def move(src, dst):
        tries.append(dst)
        if len(tries) < 3:
            raise PermissionError(32, "The process cannot access the file because it is being used")
        return real_move(src, dst)
    with mock.patch.object(B.shutil, "move", move):
        got = b._name_download("g-1", "report.txt")
    ctx.check(f"moved after the hold, got {got} after {len(tries)} tries",
              got == dl / "report.txt" and got.read_bytes() == REPORT and len(tries) == 3)


@test
def test_after_the_browser_nothing_of_it_is_left_in_the_temp_folder(ctx: Ctx):
    """W batch 3 entry 1 (the owner: everything Halo starts ends with it, nothing is left behind): a real browser on
    Halo's kept profile, a page, 20 s for its background work, closed: the temp folder it was given (this run's own,
    standing in for the system's, so another run on the machine never counts) holds nothing new, and the browser's own
    temp folder under Halo's home is gone. What is left of the browser is the kept profile only."""
    from unittest import mock
    from halo_harness import browser_cdp as B
    from halo_harness.browser_find import find_browser
    if find_browser() is None:
        ctx.check("a browser on this machine", False)
        return
    home, given = Path(_scratch("browser-cdp-temp-")), Path(_scratch("browser-cdp-given-"))
    own = None
    with _Locked(), mock.patch.dict(os.environ, {"TMP": str(given), "TEMP": str(given), "TMPDIR": str(given)}):
        b = B.Browser("kept", home=home)
        try:
            b.start()
            own = getattr(b, "tmp", None)
            ctx.check(f"the browser's own temp folder is under Halo's home (or, for a home too deep for its socket, "
                      f"its own in the system's temp), got {own}",
                      own is not None and Path(own).is_dir() and Path(own).parent in (B.browser_home(home) / "tmp",
                                                                                      B.short_root()))
            b.open("data:text/html,<title>temp</title><p>a page</p>")
            time.sleep(20)  # the browser's own background work (an updater) starts some seconds in
        finally:
            b.close()
    left = sorted(os.listdir(given))
    ctx.check(f"nothing of the browser in the temp folder it was given (a {sys.platform} browser wrote these: "
              f"{_browser_entries(given) or left})", not left)
    ctx.check(f"its own temp folder under Halo's home is gone, got {own}", own is not None and not os.path.exists(own))
    bh = B.browser_home(home)
    rest = [n for n in os.listdir(bh) if n not in ("profile", "profile.lock", "tmp")]
    temps = os.listdir(bh / "tmp") if (bh / "tmp").is_dir() else []
    ctx.check(f"what stays is the kept profile only, got {rest} {temps}", not rest and not temps)


@test
def test_the_kept_profile_is_halos_own_serves_one_browser_and_stays(ctx: Ctx):
    from halo_harness import browser_cdp as B
    from halo_harness.browser_find import find_browser
    if find_browser() is None:
        ctx.check("a browser on this machine", False)
        return
    home = Path(_scratch("browser-cdp-kept-"))
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
