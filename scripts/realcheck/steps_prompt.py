"""scripts/realcheck/steps_prompt.py -- the step `prompt` (3.6.0.2 "one prompt", the owner's point 21: "the gui prompt
and tui prompt need to be 1:1"; promptF-design section 7). Its OWN `halo studio` and one real `halo` in a terminal,
in one scratch home; Studio is called over HTTP the way its page calls it (the token and the owner proof of the
private studio.json: studio/launch.api_call). No browser. Each assert alone, as '(n) what a person saw':

  (1) a prompt sent the way Studio's Prompt sends it shows ONCE in the terminal: its own `❯` row and no grey copy
      (`(from Studio) prompt:` or `(remote) prompt:`; the session's title, made from the same words, is no copy), and
      the answer is drawn after it
      (Textual paints only the rows in view: the answer drawn means the view followed it to the bottom)
  (2) `/model or:realcheck/two` sent from Studio switches the model: the answer is `ran: true` with `Model set to`,
      and the terminal draws the line's row and the new model
  (3) a permission ask answered from Studio: the terminal's card reads `Answered in Studio: Allow`, the key that
      closes it (Enter) sends nothing to the model, and `RC-ASK next` typed next runs as a turn (that the card stays
      until that key is P5's tests/test_prompt_one_terminal.py: a stream of bytes shows what was drawn, not what stays)
  (4) neither the session's log nor the screen holds the machine's user name or host name (the rig's own paths taken
      out first)
  (5) the session's row carries `first_words` after the first prompt, and after `/clear` in the terminal the new row's
      `follows` names the old id
Everything it starts ends in its own finally, by pid (the rig's scan finds nothing of the run left)."""
from __future__ import annotations

import getpass
import json
import re
import socket
import time
import uuid

from realcheck import fakes, screen
from realcheck.core import Fail, excerpt, wait_address, wait_until
from realcheck.steps_a import _no_leftovers

TEXT = "RC-ASK one line from Studio"
MODEL = "or:realcheck/two"


def _api(h, method: str, path: str, body=None):
    from halo_harness.studio.launch import api_call
    got = api_call(h.state, method, path, body, timeout=15.0)
    return got if got is not None else (0, {})


def _rows(h) -> list:
    status, rows = _api(h, "GET", "sessions")
    return rows if status == 200 and isinstance(rows, list) else []


def _send(h, sid: str, body: dict):
    return _api(h, "POST", f"sessions/{sid}/command", body)


def _alone(n: int, bad: list, fn, *args):
    try:
        return fn(*args)
    except Exception as e:
        bad.append(f"({n}) not run: realcheck could not call Studio or read the screen: {type(e).__name__}: {str(e)[:160]}")
        return None


def _since(t, mark: int) -> str:
    return t.plain()[mark:]


# -- (1) one row ------------------------------------------------------------------------------------------------------
def _once(ctx, h, t, sid: str, ev: dict, bad: list) -> None:
    mark = len(t.plain())
    status, ans = _send(h, sid, {"cmd": "submit", "text": TEXT, "when_busy": "refuse", "client_id": "rc-" + uuid.uuid4().hex})
    answered = t.wait_for(lambda s: fakes.ANSWER in s[mark:], 30)
    seen = _since(t, mark)
    drawn = len(re.findall(re.escape(TEXT), seen))
    rows = len(re.findall(r"❯\s*" + re.escape(TEXT), seen))
    ev["once"] = {"status": status, "taken": (ans.get("result") or {}).get("taken") if isinstance(ans, dict) else None,
                  "drawn": drawn, "rows": rows, "answered": answered}
    if status != 200:
        bad.append(f"(1) Studio's submit answered {status}: {str(ans)[:160]}")
    elif not rows:
        bad.append("(1) the prompt sent from Studio has no `❯` row on the terminal: " + excerpt(seen, 200))
    elif re.search(r"\((from Studio|remote)\)\s*prompt:", seen):  # the second, grey copy of 3.6.0.1 and before
        at = re.search(r"\((from Studio|remote)\)\s*prompt:", seen).start()
        bad.append(f"(1) the prompt shows twice: its row and a grey copy: " + excerpt(seen[at:at + 160], 160))
    elif not answered or seen.rfind(fakes.ANSWER) < seen.find(TEXT):
        bad.append("(1) the answer was not drawn after the prompt's row (the view did not follow): " + excerpt(seen, 200))


# -- (2) /model from Studio -------------------------------------------------------------------------------------------
def _model(ctx, h, t, sid: str, ev: dict, bad: list) -> None:
    mark = len(t.plain())
    status, ans = _send(h, sid, {"cmd": "slash", "line": f"/model {MODEL}"})
    result = (ans.get("result") or {}) if isinstance(ans, dict) else {}
    shown = t.wait_for(lambda s: MODEL.split(":", 1)[1] in s[mark:], 10)
    ev["model"] = {"status": status, "ran": result.get("ran"), "output": str(result.get("output") or "")[:200],
                   "row": f"/model {MODEL}" in _since(t, mark), "shown": shown}
    if status != 200 or result.get("ran") is not True or "Model set to" not in str(result.get("output") or ""):
        bad.append(f"(2) `/model {MODEL}` from Studio: {status} {str(ans)[:200]}")
    elif not shown or f"/model {MODEL}" not in _since(t, mark):
        bad.append("(2) the terminal does not show the line's row and the new model: " + excerpt(_since(t, mark), 200))


# -- (3) an ask answered from Studio ----------------------------------------------------------------------------------
def _waiting(h, sid: str) -> str:
    row = next((r for r in _rows(h) if r.get("session_id") == sid), None) or {}
    ids = ((row.get("pending") or {}).get("permission") or [])
    return str(ids[0]) if ids else ""


def _ask(ctx, h, t, sid: str, ev: dict, bad: list) -> None:
    mark = len(t.plain())
    _send(h, sid, {"cmd": "submit", "text": "RC-PERM make the folder", "when_busy": "refuse", "client_id": "rc-" + uuid.uuid4().hex})
    rid = wait_until(lambda: _waiting(h, sid), 30, 0.25)
    out: dict = {"request": rid}
    ev["ask"] = out
    if not rid:
        return bad.append("(3) no permission ask came for RC-PERM in 30 s: " + excerpt(_since(t, mark), 200))
    status, ans = _send(h, sid, {"cmd": "answer", "kind": "permission", "request_id": rid, "action": "allow", "scope": "once",
                                 "client_id": "rc-" + uuid.uuid4().hex})
    out["status"] = status
    out["line"] = t.wait_for(lambda s: "Answered in Studio: Allow" in s[mark:], 15)
    out["answered"] = t.wait_for(lambda s: fakes.ANSWER in s[mark:], 30)
    out["turn_done"] = t.wait_for(lambda s: re.search(r"done · \d", s[mark:]) is not None, 15)  # the turn's end row
    seen = _since(t, mark)
    if status != 200 or not out["line"]:
        return bad.append(f"(3) answered from Studio ({status}): no `Answered in Studio: Allow` on the terminal: " + excerpt(seen, 200))
    time.sleep(1.0)
    before = len(ctx.provider.mock.requests)
    t.write(b"\r")  # the key that closes the answered card: it sends nothing
    time.sleep(1.5)
    out["after_key"] = len(ctx.provider.mock.requests) - before
    if out["after_key"]:
        bad.append(f"(3) the key that closed the answered card sent {out['after_key']} model request(s)")
    mark = len(t.plain())
    t.type("RC-ASK next")
    time.sleep(1.0)  # past a card's first 0.6 s, as a person types
    t.write(b"\r")
    out["next"] = bool(t.wait_for(lambda s: fakes.ANSWER in s[mark:], 20) and ctx.provider.requests_with("RC-ASK next"))
    if not out["next"]:  # evidence only: does a second Enter send it (the first one used up)?
        t.write(b"\r")
        out["second_enter_sent"] = bool(t.wait_for(lambda s: fakes.ANSWER in s[mark:], 10) and ctx.provider.requests_with("RC-ASK next"))
        out["screen"] = excerpt(_since(t, mark), 1500)
    if not out["next"]:
        bad.append("(3) `RC-ASK next` typed after the card did not run as a turn: " + excerpt(_since(t, mark), 200))


# -- (4) no user or host name -----------------------------------------------------------------------------------------
def _names() -> list:
    out = []
    for n in (getpass.getuser(), socket.gethostname(), socket.gethostname().split(".")[0]):
        if n and len(n) >= 3 and n.lower() not in [x.lower() for x in out]:
            out.append(n)
    return out


def _roots(ctx, h) -> list:
    """The rig's own folders and the program's (the checkout, the installed package, Python, the real home): a path
    is where a program lives, not a name a request carried. The longest first."""
    import sys
    import tempfile
    from pathlib import Path

    import halo_harness
    got = {str(ctx.root), str(h.dir), str(h.home), str(h.proj), str(ctx.repo),
           str(Path(halo_harness.__file__).resolve().parents[1]), sys.prefix, sys.base_prefix, str(Path.home()),
           tempfile.gettempdir()}
    return sorted((r for r in got if r and len(r) > 3), key=len, reverse=True)


def _without_paths(text: str, ctx, h) -> str:
    import platform
    for root in _roots(ctx, h):
        for form in (root, root.replace("\\", "/"), json.dumps(root)[1:-1]):
            text = text.replace(form, "<rig>")
    for word in sorted({platform.platform(), platform.release(), platform.version()}, key=len, reverse=True):
        if word and len(word) > 3:  # the system's own name for itself (a kernel named after its distribution)
            text = text.replace(word, "<os>")
    return text


def _private(ctx, h, t, sid: str, ev: dict, bad: list) -> None:
    logs = sorted(h.home.rglob(f"{sid}.jsonl"))
    log = "\n".join(p.read_text(encoding="utf-8", errors="replace") for p in logs)
    shown = re.sub(r"[A-Za-z]:\\\S*|(?<![\w.])/\S+|~\S*", " ", _without_paths(t.plain(), ctx, h))  # paths: the rig's own
    names = _names()
    hits = [(n, where) for n in names for where, text in (("log", _without_paths(log, ctx, h)), ("screen", shown))
            if re.search(re.escape(n), text, re.IGNORECASE)]
    ev["private"] = {"logs": len(logs), "log_bytes": len(log), "names": len(names), "hits": [w for _n, w in hits]}
    if not logs:
        bad.append("(4) the session's log was not found under the home")
    for n, where in hits[:2]:
        text = _without_paths(log, ctx, h) if where == "log" else shown
        at = re.search(re.escape(n), text, re.IGNORECASE).start()
        bad.append(f"(4) the machine's {'user' if n == getpass.getuser() else 'host'} name is in the session's {where}: "
                   + excerpt(text[max(0, at - 80):at + 40].replace(n, "<name>"), 140))


# -- (5) first words, then follows after /clear -----------------------------------------------------------------------
def _clear(ctx, h, t, sid: str, ev: dict, bad: list) -> None:
    row = next((r for r in _rows(h) if r.get("session_id") == sid), None) or {}
    out = {"first_words": row.get("first_words")}
    ev["clear"] = out
    if not str(row.get("first_words") or "").startswith("RC-ASK one line"):
        bad.append(f"(5) the session's row has no first words after the first prompt, got {row.get('first_words')!r}")
    t.type("/clear")
    time.sleep(0.3)
    t.write(b"\r")
    new = wait_until(lambda: next((r for r in _rows(h) if r.get("follows") == sid), None), 30, 0.25)
    out["follows"] = bool(new)
    if not new:
        bad.append("(5) after /clear in the terminal no row follows the old id: "
                   + str([(r.get("session_id", "")[:8], r.get("follows")) for r in _rows(h)])[:200])


def prompt(ctx):
    h = ctx.home("prompt")
    ts = ctx.terminal(h, "studio")  # its OWN Studio: nothing is handed over between steps
    url, at, meanwhile = wait_address(ctx, h, ts, 60)
    if not url:
        screen.quit_with_ctrl_c(ts)
        ts.cleanup()
        ctx.end_leftovers(h)
        raise Fail(f"`halo studio` printed no address in {at:.0f} s: " + excerpt(ts.plain(), 200), {"while_waiting": meanwhile})
    ev: dict = {"address_s": round(at, 1)}
    bad: list = []
    t = None
    try:
        t = ctx.terminal(h, cols=160, rows=50)
        ev["session_up_s"] = round(screen.tui_ready(t, 60), 1)
        sid = ""
        if ev["session_up_s"]:
            sid = wait_until(lambda: next((r.get("session_id") for r in _rows(h) if r.get("kind") == "tui"), ""), 30, 0.25) or ""
        if not sid:
            bad.append("(1)-(5) not run: the terminal session never showed its status line or never reached Studio's list: "
                       + excerpt(t.plain(), 200))
        else:
            ev["sid"] = sid[:8]
            for n, fn in ((1, _once), (2, _model), (3, _ask), (4, _private), (5, _clear)):
                _alone(n, bad, fn, ctx, h, t, sid, ev, bad)
    finally:
        for term in (t, ts):
            if term is not None:
                screen.quit_with_ctrl_c(term)
                term.cleanup()
        try:
            _no_leftovers(ctx, h, "the session and Studio")
        except Fail as e:
            bad.append("left running: " + e.detail)
            ev["left"] = e.evidence.get("left")
        ctx.end_leftovers(h)
    if bad:
        raise Fail("; ".join(bad[:8]) + (f" (+{len(bad) - 8} more)" if len(bad) > 8 else ""), ev)
    return "one row, /model from Studio, the ask answered in Studio, no user or host name, follows after /clear", ev
