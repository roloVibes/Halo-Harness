"""tests.test_browser_tool_real -- the Browser tool with a real installed browser (3.6.0.6 W entry 3; the Linux VM and
every CI leg, which have Chrome): (1) through the TOOL: open a `file://` page and get its title, text and numbered
controls; click by number changes the text; type fills the box; screenshot writes a PNG into the session's
attachments folder; close; nothing left. (2) A REAL `halo -p` session, its model the suite's fake OpenAI upstream
scripted to call Browser (open, click, type, screenshot, close): the page opens in the real browser, is read, pressed
and pictured, and when halo has exited no process carries the browser's profile or the scratch home.
Run: python -m tests.test_browser_tool_real
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("BRIDGE_TEST_HOME", tempfile.mkdtemp(prefix="browser-real-home-"))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402
from tests.test_browser_cdp import _Locked, _pages, _tree_pids  # noqa: E402

test, TESTS = new_registry()
DONE = "BROWSER-REAL-DONE"
SCAN_S = 5.0


def _gone(needle: str, seconds: float = SCAN_S) -> list:
    end = time.monotonic() + seconds
    left = _tree_pids(needle)
    while left and time.monotonic() < end:
        time.sleep(0.2)
        left = _tree_pids(needle)
    return left


@test
def test_through_the_tool_a_real_page_is_read_pressed_typed_and_pictured(ctx: Ctx):
    from halo_harness.browser_find import find_browser
    from halo_harness.tools import browser as T
    from halo_harness.tools.base import ToolContext
    if find_browser() is None:
        ctx.check("a browser on this machine", False)
        return
    sess = Path(tempfile.mkdtemp(prefix="browser-real-sess-")) / f"sess-real-{os.getpid()}"
    sess.mkdir(parents=True)
    c = ToolContext(cwd=sess, session_dir=sess, model_ref="ol:tiny:3b@lan")
    tool, url = T.BrowserTool(), _pages()
    profile = None
    with _Locked():
        try:
            out = tool.run({"action": "open", "url": url}, c).content
            b = T.browser_for(sess.name, start=False)
            profile = b.profile if b else None
            ctx.check(f"open: title, text, numbered controls, picture, got {out[:300]!r}",
                      "Title: Halo test page" in out and "Hello from the W page" in out and "1. button: Press me" in out
                      and "2. text box: your name" in out and out.splitlines()[-1].startswith("Picture: "))
            out = tool.run({"action": "click", "target": "1"}, c).content
            ctx.check(f"click by number changes the text, got {out[:200]!r}", "after click" in out)
            out = tool.run({"action": "type", "target": "2", "text": "Ada", "enter": True}, c).content
            ctx.check(f"type fills the box, got {out[:200]!r}", "sent Ada" in out)
            shot = tool.run({"action": "screenshot"}, c).content
            path = json.loads(shot.splitlines()[0])["path"]
            ctx.check(f"screenshot: a PNG in the session's attachments folder, got {path}",
                      Path(path).read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
                      and Path(path).parent.name == sess.name and Path(path).parent.parent.name == "attachments")
            out = tool.run({"action": "close"}, c).content
            ctx.check(f"close says so, got {out!r}", out == T.CLOSED)
        finally:
            T.close_for(sess.name)
    left = _gone(profile) if profile else ["no profile"]
    ctx.check(f"nothing left, got {left}", not left)


def text_step(text: str) -> list:
    """One streamed assistant message (scripts/realcheck/fakes.py's shape)."""
    return [{"choices": [{"index": 0, "delta": {"role": "assistant"}}]},
            {"choices": [{"index": 0, "delta": {"content": text}}]},
            {"choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]}]


def tool_step(*calls) -> list:
    """One assistant message calling tools: `calls` = (name, arguments, call id)."""
    tcs = [{"index": i, "id": cid, "type": "function", "function": {"name": n, "arguments": json.dumps(a)}}
           for i, (n, a, cid) in enumerate(calls)]
    return [{"choices": [{"index": 0, "delta": {"role": "assistant"}}]},
            {"choices": [{"index": 0, "delta": {"tool_calls": tcs}}]},
            {"choices": [{"index": 0, "delta": {}, "finish_reason": "tool_calls"}]}]


def _script(state: dict, url: str):
    from tests.helpers.mock_openai import _finish
    steps = [("Browser", {"action": "open", "url": url}),
             ("Browser", {"action": "click", "target": "1"}),
             ("Browser", {"action": "type", "target": "your name", "text": "Ada", "enter": True}),
             ("Browser", {"action": "screenshot"}),
             ("Browser", {"action": "close"})]

    def answer(h, body):
        msgs = (body or {}).get("messages") or []
        results = [m for m in msgs if isinstance(m, dict) and m.get("role") == "tool"]
        state["results"] = [m.get("content") for m in results]
        done = len(results)
        if done < len(steps):
            name, args = steps[done]
            return _finish(h, tool_step((name, args, f"call_browser_{done}")))
        return _finish(h, text_step(DONE))
    return answer


@test
def test_a_real_halo_session_drives_the_browser_and_leaves_nothing(ctx: Ctx):
    from halo_harness.browser_find import find_browser
    if find_browser() is None:
        ctx.check("a browser on this machine", False)
        return
    from tests.helpers.mock_openai import SCENARIOS, MockUpstream
    d = Path(tempfile.mkdtemp(prefix="browser-real-halo-"))
    home, proj, state_dir = d / "home", d / "proj", d / "home" / "state"
    for p in (home, proj, state_dir):
        p.mkdir(parents=True, exist_ok=True)
    url, state = _pages(), {}
    saved = SCENARIOS.get("browserreal")
    SCENARIOS["browserreal"] = _script(state, url)
    mock = MockUpstream()
    mock.models_response = {"data": [{"id": "mock/browserreal", "name": "browserreal", "context_length": 131072,
                                      "pricing": {"prompt": "0", "completion": "0"}, "supported_parameters": ["tools"]}]}
    mock.start()
    scrub = ("HALO_", "BRIDGE_", "OPENROUTER_", "ANTHROPIC_", "DATABRICKS_", "OPENAI_", "CLAUDE_")
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith(scrub)}
    env.update(HOME=str(home), USERPROFILE=str(home), BRIDGE_TEST_HOME=str(home), BRIDGE_STATE_DIR=str(state_dir),
               OLLAMA_HOST="http://127.0.0.1:9", HALO_NO_UPDATER="1", OPENROUTER_API_KEY="sk-or-test-not-a-key",
               BRIDGE_OPENROUTER_BASE_URL=mock.base_url, PYTHONPATH=str(ROOT))
    if sys.platform == "win32":  # a real Windows home has these; Chrome waits forever on a USERPROFILE without them
        appdata = home / "AppData"
        for sub in ("Local", "Roaming"):
            (appdata / sub).mkdir(parents=True, exist_ok=True)
        env.update(APPDATA=str(appdata / "Roaming"), LOCALAPPDATA=str(appdata / "Local"))
    if os.environ.get("HALO_CHROME"):
        env["HALO_CHROME"] = os.environ["HALO_CHROME"]
    if os.environ.get("HALO_TEST_NO_PROC"):
        env["HALO_TEST_NO_PROC"] = os.environ["HALO_TEST_NO_PROC"]
    p = None
    try:
        with _Locked():
            p = subprocess.Popen([sys.executable, "-m", "halo_harness", "-p", "open the test page and press on it",
                                  "--model", "or:mock/browserreal", "--permission-mode", "auto"], cwd=str(proj), env=env,
                                 stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            out, err = p.communicate(timeout=240)
        ctx.check(f"halo answered and exited 0, got {p.returncode} {out[-200:]!r} {err[-400:]!r}",
                  p.returncode == 0 and DONE in out)
        res = [r if isinstance(r, str) else json.dumps(r) for r in state.get("results") or []]
        ctx.check(f"five Browser results came back, got {len(res)}", len(res) == 5)
        if len(res) == 5:
            ctx.check(f"open read the real page, got {res[0][:200]!r}",
                      "Title: Halo test page" in res[0] and "1. button: Press me" in res[0])
            ctx.check(f"the press changed it, got {res[1][:160]!r}", "after click" in res[1])
            ctx.check(f"the typing and Enter reached it, got {res[2][:160]!r}", "sent Ada" in res[2])
            ctx.check(f"its picture was taken, got {res[3][:200]!r}", ".png" in res[3])
            ctx.check(f"closed, got {res[4]!r}", res[4] == "The browser is closed.")
            pics = list((state_dir / "attachments").glob("*/page-*.png"))
            ctx.check(f"the pictures are in the session's attachments folder, got {len(pics)}", len(pics) >= 4)
        profile = state_dir / "browser" / "profile"
        ctx.check("the session used Halo's kept profile, which stays", profile.is_dir())
        left = _gone(str(profile))
        ctx.check(f"no process carries the browser's profile, got {left}", not left)
        left = _gone(str(home))
        ctx.check(f"nothing of the session is left running, got {left}", not left)
    finally:
        if p is not None and p.poll() is None:
            p.kill()
            p.communicate(timeout=30)
        mock.stop()
        if saved is None:
            SCENARIOS.pop("browserreal", None)
        else:
            SCENARIOS["browserreal"] = saved


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
