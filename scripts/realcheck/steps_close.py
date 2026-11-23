"""scripts/realcheck/steps_close.py -- steps 10 to 12: closing every way, nothing reused, the machine not held.

10. Each thing a person starts -- a session (bare `halo`), `halo init`, `halo studio`, a one-shot mid-turn, a session
    with a sub-agent mid-run, a session with an MCP server, a managed local model server, a one-shot whose Bash tool
    is mid-run, a session with a background Bash job (the shells and their `sleep`s) -- is ended by Ctrl+C (the
    key typed into its terminal; a full-screen session's "Quit Halo?" answered with Enter, as a person does), by its
    terminal closing (the pty's master closed: SIGHUP; the pseudoconsole closed: CTRL_CLOSE_EVENT) and by a hard kill
    of the top process. Five seconds later no process started under that launch's scratch home may be alive.
11. After a `halo init` is ended, a second `halo init` must start its own Studio (a new pid, started after it).
12. A Studio idle 60 s with Agents -> Live open on a session on Auto that handed work out (3.6.0.14 K2: one piece of
    work handed out in a terminal session, the helper's box opened in place and closed once before the minute): Halo's
    processes together under 5% of one core, and no interval timer added by the drawing or the box that opens in place
    (the page's live interval timers counted before Live, with it, with the box open, closed, and after the minute)."""
from __future__ import annotations

import json
import re
import sys
import time

from realcheck import screen
from realcheck.core import URL, Fail, Skip, browser, excerpt, wait_address

HOW = ("Ctrl+C", "closed terminal", "hard kill")


def _mcp_home(ctx, h) -> None:
    """The scratch home's ~/.claude.json names one stdio MCP server (the suite's fake), as a person's would; loaded at
    the start (`mcpLazy: false`; a lazy one starts only when a turn asks for its tools)."""
    server = {"type": "stdio", "command": sys.executable, "args": ["-m", "tests.helpers.fake_mcp_server"],
              "env": {"PYTHONPATH": str(ctx.repo)}, "mcpLazy": False}
    (h.home / ".claude.json").write_text(json.dumps({"mcpServers": {"rc-fake": server}}), encoding="utf-8")


def _gguf(ctx, h) -> str:
    """A model file and the suite's fake llama-server as the server Halo runs for it (huggingface.llama_server_bin)."""
    f = h.home / "models" / "rc-tiny-Q4_K_M.gguf"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_bytes(b"GGUF" + b"\0" * 2048)
    fake = [sys.executable, str(ctx.repo / "tests" / "helpers" / "fake_llama_server.py")]
    ctx.run(h, "config", "set", "huggingface.llama_server_bin", json.dumps(fake), timeout=30)
    return str(f)


def _has(ctx, h, word: str):
    return lambda: any(word in p.cmdline for p in ctx.ours(h).values())


def _allow_sleep(ctx, h) -> None:
    """The scratch home's Claude Code settings allow the shell command the provider asks for, as a person's would: the
    Bash tool then runs it with no question (fakes: RC-BASH / RC-BGBASH run `sleep`)."""
    (h.home / ".claude").mkdir(parents=True, exist_ok=True)
    (h.home / ".claude" / "settings.json").write_text(json.dumps({"permissions": {"allow": ["Bash(sleep:*)"]}}),
                                                      encoding="utf-8")


def _is_shell(p) -> bool:
    """A `sleep` the Bash tool's shell started (sleep, /bin/sleep, Git Bash's sleep.exe): the most common child of a
    real session, and on macOS one the closing procedure's marker does not reach."""
    return p.name.lower().rsplit("/", 1)[-1].split(".")[0] == "sleep"


def _shell_up(ctx, h) -> bool:
    return any(_is_shell(p) for p in ctx.ours(h).values())


def _typed_bg_job(ctx, h, t) -> bool:
    """Once the session is up: the prompt RC-BGBASH typed and sent (a Bash call run in the background); up when its
    shell runs."""
    if not screen.READY.search(t.plain()):
        return False
    if not getattr(h, "typed", False):
        h.typed = True
        t.type("RC-BGBASH start the job")
        time.sleep(0.3)
        t.write(b"\r")
    return _shell_up(ctx, h)


def _served_beside(ctx, h, t) -> bool:
    """Once the session is up: `halo local serve <file>` from another shell on the same home (it returns at once and
    leaves the server running "until the last Halo process on this home exits"); up when the server runs."""
    if not screen.READY.search(t.plain()):
        return False
    if not getattr(h, "served", False):
        h.served = True
        ctx.run(h, "local", "serve", _gguf(ctx, h), timeout=60)
    return _has(ctx, h, "fake_llama_server")()


# name: (how to prepare the home and the argv, when it is up)
TARGETS = {
    "session": (lambda ctx, h: (), lambda ctx, h, t: screen.READY.search(t.plain())),
    "init": (lambda ctx, h: ("init",), lambda ctx, h, t: re.search(URL, t.plain())),
    "studio": (lambda ctx, h: ("studio",), lambda ctx, h, t: re.search(URL, t.plain())),
    "one-shot mid-turn": (lambda ctx, h: ("-p", "RC-SLOW hold the turn"), lambda ctx, h, t: "RC-SLOW" in ctx.provider.hung),
    "sub-agent mid-run": (lambda ctx, h: ("-p", "RC-HANG spawn and wait"),
                          lambda ctx, h, t: "RC-SUBHANG" in ctx.provider.hung),
    "session + MCP server": (lambda ctx, h: _mcp_home(ctx, h) or (),
                             lambda ctx, h, t: screen.READY.search(t.plain()) and _has(ctx, h, "fake_mcp_server")()),
    "session + local model server": (lambda ctx, h: (), _served_beside),
    "one-shot, Bash tool mid-run": (lambda ctx, h: _allow_sleep(ctx, h) or ("-p", "RC-BASH run the shell"),
                                    lambda ctx, h, t: _shell_up(ctx, h)),
    "session, background Bash job": (lambda ctx, h: _allow_sleep(ctx, h) or (), _typed_bg_job),
}


def serve_alone(ctx) -> dict:
    """`halo local serve <file>` returns at once; it says the server "stops when the last Halo process on this home
    exits", and no other Halo process runs here: 5 s after it returned nothing may be left."""
    h = ctx.home("close")
    r = ctx.run(h, "local", "serve", _gguf(ctx, h), timeout=60)
    row = {"target": "`halo local serve` with no session", "how": "it returned", "top_exit": r.code,
           "said": excerpt(r.out, 160)}
    row["left"] = [f"{p.short(110)} [{p.why}]" for p in ctx.left_after(h, 5.0)]
    ctx.end_leftovers(h)
    return row


TRACE_LINES = 200  # of a row's close trace kept in its evidence (the phases and a stack dump of every thread)


def _noter(path):
    """Writes the check's own keys into the row's close trace, on the same clock as Halo's lines."""
    def note(line: str) -> None:
        try:
            with open(path, "a", encoding="utf-8") as fh:
                fh.write(f"{time.time():.3f} {line}\n")
        except OSError:
            pass
    return note


def leftover_evidence(trace_path, shown: str) -> dict:
    """fx jb12: what a row that left something running carries, so a CI run names the cause: the close trace Halo
    wrote under HALO_CLOSE_TRACE (its phases, the check's keys, the keys its console read under HALO_INPUT_TRACE, and
    every thread's stack when the close was still running 4 s on) and the last screen of its terminal (the final 600
    characters, control sequences stripped). No trace line at all says Halo never saw a key of the way out."""
    try:
        lines = [ln for ln in open(trace_path, encoding="utf-8", errors="replace").read().splitlines() if ln.strip()]
    except OSError:
        lines = []
    return {"close_trace": lines[-TRACE_LINES:], "last_screen": excerpt(shown, 600)}


def _detail(row: dict) -> str:
    """The row's one-line detail: its last trace line and the end of its last screen (a row that left nothing: '')."""
    if "last_screen" not in row:
        return ""
    phases = [ln for ln in row.get("close_trace") or [] if " mono=" in ln]  # Halo's own lines, not keys or stacks
    last = phases[-1][:160] if phases else "no line: Halo wrote no phase"
    return f" [trace: {last}; screen: {row['last_screen'][-160:]}]"


def _end(ctx, t, how: str, full_screen: bool, note=None) -> str:
    if how == "closed terminal":
        t.close_window()
        return "terminal closed"
    if how == "hard kill":
        t.hard_kill()
        return "top process killed"
    if full_screen:  # a full-screen session reads Ctrl+C as a key, typed like any other
        return screen.quit_with_ctrl_c(t, wait=0.5, note=note)
    probe = ctx.ctrl_c()
    if not probe["delivered"]:  # said, never passed off as a Ctrl+C
        t.ctrl_break()
        return "Ctrl+Break (Ctrl+C is not deliverable on this host)"
    press = (lambda: t.console_event(0)) if probe["via"] == "console event" else t.ctrl_c
    label = "Ctrl+C" + (" (as the console's event)" if probe["via"] == "console event" else "")
    press()
    keys = label
    if t.wait(2.0) is None:  # still up: a person presses it again
        press()
        keys += " " + label
    return keys


def one_close(ctx, target: str, how: str) -> dict:
    prep, ready = TARGETS[target]
    h = ctx.home("close")
    ctx.provider.rearm()
    args = prep(ctx, h)
    trace = h.dir / "close-trace.txt"  # fx jb12: Halo's way out, step by step, for a row that leaves something
    t = ctx.terminal(h, *args, env=ctx.env(h, HALO_CLOSE_TRACE=str(trace), HALO_INPUT_TRACE=str(trace)))
    row: dict = {"target": target, "how": how}
    up = None
    end = time.monotonic() + 45
    while time.monotonic() < end and t.poll() is None:
        try:
            up = ready(ctx, h, t)
        except Exception:
            up = None
        if up:
            break
        time.sleep(0.2)
    row["ready_s"] = round(time.monotonic() - t.started_at, 1)
    if not up:
        row["not_started"] = excerpt(t.plain(), 240) or f"exit {t.poll()}"
    else:
        row["running"] = len(ctx.ours(h))
        row["keys"] = _end(ctx, t, how, full_screen=target.startswith("session"), note=_noter(trace))
        if row["keys"].startswith("Ctrl+Break"):
            row["how"] = "Ctrl+Break (Ctrl+C not deliverable on this host)"
        left = ctx.left_after(h, 5.0)
        row["top_exit"] = t.poll()
        row["left"] = [f"{p.short(110)} [{p.why}]" for p in left]
        if left:  # slow, or never? what was left at 5 s is followed to 30 s
            later = ctx.left_after(h, 25.0)
            row["gone_after_s"] = None if later else "between 5 and 30 s"
            row["still_running_at_30_s"] = [p.short(90) for p in later]
            row.update(leftover_evidence(trace, t.plain()))
    ctx.provider.release()
    t.cleanup()
    ctx.end_leftovers(h)
    return row


def _programs(left: list) -> str:
    """Every distinct program in a row's leftovers ("pid N (name) ..."), with how many of each: the first alone hid the
    rest (16 msedge.exe in front of anything of Halo's)."""
    names: dict = {}
    for line in left:
        m = re.match(r"pid \d+ \(([^)]*)\)", line)
        name = m.group(1) if m else "?"
        names[name] = names.get(name, 0) + 1
    return ", ".join(f"{n} x{c}" if c > 1 else n for n, c in names.items())


def closing(ctx):
    rows = [one_close(ctx, target, how) for target in TARGETS for how in HOW] + [serve_alone(ctx)]
    left = [r for r in rows if r.get("left")]
    unstarted = [r for r in rows if "not_started" in r]
    probe = ctx.ctrl_c()
    ev = {"rows": rows, "ctrl_c_on_this_host": probe}
    bad = [f"{r['target']} / {r['how']}: {len(r['left'])} left, {_programs(r['left'])} ({r['left'][0][:90]})"
           f"{_detail(r)}" for r in left]
    bad += [f"{r['target']} did not come up to be closed ({r['not_started'][:100]})" for r in unstarted]
    note = ("" if probe["delivered"] else f"Ctrl+C is not deliverable on this host ({probe['why']}); the one-shot, init "
            f"and studio rows sent Ctrl+Break instead (it {'ended' if probe['break_works'] else 'did not reach'} a test child). ")
    if bad:
        raise Fail(note + f"{len(left)} of {len(rows)} ways out left processes running 5 s later: " + "; ".join(bad), ev)
    return f"all {len(rows)} ways out ({len(TARGETS)} launches x {len(HOW)}, + `halo local serve`) left nothing", ev


def _studio_pid(h, timeout: float = 15.0) -> int:
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        try:
            return int(json.loads((h.state / "studio.json").read_text(encoding="utf-8"))["pid"])
        except (OSError, ValueError, KeyError, TypeError):
            time.sleep(0.1)
    return 0


def no_reuse(ctx):
    from realcheck import procs
    h = ctx.home("no-reuse")
    first = ctx.terminal(h, "init")
    url, at, meanwhile = wait_address(ctx, h, first, 60)
    if not url:
        ctx.end_leftovers(h)
        raise Fail(f"the first `halo init` printed no address in {at:.0f} s: " + excerpt(first.plain(), 200),
                   {"while_waiting": meanwhile})
    a = _studio_pid(h)
    screen.quit_with_ctrl_c(first)
    first.cleanup()
    a_alive = bool(a) and procs.alive(a)
    launched = time.time()
    second = ctx.terminal(h, "init")
    wait_address(ctx, h, second, 60)
    b = _studio_pid(h)
    b_started = procs.started_at(b) if b else 0.0
    ev = {"first_studio": a, "first_alive_after_ctrl_c": a_alive, "second_studio": b,
          "second_started_after_launch_s": round(b_started - launched, 2) if b_started else None,
          "second_screen": excerpt(second.plain(), 240)}
    screen.quit_with_ctrl_c(second)
    second.cleanup()
    ctx.end_leftovers(h)
    if not b:
        raise Fail("the second `halo init` has no Studio (no studio.json)", ev)
    if b == a or (b_started and b_started < launched - 1):
        raise Fail(f"the second `halo init` attached to the Studio from before (pid {b}, started "
                   f"{launched - b_started:.0f}s before the launch) instead of starting its own", ev)
    return f"the second `halo init` started its own Studio (pid {b}, {b_started - launched:.1f}s after it)", ev


# 3.6.0.14 K2: the page's live interval timers, wrapped before the page loads (installed first, before steps_map.HOOK,
# which sets none); COUNT is the periods of those still running (their number is the count)
INTERVALS = """(() => { if (window.__rci) return; const si = window.setInterval, ci = window.clearInterval, live = new Map(); window.__rci = live;
  window.setInterval = function (fn, ms, ...a) { const id = si.call(window, fn, ms, ...a); live.set(id, Number(ms) || 0); return id; };
  window.clearInterval = function (id) { live.delete(id); return ci.call(window, id); }; })();"""
COUNT = "window.__rci ? [...window.__rci.values()] : null"
# The interval timers Agents -> Live adds to the page (count B - count A), measured on the Linux VM on exports of the
# released 3.6.0.12 (before 3.6.0.13's drawing) with this step copied over, and checked equal on 3.6.0.13 and on
# 3.6.0.14's tree, three runs each: two timers of 1000 ms every time (A: 500, 1000, 6000, 15000 ms on Session). Pinned:
# a higher count is a timer added; never raise it to make the step pass.
LIVE_INTERVALS = 2
IDLE_WAIT_S = 60.0 if sys.platform == "win32" else 30.0
LIVE_DONE = "[data-testid=live-group] [data-member][data-state=done]"  # 3.6.0.12 and 3.6.0.13 both draw data-state


def _timers(n: int) -> str:
    return f"{n} interval timer{'' if n == 1 else 's'}"


def judge_idle(share: float, counts: dict, live_added: int = LIVE_INTERVALS, seconds: float = 60.0) -> list:
    """What a person saw of the idle minute ([] when right): the share of one core against 5%, and the page's live
    interval timers -- A before Live, B with Live, C with the box open, D closed, E after the minute (a list of periods
    or a number each; None when the hook could not count)."""
    bad = []
    if share >= 0.05:
        bad.append(f"an idle Studio with Agents -> Live open used {share:.1%} of one core over {seconds:.0f}s (budget 5%)")
    n = {k: (len(v) if isinstance(v, (list, tuple)) else v) for k, v in (counts or {}).items()}
    if any(n.get(k) is None for k in "ABCDE"):
        return bad + ["the page's timers could not be counted"]
    a, b, c, d, e = (n[k] for k in "ABCDE")
    if c != b:
        bad.append(f"the open sheet added {_timers(c - b)}")
    if d != b:
        bad.append(f"the closed sheet left {_timers(d - b)}")
    if e != b:
        bad.append(f"the idle minute ended with {_timers(e - b)} more")
    if b - a != live_added:
        bad.append(f"Agents -> Live added {_timers(b - a)}; before the drawing it added {live_added}")
    return bad


def _idle_page(ctx, h, c, url: str, counts: dict, ev: dict):
    """The page on Studio's address (Session), a session on Auto in a second terminal that hands one piece of work out, Agents ->
    Live, the helper's box opened in place and closed, the pointer off the drawing; the counts A-D as they are read
    (into `counts`, kept in the evidence at once). The session's terminal; raises Fail with what a person saw."""
    from realcheck import fakes
    from realcheck.steps_map import _away
    from realcheck.steps_map import ROW, _followed, _say, _started, alt

    def wait(expr: str) -> bool:
        try:
            return bool(c.wait(expr, IDLE_WAIT_S))
        except TimeoutError:
            return False
    from realcheck.core import split_url
    base, token = split_url(url)
    c.go(f"{base}/?mode=session&tour=off#t={token}")  # Session (a fresh home's bare address opens Setup: no section keys)
    s = ctx.terminal(h, cols=200, rows=50)  # bare `halo`: Auto, in the same home and project
    ev["_session"] = s
    if not screen.tui_ready(s, 60):
        raise Fail("the terminal session never showed its status line in 60 s: " + excerpt(s.plain(), 200), ev)
    bad: list = []
    if not _followed(c, ev, bad, _started(h)):
        raise Fail(bad[0], ev)
    # the session's row on the page first, as session-map does: a line typed a tenth of a second after the status line
    # first showed was not taken once on Windows (it stayed in the box and the turn never began)
    if not wait(ROW):
        raise Fail(f"Session never drew the session's row in {IDLE_WAIT_S:.0f} s (the session was not asked)", ev)
    _say(s, "RC-PACK agent=researcher")  # one Agent spawn: on Auto one group, then PACK_DONE
    if not s.wait_for(lambda x: fakes.PACK_DONE in x, IDLE_WAIT_S):
        raise Fail(f"the session's turn never ended in {IDLE_WAIT_S:.0f} s: " + excerpt(s.plain(), 200), ev)
    if not wait(ROW):  # count A is read off Session with the session's row drawn, never off another page state
        raise Fail(f"Session never drew the session's row in {IDLE_WAIT_S:.0f} s (count A not read)", ev)
    counts["A"] = c.js(COUNT)
    alt(c, 2)  # Agents opens on 4 · Live while a session runs
    if not wait(f"!!document.querySelector('{LIVE_DONE}')"):
        ev["page"] = c.js("({at: location.search, live: !!document.querySelector('[data-testid=agents-live]'), shown: [...document."
                          "querySelectorAll('[data-testid=agents-live], [data-testid=session-lit-map]')].map((e) => e.offsetParent !== null),"
                          " groups: document.querySelectorAll('[data-testid=live-group]').length, members: [...document.querySelectorAll("
                          "'[data-member]')].map((m) => m.dataset.state)})")
        raise Fail(f"Agents -> Live never drew the helper that ended in {IDLE_WAIT_S:.0f} s", ev)
    counts["B"] = c.js(COUNT)
    if _away(c, "live")["over"]:
        raise Fail("the pointer at (2, 400) is over the drawing: the minute would not be idle", ev)
    c.click_on(f"document.querySelector('{LIVE_DONE}')")
    if not wait("!!document.querySelector('[data-testid=map-step-in][data-open]')"):
        raise Fail(f"the helper's box never opened in place in {IDLE_WAIT_S:.0f} s", ev)
    counts["C"] = c.js(COUNT)
    c.key("Escape")
    if not wait("!document.querySelector('.mp-step-in')"):
        raise Fail(f"Escape never closed the helper's box in {IDLE_WAIT_S:.0f} s", ev)
    counts["D"] = c.js(COUNT)
    if _away(c, "live")["over"]:
        raise Fail("the pointer at (2, 400) is over the drawing: the minute would not be idle", ev)
    return s


def idle_cpu(ctx, seconds: float = 60.0):
    from tests.helpers.chrome_driver import open_chrome
    from realcheck.steps_map import HOOK
    exe = browser(ctx)  # first: --browser none is a SKIP before any halo starts
    h = ctx.home("idle")
    t = ctx.terminal(h, "studio")
    url, at, meanwhile = wait_address(ctx, h, t, 60)
    if not url:
        ctx.end_leftovers(h)
        raise Fail(f"`halo studio` printed no address in {at:.0f} s: " + excerpt(t.plain(), 200),
                   {"while_waiting": meanwhile})
    counts: dict = {}
    ev: dict = {"address_s": round(at, 1), "while_waiting": meanwhile, "timers": counts}
    c = s = None
    try:
        c = open_chrome(1440, 900, exe=exe)
        if c is None:
            raise Fail("no Chrome opened (" + str(exe) + ")", ev)
        c.call("Emulation.setDeviceMetricsOverride", width=1440, height=900, deviceScaleFactor=1, mobile=False)
        c.call("Page.enable")
        for src in (INTERVALS, HOOK):  # before the first load: every timer the page sets is counted
            c.call("Page.addScriptToEvaluateOnNewDocument", source=src)
        try:
            s = _idle_page(ctx, h, c, url, counts, ev)
        finally:
            s = ev.pop("_session", s)
        before = {p.pid: p for p in ctx.ours(h).values()}
        time.sleep(seconds)  # the idle minute: nobody touches the page or the terminal
        after = {p.pid: p for p in ctx.ours(h).values()}
        counts["E"] = c.js(COUNT)
    finally:
        if c is not None:
            c.close()
        for term in (s, t):
            if term is not None:
                screen.quit_with_ctrl_c(term)
                term.cleanup()
        ctx.end_leftovers(h)
    used, per, studio, session = 0.0, {}, 0.0, 0.0
    for pid, p in after.items():
        if p.cpu < 0:
            continue
        d = p.cpu - (before[pid].cpu if pid in before and before[pid].cpu >= 0 else 0.0)
        per[p.short(70)] = round(d, 2)
        used += d
        if "studio" in p.cmdline:
            studio += d
        else:
            session += d
    share = used / seconds
    ev.update(cpu_seconds=round(used, 2), studio_cpu_s=round(studio, 2), session_cpu_s=round(session, 2),
              share_of_one_core=round(share, 4), processes=per)
    if not after:
        raise Fail("no Halo process was found to measure (the scan saw none under the home)", ev)
    bad = judge_idle(share, counts, LIVE_INTERVALS, seconds)
    if bad:
        raise Fail("; ".join(bad), ev)
    b = len(counts["B"])
    return (f"{share:.1%} of one core over {seconds:.0f}s with Agents -> Live open on a session on Auto; {b} interval "
            "timers, as before"), ev
