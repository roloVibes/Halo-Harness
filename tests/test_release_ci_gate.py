"""tests.test_release_ci_gate -- scripts/release_gate.py, the gate of scripts/release.py (Halo 3.1.0.0 R1; 3.6.0.0
R13: the candidate branch), over a fake `gh` (tests/helpers/fake_gh.py) and a fake clock (no process, no network, no
real sleep). The main()-level flow (rc branch, fast-forward, tag) is in tests/test_release_script.py.

1. The push run on the candidate branch for the exact sha is found (after it appears) and polled until it
   completes; every required job green: the accepted line comes back.
2. The required jobs are one list: Linux x4, Windows x4, macOS x4, studio-ui and the six realcheck legs (3.6.0.0:
   macOS and realcheck required by default; only an explicit emergency switch leaves either out).
3. A red, skipped or missing required job stops the gate and names every failing job: a red macOS shard, a red or
   missing realcheck leg (checkout or installed, any system) included; with the emergency switch off they do not.
4. A run that never finishes, or never appears, stops the gate; a run for another sha is refused; no `gh` is one line.
5. "driver retried once" lines in the run's log come back as warnings naming the job and the test.
Run: python -m tests.test_release_ci_gate
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.fake_gh import FakeGh
from tests.helpers.runner import Ctx, new_registry, print_results, run_all

REPO_DIR = Path(__file__).resolve().parent.parent
test, TESTS = new_registry()

_spec = importlib.util.spec_from_file_location("halo_release_gate_test", REPO_DIR / "scripts" / "release_gate.py")
gate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gate)
SHA = "a1b2c3d4" * 5
BRANCH = "rc/9.9.9"


class _Clock:
    def __init__(self):
        self.t = 0.0
        self.sleeps: list = []

    def now(self) -> float:
        return self.t

    def sleep(self, s: float) -> None:
        self.sleeps.append(s)
        self.t += s


def _gate(gh, clock=None, **kw):
    clock = clock or _Clock()
    lines: list = []
    got = gate.candidate_gate(SHA, branch=BRANCH, repo_dir=REPO_DIR, run_fn=gh, sleep_fn=clock.sleep,
                              clock_fn=clock.now, log=lines.append, **kw)
    return got, lines, clock


def _refused(ctx, gh, want: "list[str]", why: str, **kw) -> str:
    try:
        _gate(gh, **kw)
        ctx.check(f"{why}: the gate raises", False)
        return ""
    except gate.GateError as e:
        ctx.check(f"{why}: it names {want}, got {e}", all(w in str(e) for w in want))
        return str(e)


@test
def test_the_branch_run_is_found_polled_and_accepted(ctx: Ctx):
    gh = FakeGh(polls=4, appear_after=2)
    (accepted, warnings), lines, clock = _gate(gh)
    ctx.check(f"accepted, naming the run, the branch and the job count, got {accepted}",
              accepted == [f"suites run 303 on {BRANCH}: all 19 required jobs concluded success for {SHA[:12]}"])
    ctx.check(f"no retries, no warnings, got {warnings}", warnings == [])
    ctx.check(f"two looks for the run (10 s), three polls (30 s), got {clock.sleeps}",
              clock.sleeps == [10.0, 10.0, 30.0, 30.0, 30.0])
    ctx.check(f"each wait is logged, got {lines}", sum("waiting for the suites run 303" in ln for ln in lines) == 3)
    asked = [c for c in gh.gh_calls() if c[1:3] == ["run", "list"]]
    ctx.check(f"it asks for the push run on the branch for the exact sha, got {asked[:1]}",
              asked and "--branch" in asked[0] and BRANCH in asked[0] and SHA in asked[0] and "push" in asked[0])
    ctx.check("nothing is dispatched any more", not [c for c in gh.gh_calls() if c[1:3] == ["workflow", "run"]])


@test
def test_the_required_jobs_are_one_list_macos_and_realcheck_included_by_default(ctx: Ctx):
    base = gate.required_jobs(macos=False, realcheck=False)
    ctx.check(f"Linux x4, Windows x4, studio-ui, got {base}", len(base) == 9
              and sum(n.startswith("suites (linux, py3.12, shard ") for n in base) == 4
              and sum(n.startswith("suites (windows, py3.12, shard ") for n in base) == 4
              and "studio-ui (build + drift gate)" in base)
    both = gate.required_jobs(macos=True, realcheck=True)
    # join batch 1: realcheck runs two legs per OS (checkout and installed): x6, not x3
    ctx.check(f"the flags add macOS x4 and realcheck x6, got {both}", len(both) == 19
              and sum(n.startswith("suites (macos, ") for n in both) == 4
              and {f"realcheck ({p}{f}" for p in ("linux", "windows", "macos") for f in (")", ", installed)")} <= set(both))
    no_mac = gate.required_jobs(macos=False, realcheck=True)
    ctx.check(f"skipping macOS (the emergency switch) leaves out realcheck's macOS legs too, got {no_mac[9:]}",
              no_mac[9:] == ["realcheck (linux)", "realcheck (linux, installed)", "realcheck (windows)",
                             "realcheck (windows, installed)"])
    # 3.6.0.0: the owner's bar is Windows, macOS and Linux; macOS and the real-use check are required by default
    ctx.check("the defaults are the module's flags, both on",
              gate.required_jobs() == gate.required_jobs(macos=gate.REQUIRE_MACOS, realcheck=gate.REQUIRE_REALCHECK)
              and gate.REQUIRE_MACOS is True and gate.REQUIRE_REALCHECK is True)
    ctx.check(f"by default all 19 are required, got {len(gate.required_jobs())}", gate.required_jobs() == both)
    ctx.check("nothing is skipped by default", gate.skipped_jobs() == [])
    skipped = gate.skipped_jobs(macos=False)
    ctx.check(f"skipping macOS names its six legs, got {skipped}",
              skipped == [f"suites (macos, py3.12, shard {i}/4)" for i in range(4)]
              + ["realcheck (macos)", "realcheck (macos, installed)"])
    ctx.check(f"skipping realcheck names its six legs, got {gate.skipped_jobs(realcheck=False)}",
              gate.skipped_jobs(realcheck=False) == [n for n in both if n.startswith("realcheck")]
              and len(gate.skipped_jobs(realcheck=False)) == 6)
    ctx.check("the dry run's line names them", "suites (windows, py3.12, shard 3/4)" in gate.describe(BRANCH)
              and "suites (macos, py3.12, shard 3/4)" in gate.describe(BRANCH)
              and "realcheck (macos, installed)" in gate.describe(BRANCH)
              and "all 19 required jobs" in gate.describe(BRANCH)
              and "90 min" in gate.describe(BRANCH) and "driver retried once" in gate.describe(BRANCH))


@test
def test_a_red_skipped_or_missing_required_job_stops_the_gate_naming_each(ctx: Ctx):
    win2, linux0 = "suites (windows, py3.12, shard 2/4)", "suites (linux, py3.12, shard 0/4)"
    _refused(ctx, FakeGh(conclusions={win2: "failure", linux0: "cancelled"}),
             [f"{linux0}: cancelled", f"{win2}: failure", "failing jobs"], "two red jobs")
    _refused(ctx, FakeGh(conclusions={"studio-ui (build + drift gate)": "skipped"}),
             ["studio-ui (build + drift gate): skipped"], "a skipped required job")
    _refused(ctx, FakeGh(conclusions={win2: None}), [f"{win2}: missing"], "a required job not in the run")
    # 3.6.0.0: macOS and realcheck are required by default (no flag)
    mac = "suites (macos, py3.12, shard 1/4)"
    err = _refused(ctx, FakeGh(conclusions={mac: "failure"}), [f"{mac}: failure"], "a red macOS shard by default")
    ctx.check(f"the refusal is one line: the run, the branch, the sha and the red leg, got {err!r}",
              err == f"the suites run 303 on {BRANCH} for {SHA[:12]} is not green -- failing jobs: {mac}: failure")
    _refused(ctx, FakeGh(conclusions={"suites (macos, py3.12, shard 3/4)": None}),
             ["suites (macos, py3.12, shard 3/4): missing"], "a missing macOS shard by default")
    for leg in [f"realcheck ({p}{f}" for p in ("linux", "windows", "macos") for f in (")", ", installed)")]:
        _refused(ctx, FakeGh(conclusions={leg: None}), [f"{leg}: missing"], f"{leg} missing by default")
        _refused(ctx, FakeGh(conclusions={leg: "failure"}), [f"{leg}: failure"], f"{leg} red by default")
    err = _refused(ctx, FakeGh(conclusions={"realcheck (windows, installed)": None}), [], "a missing realcheck leg")
    ctx.check(f"a missing leg's refusal names it as missing, got {err!r}",
              err == f"the suites run 303 on {BRANCH} for {SHA[:12]} is not green -- failing jobs: "
                     "realcheck (windows, installed): missing")
    (accepted, _w), _l, _c = _gate(FakeGh())
    ctx.check(f"every leg green: the default gate accepts the run, got {accepted}",
              accepted == [f"suites run 303 on {BRANCH}: all 19 required jobs concluded success for {SHA[:12]}"])
    # the emergency switches (release.py --emergency-skip-macos-gate / --emergency-skip-realcheck-gate)
    (accepted, _w), _l, _c = _gate(FakeGh(conclusions={mac: "failure", "realcheck (macos, installed)": None}),
                                   macos=False)
    ctx.check(f"macOS switched off: its red shard and missing realcheck leg do not stop it, got {accepted}",
              accepted and "all 13 required jobs" in accepted[0])
    _refused(ctx, FakeGh(conclusions={mac: "failure", "realcheck (linux)": "failure"}), ["realcheck (linux): failure"],
             "macOS switched off, a red Linux realcheck leg still stops it", macos=False)
    (accepted, _w), _l, _c = _gate(FakeGh(conclusions={"realcheck (linux)": "failure"}), realcheck=False)
    ctx.check(f"realcheck switched off: a red leg does not stop it, got {accepted}",
              accepted and "all 13 required jobs" in accepted[0])
    _refused(ctx, FakeGh(conclusions={mac: "failure", "realcheck (linux)": "failure"}), [f"{mac}: failure"],
             "realcheck switched off, a red macOS shard still stops it", realcheck=False)


def _workflow_job_names() -> "set[str]":
    """Every job name .github/workflows/suites.yml produces, each `${{ matrix.<key> }}` expanded from its job's
    matrix (a plain reader of this file's shape: a job at two spaces, `name:` at four, matrix lists `key: [a, b]`).
    join batch 1: also the `${{ matrix.<key> == '<v>' && '<a>' || '<b>' }}` form (realcheck's installed legs); a
    name with any other expression left in it is kept as written, so a test sees it rather than a guess."""
    import itertools
    import re
    text = (REPO_DIR / ".github" / "workflows" / "suites.yml").read_text(encoding="utf-8")
    jobs_part = text.split("\njobs:\n", 1)[1]
    names: set = set()
    plain = r"\$\{\{\s*matrix\.(\w+)\s*\}\}"
    cond = r"\$\{\{\s*matrix\.(\w+)\s*==\s*'([^']*)'\s*&&\s*'([^']*)'\s*\|\|\s*'([^']*)'\s*\}\}"
    for block in re.split(r"\n(?=  [A-Za-z0-9_-]+:\s*\n)", jobs_part):
        m = re.search(r"^    name:\s*(.+?)\s*$", block, re.M)
        if not m:
            continue
        template = m.group(1).strip("'\"")
        keys = list(dict.fromkeys(re.findall(plain, template) + [c[0] for c in re.findall(cond, template)]))
        values = {}
        for k in keys:
            mm = re.search(rf"^\s+{k}:\s*\[([^\]]*)\]", block, re.M)
            values[k] = [v.strip().strip("'\"") for v in mm.group(1).split(",")] if mm else []
        for combo in itertools.product(*(values[k] for k in keys)):
            row = dict(zip(keys, combo))
            name = re.sub(cond, lambda c: c.group(3) if row.get(c.group(1)) == c.group(2) else c.group(4), template)
            name = re.sub(plain, lambda c: row.get(c.group(1), c.group(0)), name)
            names.add(name)
    return names


@test
def test_every_required_job_name_is_one_the_workflow_runs(ctx: Ctx):
    """3.6.0.0 fix: --require-realcheck asked for a job named `realcheck`; the workflow's are `realcheck (<os>)`,
    so the switch could never pass. Every name the gate can require is read against suites.yml itself."""
    produced = _workflow_job_names()
    legs = sorted(n for n in produced if n.startswith("realcheck"))
    ctx.check(f"the workflow reader finds the realcheck legs, both forms, got {legs}",
              legs == sorted(f"realcheck ({p}{f}" for p in ("linux", "macos", "windows") for f in (")", ", installed)")))
    want = gate.required_jobs(macos=True, realcheck=True)
    ctx.check(f"each required name is a job of suites.yml; not: {[n for n in want if n not in produced]}",
              all(n in produced for n in want))
    # join batch 1: the gate saw only the checkout legs; the installed legs (the wheel a user installs) went unread
    ctx.check(f"with both flags on, every realcheck leg of the workflow is required; not: "
              f"{[n for n in legs if n not in want]}", all(n in want for n in legs))
    ctx.check(f"with both flags on, every macOS suites leg of the workflow is required; not: "
              f"{[n for n in produced if n.startswith('suites (macos') and n not in want]}",
              all(n in want for n in produced if n.startswith("suites (macos")))
    no_mac = gate.required_jobs(macos=False, realcheck=True)
    ctx.check(f"realcheck without the macOS flag: every Linux and Windows leg, both forms, no macOS one, got {no_mac[9:]}",
              sorted(no_mac[9:]) == sorted(n for n in legs if "macos" not in n))
    from tests.helpers.fake_gh import all_jobs
    ctx.check(f"the fake gh's jobs are the workflow's; not: {[n for n in all_jobs() if n not in produced]}",
              all(n in produced for n in all_jobs()))


@test
def test_every_required_leg_fails_the_run_when_red(ctx: Ctx):
    """3.6.0.0: the macOS suite legs and the realcheck legs lost their job-level `continue-on-error`, so a red one
    makes the run red (and blocks the branch); `upgrade from 3.5.0.1` alone stays informative."""
    import yaml
    jobs = yaml.safe_load((REPO_DIR / ".github" / "workflows" / "suites.yml").read_text(encoding="utf-8"))["jobs"]
    lax = sorted(key for key, j in jobs.items() if "continue-on-error" in j and key != "upgrade-from-3501")
    ctx.check(f"no job but the upgrade check has a job-level continue-on-error, got {lax}", lax == [])
    ctx.check("the macOS suites legs run in the `linux` job (os in its matrix), which never forgives a red leg",
              "macos" in jobs["linux"]["strategy"]["matrix"]["os"] and "continue-on-error" not in jobs["linux"])
    ctx.check("the realcheck job runs on every system and never forgives a red leg",
              jobs["realcheck"]["strategy"]["matrix"]["os"] == ["linux", "macos", "windows"]
              and "continue-on-error" not in jobs["realcheck"])
    ctx.check("the upgrade check stays non-blocking (it informs)",
              jobs["upgrade-from-3501"].get("continue-on-error") is True)


@test
def test_a_run_that_never_finishes_never_appears_or_is_for_another_sha_stops_it(ctx: Ctx):
    _refused(ctx, FakeGh(polls=10_000), ["303", "90 min"], "never finishes")
    _refused(ctx, FakeGh(appear_after=None), ["no suites run (push) on rc/9.9.9", "appeared"], "never appears")
    _refused(ctx, FakeGh(head_sha="f" * 40), ["303 is for ffffffffffff"], "another sha")

    def no_gh(cmd, **kw):
        raise FileNotFoundError(cmd[0])
    _refused(ctx, no_gh, ["`gh` CLI"], "no gh")


class _Flaky:
    """A `gh` whose calls numbered in `fail_at` (1-based, `gh` calls only) end as a network fault ends them."""

    def __init__(self, inner, fail_at):
        self.inner, self.fail_at, self.n = inner, set(fail_at), 0

    def __call__(self, cmd, **kw):
        if list(cmd[:1]) == ["gh"]:
            self.n += 1
            if self.n in self.fail_at:
                return SimpleNamespace(returncode=1, stdout="", stderr="net/http: TLS handshake timeout")
        return self.inner(cmd, **kw)


@test
def test_a_gh_read_that_fails_while_the_gate_waits_is_asked_again(ctx: Ctx):
    """3.6.0.16: one failed `gh run view` (a TLS handshake timeout) ended the release tool while its run was still
    going. A read that fails is asked again after the pause; three failures in a row stop the gate with the last
    reason; a read that works in between starts the count anew. Red on 602c5df6."""
    gh = _Flaky(FakeGh(polls=3), {1, 3, 4})  # the look for the run once, then the run's view twice in a row
    (accepted, _warnings), lines, clock = _gate(gh)
    ctx.check(f"the gate still accepts the green run, got {accepted}",
              accepted == [f"suites run 303 on {BRANCH}: all 19 required jobs concluded success for {SHA[:12]}"])
    again = [ln for ln in lines if "asking again" in ln]
    ctx.check(f"each failed read is said in one line with its reason and its count, got {again}",
              len(again) == 3 and all("TLS handshake timeout" in ln for ln in again)
              and again[0].endswith("asking again (1 of 2)") and again[2].endswith("asking again (2 of 2)"))
    ctx.check(f"it pauses before it asks again (10 s for the look, 30 s for a view), got {clock.sleeps}",
              clock.sleeps == [10.0, 30.0, 30.0, 30.0, 30.0])
    why = _refused(ctx, _Flaky(FakeGh(polls=3), {2, 3, 4}), ["exited 1", "TLS handshake timeout"],
                   "three failed reads in a row")
    ctx.check(f"the reason is the last read's own, got {why}", "gh run view 303" in why)
    (accepted, _warnings), lines, _clock = _gate(_Flaky(FakeGh(polls=4), {2, 3, 5, 6}))
    ctx.check(f"two failures, a read that works, two more: never three in a row, so it goes on, got {accepted}",
              bool(accepted) and sum("asking again" in ln for ln in lines) == 4)


@test
def test_driver_retries_come_back_as_warnings(ctx: Ctx):
    gh = FakeGh(retried=[("suites (windows, py3.12, shard 1/4)", "test_studio_local"),
                         ("suites (linux, py3.12, shard 3/4)", "test_studio_map")])
    (accepted, warnings), _l, _c = _gate(gh)
    ctx.check(f"still accepted (a retry warns, it does not stop), got {accepted}", bool(accepted))
    ctx.check(f"one warning per retry, naming the job and the test, got {warnings}",
              len(warnings) == 2 and warnings[0].startswith("suites (windows, py3.12, shard 1/4): test_studio_local -- "
                                                           "driver retried once: Runtime.evaluate timed out")
              and "test_studio_map" in warnings[1])
    ctx.check("the log is read once", sum(1 for c in gh.gh_calls() if "--log" in c) == 1)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
