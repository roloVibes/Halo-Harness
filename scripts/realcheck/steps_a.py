"""scripts/realcheck/steps_a.py -- steps 1 to 5: it starts, the first run, the theme you pick, one question, a real
turn of work. Each returns (one line, evidence) or raises Fail / Skip."""
from __future__ import annotations

import json
import re
import time
from pathlib import Path

from realcheck import fakes, screen
from realcheck.core import Fail, excerpt, http_get, split_url, wait_address, wait_until

# 3.6.0.0 R11, measured on the day (bd984ce6): the bytes of the one request `halo -p "<one line>"` sends in a fresh
# home (Windows carries the PowerShell tool). The budget is that + 10%; a change that makes a one-line ask cost more
# fails here and says by how much. macOS was not measured: it takes the Linux number until a run says otherwise.
REQUEST_BYTES = {"win32": 49847, "linux": 48565, "darwin": 48565}
# how long `halo init` has, after its address, to hand the page to the browser it was given (BROWSER)
BROWSER_WAIT_S = 10.0


def _no_leftovers(ctx, h, what: str) -> None:
    left = ctx.left_after(h, 5.0)
    if left:
        said = ctx.end_leftovers(h)
        raise Fail(f"{what} ended but {len(left)} process(es) it started still run 5 s later: "
                   + "; ".join(p.short(90) for p in left[:3]), {"left": said})


def _registry_commands(repo: Path) -> "tuple[set, set]":
    """3.6.0.0 R16: (the commands halo_harness/cli_commands.py registers for `halo --help`, the ones it leaves out on
    purpose: internal and retired), read from the file's `_c(...)` rows without importing it."""
    import ast
    path = repo / "halo_harness" / "cli_commands.py"
    if not path.is_file():
        return set(), set()
    listed, left_out = set(), set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "_c" and node.args
                and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str)):
            continue
        kind = next((k.value.value for k in node.keywords if k.arg == "kind" and isinstance(k.value, ast.Constant)), "")
        if len(node.args) > 4 and isinstance(node.args[4], ast.Constant):
            kind = node.args[4].value
        (left_out if kind else listed).add(node.args[0].value)
    return listed, left_out


def _commands_in_source(repo: Path) -> "tuple[list, list]":
    """(every top-level verb halo runs -- the registry's listed commands and any verb cli.py still dispatches itself --,
    the ones that only say where a verb went or are left out of the help on purpose)."""
    src = (repo / "halo_harness" / "cli.py").read_text(encoding="utf-8")
    listed, left_out = _registry_commands(repo)
    verbs = set(re.findall(r'argv\[0\] == "([a-z][\w-]*)"', src)) | listed
    for group in re.findall(r"argv\[0\] in \(([^)]*)\)", src):
        verbs.update(re.findall(r'"([a-z][\w-]*)"', group))
    verbs.update(re.findall(r'argv\[:2\] == \["([a-z][\w-]*)"', src))
    gone = set(re.findall(r'^\s+"([a-z][\w-]*)": "', src.split("GONE_VERBS = {", 1)[1].split("}", 1)[0], re.M))
    moved = set(re.findall(r'argv\[0\] == "([a-z][\w-]*)":[^\n]*\n(?:[^\n]*\n){0,2}[^\n]*moved_line\(', src))
    return sorted(verbs - gone - moved - left_out), sorted(gone | moved | left_out)


def starts(ctx):
    h = ctx.home("starts")
    v = ctx.run(h, "--version", timeout=30)
    hp = ctx.run(h, "--help", timeout=30)
    ev = {"version_s": round(v.seconds, 2), "help_s": round(hp.seconds, 2), "version": excerpt(v.out, 80)}
    bad = []
    if v.code != 0 or "halo " not in v.out:
        bad.append(f"`halo --version` exit {v.code}: {excerpt(v.out + v.err, 160)}")
    if hp.code != 0:
        bad.append(f"`halo --help` exit {hp.code}: {excerpt(hp.err, 160)}")
    for what, ran in (("--version", v), ("--help", hp)):
        if ran.seconds > 2.0:
            bad.append(f"`halo {what}` took {ran.seconds:.1f}s (budget 2 s)")
    verbs, skipped = _commands_in_source(ctx.repo)
    text = re.sub(r"\s+", " ", hp.out)
    missing = [w for w in verbs if not re.search(rf"(?<![\w-]){re.escape(w)}(?![\w-])", text)]
    ev.update(commands=len(verbs), not_in_help=missing, not_counted=skipped)
    if not verbs:  # the scan found nothing to look for: "names all 0 commands" would pass whatever the help says
        bad.append("found no command in halo_harness/cli_commands.py or cli.py to look for in `halo --help`")
    if missing:
        bad.append(f"`halo --help` does not name {len(missing)} of the {len(verbs)} commands halo runs: "
                   + ", ".join(missing))
    _no_leftovers(ctx, h, "`halo --version` / `--help`")
    if bad:
        raise Fail("; ".join(bad), ev)
    return f"--version {v.seconds:.1f}s, --help {hp.seconds:.1f}s names all {len(verbs)} commands", ev


def tui_first_frame(ctx, h, env=None) -> dict:
    """Bare `halo` in a terminal: when its first frame was up, the palette it drew, how a person leaves it."""
    t = ctx.terminal(h, env=env)
    up = screen.tui_ready(t, 30)
    time.sleep(0.5)
    raw = t.raw()
    out = {"ready_s": round(up, 2), **screen.palette_of(raw), "beeps": screen.beeps(raw),
           "traceback": screen.TRACEBACK in t.plain()}
    out["quit_keys"] = screen.quit_with_ctrl_c(t)
    out["exit"] = t.poll()
    if not up:
        out["screen"] = excerpt(t.plain(), 400)
    t.cleanup()
    return out


def first_run(ctx):
    h = ctx.home("first-run")
    t = ctx.terminal(h, "init")
    url, at, meanwhile = wait_address(ctx, h, t, 60)
    ev: dict = {"address_s": round(at, 2), "while_waiting": meanwhile}
    bad: list = []
    if not url:
        ev["screen"] = excerpt(t.plain(), 500)
        ctx.end_leftovers(h)
        raise Fail(f"`halo init` printed no Studio address in {at:.0f} s: " + excerpt(t.plain(), 200), ev)
    if at > 2.0:
        bad.append(f"the Studio address took {at:.1f}s to appear (budget 2 s)")
    base, token = split_url(url)
    # the page must reach the browser Halo was given: an empty list here once passed while a real browser opened
    ours = lambda: [u for u in fakes.opened_urls(h.opened) if split_url(u)[0] == base]  # noqa: E731
    wait_until(ours, BROWSER_WAIT_S)
    ev["browser_opened"] = fakes.opened_urls(h.opened)
    if not ours():
        bad.append(f"`halo init` did not open its page ({base}) in the browser it was given (BROWSER) within "
                   f"{BROWSER_WAIT_S:.0f} s; that browser was asked to open {ev['browser_opened'] or 'nothing'}")
    status, page, s = http_get(base + "/", timeout=10)
    ev.update(page_status=status, page_s=round(s, 2), page_theme=screen.page_theme(page))
    if status != 200 or s > 2.0:
        bad.append(f"the page answered {status} in {s:.1f}s (budget 2 s)")
    st, body, s2 = http_get(base + "/api/setup/state", token, timeout=30)
    ev.update(setup_state_status=st, setup_state_s=round(s2, 2))
    if st != 200 or s2 > 5.0:
        bad.append(f"Setup's first read (GET /api/setup/state) answered {st} in {s2:.1f}s (budget 5 s)")
    if ev["page_theme"] != "instrument":
        bad.append(f"a fresh home's page draws {ev['page_theme'] or 'no theme'}, not instrument")
    time.sleep(0.5)
    raw = t.raw()
    ev["init_beeps"] = screen.beeps(raw)
    if screen.TRACEBACK in t.plain():
        bad.append("`halo init` printed a traceback: " + excerpt(t.plain()[t.plain().find(screen.TRACEBACK):], 200))
    screen.quit_with_ctrl_c(t)
    t.cleanup()
    ctx.end_leftovers(h)  # what Ctrl+C leaves behind is step 10's to judge
    # the terminal's theme in a fresh home: bare `halo`'s first frame, on a truecolor terminal and on one without
    tui = tui_first_frame(ctx, ctx.home("first-run-tui"))
    h3 = ctx.home("first-run-ansi")
    ansi = tui_first_frame(ctx, h3, env=ctx.env(h3, COLORTERM=None))
    ev.update(tui=tui, tui_ansi=ansi)
    ctx.end_leftovers(None)
    if not tui["ready_s"]:
        bad.append("bare `halo` in a fresh home showed no status line in 30 s: " + tui.get("screen", "")[:160])
    elif tui["theme"] != "instrument":
        bad.append(f"bare `halo` in a fresh home draws {tui['theme'] or 'no known palette'} "
                   f"(backgrounds {tui['top_bg']}), not instrument")
    if not ansi["ready_s"]:
        bad.append("bare `halo` on a terminal without truecolor showed no status line in 30 s: "
                   + ansi.get("screen", "")[:160])
    elif "instrument-ansi" not in ansi["themes"]:  # 256-colour numbers, or (Windows consoles) the 16 colours as 24-bit
        bad.append(f"on a terminal without truecolor a fresh home draws {ansi['theme'] or 'no known palette'} "
                   f"(backgrounds {ansi['top_bg']}), not instrument-ansi")
    rings = [(w, d["beeps"]["bare"] if "beeps" in d else d["bare"]) for w, d in
             (("halo init", ev["init_beeps"]), ("halo", tui), ("halo (no truecolor)", ansi))]
    rings = [(w, n) for w, n in rings if n]
    if rings:
        bad.append("the terminal beeps (BEL, 0x07): " + ", ".join(f"{w} wrote {n}" for w, n in rings))
    for w, d in (("halo", tui), ("halo (no truecolor)", ansi)):
        if d.get("traceback"):
            bad.append(f"{w} printed a traceback")
    if bad:
        raise Fail("; ".join(bad), ev)
    return (f"address {at:.1f}s, page {s:.1f}s, Setup's read {s2:.1f}s, instrument in the terminal and the page, "
            f"no beep"), ev


CLAUDE_CODE_THEME = "claude-dark"  # a theme left in Claude Code's settings: the pick made in Halo must beat it


def theme_pick(ctx):
    h = ctx.home("theme")
    # 3.5.0.1: a `theme` in Claude Code's settings beat the one picked in Halo. A home without such a theme cannot
    # show that, so this one has one, of the other posture than the pick (paper is light, claude-dark is dark).
    cc = h.home / ".claude" / "settings.json"
    cc.parent.mkdir(parents=True, exist_ok=True)
    cc.write_text(json.dumps({"theme": CLAUDE_CODE_THEME}), encoding="utf-8")
    r = ctx.run(h, "config", "set", "theme", "paper", timeout=30)
    if r.code != 0:
        raise Fail(f"`halo config set theme paper` exit {r.code}: {excerpt(r.out + r.err, 200)}")
    tui = tui_first_frame(ctx, h)
    # a pick is drawn as picked on a terminal without truecolor too (the terminal downgrades its colours; only an
    # unset theme falls back to the -ansi sibling)
    ansi = tui_first_frame(ctx, h, env=ctx.env(h, COLORTERM=None))
    t = ctx.terminal(h, "studio")
    url, at, meanwhile = wait_address(ctx, h, t, 60)
    page = http_get(split_url(url)[0] + "/", timeout=10)[1] if url else b""
    ev = {"claude_code_theme": CLAUDE_CODE_THEME, "tui": tui, "tui_ansi": ansi, "page_theme": screen.page_theme(page),
          "studio_address_s": round(at, 1), "while_waiting": meanwhile}
    screen.quit_with_ctrl_c(t)
    t.cleanup()
    ctx.end_leftovers(h)
    bad = []
    for where, d in (("the terminal", tui), ("the terminal without truecolor", ansi)):
        if not d["ready_s"]:
            bad.append(f"{where} showed no status line in 30 s: " + d.get("screen", "")[:160])
        elif "paper" not in d["themes"]:
            bad.append(f"after `halo config set theme paper` (Claude Code's settings say {CLAUDE_CODE_THEME}) {where} "
                       f"draws {', '.join(d['themes']) or 'no known palette'} (backgrounds {d['top_bg']})")
    if ev["page_theme"] != "paper":
        bad.append(f"Studio's page draws {ev['page_theme'] or 'nothing'}, not the picked paper"
                   + ("" if url else f" (`halo studio` printed no address in {at:.0f} s)"))
    if bad:
        raise Fail("; ".join(bad), ev)
    return (f"paper (picked; Claude Code's settings say {CLAUDE_CODE_THEME}) in the terminal's first frame, "
            "with and without truecolor, and in the page"), ev


def question(ctx):
    h = ctx.home("question")
    r = ctx.run(h, "-p", "RC-ASK: answer in one word", timeout=60)
    reqs = ctx.provider.requests_with("RC-ASK")
    size = ctx.provider.size_of(reqs[0]) if reqs else 0
    import sys
    budget = int(REQUEST_BYTES.get(sys.platform, REQUEST_BYTES["linux"]) * 1.10)
    ev = {"exit": r.code, "seconds": round(r.seconds, 2), "request_bytes": size, "budget_bytes": budget,
          "requests": len(reqs), "stdout": excerpt(r.out, 120)}
    bad = []
    if r.code != 0 or fakes.ANSWER not in r.out:
        bad.append(f"`halo -p` exit {r.code}, printed {excerpt(r.out, 100)!r}, stderr {excerpt(r.err, 160)!r}")
    if r.seconds > 5.0:
        bad.append(f"the answer took {r.seconds:.1f}s (budget 5 s)")
    if size > budget:
        bad.append(f"the one request was {size:,} bytes (budget {budget:,})")
    if screen.TRACEBACK in r.err:
        bad.append("stderr has a traceback: " + excerpt(r.err, 200))
    _no_leftovers(ctx, h, "`halo -p`")
    if bad:
        raise Fail("; ".join(bad), ev)
    return f"answered in {r.seconds:.1f}s, request {size:,} bytes (budget {budget:,})", ev


def _session_tools(h) -> dict:
    """{tool name: [ok?]} from the session logs under the home (every *.jsonl a session wrote)."""
    seen: dict = {}
    for f in (h.state / "sessions").rglob("*.jsonl") if (h.state / "sessions").exists() else []:
        for line in f.read_text(encoding="utf-8", errors="replace").splitlines():
            for m in re.finditer(r'"type": ?"tool_use"[^{}]*?"name": ?"(\w+)"', line):
                seen.setdefault(m.group(1), []).append(f.name)
    return seen


def real_turn(ctx):
    h = ctx.home("turn")
    notes = h.proj / "notes-realcheck.txt"
    notes.write_text("realcheck notes: the number is 7\n", encoding="utf-8")
    wf = ctx.run(h, "workflows", "new", "rc-flow", "--from", "research", timeout=30)
    if wf.code != 0:
        raise Fail(f"`halo workflows new rc-flow --from research` exit {wf.code}: {excerpt(wf.out + wf.err, 200)}")
    ev: dict = {}
    bad: list = []
    first = _turn(ctx, h, f"RC-WORK file={notes} wf=rc-flow", ev, "default")
    refused = [x for x in first if "Permission denied" in x]
    if refused:  # what the refusal suggests, the way a person reads it and runs again
        bad.append("in the default permission mode `halo -p` refuses a tool the model called: " + refused[0][-150:])
        first = _turn(ctx, h, f"RC-WORK file={notes} wf=rc-flow again", ev, "allowed", "--allowedTools", "Workflow")
    if not any("the number is 7" in x for x in first):
        bad.append("the Read of a project file did not come back with its text")
    subs = ev["allowed_sub_calls" if refused else "default_sub_calls"]
    if subs < 2:
        bad.append(f"the sub-agent and the workflow's step reached the model {subs} time(s), not 2 or more")
    tools = _session_tools(h)
    ev["logged_tools"] = sorted(tools)
    for name in ("Read", "Agent", "Workflow"):
        if name not in tools:
            bad.append(f"the session's log has no {name} call")
    errs = [x for x in first if re.search(r"Permission denied|\berror\b|Traceback", x, re.I)]
    if errs:
        bad.append("a tool answered with an error: " + errs[0][-200:])
    for k in [k for k in ev if k.endswith("_exit")]:
        if ev[k] != 0:
            bad.append(f"`halo -p` ({k[:-5]}) exit {ev[k]}: {ev.get(k[:-5] + '_stderr', '')}")
    _no_leftovers(ctx, h, "the turn")
    if bad:
        raise Fail("; ".join(bad), ev)
    return f"Read, a sub-agent and the Workflow tool ran; {ev['default_seconds']}s", ev


def _turn(ctx, h, prompt: str, ev: dict, tag: str, *flags: str) -> list:
    """One `halo -p` of the work turn; the tool results the model saw come back (the last request's tool messages)."""
    before = len(ctx.provider.requests_with("RC-SUB: answer"))
    r = ctx.run(h, *flags, "-p", prompt, timeout=180)
    works = ctx.provider.requests_with(prompt)
    results = []
    for m in (works[-1].get("body") or {}).get("messages") or [] if works else []:
        if isinstance(m, dict) and m.get("role") == "tool":
            results.append(excerpt(fakes._text(m.get("content")), 240))
    ev.update({f"{tag}_exit": r.code, f"{tag}_seconds": round(r.seconds, 2), f"{tag}_results": results,
               f"{tag}_model_calls": len(works), f"{tag}_stdout": excerpt(r.out, 120), f"{tag}_stderr": excerpt(r.err, 200),
               f"{tag}_sub_calls": len(ctx.provider.requests_with("RC-SUB: answer")) - before})
    if fakes.WORK_DONE not in r.out:
        ev[f"{tag}_exit"] = r.code if r.code else -1
    return results
