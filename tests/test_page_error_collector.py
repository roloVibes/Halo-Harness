"""tests.test_page_error_collector -- Halo 3.6.0.5 (package b, batch 8, entry 3): the browser drivers' page-error collector
really runs. A script added with Page.addScriptToEvaluateOnNewDocument runs only once the Page domain is on; measured on
the Linux VM, seven drivers added ERRS_JS without it, so `window.__errs` was never there on their pages. Now ONE function,
tests/helpers/studio_session.py `collect_page_errors(c)`, turns Page on and adds it, and ONE reader, `page_errors(c)`,
says when the collector is missing instead of reading nothing. Plain Python, no browser: runs anywhere.
Run: python -m tests.test_page_error_collector
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
HELPERS = REPO / "tests" / "helpers"


class _Conn:
    """A stand-in for cdp.Chrome: records what is sent; `js` answers from `page`."""

    def __init__(self, page=None):
        self.sent: list = []
        self.page = page

    def call(self, method: str, **params):
        self.sent.append((method, params))
        return {"identifier": "1"}

    def js(self, expr: str):
        self.sent.append(("js", {"expression": expr}))
        return self.page


@test
def test_collector_turns_page_on_before_it_adds_the_script(ctx: Ctx):
    from tests.helpers import studio_session as S
    c = _Conn()
    S.collect_page_errors(c)
    methods = [m for m, _ in c.sent]
    adds = [i for i, (m, p) in enumerate(c.sent) if m == "Page.addScriptToEvaluateOnNewDocument" and p.get("source") == S.ERRS_JS]
    ctx.check(f"Page.enable, then ERRS_JS added once, got {methods}",
              len(adds) == 1 and "Page.enable" in methods[:adds[0]])


@test
def test_reader_says_when_the_collector_is_missing(ctx: Ctx):
    from tests.helpers import studio_session as S
    try:
        S.page_errors(_Conn(page=None))
        missing = ""
    except Exception as e:  # noqa: BLE001 -- the message is what is checked
        missing = str(e)
    ctx.check(f"no collector on the page: it raises and says so, got {missing!r}", "collector is missing" in missing)
    got = S.page_errors(_Conn(page=["boom", "rejected: x"]))
    ctx.check(f"with the collector: its errors as a list of strings, got {got!r}", got == ["boom", "rejected: x"])
    ctx.check(f"none: an empty list, got {S.page_errors(_Conn(page=[]))!r}", S.page_errors(_Conn(page=[])) == [])


@test
def test_every_driver_adds_and_reads_through_the_one_pair(ctx: Ctx):
    """No helper adds the collector on its own (ERRS_JS, or a copy of its script) and none reads `window.__errs` but
    page_errors; no driver turns the Page domain off once the collector is on."""
    own, reads, off = [], [], []
    for p in sorted(HELPERS.glob("*.py")):
        t = p.read_text(encoding="utf-8")
        if p.name == "studio_session.py":  # its one add is collect_page_errors' own
            at = t.find("def collect_page_errors")
            t = t.replace(t[at:t.find("def page_errors")], "") if at >= 0 else t
        if re.search(r"source=ERRS(_JS)?\b", t) or ("window.__errs = []" in t and p.name != "studio_session.py"):
            own.append(p.name)
        body = t.replace(t[t.find("def page_errors"):t.find("def page_errors") + 600], "") if p.name == "studio_session.py" else t
        if "window.__errs" in body.replace("window.__errs = []", "").replace("window.__errs.push", ""):
            reads.append(p.name)
        if "collect_page_errors(" in t and '"Page.disable"' in t:
            off.append(p.name)
    ctx.check(f"no helper adds the collector on its own, got {own}", not own)
    ctx.check(f"no helper reads window.__errs but page_errors, got {reads}", not reads)
    ctx.check(f"no driver with the collector turns Page off, got {off}", not off)
    users = sorted(p.name for p in HELPERS.glob("*.py") if "collect_page_errors(c)" in p.read_text(encoding="utf-8"))
    want = sorted(["studio_session.py", "studio_controls.py", "studio_session_just_built.py", "studio_session_map_down.py",
                   "studio_session_map_down_draw.py", "studio_auto_groups_draw.py", "studio_session_run.py",
                   "studio_session_step_in.py", "studio_session_truth.py", "studio_run_parts.py"])
    ctx.check(f"the ten drivers that collected page errors call collect_page_errors(c), got {users}", users == want)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
