"""tests.test_flake_rules -- Halo 3.3.8.1 (the CI addendum, item 10): the flake lint. The 3.3.8.0 candidate went through
five CI heads in one day with no product bug -- every red was one of the classes below; each is a rule here, one
assertion per rule, the offending file:line in the message and the fix in one sentence (docs/DEVELOPMENT.md "Flake
rules"). Text and ast reads over tests/ and halo_harness/, about a second, nothing imported from the code under test:

1. no `audited(<literal int>)`: a host audit wait names the op (`audited_op(op, n)`, `audit_rows(n, op=, path=)`) or a
   baseline plus k (`audited(before + k)`) -- `audited(n)` counts every request, the pair and the views too;
2. no `read_audit(` in a test module but a baseline (`before = len(read_audit(...))`): the audit line lands after the
   reply, so a read goes through a wait helper (tests/helpers/host_rig.py);
3. in a Chrome driver (tests/helpers/studio_*.py), no `c.js(` read of a list (`querySelectorAll`, `qa(`) on the line
   after a click / press that starts a job (`-run]`, `-go]`, `-apply]`, `-bench]`, `-yes]`): the read is a `c.wait(`
   with the count it asserts;
4. no `time.mktime(` / `tm_mday` date arithmetic in a test that also builds a rig unless the same helper keeps the
   result ahead of the real clock (`time.time()` in it): a fake `now` behind the rig's real-time stamps reads busy;
5. no sort of rows newest first by an `at` / `ts` / `started` stamp alone in halo_harness/ (`reverse=True` or `-key`):
   rows of one millisecond keep file order, the older first -- `halo_harness.newest_first` breaks the tie;
6. a driver reads a verdict before the step that changes its inputs -- not lintable in general; the one known case
   is pinned: tests/helpers/studio_pool_watch.py yields bench, bundles, findings, adviser (the Bundles group is read
   while the pool is healthy, the degrading finding after).
Run: python -m tests.test_flake_rules
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
REPO = Path(__file__).resolve().parent.parent
SELF = Path(__file__).name
AUDITED_LITERAL = re.compile(r"\baudited\(\s*\d+\s*[,)]")
BASELINE = re.compile(r"=\s*len\(\s*read_audit\(")
JOB_TARGET = re.compile(r"-(run|go|apply|bench|yes)\]")
ACTION = re.compile(r"\b(click|press|click_on)\(")
STAMPS = ("at", "ts", "started")
SORT_ALLOWED: dict = {}  # "path:line": why a descending stamp sort there cannot tie -- none left after 3.3.8.1


def _tests(pattern: str = "**/*.py"):
    return [p for p in sorted((REPO / "tests").glob(pattern)) if p.name != SELF and "__pycache__" not in p.parts]


def _rel(p: Path, n: int) -> str:
    return f"{p.relative_to(REPO).as_posix()}:{n}"


def literal_audits(paths) -> list:
    return [_rel(p, i) for p in paths for i, ln in enumerate(p.read_text(encoding="utf-8").splitlines(), 1)
            if AUDITED_LITERAL.search(ln) and not ln.lstrip().startswith(("#", "def "))]


def raw_audit_reads(paths) -> list:
    return [_rel(p, i) for p in paths for i, ln in enumerate(p.read_text(encoding="utf-8").splitlines(), 1)
            if "read_audit(" in ln and not BASELINE.search(ln) and not ln.lstrip().startswith("#")]


def job_reads(text: str) -> list:
    """The line numbers of a list read straight after a click / press that starts a job."""
    out, prev = [], ""
    for i, ln in enumerate(text.splitlines(), 1):
        if not ln.strip():
            continue
        if "c.js(" in ln and ("querySelectorAll" in ln or "qa(" in ln) and ACTION.search(prev) and JOB_TARGET.search(prev):
            out.append(i)
        prev = ln
    return out


def list_reads_after_a_job(paths) -> list:
    return [_rel(p, i) for p in paths for i in job_reads(p.read_text(encoding="utf-8"))]


def _calls_a_rig(text: str) -> bool:
    return bool(re.search(r"\b\w*Rig\(", text))


def clocks_behind(paths) -> list:
    out = []
    for p in paths:
        text = p.read_text(encoding="utf-8")
        if not ("mktime(" in text or "tm_mday" in text) or not _calls_a_rig(text):
            continue
        tree, lines = ast.parse(text), text.splitlines()
        covered: set = set()
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                seg = "\n".join(lines[node.lineno - 1:node.end_lineno])
                span = set(range(node.lineno, node.end_lineno + 1))
                if "time.time()" in seg:
                    covered |= span
        out += [_rel(p, i) for i, ln in enumerate(lines, 1) if ("mktime(" in ln or "tm_mday" in ln)
                and i not in covered and not ln.lstrip().startswith("#")]
    return out


def _stamp_of(node, arg: str):
    """(the stamp key, descending by a minus) when the lambda body is one stamp read of its argument, else (None, _)."""
    neg = False
    while True:
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
            neg, node = not neg, node.operand
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in ("float", "str", "int") \
                and len(node.args) == 1:
            node = node.args[0]
        elif isinstance(node, ast.BoolOp) and isinstance(node.op, ast.Or) and len(node.values) == 2 \
                and isinstance(node.values[1], ast.Constant):
            node = node.values[0]
        else:
            break
    key = None
    if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name) and node.value.id == arg:
        sl = node.slice
        key = sl.value if isinstance(sl, ast.Constant) else None
    elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "get" \
            and isinstance(node.func.value, ast.Name) and node.func.value.id == arg and node.args \
            and isinstance(node.args[0], ast.Constant):
        key = node.args[0].value
    return (key if key in STAMPS else None), neg


def newest_first_by_a_stamp(paths) -> list:
    out = []
    for p in paths:
        text = p.read_text(encoding="utf-8")
        if "sort" not in text or not any(f'"{k}"' in text or f"'{k}'" in text for k in STAMPS):
            continue
        for node in ast.walk(ast.parse(text)):
            if not isinstance(node, ast.Call):
                continue
            f = node.func
            if not ((isinstance(f, ast.Name) and f.id == "sorted") or (isinstance(f, ast.Attribute) and f.attr == "sort")):
                continue
            kws = {k.arg: k.value for k in node.keywords}
            lam = kws.get("key")
            if not isinstance(lam, ast.Lambda) or len(lam.args.args) != 1:
                continue
            key, neg = _stamp_of(lam.body, lam.args.args[0].arg)
            rev = isinstance(kws.get("reverse"), ast.Constant) and kws["reverse"].value is True
            if key and (neg != rev) and _rel(p, node.lineno) not in SORT_ALLOWED:
                out.append(_rel(p, node.lineno))
    return out


@test
def test_rule_1_no_absolute_audit_count(ctx: Ctx):
    hits = literal_audits(_tests())
    ctx.check(f"audited(<literal>) at {hits}: wait on the op (rig.audited_op(op, n)) or a baseline (audited(before + k))",
              not hits)
    ctx.check("the lint sees one", literal_audits_of("        rig.audited(4)\n") and not literal_audits_of("rig.audited(before + 2)\n"))


def literal_audits_of(text: str) -> list:
    return [ln for ln in text.splitlines() if AUDITED_LITERAL.search(ln)]


@test
def test_rule_2_audit_reads_go_through_a_wait(ctx: Ctx):
    hits = raw_audit_reads(_tests("test_*.py"))
    ctx.check(f"read_audit( in a test module at {hits}: the line lands after the reply -- read it with rig.audit_rows(n, "
              "op=, path=) or rig.audited_op(op, n)", not hits)


@test
def test_rule_3_a_driver_waits_for_the_list_it_reads(ctx: Ctx):
    hits = list_reads_after_a_job(_tests("helpers/studio_*.py"))
    ctx.check(f"c.js( list read right after starting a job at {hits}: make it c.wait( with the count it asserts", not hits)
    press = "    press(c, q('[data-testid=pull-go]'), '1')"
    bad = press + "\n    out['rows'] = c.js(qa('[data-testid=row]') + '.length')\n"
    good = press + "\n    out['rows'] = c.wait(qa('[data-testid=row]') + '.length >= 2', 20)\n"
    ctx.check("the lint sees a list read after a job and passes a wait", job_reads(bad) == [2] and job_reads(good) == [])


@test
def test_rule_4_a_fake_clock_stays_ahead_of_the_real_one(ctx: Ctx):
    hits = clocks_behind(_tests())
    ctx.check(f"date arithmetic with a rig at {hits}: return the first such time ahead of time.time() (tests/"
              "test_host_refresh.at) or use an epoch far from today", not hits)


@test
def test_rule_5_a_newest_first_sort_breaks_a_tie(ctx: Ctx):
    hits = newest_first_by_a_stamp(sorted((REPO / "halo_harness").rglob("*.py")))
    ctx.check(f"newest first by a stamp alone at {hits}: rows of one millisecond keep file order (the older first) -- "
              "use halo_harness.newest_first.newest_first(rows, stamp)", not hits)
    tree = ast.parse("rows.sort(key=lambda r: str(r.get('at')), reverse=True)\nsorted(x, key=lambda j: -j['started'])\n"
                     "sorted(x, key=lambda j: j['started'])\n")
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and node.keywords and isinstance(node.keywords[0].value, ast.Lambda):
            lam = node.keywords[0].value
            key, neg = _stamp_of(lam.body, lam.args.args[0].arg)
            rev = any(k.arg == "reverse" for k in node.keywords)
            found.append((key, neg != rev))
    ctx.check(f"the lint tells a descending stamp sort from an ascending one, got {found}",
              found == [("at", True), ("started", True), ("started", False)])
    from halo_harness.newest_first import newest_first
    ctx.check("newest_first: the later of one stamp first", newest_first([{"at": 1, "i": 0}, {"at": 1, "i": 1}, {"at": 0, "i": 2}],
                                                                      lambda r: r["at"]) == [{"at": 1, "i": 1}, {"at": 1, "i": 0}, {"at": 0, "i": 2}])


@test
def test_rule_6_the_pool_watch_driver_reads_bundles_before_it_degrades(ctx: Ctx):
    text = (REPO / "tests" / "helpers" / "studio_pool_watch.py").read_text(encoding="utf-8")
    ctx.check("studio_pool_watch.py yields bench, bundles, findings, adviser: the Bundles verdict is read while the pool "
              "is healthy, the degrading finding after", "for fn in (bench, bundles, findings, adviser)" in text)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
