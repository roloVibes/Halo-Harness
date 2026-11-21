"""halo_harness.tools.browser -- the built-in `Browser` tool (3.6.0.6 W; the owner: "We need a different solution
that allows agents in the harness to FULLY CONTROL A BROWSER AND SEE IT"). Nothing to install and nothing to switch
on: it drives a Chrome, Chromium, Edge or Brave already on this machine through Halo's own browser
(halo_harness/browser_cdp.py: a DevTools pipe, no port, Halo's child, ended with the session).

    Browser {action: open|read|click|type|key|scroll|back|js|screenshot|close, url?, target?, text?, enter?, show?}

ONE browser per session, started by the first call that needs it. Every action but screenshot and close answers the
same plain text: the page's title and address, its visible text (cut by tools/truncate.py with its line saying how
much was cut), the numbered list of what can be pressed or typed into, and -- after every action that can change the
page -- "Picture: <path>": the page's picture, `page-<n>.png` in the session's attachments folder (the newest
PICTURES_KEPT kept), NOT sent to the model. `screenshot` gives the model the picture the way the Screenshot tool
gives its own (tools/screenshot.picture_result). Permissions: permissions.py decides open/read/screenshot/close as
WebFetch for the same address, the rest as a tool that changes something; `permission_content` is "<action> <address>".
"""

from __future__ import annotations

import re
import threading
from pathlib import Path
from typing import Optional

from halo_harness.tools.base import Tool, ToolContext, ToolResult

ACTIONS = ("open", "read", "click", "type", "key", "scroll", "back", "js", "screenshot", "close")
CHANGES = ("open", "click", "type", "key", "scroll", "back", "js")  # each answer ends with the page's picture
READS = ("open", "read", "screenshot", "close")  # decided as WebFetch is (permissions.py)
PICTURES_KEPT = 20
TEXT_CAP = 12_000
CLOSED = "The browser is closed."
NOT_OPEN = "No browser is open. Call open with a url first."

_BROWSERS: dict = {}
_LOCK = threading.Lock()
_LAST = {"url": ""}


def last_address() -> str:
    """The address the last Browser call in this process left open (the permission card's suggested rule)."""
    return _LAST["url"]


def _key(ctx: ToolContext) -> str:
    return Path(ctx.session_dir).name if ctx.session_dir else "_unscoped"


def step_words(input) -> str:
    """A Browser call's row, the ONE place its words are made: the terminal's tool card (BrowserTool.summary) and
    Studio's Live rows (agent_transcript.tool_label) both read it. The typed text is never in the words."""
    inp = input if isinstance(input, dict) else {}
    action = str(inp.get("action") or "?").strip().lower()

    def one(v) -> str:
        t = " ".join(str(v or "").split())
        return t if len(t) <= 100 else t[:97] + "..."
    target, text = one(inp.get("target")), one(inp.get("text"))
    words = {"open": f"open {one(inp.get('url'))}", "click": f"click {target}",
             "type": f"type into {target}" if target else "type", "key": f"key {text}",
             "scroll": f"scroll {text}"}.get(action, action)
    return f"Browser {words}".strip()


def browser_for(key: str, start: bool = True, *, show: Optional[bool] = None, folder: Optional[Path] = None):
    """The session's one browser (started now when `start`), or None. `show` True: a window a person can watch; a
    running browser without one is ended first (it keeps no state). `folder`: where its downloads land."""
    from halo_harness.browser_cdp import Browser
    with _LOCK:
        b = _BROWSERS.get(key)
        if b is not None and start and show and not getattr(b, "want_show", False):
            _BROWSERS.pop(key, None)
            old, b = b, None
        else:
            old = None
        if b is None and start:
            b = _BROWSERS[key] = Browser(show=True) if show else Browser()
    if old is not None:
        old.close()
    if b is not None and start:
        if folder is not None:
            b.download_dir = folder
        b.start()
    return b


def close_for(key: str) -> bool:
    with _LOCK:
        b = _BROWSERS.pop(key, None)
    if b is None:
        return False
    b.close()
    return True


def _next_picture(folder: Path) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    nums = [int(m.group(1)) for p in folder.glob("page-*.png") if (m := re.fullmatch(r"page-(\d+)\.png", p.name))]
    return folder / f"page-{max(nums, default=0) + 1}.png"


def _keep_newest(folder: Path) -> None:
    pics = sorted(((int(m.group(1)), p) for p in folder.glob("page-*.png")
                   if (m := re.fullmatch(r"page-(\d+)\.png", p.name))), key=lambda t: t[0])
    for _n, p in pics[:-PICTURES_KEPT]:
        try:
            p.unlink()
        except OSError:
            pass


def save_picture(b, sid: Optional[str]) -> Path:
    from halo_harness.tools.screenshot import images_folder
    folder = images_folder(sid)
    path = _next_picture(folder)
    path.write_bytes(b.screenshot())
    _keep_newest(folder)
    return path


def _notes(b) -> "list[str]":
    """What happened during the action, in order (a window, a box, a new tab, a download): the answer begins with it."""
    if hasattr(b, "collect"):
        b.collect()
    if hasattr(b, "take_notes"):
        return b.take_notes()
    out, b.notes = list(b.notes), []
    return out


def page_answer(b, ctx: ToolContext, *, loaded: bool = True, said: str = "") -> str:
    from halo_harness.browser_cdp import STILL_LOADING
    from halo_harness.tools.truncate import spill_and_truncate
    lines = _notes(b)
    if not loaded:
        lines.append(STILL_LOADING)
    pg = b.page()
    b.last_url = pg["url"]
    rows, total = b.controls()
    text = spill_and_truncate(pg["text"].strip(), cap=TEXT_CAP, session_dir=ctx.session_dir,
                              tool_use_id=(f"{ctx.tool_use_id}-page" if ctx.tool_use_id else None))
    if said:
        lines.append(said)
    lines += [f"Title: {pg['title'] or '(none)'}", f"Address: {pg['url']}"]
    lines += ["", text or "(the page shows no text)", ""]
    if total:
        head = f"Controls ({total})" if total == len(rows) else f"Controls (the first {len(rows)} of {total})"
        lines.append(head + ": target one by its number, its words, or css:<selector>")
        lines += [f"{r['n']}. {r['kind']}: {r['words'] or '(no words)'}" for r in rows]
    else:
        lines.append("Controls: none")
    return "\n".join(lines)


class BrowserTool(Tool):
    name: str = "Browser"
    description: str = ("Drive a real browser on this machine (Chrome, Edge, Chromium or Brave; Halo starts it, "
                        "headless): open a page, read it, click, type, press keys, scroll, go back, run JavaScript, "
                        "take a screenshot. Each answer is the page's title, address, text and numbered controls; "
                        "target a control by its number, its words, or css:<selector>. WebFetch is faster to read a "
                        "page that needs no script and no click.")
    input_schema: dict = {"type": "object", "properties": {
        "action": {"type": "string", "enum": list(ACTIONS)},
        "url": {"type": "string", "description": "open: the address"},
        "target": {"type": "string", "description": "click, type: a number from the list, the words, or css:<selector>"},
        "text": {"type": "string", "description": "type: the text; key: Enter, Tab, Control+a...; scroll: up, down, "
                                                  "top, bottom; js: the script"},
        "enter": {"type": "boolean", "description": "type: press Enter after"},
        "show": {"type": "boolean", "description": "open: a window a person can see"}},
        "required": ["action"]}
    is_read_only: bool = False
    is_destructive: bool = False

    def __init__(self) -> None:
        self._page_url = ""

    def page_url(self) -> str:
        """The address of the page the last call left open (what read, click... act on), for the permission engine."""
        return self._page_url

    def address(self, input: dict) -> str:
        inp = input if isinstance(input, dict) else {}
        return str(inp.get("url") or "") if inp.get("action") == "open" else self._page_url

    def summary(self, input: dict) -> str:
        return step_words(input)

    def permission_content(self, input: dict) -> str:
        inp = input if isinstance(input, dict) else {}
        return f"{inp.get('action') or ''} {self.address(inp)}".strip()

    def pool_wait_s(self, input: dict) -> Optional[float]:
        return 120.0

    def run(self, input: dict, ctx: ToolContext) -> ToolResult:
        from halo_harness.browser_cdp import BrowserError
        inp = input if isinstance(input, dict) else {}
        action = str(inp.get("action") or "").strip().lower()
        if action not in ACTIONS:
            return ToolResult(f"action must be one of: {', '.join(ACTIONS)}.", is_error=True)
        key = _key(ctx)
        sid = None if key == "_unscoped" else key
        if action == "close":
            return ToolResult(CLOSED if close_for(key) else "No browser was open.")
        try:
            if action != "open" and browser_for(key, start=False) is None:
                return ToolResult(NOT_OPEN, is_error=True)
            from halo_harness.tools.screenshot import images_folder
            b = browser_for(key, show=bool(inp.get("show")) and action == "open", folder=images_folder(sid))
            loaded, said = True, ""
            if action == "open":
                loaded = b.open(str(inp.get("url") or ""))
            elif action == "click":
                loaded = b.press(inp.get("target")) is not False
            elif action == "type":
                loaded = b.type_into(inp.get("target"), str(inp.get("text") or ""), bool(inp.get("enter"))) is not False
            elif action == "key":
                loaded = b.key(str(inp.get("text") or "")) is not False
            elif action == "scroll":
                b.scroll(str(inp.get("text") or ""))
            elif action == "back":
                loaded = b.back() is not False
            elif action == "js":
                from halo_harness.tools.truncate import spill_and_truncate
                said = "Result: " + spill_and_truncate(b.js(str(inp.get("text") or "")), cap=TEXT_CAP, session_dir=None,
                                                       tool_use_id=None)
                loaded = getattr(b, "loaded", True) is not False
            elif action == "screenshot":
                return self._screenshot(b, sid, ctx)
            answer = page_answer(b, ctx, loaded=loaded, said=said)
            self._page_url = _LAST["url"] = getattr(b, "last_url", "") or self._page_url
            if action in CHANGES:
                answer += f"\nPicture: {save_picture(b, sid)}"
            return ToolResult(answer)
        except BrowserError as e:
            return ToolResult(str(e), is_error=True)

    def _screenshot(self, b, sid, ctx: ToolContext) -> ToolResult:
        from halo_harness.tools.screenshot import picture_result
        path = save_picture(b, sid)
        from halo_harness.browser_cdp import HEIGHT, WIDTH
        head = (f"Screenshot saved at {path} ({WIDTH} x {HEIGHT}, {path.stat().st_size // 1024} KiB, "
                f"{b.name or 'the browser'})")
        return picture_result(str(path), WIDTH, HEIGHT, head, ctx)
