"""tests.test_browser_tool -- the built-in Browser tool (halo_harness/tools/browser.py, 3.6.0.6 W entry 3), with Halo's
browser (browser_cdp.Browser) replaced by a stand-in: it is in every platform's tool list; each action's answer has
its shape (title, address, text, numbered controls, "Picture: <path>" after a change, the picture given to the model
by screenshot exactly as the Screenshot tool gives its own); no browser installed answers entry 1's one line and
starts nothing; the permission engine decides open/read/screenshot/close as WebFetch for the same address and the
rest as a change; its whole cost on the wire is at most 500 tokens; a lean session at 16,384 gets it by name only
and its tool block does not grow. Run: python -m tests.test_browser_tool
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("BRIDGE_TEST_HOME", tempfile.mkdtemp(prefix="browser-tool-home-"))
os.environ.setdefault("BRIDGE_TEST_NO_BACKGROUND_NET", "1")

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
_N = __import__("itertools").count(1)
PNG = (b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
       b"\x00\x00\x00\rIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82")


class FakeBrowser:
    """browser_cdp.Browser's methods, on a two-page site in memory."""
    made: list = []

    def __init__(self, profile=None, **kw):
        self.notes, self.name, self.started, self.closed = [], "Google Chrome", 0, False
        self.url, self.state, self.typed = "about:blank", "before", ""
        FakeBrowser.made.append(self)

    def start(self):
        self.started += 1
        return self

    def open(self, url, wait_s=15):
        self.url = url
        return "slow" not in url

    def page(self):
        return {"title": "Test page", "url": self.url, "text": f"Hello\n{self.state}"}

    def controls(self):
        return [{"n": 1, "kind": "button", "words": "Press me"}, {"n": 2, "kind": "text box", "words": "your name"}], 2

    def press(self, target):
        from halo_harness.browser_cdp import BrowserError
        if str(target) not in ("1", "Press me"):
            raise BrowserError(f"No control matches '{target}'. Call read to see the list.")
        self.state = "after click"

    def type_into(self, target, text, enter=False):
        self.state = f"typed {text}{' and Enter' if enter else ''}"

    def key(self, name):
        self.state = f"key {name}"

    def scroll(self, where):
        self.state = f"scrolled {where}"

    def back(self):
        self.url = "file:///first.html"

    def js(self, expr):
        return "3"

    def screenshot(self):
        return PNG

    def close(self):
        self.closed = True


def _ctx(session="sess-browser-1", vision=False):
    from halo_harness.tools.base import ToolContext
    d = Path(tempfile.mkdtemp(prefix="browser-tool-sess-")) / f"{session}-{os.getpid()}-{next(_N)}"
    d.mkdir(parents=True)
    return ToolContext(cwd=Path(tempfile.gettempdir()), session_dir=d, vision=vision, model_ref="ol:tiny:3b@lan")


def _text(res) -> str:
    return res.content if isinstance(res.content, str) else json.dumps(res.content)


@test
def test_every_platform_has_the_browser_tool(ctx: Ctx):
    from halo_harness.tools.registry import default_tools, known_tool_names
    for plat in ("win32", "linux", "darwin"):
        ctx.check(f"{plat}: Browser in default_tools()", "Browser" in [t.name for t in default_tools(plat)])
    ctx.check("Studio's tool names list it", "Browser" in known_tool_names())


@test
def test_each_action_answers_the_page_and_a_change_ends_with_its_picture(ctx: Ctx):
    from halo_harness.tools import browser as T
    tool, c = T.BrowserTool(), _ctx()
    FakeBrowser.made.clear()
    with mock.patch("halo_harness.browser_cdp.Browser", FakeBrowser):
        r = tool.run({"action": "read"}, c)
        ctx.check(f"read before open says what to do, got {_text(r)!r}", r.is_error and _text(r) == T.NOT_OPEN)
        r = tool.run({"action": "open", "url": "https://example.com/a"}, c)
        out = _text(r)
        lines = out.splitlines()
        ctx.check(f"open: title, address, text, controls, picture, got {out!r}",
                  lines[0] == "Title: Test page" and lines[1] == "Address: https://example.com/a" and "Hello" in out
                  and "1. button: Press me" in out and "2. text box: your name" in out
                  and lines[-1].startswith("Picture: ") and lines[-1].endswith("page-1.png"))
        pic = Path(lines[-1][len("Picture: "):])
        ctx.check(f"the picture is in the session's attachments folder, got {pic}",
                  pic.is_file() and pic.parent.name == c.session_dir.name and pic.parent.parent.name == "attachments")
        ctx.check("one browser for the session, started once per call", len(FakeBrowser.made) == 1)
        for inp, want in (({"action": "click", "target": "1"}, "after click"),
                          ({"action": "type", "target": "2", "text": "Ada", "enter": True}, "typed Ada and Enter"),
                          ({"action": "key", "text": "PageDown"}, "key PageDown"),
                          ({"action": "scroll", "text": "down"}, "scrolled down"),
                          ({"action": "back"}, "Address: file:///first.html"),
                          ({"action": "js", "text": "1 + 2"}, "Result: 3")):
            out = _text(tool.run(inp, c))
            ctx.check(f"{inp['action']}: {want!r} and a picture, got {out[-160:]!r}",
                      want in out and out.splitlines()[-1].startswith("Picture: "))
        out = _text(tool.run({"action": "read"}, c))
        ctx.check("read: the page, no new picture", "Title: Test page" in out and "Picture:" not in out)
        r = tool.run({"action": "click", "target": "Sign in"}, c)
        ctx.check(f"a miss is a plain sentence, got {_text(r)!r}",
                  r.is_error and _text(r) == "No control matches 'Sign in'. Call read to see the list.")
        out = _text(tool.run({"action": "open", "url": "https://example.com/slow", "show": True}, c))
        ctx.check(f"show is accepted and ignored with one line; a slow load is said, got {out[:240]!r}",
                  T.SHOW_LATER in out and "still loading after 15 s" in out)
        shot = tool.run({"action": "screenshot"}, c)
        body = _text(shot)
        ctx.check(f"screenshot: a model that cannot see gets the path and the note, got {body[:200]!r}",
                  "cannot see images" in body and "page-" in body)
        c2 = _ctx("sess-browser-1b", vision=True)
        tool.run({"action": "open", "url": "https://example.com/b"}, c2)
        seen = tool.run({"action": "screenshot"}, c2)
        ctx.check("a model that sees gets the image block", isinstance(seen.content, list)
                  and seen.content[1]["type"] == "image" and seen.content[0]["text"].startswith("Screenshot saved at"))
        b = FakeBrowser.made[0]
        r = tool.run({"action": "close"}, c)
        ctx.check(f"close ends it now and says so, got {_text(r)!r}", _text(r) == T.CLOSED and b.closed)
        T.close_for(c2.session_dir.name)


@test
def test_pictures_keep_the_newest_twenty(ctx: Ctx):
    from halo_harness.tools import browser as T
    tool, c = T.BrowserTool(), _ctx("sess-browser-20")
    with mock.patch("halo_harness.browser_cdp.Browser", FakeBrowser):
        for i in range(23):
            tool.run({"action": "scroll", "text": "down"} if i else {"action": "open", "url": "https://e.com"}, c)
        T.close_for(c.session_dir.name)
    from halo_harness.tools.screenshot import images_folder
    names = sorted(int(p.stem.split("-")[1]) for p in images_folder(c.session_dir.name).glob("page-*.png"))
    ctx.check(f"the newest 20 kept, got {names}", names == list(range(4, 24)))


@test
def test_no_browser_answers_the_one_line_and_starts_nothing(ctx: Ctx):
    from halo_harness.tools import browser as T
    started = []
    c = _ctx("sess-none")
    with mock.patch("halo_harness.browser_find.find_browser", lambda **k: None), \
            mock.patch.dict(os.environ, {"HALO_CHROME": ""}), \
            mock.patch("halo_harness.subprocess_safe.Popen", lambda *a, **k: started.append(a)):
        r = T.BrowserTool().run({"action": "open", "url": "https://example.com"}, c)
        T.close_for(c.session_dir.name)
    ctx.check(f"the line of entry 1, got {_text(r)!r}", r.is_error and _text(r) == (
        "No browser found: install Google Chrome, Chromium, Microsoft Edge or Brave, or set HALO_CHROME to a "
        "browser's path. Halo downloads none."))
    ctx.check("nothing started", not started)


@test
def test_permissions_open_read_as_webfetch_and_a_press_as_a_change(ctx: Ctx):
    from halo_harness import permissions as P
    from halo_harness.tools.browser import BrowserTool
    cwd = Path(tempfile.gettempdir())
    tool = BrowserTool()
    tool._page_url = "https://example.com/page"
    from halo_harness.tools import browser as T
    T._LAST["url"] = tool._page_url  # what the card's suggestion reads (the last address in this process)
    for mode in ("default", "acceptEdits", "plan", "dontAsk", "auto", "bypassPermissions"):
        eng = P.PermissionEngine(mode=mode, cwd=cwd)
        web = eng.decide("WebFetch", {"url": "https://example.com/page", "prompt": "x"}).action
        for action in ("open", "read", "screenshot", "close"):
            inp = {"action": action, "url": "https://example.com/page"} if action == "open" else {"action": action}
            got = eng.decide("Browser", inp, tool).action
            ctx.check(f"{mode}: {action} decided as WebFetch ({web}), got {got}", got == web)
        bash = eng.decide("Bash", {"command": "npm install"}).action
        for action in ("click", "type", "key", "scroll", "back", "js"):
            got = eng.decide("Browser", {"action": action, "target": "1", "text": "x"}, tool).action
            ctx.check(f"{mode}: {action} decided as a change (as a Bash that changes something, {bash}), got {got}", got == bash)
    eng = P.PermissionEngine(mode="default", cwd=cwd,
                             allow_rules=[P.parse_rule("Browser(domain:example.com)", source="user")])
    ctx.check("Browser(domain:example.com) allows open there",
              eng.decide("Browser", {"action": "open", "url": "https://example.com/x"}, tool).action == "allow")
    ctx.check("and read of the page open there",
              eng.decide("Browser", {"action": "read"}, tool).action == "allow")
    ctx.check("never another domain",
              eng.decide("Browser", {"action": "open", "url": "https://other.org/"}, tool).action == "ask")
    ctx.check("a rule that is not domain: is invalid, as WebFetch's",
              P.parse_rule("Browser(example.com)", source="user").kind == "invalid")
    d = P.PermissionEngine(mode="default", cwd=cwd).decide("Browser", {"action": "click", "target": "1"}, tool)
    ctx.check(f"the card's suggested rule is the page's domain, got {d.suggested_rule}",
              d.suggested_rule == "Browser(domain:example.com)")
    ctx.check("permission_content is '<action> <address>'",
              tool.permission_content({"action": "click", "target": "1"}) == "click https://example.com/page"
              and tool.permission_content({"action": "open", "url": "https://a.b/"}) == "open https://a.b/")


@test
def test_its_whole_cost_on_the_wire_is_at_most_500_tokens_and_the_description_says_webfetch(ctx: Ctx):
    from halo_harness.agent.prompt_diet import wire_tokens
    from halo_harness.tools.browser import BrowserTool
    defn = BrowserTool().definition()
    n = wire_tokens(defn)
    ctx.check(f"at most 500 tokens on the wire, got {n}", n <= 500)
    desc = defn["description"]
    ctx.check(f"at most three sentences, got {desc!r}", desc.count(". ") + 1 <= 3)
    ctx.check("it names WebFetch as the faster way", "WebFetch is faster" in desc)
    ctx.check("the ten actions", defn["input_schema"]["properties"]["action"]["enum"] == [
        "open", "read", "click", "type", "key", "scroll", "back", "js", "screenshot", "close"])


@test
def test_a_lean_session_at_16384_gets_browser_by_name_only(ctx: Ctx):
    from types import SimpleNamespace
    from halo_harness.agent.prompt_diet import by_name_line, diet
    from halo_harness.tools.registry import ToolRegistry, default_tools
    defs = ToolRegistry(default_tools("linux")).definitions()
    without = [d for d in defs if d["name"] != "Browser"]
    for window in (16384, 8192):
        s = SimpleNamespace(_measure_window=window, _measure_platform="linux")
        kept, dropped = diet(s, defs, "open a page", platform="linux")
        kept0, _d0 = diet(s, without, "open a page", platform="linux")
        ctx.check(f"{window}: Browser left out of the block", "Browser" in dropped and
                  "Browser" not in [d["name"] for d in kept])
        ctx.check(f"{window}: the block is unchanged by one token",
                  json.dumps(kept, sort_keys=True) == json.dumps(kept0, sort_keys=True))
        ctx.check(f"{window}: the by-name line names it", "Browser" in by_name_line(dropped))
    s = SimpleNamespace(_measure_window=32768, _measure_platform="linux")
    kept, dropped = diet(s, defs, "open a page", platform="linux")
    ctx.check(f"32,768: in the block when the 4,500 budget holds it, dropped {dropped}",
              "Browser" in [d["name"] for d in kept])


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
