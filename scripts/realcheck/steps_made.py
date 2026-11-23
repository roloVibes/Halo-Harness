"""scripts/realcheck/steps_made.py -- the step `made-at-once` (3.6.0.15 K1, the design's "made and started at once"): a
pick in a running helper's box acts at once. A real Studio (`halo studio`) and a real terminal session (`halo`) in one
scratch home on Auto, the fake provider playing main and its helpers (fakes.MADE_CALLS), headless Chrome at 1440 x 900
on Session with its drawer open. What a person does, each scene alone, every one reported as '(x) what a person saw':

  (a) main starts the built-in Judge (held running); he opens its box (the sheet), presses MODEL's "Change", reads the
      block (BUILT-IN: "Judge is built into Halo and has no file. Picking a model makes judge ..." and "This helper keeps
      {model} until it ends."), picks the step's second model; the block reads "Made judge, an agent of yours on {ref}:
      main can start it now, unless it names a model itself." with Undo, and judge.yaml is his agent on that model
  (b) the Judge let go: main's first request after the pick carries N1 for judge once (none before it), main starts
      `judge`, and judge's request goes to the picked model
  (d) Undo in the same sheet (its token lives only there): "Taken back: judge is gone.", judge.yaml gone; the next turn's
      first request carries N2 for judge once
  (c) Agents' form: a new agent `sorter` saved while the session runs: "Saved sorter.", the save's answer says this
      session took it, the next turn's first request carries its N1 once, letter for letter
  (e) nothing the step started is left (the check's own closing judge)

(d) runs before (c): Undo is a button of the open sheet, and (c) leaves Session for Agents. The step adds the second
model to the fake provider for its own run only and puts back exactly what it found. Every wait names the state it
waits for and ends only on a true value; the judges are pure functions of a read (tests/test_realcheck.py). SKIP when no
browser may be used (--browser none); with no Chrome found, a FAIL that names it (the first thing it does). No other step's
module is imported for a helper (live-scene's included): the shared helpers live in steps_map.py and steps_auto.py."""
from __future__ import annotations

import json
import re
import sys

from realcheck import fakes
from realcheck.core import browser
from realcheck.steps_auto import _fail, _open, _quit, _session
from realcheck.steps_b import WATCH
from realcheck.steps_map import HOOK, _alone, _say, _wide_chrome

WIN = sys.platform == "win32"
TURN_WAIT_S = 120.0 if WIN else 60.0  # a real session's turn on Auto (main's call, a helper started)
LIVE_WAIT_S = 30.0 if WIN else 15.0  # a page state after a press

# == the words, letter for letter as the product writes them (tests/test_realcheck.py ties each to its constant) ======
# studio/crew_model_api.py LINES[(BUILTIN, True)] with X "Judge" and the name name_of gives it in an empty home, KEEPS,
# MADE_NOW, TAKEN_BACK; crew/kinds_note.py N1 / N1_BARE and N2_GONE
LINE_NOW = ("Judge is built into Halo and has no file. Picking a model makes judge, an agent of yours built from Judge, "
            "on that model: main can start judge from now, in this session too, unless it names a model itself.")
KEEPS = "This helper keeps {model} until it ends."
KEEPS_RE = re.compile(r"This helper keeps .+ until it ends\.")
MADE = "Made judge, an agent of yours on {ref}: main can start it now, unless it names a model itself."
TAKEN = "Taken back: judge is gone."
SORTER_DOES = "Sorts the files it is given by kind."  # UN's own example
N1_SORTER = "[Halo] A new helper you can start now: sorter (Sorts the files it is given by kind)."
N1_JUDGE_RE = re.compile(re.escape("[Halo] A new helper you can start now: judge") + r"(?: \([^()\n]*\))?\.")
N2_JUDGE = "[Halo] Taken back: judge can no longer be started in this session."
SAVED = "Saved sorter."

# == the page: every wait expression gives true only (an element through returnByValue is {}, never ends a wait) =====
ROOT = "document.querySelector('[data-testid=session-lit-map]')"
SHEET = "document.querySelector('[data-testid=map-step-in][data-open]')"
OPEN = f"!!{SHEET}"
GONE = "!document.querySelector('.mp-step-in')"
TOGGLE = f"{SHEET}?.querySelector('[data-testid=map-step-in-model-toggle]')"
CONTENT = f"{SHEET}?.querySelector('[data-testid=map-step-in-model-content]')"
ROWS = f"((k) => k ? [...k.querySelectorAll('[data-testid=map-step-in-model-line] p')].map((p) => p.textContent) : [])({CONTENT})"
UNDO = f"{CONTENT}?.querySelector('[data-testid=map-step-in-model-undo]')"
FIELD = f"{SHEET}.querySelector('[data-testid=map-step-in-model-select]')"
DIALOG = "document.querySelector('[data-testid=\"model-select-dialog\"]')"
# the open picker's row of the step's second model (tests/helpers/model_pick.py: the dialog, else the field's fold)
ROW = (f"({DIALOG} || ({FIELD}).closest('.msel') || ({FIELD}))"
       f".querySelector('[data-testid$=\"-row\"][data-ref$={json.dumps(fakes.JUDGE_MODEL.split('/', 1)[1])}]')")
# a fresh home has no model list cached: the picker says so with its Refresh (routes/shared/picker/PickerParts.tsx)
REFRESH = (f"({DIALOG} || ({FIELD}).closest('.msel') || ({FIELD}))"
           ".querySelector('[data-testid=model-select-refresh]:not([disabled])')")
NEW = "(document.querySelector('[data-testid=crew-new]') || document.querySelector('[data-testid=crew-empty-new]'))"
FORM = "!!document.querySelector('[data-testid=crew-form]')"
NAME = "document.querySelector('[data-testid=crew-name]')"
DOES = "document.querySelector('[data-testid=crew-does]')"
SAVE = "document.querySelector('[data-testid=crew-save]')"
NOTE = "document.querySelector('[data-testid=crew-note]')"
SORTER_PATH = "/api/crew/agent/sorter"

# state that stays: every write of an agent or a pick the page sent, with its answer (the hook runs before the page's
# own scripts on every new document, so lib/api.ts's fetch is this one)
MADE_HOOK = r"""(() => { if (window.__rcm) return; const M = window.__rcm = {calls: []}; const f = window.fetch;
  window.fetch = function (input, init) {
    const url = typeof input === 'string' ? input : (input && input.url) || String(input);
    const method = String((init && init.method) || (input && input.method) || 'GET').toUpperCase();
    let path = ''; try { path = new URL(url, location.href).pathname; } catch (e) { path = String(url); }
    const p = f.apply(this, arguments);
    if (method !== 'GET' && (path.startsWith('/api/crew/agent/') || path.startsWith('/api/crew/agent-model'))) {
      const row = {method, path, status: 0, body: null}; M.calls.push(row);
      p.then((r) => { row.status = r.status; r.clone().json().then((j) => { row.body = j; }, () => { row.body = {}; }); },
             () => { row.status = -1; row.body = {}; }); }
    return p; }; })();"""


def member_wait(what: str) -> str:
    """A member of Session's drawer whose line ends with `what`, running."""
    return (f"((r) => !!r && [...r.querySelectorAll('[data-member]')].some((m) => m.dataset.raw === 'running' && "
            f"(m.querySelector('[data-testid=map-member-line]')?.textContent || '').endsWith({json.dumps(what)})))({ROOT})")


def member_id(what: str) -> str:
    return (f"((r) => (r ? [...r.querySelectorAll('[data-member]')].find((m) => m.dataset.raw === 'running' && "
            f"(m.querySelector('[data-testid=map-member-line]')?.textContent || '').endsWith({json.dumps(what)})) : null)"
            f"?.dataset.member || '')({ROOT})")


def member(aid: str) -> str:
    return f"{ROOT}?.querySelector('[data-member={json.dumps(aid)}]')"


def content_wait() -> str:
    """The opened MODEL block has read the helper's agent: its kind is set and it has rows."""
    return (f"((k) => !!k && !!k.dataset.kind && k.querySelectorAll('[data-testid=map-step-in-model-line] p').length > 0)"
            f"({CONTENT})")


def changed_wait(before: list) -> str:
    """The block's rows read something other than `before` (a pick's or Undo's answer replaced them)."""
    return (f"((rows, b) => rows.length > 0 && (rows.length !== b.length || rows.some((r, i) => r !== b[i])))"
            f"({ROWS}, {json.dumps(before)})")


def row_wait() -> str:
    return f"(() => {{ try {{ return !!{ROW}; }} catch (e) {{ return false; }} }})()"


def listed_wait() -> str:
    """The open picker drew the second model's row, or its Refresh (no list cached yet in a fresh home)."""
    return f"(() => {{ try {{ return !!{ROW} || !!{REFRESH}; }} catch (e) {{ return false; }} }})()"


def note_wait() -> str:
    return f"({NOTE}?.textContent || '') === {json.dumps(SAVED)}"


def saved_wait() -> str:
    return (f"!!window.__rcm && window.__rcm.calls.some((r) => r.method === 'POST' && r.path === {json.dumps(SORTER_PATH)}"
            " && r.body !== null)")


def waits() -> dict:
    """Every wait expression of the step (tests/test_realcheck.py evaluates each against a page stand-in)."""
    return {"member": member_wait("judge the draft"), "open": OPEN, "toggle": f"!!{TOGGLE}", "content": content_wait(),
            "listed": listed_wait(), "row": row_wait(), "changed": changed_wait(["x"]), "gone": GONE, "new": f"!!{NEW}", "form": FORM,
            "note": note_wait(), "saved": saved_wait()}


# == the judges: pure functions of what was read ======================================================================
def made_reqs(requests: list, mark: int = 0, start: int = 0) -> list:
    """The model calls from `start` on, each {i, after (sent at or after `mark`), who, model, text}: `who` is "main" (a
    call with tools whose user messages hold MADE_PROMPT), "j1" / "j2" (the Judge's and judge's), else ""."""
    out = []
    for i, r in enumerate(requests or []):
        body = r.get("body") if isinstance(r, dict) else None
        if i < start or r.get("method") != "POST" or not isinstance(body, dict):
            continue
        msgs = [m for m in body.get("messages") or [] if isinstance(m, dict)]
        if not msgs:
            continue
        users = [fakes._text(m.get("content")) for m in msgs if m.get("role") == "user"]
        said = lambda k: any(k in u for u in users)  # noqa: E731
        who = ("main" if said(fakes.MADE_PROMPT) and body.get("tools") else "j1" if said("RC-MADEJ1")
               else "j2" if said("RC-MADEJ2") else "")
        out.append({"i": i, "after": i >= mark, "who": who, "model": str(body.get("model") or ""),
                    "text": "\n".join(fakes._text(m.get("content")) for m in msgs)})
    return out


def _first_main(reqs: list) -> "dict | None":
    return next((r for r in reqs if r.get("after") and r.get("who") == "main"), None)


def _n1_judge(text: str) -> int:
    return len(N1_JUDGE_RE.findall(text or ""))


def judge_made_block(read: dict) -> list:
    """(a) the MODEL block of the built-in Judge's sheet before and after the pick, and the file the pick wrote."""
    bad = []
    ref = str(read.get("ref") or "")
    if read.get("kind") != "BUILT-IN":
        bad.append(f"(a) the block's kind is {read.get('kind')!r}, not 'BUILT-IN'")
    before = list(read.get("before") or [])
    if not (len(before) == 2 and before[0] == LINE_NOW and KEEPS_RE.fullmatch(before[1] or "")):
        bad.append(f"(a) before the pick the block reads {before}, want {[LINE_NOW, KEEPS]}")
    after = list(read.get("after") or [])
    if after != [MADE.format(ref=ref)]:
        bad.append(f"(a) after the pick the block reads {after}, want {[MADE.format(ref=ref)]}")
    if read.get("undo_word") != "Undo":
        bad.append("(a) no Undo after the pick")
    if not read.get("file") or read.get("file_model") != ref:
        bad.append(f"(a) judge.yaml was not written as his agent on {ref} (the file: {bool(read.get('file'))}, its "
                   f"model: {read.get('file_model')!r})")
    return bad


def judge_made_requests(reqs: list, ref_model: str) -> list:
    """(b) N1 for judge on main's first request after the pick, once, and on none before it; main started judge and
    judge's request went to the picked model (a row's ref may carry a provider prefix: the body names the model)."""
    bad = []
    early = [r["i"] for r in reqs if not r.get("after") and _n1_judge(r.get("text", ""))]
    if early:
        bad.append(f"(b) a request before the pick carried N1 for judge (requests {early})")
    first = _first_main(reqs)
    if first is None:
        bad.append("(b) main sent no request after the pick")
    else:
        n = _n1_judge(first.get("text", ""))
        if n == 0:
            bad.append("(b) main's first request after the pick does not carry N1 for judge")
        elif n != 1:
            bad.append(f"(b) main's first request after the pick carries N1 for judge {n} times")
    j2 = next((r for r in reqs if r.get("who") == "j2"), None)
    want = str(ref_model or "").split(":", 1)[-1]
    if j2 is None:
        bad.append("(b) main never started judge (no request of RC-MADEJ2)")
    elif j2.get("model") != want:
        bad.append(f"(b) judge's request went to {j2.get('model')!r}, not the picked {ref_model!r}")
    return bad


def judge_made_undo(read: dict) -> list:
    """(d) Undo's line, the file gone, N2 on main's first request after Undo, once."""
    bad = []
    rows = list(read.get("rows") or [])
    if rows != [TAKEN]:
        bad.append(f"(d) after Undo the block reads {rows}, want {[TAKEN]}")
    if read.get("file"):
        bad.append("(d) judge.yaml is still there after Undo")
    first = _first_main(read.get("reqs") or [])
    if first is None:
        bad.append("(d) main sent no request after Undo")
    else:
        n = (first.get("text") or "").count(N2_JUDGE)
        if n == 0:
            bad.append("(d) main's first request after Undo does not carry N2 for judge")
        elif n != 1:
            bad.append(f"(d) main's first request after Undo carries N2 for judge {n} times")
    return bad


def judge_made_save(read: dict, sid: str) -> list:
    """(c) the form's note, the save's answer (this session took sorter), N1 for sorter on main's next request, once."""
    bad = []
    if read.get("note") != SAVED:
        bad.append(f"(c) the form did not say \"{SAVED}\" (it read {read.get('note')!r})")
    live = read.get("live")
    if not any(isinstance(x, dict) and x.get("session_id") == sid and x.get("took") is True for x in live or []):
        bad.append(f"(c) the save's answer does not say this session took sorter: {live}")
    first = _first_main(read.get("reqs") or [])
    if first is None:
        bad.append("(c) main sent no request after the save")
    else:
        n = (first.get("text") or "").count(N1_SORTER)
        if n == 0:
            bad.append("(c) main's first request after the save does not carry N1 for sorter")
        elif n != 1:
            bad.append(f"(c) main's first request after the save carries N1 for sorter {n} times")
    return bad


# == the step =========================================================================================================
def _wait(c, expr: str, timeout: float = LIVE_WAIT_S):
    try:
        return c.wait(expr, timeout)
    except TimeoutError:
        return None


def _file(h) -> "tuple[bool, str]":
    """Whether his judge.yaml exists, and its model (the file as the Agents form writes it)."""
    path = h.state / "crew" / "agents" / "judge.yaml"
    if not path.is_file():
        return False, ""
    m = re.search(r"(?m)^model:\s*['\"]?([^'\"\n]+?)['\"]?\s*$", path.read_text(encoding="utf-8", errors="replace"))
    return True, (m.group(1) if m else "")


def _calls(c) -> list:
    return c.js("window.__rcm ? window.__rcm.calls : []") or []


def _turn(t, prompt: str, done: str) -> bool:
    mark = _say(t, prompt)
    return t.wait_for(lambda s: done in s[mark:], TURN_WAIT_S)


def made_at_once(ctx):
    exe = browser(ctx)  # first: --browser none is a SKIP, no Chrome found a FAIL, before any halo starts
    h = ctx.home("made-at-once")
    p = ctx.provider
    p.rearm()
    put_back = p.with_model(fakes.JUDGE_MODEL)  # the pick is never main's own model
    bad: list = []
    c = t = ts = None
    ev: dict = {}
    try:
        ts, base, token, ev = _open(ctx, h)
        c = _wide_chrome(exe, (WATCH, HOOK, MADE_HOOK))
        t, sid = _session(ctx, h, c, f"{base}/?mode=session&open=session-map&tour=off#t={token}", ev, bad, "e")
        if ev.get("session_up_s"):
            _scenes(ctx, h, c, t, sid, f"{base}/?mode=agents&view=crew&tour=off#t={token}", ev, bad)
    finally:
        p.release()  # no held call outlives the step
        if ts is not None:
            _quit(ctx, h, c, (t, ts), bad, ev, "e")
        else:
            ctx.end_leftovers(h)
        put_back()
    _fail(bad, ev)
    return ("a Judge pick in its box made judge, main was told and started it on that model; Undo took it back and main "
            "was told; sorter saved in Agents reached the session; nothing left"), ev


def _scenes(ctx, h, c, t, sid: str, agents: str, ev: dict, bad: list) -> None:
    p = ctx.provider
    start = len(p.mock.requests)
    picked = _alone("a", bad, _pick, ctx, h, c, t, ev, bad)
    if not picked:
        return
    _alone("b", bad, _started, ctx, t, picked, start, ev, bad)
    _alone("d", bad, _undo, ctx, h, c, t, start, ev, bad)
    _alone("c", bad, _save, ctx, c, t, sid, agents, start, ev, bad)


def _pick(ctx, h, c, t, ev: dict, bad: list) -> "dict | None":
    p = ctx.provider
    _say(t, fakes.MADE_PROMPT)
    if not _wait(c, member_wait("judge the draft"), TURN_WAIT_S):
        lines = c.js(f"((r) => r ? [...r.querySelectorAll('[data-member]')].map((m) => [m.dataset.raw, "
                     f"m.querySelector('[data-testid=map-member-line]')?.textContent || '']) : null)({ROOT})")
        bad.append(f"(a)-(d) not run: Session's drawer never drew the Judge's helper ('judge the draft') running in "
                   f"{TURN_WAIT_S:.0f} s (it drew {lines})")
        return None
    aid = c.js(member_id("judge the draft")) or ""
    ev["judge_aid"] = aid
    c.js(f"{member(aid)}.scrollIntoView({{block: 'center'}}); 1")
    x, y, w, hh = c.rect(member(aid))
    c.click(x + w / 2, y + hh / 2)
    if not _wait(c, OPEN):
        bad.append(f"(a)-(d) not run: a click on the Judge's box ({aid}) opened no sheet")
        return None
    if not _wait(c, f"!!{TOGGLE}"):
        bad.append("(a)-(d) not run: the Judge's sheet has no MODEL 'Change'")
        return None
    c.js(f"{TOGGLE}.click(); 1")
    if not _wait(c, content_wait()):
        bad.append(f"(a)-(d) not run: after 'Change' the MODEL block never read the helper's agent (it reads "
                   f"{c.js(ROWS)})")
        return None
    read = {"kind": c.js(f"{CONTENT}?.dataset.kind || ''"), "before": c.js(ROWS) or []}
    from tests.helpers import model_pick
    model_pick.open_picker(c, FIELD, LIVE_WAIT_S)
    # the rows come from a read of the models after the search box shows; a fresh home has no list cached yet, and the
    # picker offers its Refresh: he presses it, as its own line asks
    read["refreshed"] = bool(_wait(c, listed_wait())) and not c.js(row_wait())
    if read["refreshed"]:
        c.js(f"{REFRESH}.click(); 1")
    if not _wait(c, row_wait(), TURN_WAIT_S if read["refreshed"] else LIVE_WAIT_S):
        bad.append(f"(a) the picker offered no row of {fakes.JUDGE_MODEL}: {model_pick.rows(c, FIELD)}; (b)-(d) not run")
        read["picker"] = c.js(f"(({DIALOG}) || ({FIELD}))?.innerText?.slice(0, 600) || ''")
        ev["a"] = read
        return None
    ref = c.js(f"{ROW}.dataset.ref") or ""
    mark = len(p.mock.requests)
    c.js(f"{ROW}.scrollIntoView({{block: 'nearest'}}); {ROW}.click(); 1")
    read["changed"] = bool(_wait(c, changed_wait(read["before"])))
    read.update(ref=ref, after=c.js(ROWS) or [], undo_word=(c.js(f"{UNDO}?.textContent || ''") or "").strip())
    read["file"], read["file_model"] = _file(h)
    read["answer"] = [x for x in _calls(c) if x.get("path") == "/api/crew/agent-model"]
    ev["a"] = read
    bad.extend(judge_made_block(read))
    return {"ref": ref, "mark": mark}


def _summary(reqs: list) -> list:
    return [[r["i"], r["who"], r["model"], _n1_judge(r["text"]), r["text"].count(N2_JUDGE), r["text"].count(N1_SORTER)]
            for r in reqs if r["who"]]


def _started(ctx, t, picked: dict, start: int, ev: dict, bad: list) -> None:
    p = ctx.provider
    p.release()  # the Judge answers: main's next request is the first after the pick
    done = t.wait_for(lambda s: fakes.MADE_DONE in s, TURN_WAIT_S)
    reqs = made_reqs(p.mock.requests, picked["mark"], start)
    ev["b"] = {"done": done, "requests": _summary(reqs)}
    if not done:
        bad.append(f"(b) main never ended its turn ({fakes.MADE_DONE}) in {TURN_WAIT_S:.0f} s")
    bad.extend(judge_made_requests(reqs, picked["ref"]))


def _undo(ctx, h, c, t, start: int, ev: dict, bad: list) -> None:
    p = ctx.provider
    if not c.js(f"!!{UNDO}"):
        bad.append(f"(d) not run: the sheet's Undo is not on the page (the sheet open: {bool(c.js(OPEN))})")
        return
    before = c.js(ROWS) or []
    mark = len(p.mock.requests)
    c.js(f"{UNDO}.click(); 1")
    changed = bool(_wait(c, changed_wait(before)))
    rows = c.js(ROWS) or []
    gone_file = not _file(h)[0]
    c.js("document.activeElement && document.activeElement.blur && document.activeElement.blur(); 1")
    c.key("Escape")
    closed = bool(_wait(c, GONE))
    noted = _turn(t, fakes.NOTED_PROMPT, fakes.NOTED_DONE)
    reqs = made_reqs(p.mock.requests, mark, start)
    ev["d"] = {"changed": changed, "rows": rows, "file_gone": gone_file, "closed": closed, "noted": noted,
               "requests": _summary([r for r in reqs if r["after"]])}
    if not closed:
        bad.append("(d) Escape did not close the sheet")
    if not noted:
        bad.append(f"(d) main never answered the turn after Undo ({fakes.NOTED_DONE}) in {TURN_WAIT_S:.0f} s")
    bad.extend(judge_made_undo({"rows": rows, "file": not gone_file, "reqs": reqs}))


def _save(ctx, c, t, sid: str, agents: str, start: int, ev: dict, bad: list) -> None:
    p = ctx.provider
    c.go(agents)  # Agents' form; the hooks come back with the new document (its calls start empty)
    if not _wait(c, f"!!{NEW}", TURN_WAIT_S):
        bad.append("(c) not run: Agents never showed '+ New agent'")
        return
    c.js(f"{NEW}.click(); 1")
    if not _wait(c, FORM):
        bad.append("(c) not run: '+ New agent' opened no form")
        return
    c.js(f"{NAME}.focus(); {NAME}.select(); 1")
    c.call("Input.insertText", text="sorter")
    c.js(f"{DOES}.focus(); 1")
    c.call("Input.insertText", text=SORTER_DOES)
    if not _wait(c, f"!!{SAVE} && !{SAVE}.disabled && {NAME}.value === 'sorter'"):
        bad.append(f"(c) not run: the form's Save never came on for 'sorter' (the name reads {c.js(f'{NAME}?.value')!r})")
        return
    mark = len(p.mock.requests)
    c.js(f"{SAVE}.click(); 1")
    _wait(c, saved_wait())
    _wait(c, note_wait())
    call = next((x for x in _calls(c) if x.get("method") == "POST" and x.get("path") == SORTER_PATH), {})
    note = c.js(f"{NOTE}?.textContent || ''") or ""
    noted = _turn(t, fakes.NOTED_PROMPT, fakes.NOTED_DONE)
    reqs = made_reqs(p.mock.requests, mark, start)
    live = (call.get("body") or {}).get("live")
    ev["c"] = {"note": note, "status": call.get("status"), "live": live, "noted": noted,
               "requests": _summary([r for r in reqs if r["after"]])}
    if not noted:
        bad.append(f"(c) main never answered the turn after the save ({fakes.NOTED_DONE}) in {TURN_WAIT_S:.0f} s")
    bad.extend(judge_made_save({"note": note, "live": live, "reqs": reqs}, sid))

