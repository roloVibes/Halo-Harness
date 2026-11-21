"""scripts/realcheck.py -- Halo driven the way a person drives it (3.6.0.0 R11).

    python scripts/realcheck.py [--only STEP ...] [--list] [--json FILE] [--summary FILE] [--real-local REF]
                                [--keep] [--installed] [--browser PATH|NAME|none] [--name-the-end]

Every bug the owner hit in one week (a launch that spins, a Studio left running overnight, a beep at start, a theme
that did not apply, an update that broke the install, a helper burning a core) passed thousands of unit tests. This
starts the real `halo` -- this checkout (`python -m halo_harness`), or with --installed the `halo` on PATH -- as
separate processes, in a terminal of their own where a person would have one, in a scratch home and project, and
judges what a person would see: did it start, how long it took, what the terminal printed, does the page answer,
did the thing asked for happen, and is anything left running afterwards. Model calls go to a fake provider on
127.0.0.1 (no key, no cost); `--real-local ol:<model>@<http://host:port>` uses a real Ollama for step 8's model calls.

One line per step: name, PASS / FAIL / SKIP, seconds, and on FAIL what a person would have seen. Exit 0 only when no
step failed. Each step has a time budget; over it is a FAIL that says the time. A failed step does not stop the rest.

It never touches the real home: everything it starts runs under a scratch folder, the process scan matches only that
folder's path (in a command line or an environment) or Halo's HALO_OWNER marker carried by one of those, and it ends
only processes that scan found. No kill by name. OLLAMA_HOST is a dead loopback port unless step 8 gives its fake.
docs/DEVELOPMENT.md ("realcheck") says how to read it."""
from __future__ import annotations

import argparse
import faulthandler
import os
import shutil
import sys
import tempfile
import time
import traceback
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
for _p in (str(REPO / "scripts"), str(REPO)):
    if _p not in sys.path:
        sys.path.insert(0, _p)
os.environ["OLLAMA_HOST"] = "http://127.0.0.1:9"  # this process too: nothing here may reach a real Ollama

from realcheck.report import FAIL, PASS, SKIP, Result, markdown, run_info, to_json  # noqa: E402


def _steps() -> list:
    """(name, budget seconds, what it checks, the function)."""
    from realcheck import steps_a as A, steps_b as B, steps_c as C, steps_close as Z, steps_map as M, steps_prompt as P
    from realcheck import steps_auto as S, steps_browser as W, steps_copy as K
    return [
        ("starts", 20, "`halo --version` and `--help` answer in 2 s; --help names every command", A.starts),
        ("first-run", 120, "`halo init` in a fresh home: address, page, Setup's read, no beep, instrument", A.first_run),
        ("theme", 90, "a theme set with `halo config set theme` is the one the terminal and the page draw", A.theme_pick),
        ("question", 30, "`halo -p` gets the answer in 5 s; the request's size is in budget", A.question),
        ("turn", 120, "a real turn: Read, a sub-agent and the Workflow tool, from the session's own log", A.real_turn),
        ("copy-drag", 120 if sys.platform == "win32" else 60, "a drag over words of an earlier answer in a terminal "
         "session copies those words on release (each time) and on Ctrl+C; Ctrl+C with nothing selected the last answer",
         K.copy_drag),
        ("studio", 300, "Studio walked through in headless Chrome: each section loads, holds still, a prompt", B.studio),
        ("prompt", 120, "one prompt in two views: Studio's sends show once in a terminal session, /model, an ask "
         "answered in Studio, no user or host name, follows after /clear", P.prompt),
        ("session-map", 180 if sys.platform == "win32" else 120, "the owner's sentence: a workflow built in a terminal "
         "session shows at once in Studio's Live drawer, down, marked; Agents opens on Live", M.session_map),
        ("auto-groups", 150 if sys.platform == "win32" else 90, "Auto's own groups: five replies of a real session "
         "drawn as four named, coloured groups in Session and in Agents -> Live; /status says Auto; nothing left",
         S.auto_groups),
        ("auto-ready-lines", 180 if sys.platform == "win32" else 120, "a build on Auto says what is ready: the card "
         "makes no map, the folded card and Studio's head say ready now and saved for the next session, crew.map "
         "unchanged; 'use it now' draws the workflow as a group", S.auto_ready_lines),
        ("browser", 180 if sys.platform == "win32" else 120, "the built-in Browser tool: a real `halo -p` opens a real page "
         "in this system's browser, presses its button, takes its picture; no listener; nothing left after a normal "
         "and a hard end", W.browser),
        ("packs", 120, "the shipped doc-review pack installs, is listed, and its agent takes work by name", C.packs),
        ("local", 120, "`halo local ps|warm|unload` on another machine's Ollama; one load per one-shot", C.local),
        ("update", 90, "`halo update --check` online and offline, in plain words", C.update),
        ("closing", 900, "Ctrl+C, a closed terminal, a hard kill: nothing Halo started is left 5 s later", Z.closing),
        ("no-reuse", 120, "a second `halo init` starts its own Studio, never one from before", Z.no_reuse),
        ("idle-cpu", 150, "a Studio idle with its page open for 60 s uses under 5% of one core", Z.idle_cpu),
    ]


def main(argv=None) -> int:
    # 3.6.0.9: a fault that ends this process (a stack overflow, a heap fault: seen once as a bare 127 after the last
    # line, on Windows) is said by Python itself, with where each thread was
    faulthandler.enable()
    ap = argparse.ArgumentParser(prog="realcheck", description=__doc__.split("\n\n")[1])
    ap.add_argument("--only", nargs="+", metavar="STEP", help="run these steps only")
    ap.add_argument("--list", action="store_true", help="list the steps and exit")
    ap.add_argument("--json", metavar="FILE", help="write the run as JSON here")
    ap.add_argument("--summary", metavar="FILE", help="append the Markdown table here (CI: $GITHUB_STEP_SUMMARY)")
    ap.add_argument("--real-local", metavar="REF", default="", help="ol:<model>@<http://host:port>: a real Ollama for step 8")
    ap.add_argument("--keep", action="store_true", help="keep the scratch folder (its processes are still ended)")
    ap.add_argument("--installed", action="store_true", help="the `halo` on PATH instead of this checkout")
    ap.add_argument("--name-the-end", action="store_true",
                    help="CI: run the checker as a child and say in one line how it ended when that was not its "
                         "own exit (scripts/realcheck/named_end.py)")
    ap.add_argument("--browser", metavar="PATH|NAME|none", default=None,
                    help="the browser the Studio steps use (headless, a throw-away profile), or `none`: those steps "
                         "SKIP (default: REALCHECK_BROWSER, else HALO_CHROME, else an installed Chrome)")
    args = ap.parse_args(argv)
    steps = _steps()
    if args.list:
        for name, budget, what, _fn in steps:
            print(f"{name:<12} {budget:>4}s  {what}")
        return 0
    names = [s[0] for s in steps]
    unknown = [n for n in args.only or [] if n not in names]
    if unknown:
        print(f"realcheck: no step {', '.join(unknown)} (the steps: {', '.join(names)})", file=sys.stderr)
        return 2
    chosen = [s for s in steps if not args.only or s[0] in args.only]
    results, version = run(chosen, installed=args.installed, real_local=args.real_local, keep=args.keep,
                           browser=args.browser)
    info = run_info(version, "installed" if args.installed else "checkout")
    if args.json:
        Path(args.json).write_text(to_json(results, info), encoding="utf-8")
    if args.summary:
        with open(args.summary, "a", encoding="utf-8") as f:
            f.write(markdown(results, info))
    failed = [r for r in results if r.status == FAIL]
    print(f"realcheck: {sum(r.status == PASS for r in results)} passed, {len(failed)} failed, "
          f"{sum(r.status == SKIP for r in results)} skipped")
    return 1 if failed else 0


def run(chosen: list, *, installed: bool = False, real_local: str = "", keep: bool = False, root=None,
        repo: Path = REPO, probe_version: bool = True, say=print, browser=None) -> "tuple[list, str]":
    """Each step in turn: (its Results, the `halo --version` line of what ran). `browser` (None: REALCHECK_BROWSER):
    a path or command name the browser steps use (HALO_CHROME for the run), `none` (they SKIP), or '' (as before)."""
    from halo_harness.browser_find import named_browser
    from realcheck.core import Ctx, Fail, Skip
    root = Path(root) if root else Path(tempfile.mkdtemp(prefix="halo-realcheck-"))
    ctx = Ctx(repo, root, installed=installed, real_local=real_local)
    if browser is None:
        browser, ctx.chrome_from = os.environ.get("REALCHECK_BROWSER", "").strip(), "REALCHECK_BROWSER"
    ctx.chrome = "none" if browser.lower() == "none" else browser
    had_chrome = os.environ.get("HALO_CHROME")
    if ctx.chrome not in ("", "none") and named_browser(ctx.chrome):
        os.environ["HALO_CHROME"] = named_browser(ctx.chrome)  # anything deeper that looks for Chrome finds this one
    results, version = [], "?"
    try:
        if probe_version:
            try:
                out = ctx.run(ctx.home("version"), "--version", timeout=60).out
                version = next((ln.strip() for ln in out.splitlines() if ln.strip().startswith("halo ")), "?")
            except Exception:
                pass
        for name, budget, _what, fn in chosen:
            t = time.monotonic()
            try:
                detail, evidence = fn(ctx)
                res = Result(name, PASS, 0.0, budget, detail, evidence)
            except Fail as e:
                res = Result(name, FAIL, 0.0, budget, e.detail, e.evidence, e.expected_until)
            except Skip as e:
                res = Result(name, SKIP, 0.0, budget, str(e))
            except Exception as e:  # the checker's own fault: said as such, never as Halo's
                res = Result(name, FAIL, 0.0, budget, f"realcheck itself failed: {type(e).__name__}: {e}",
                             {"traceback": traceback.format_exc()[-1500:]})
            res.seconds = round(time.monotonic() - t, 1)
            if res.status == PASS and res.seconds > budget:
                res.status, res.detail = FAIL, f"took {res.seconds:.0f}s, budget {budget}s ({res.detail})"
            left = ctx.end_leftovers(None)  # nothing of one step lives into the next
            if left:
                res.evidence["ended_after_step"] = left
            results.append(res)
            say(res.line())
            sys.stdout.flush()
    finally:
        if had_chrome is None:
            os.environ.pop("HALO_CHROME", None)
        else:
            os.environ["HALO_CHROME"] = had_chrome
        ctx.close()
        if not keep:
            shutil.rmtree(root, ignore_errors=True)
        else:
            say(f"realcheck: kept {root}")
    return results, version


if __name__ == "__main__":
    if "--name-the-end" in sys.argv[1:]:  # the parent: the checker is its child, and its end is named
        from realcheck.named_end import run_named
        sys.exit(run_named([sys.executable, str(Path(__file__).resolve())]
                           + [a for a in sys.argv[1:] if a != "--name-the-end"]))
    sys.exit(main())
