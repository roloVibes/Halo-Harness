"""tests.helpers.studio_prompt_pick -- 3.6.0.2 P6 ("one prompt", the design's F2: P27-P29, P31, P32) on Session's
Prompt header and box through real clicks in headless Chrome, over tests/helpers/prompt_rig.py (the scripted fake
session behind the real Controller and its real control socket, an in-process Studio). More sessions are rows in the
same scratch registry that reach the same socket (a row is listed while its socket answers); `/clear` in a terminal is
what P5 makes the registry do: the new row (its `follows` naming the old id) is written, then the old row goes.
tests/test_studio_prompt.py runs it as a subprocess:

    python -m tests.helpers.studio_prompt_pick pick

1. P27: the header names the session in words (folder, title or `no messages yet`, started, in a terminal), never its
   id; a one-line and a two-line title give the header the same height, neither is clipped, the box does not move;
2. P28: `Change session` lists every open session in the same words, newest first, the current one marked; choosing
   one sets the pick and shows no line;
3. P29: a pick changed any other way (`/studio`: POST focus) shows `Now typing into <folder> · <title>.` in the
   header's place for 6 s, the box where it was before, during and after; a title past two lines gives the short line;
4. P31: /clear in the terminal moves the pick to the new row (`Same terminal, new conversation: <folder>.`), the box
   editable, its text the same, the ended line never shown;
5. P32: the picked session ends with nothing following it: the box read-only with its text, the ended line and Copy
   (`Copied.`, the text on the clipboard); a row that follows it later, or another pick, makes the box editable again.
The last stdout line is a JSON object of what it saw (exit 2: no Chrome). No model is called."""
from __future__ import annotations

import json
import sys
import time
import urllib.request
import uuid
from contextlib import contextmanager
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from tests.helpers.chrome_driver import Driver  # noqa: E402
from tests.helpers.studio_prompt import INPUT, P, opened, typed  # noqa: E402

TO = "document.querySelector('[data-testid=\"prompt-to\"]')"
MOVED = "document.querySelector('[data-testid=\"prompt-moved\"]')"
ENDED = "document.querySelector('[data-testid=\"prompt-ended\"]')"
COPY = "document.querySelector('[data-testid=\"prompt-copy\"]')"
ITEMS = "[...document.querySelectorAll('[data-testid=\"prompt-pick-item\"]')]"
# where things are: the header's height, the words' box, the box's top (a P29 line or a title never moves it)
GEOM = (f"(() => {{ const h = {TO}.closest('header').getBoundingClientRect(), w = {TO};"
        f" return {{head: Math.round(h.height), top: Math.round({INPUT}.getBoundingClientRect().top),"
        f" sw: w.scrollWidth, cw: w.clientWidth, sh: w.scrollHeight, ch: w.clientHeight, text: w.textContent}}; }})()")
# the ended line appearing at any moment (a MutationObserver: a flash between two polls is seen too)
WATCH_ENDED = ("(() => { window.__ended = 0; if (window.__endedObs) window.__endedObs.disconnect();"
               " window.__endedObs = new MutationObserver(() => { if (document.querySelector('[data-testid=\"prompt-ended\"]'))"
               " window.__ended += 1; }); window.__endedObs.observe(document.body, {subtree: true, childList: true}); return 1; })()")


def _session_is(c, sid: str, timeout: float = 25) -> bool:
    return bool(c.wait(f"{P} && {P}.dataset.session === {sid!r} && 'ok'", timeout))


def _row(rig, sid: str, **fields) -> dict:
    """A row of the scratch registry that reaches the rig's socket (so it is listed), with `fields`."""
    from halo_harness.remote import registry
    base = dict(registry.entry_for(rig.sid) or {})
    base.update({"session_id": sid, "follows": None, "first_words": "", "title": "", **fields})
    registry.register(base)
    return base


def _focus(rig, sid: str) -> int:
    """`/studio` from another terminal: POST focus {mode: session, session} on the running Studio."""
    from halo_harness.studio import owner_proof
    base, tok = rig.url().split("/?", 1)[0], rig.url().split("#t=", 1)[1]
    req = urllib.request.Request(f"{base}/api/focus", data=json.dumps({"mode": "session", "session": sid}).encode(),
                                 method="POST", headers={"Authorization": "Bearer " + tok, "Content-Type": "application/json",
                                                         owner_proof.HEADER: owner_proof.header_for(rig.server)})
    with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(req, timeout=10) as r:
        return r.status


def _retitle(rig, sid: str, title: str, **more) -> None:
    """A title change (a session sends its own `registry` frame for it; these rows have no session of their own): the
    row in the registry (with `more` of its fields), then the bridge's `sessions` frame, on which the page reads GET
    live again."""
    from halo_harness.remote import registry
    from halo_harness.studio.events import bridge_for
    registry.update(sid, title=title, **more)
    b = bridge_for(rig.server)
    b.publish(b._sessions_frame())


def _title(rig, sid: str, title: str, c) -> dict:
    _retitle(rig, sid, title)
    try:
        c.wait(f"{TO}.textContent.includes({title[:40]!r}) && 'ok'", 25)
    except TimeoutError:
        return dict(c.js(GEOM) or {}, missed=title)
    time.sleep(0.4)
    return c.js(GEOM)


def header(c, rig) -> dict:
    out: dict = {"folder": rig.cwd.name, "sid": rig.sid}
    c.wait(f"{TO}.textContent.includes('in a terminal') && 'ok'", 25)
    out["first"] = c.js(GEOM)
    one = _title(rig, rig.sid, "Fix the parser", c)
    width = c.js(f"{TO}.querySelector('.spp-title').getBoundingClientRect().width") or 1
    per_px = len("Fix the parser") / width
    chars = int(c.js(f"{TO}.clientWidth") * per_px)  # about one line of the header's words
    out.update(one=one, chars_per_line=chars, widths=[width, c.js(f"{TO}.clientWidth"), c.js(f"{P}.getBoundingClientRect().width")])
    rest = len(one.get("text") or "") - len("Fix the parser")  # the folder, the start, the terminal and the dots
    out["two"] = _title(rig, rig.sid, ("parser " * 400)[: max(20, int(chars * 1.6) - rest)].strip() + " end", c)
    out["two_lines"] = c.js(f"new Set([...{TO}.querySelectorAll('.spp-words-in > span')].flatMap((e) => [...e.getClientRects()]"
                            f".map((r) => Math.round(r.top)))).size")
    _title(rig, rig.sid, "Fix the parser", c)
    return {"header": out}


def change(c, rig) -> dict:
    out: dict = {}
    sid2 = uuid.uuid4().hex
    other = rig.cwd.parent / (rig.cwd.name + "-other")
    other.mkdir(exist_ok=True)
    _row(rig, sid2, cwd=str(other), title="Second session", started=time.time() + 60)
    rig.extra = [sid2]
    c.wait(f"!document.querySelector('[data-testid=\"prompt-change\"]').disabled && 'ok'", 10)
    c.click_on("document.querySelector('[data-testid=\"prompt-change\"]')")
    out["listed"] = c.wait(f"{ITEMS}.length === 2 && {ITEMS}.map((i) => ({{sid: i.dataset.session, on: !!i.dataset.on,"
                           f" words: i.querySelector('.spp-pick-words').textContent}}))", 25)
    out["head_words"] = c.js(f"{TO}.textContent")
    c.click_on(f"{ITEMS}.find((i) => i.dataset.session === {sid2!r})")
    out["chosen"] = _session_is(c, sid2)
    t0 = time.monotonic()
    seen = None
    while time.monotonic() - t0 < 1.5 and not seen:
        seen = c.js(f"{MOVED} && {MOVED}.textContent")
        time.sleep(0.1)
    out.update(line_after_list=seen, list_closed=c.js(f"{ITEMS}.length") == 0, sid2=sid2, other=other.name)
    # P29: `/studio` from another terminal names the rig's session
    before = c.js(GEOM)
    out["focus_status"] = _focus(rig, rig.sid)
    out["moved"] = c.wait(f"{MOVED} && {MOVED}.textContent", 20)
    t1 = time.monotonic()
    during = c.js(GEOM)
    gone = c.wait(f"!{MOVED} && 'gone'", 12)
    out.update(shown_s=round(time.monotonic() - t1, 1), gone=gone, before=before, during=during, after=c.js(GEOM),
               pick_after_focus=c.js(f"{P}.dataset.session"))
    # a title past two lines: the short line, the header's height held. Both rows carry the same header WORDS here (the
    # same long title, a folder of the same name, the same start), so the header has one height for both in any font:
    # `-other` in one folder's name made the second row's words one line longer than the first's in some fonts (the
    # macOS runner's: 121 -> 105 px, 3.6.0.3 S), and a header rightly takes the height of the session it names
    from halo_harness.remote import registry
    long = ("parser " * 400)[: int(c.js(f"{TO}.clientWidth") * 3.2 / 5.9)].strip()  # about three lines
    kept = {k: registry.entry_for(sid2).get(k) for k in ("cwd", "started")}
    twin = other / rig.cwd.name
    twin.mkdir(exist_ok=True)
    _retitle(rig, rig.sid, long)
    _retitle(rig, sid2, long, cwd=str(twin), started=registry.entry_for(rig.sid).get("started"))
    c.wait(f"{TO}.textContent.includes('parser parser') && 'ok'", 25)
    same = c.js(f"{TO}.textContent")
    c.click_on("document.querySelector('[data-testid=\"prompt-change\"]')")
    c.wait(f"{ITEMS}.length === 2 && 'ok'", 10)
    c.click_on(f"{ITEMS}.find((i) => i.dataset.session === {sid2!r})")
    _session_is(c, sid2)
    try:
        c.wait(f"{TO}.textContent === {same!r} && 'ok'", 25)
    except TimeoutError:
        raise TimeoutError(f"the second session's header never showed the first one's words {same!r}, it shows "
                           f"{c.js(f'{TO}.textContent')!r}") from None
    time.sleep(0.5)
    lb = c.js(GEOM)
    _focus(rig, rig.sid)
    short = c.wait(f"{MOVED} && {MOVED}.textContent", 20)
    out["long"] = {"line": short, "before": lb, "during": c.js(GEOM)}
    c.wait(f"!{MOVED} && 'gone'", 12)
    out["long"]["after"] = c.js(GEOM)
    _retitle(rig, rig.sid, "Fix the parser")
    _retitle(rig, sid2, "Second session", **kept)
    c.wait(f"{TO}.textContent.includes('Fix the parser') && 'ok'", 25)
    return {"change": out}


def follow_and_end(c, rig) -> dict:
    from halo_harness.remote import registry
    out: dict = {}
    sid2 = rig.extra[0]
    cwd2 = registry.entry_for(sid2)["cwd"]
    c.click_on("document.querySelector('[data-testid=\"prompt-change\"]')")
    c.wait(f"{ITEMS}.length >= 2 && 'ok'", 10)
    c.click_on(f"{ITEMS}.find((i) => i.dataset.session === {sid2!r})")
    _session_is(c, sid2)
    time.sleep(0.5)
    typed(c, "a draft he keeps")
    out["box_before"] = c.js(f"{INPUT}.value")
    c.js(WATCH_ENDED)
    # P31: /clear in sid2's terminal (P5: the new row first, then the old one goes)
    sid3 = uuid.uuid4().hex
    _row(rig, sid3, cwd=cwd2, follows=sid2)
    rig.extra.append(sid3)
    time.sleep(0.3)
    registry.unregister(sid2)
    out["followed"] = _session_is(c, sid3)
    out["line"] = c.wait(f"{MOVED} && {MOVED}.textContent", 10)
    out["head_after"] = c.wait(f"!{MOVED} && {TO}.textContent", 12)
    out.update(box_after=c.js(f"{INPUT}.value"), editable=c.js(f"!{INPUT}.readOnly && !{INPUT}.disabled"),
               ended_seen=c.js("window.__ended"), sid3=sid3)
    # P32: sid3's session ends, nothing follows it
    registry.unregister(sid3)
    end: dict = {"shown": c.wait(f"{ENDED} && {ENDED}.querySelector('.spp-ended-line').textContent", 25)}
    end.update(box=c.js(f"{INPUT}.value"), read_only=c.js(f"{INPUT}.readOnly"), send_off=c.js(
        "document.querySelector('[data-testid=\"prompt-send\"]').disabled"), head=c.js(f"{TO}.textContent"),
               copy_word=c.js(f"{COPY}.textContent"))
    origin = rig.url().split("/?", 1)[0]
    c.call("Browser.grantPermissions", origin=origin, permissions=["clipboardReadWrite", "clipboardSanitizedWrite"])
    c.click_on(COPY)
    end["copied_word"] = c.wait(f"{COPY}.textContent === 'Copied.' && 'Copied.'", 5)
    t = time.monotonic()
    end["clipboard"] = c.js("navigator.clipboard.readText()")
    end["back_to_copy"] = c.wait(f"{COPY}.textContent === 'Copy' && 'Copy'", 6)
    end["copied_s"] = round(time.monotonic() - t, 1)
    out["ended"] = end
    # P31 from P32's state: a row that follows the ended one takes the pick, the box editable with the same text
    sid4 = uuid.uuid4().hex
    _row(rig, sid4, cwd=cwd2, follows=sid3)
    rig.extra.append(sid4)
    again = {"followed": _session_is(c, sid4), "line": c.wait(f"{MOVED} && {MOVED}.textContent", 10)}
    again.update(box=c.js(f"{INPUT}.value"), editable=c.js(f"!{INPUT}.readOnly && !{INPUT}.disabled"),
                 ended_gone=c.js(f"!{ENDED}"))
    out["from_ended"] = again
    # ended again, then another session picked from the list: editable, the same text
    registry.unregister(sid4)
    c.wait(f"!!{ENDED} && 'ok'", 25)
    c.click_on("document.querySelector('[data-testid=\"prompt-change\"]')")
    c.wait(f"{ITEMS}.length >= 1 && 'ok'", 10)
    c.click_on(f"{ITEMS}.find((i) => i.dataset.session === {rig.sid!r})")
    out["other_pick"] = {"picked": _session_is(c, rig.sid), "box": c.js(f"{INPUT}.value"),
                         "editable": c.js(f"!{INPUT}.readOnly && !{INPUT}.disabled"), "ended_gone": c.js(f"!{ENDED}")}
    return {"pick": out}


def one_refused_connect(c, rig) -> dict:
    """3.6.0.4 S4: every row's next connect probe is refused ONCE (what a full accept queue does on a loaded machine),
    then Studio reads GET live: the picked session stays listed, the box editable with its text, never the ended line.
    Before 3.6.0.4 that one refusal pruned the row for good and the box went read-only ("ended")."""
    from halo_harness.remote import client, registry
    from halo_harness.studio.events import bridge_for
    out: dict = {"picked": _session_is(c, rig.sid), "box_before": c.js(f"{INPUT}.value")}
    c.js(WATCH_ENDED)
    real, left = client.probe, [len(registry._load(registry.registry_path()))]

    def refused_once(endpoint, *a, **kw):
        if left[0] > 0:
            left[0] -= 1
            return False
        return real(endpoint, *a, **kw)
    client.probe = refused_once
    try:
        b = bridge_for(rig.server)
        b.publish(b._sessions_frame())  # the page reads GET live on it
        end = time.monotonic() + 25
        while left[0] > 0 and time.monotonic() < end:
            time.sleep(0.1)
        out["refusals_used"] = left[0] == 0
        time.sleep(1.5)  # past local_view's 1 s cache
        b.publish(b._sessions_frame())
        time.sleep(3.0)
    finally:
        client.probe = real
    row = next((r for r in registry._load(registry.registry_path()) if r.get("session_id") == rig.sid), None)
    box = f"({INPUT} || null)"  # the box itself may be gone (a red run): say so, never raise
    out.update(listed=row is not None, ended_seen=c.js("window.__ended"), box=c.js(f"{box} && {box}.value"),
               editable=c.js(f"!!{box} && !{box}.readOnly && !{box}.disabled"), ended_gone=c.js(f"!{ENDED}"),
               box_shown=c.js(f"!!{box}"))
    return {"refused": out}


class PromptPickDriver(Driver):
    no_chrome = {"skip": "no Chrome found"}

    @contextmanager
    def session(self, c):
        from tests.helpers.prompt_rig import PromptRig
        with PromptRig() as rig:
            rig.extra = []
            try:
                yield ((opened, (c, rig)), (header, (c, rig)), (change, (c, rig)), (follow_and_end, (c, rig)),
                       (one_refused_connect, (c, rig)))
            finally:
                from halo_harness.remote import registry
                for sid in rig.extra:
                    registry.unregister(sid)


if __name__ == "__main__":
    sys.exit(PromptPickDriver(sys.argv[1:]).main())
