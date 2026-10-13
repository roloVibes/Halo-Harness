"""tests.test_review3_m2 -- pins for the 3.0.2.0 review fix pass, round M-data-misc,
the rest (review items 89, 90, 156, 159, 160):

  * 89   a transient probe failure became a permanent gateway-dialect override
  * 90   screen-reader mode never answered `approval_request`
  * 156  correction cues matched by raw prefix ("Now ...", "Note ...")
  * 159  machine-name findings ignored the allowlist
  * 160  `gym propose --apply` left its temp directory behind
"""
from __future__ import annotations

import builtins
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all
from tests.test_review2_round10 import scoped_home

test, TESTS = new_registry()


# ---- 89 ------------------------------------------------------------------------

def _report(*rows):
    return {"rows": [dict(r) for r in rows]}


@test
def test_transient_failures_never_become_a_dialect_override(ctx: Ctx):
    from halo_harness.work_matrix import classify_row, writable_overrides
    good = {"endpoint": "e (anthropic gateway)", "status": "200"}
    for status, error in (("429", ""), ("500", ""), ("503", ""), ("408", ""),
                          ("error", "TimeoutError: read timed out")):
        report = _report({"endpoint": "e", "status": status, "error": error}, good)
        ctx.check(f"{status}: no override, got {writable_overrides(report)}", writable_overrides(report) == [])
        c = classify_row(report["rows"][0], {r["endpoint"]: r for r in report["rows"]})
        ctx.check(f"{status}: advice is to retry, got {c}", "retry" in c["action"] and c["config_key"] is None)


@test
def test_a_deterministic_rejection_with_a_working_companion_still_writes(ctx: Ctx):
    from halo_harness.work_matrix import writable_overrides
    for status in ("400", "404", "415", "422"):
        report = _report({"endpoint": "glm", "status": status}, {"endpoint": "glm (anthropic gateway)", "status": "200"})
        ctx.check(f"{status}: override written, got {writable_overrides(report)}",
                  writable_overrides(report) == [("databricks.gateway.glm", "anthropic")])
    only = _report({"endpoint": "x", "status": "422"})
    ctx.check("no companion, no override", writable_overrides(only) == [])


# ---- 90 ------------------------------------------------------------------------

class _Ctl:
    def __init__(self, events_in):
        import queue
        self.events = queue.Queue()
        for ev in events_in:
            self.events.put(ev)
        self.approvals = []

    def answer_approval(self, request_id, decision):
        self.approvals.append((request_id, decision))
        return True


def _drain_with_input(events_in, lines):
    from types import SimpleNamespace
    from halo_harness import ax_mode
    ctl = _Ctl([SimpleNamespace(kind=k, data=d) for k, d in events_in])
    feed = iter(lines)
    real = builtins.input

    def fake_input(*a, **k):
        try:
            return next(feed)
        except StopIteration:
            raise EOFError
    builtins.input = fake_input
    try:
        ax_mode._drain_until_idle(ctl)
    finally:
        builtins.input = real
    return ctl.approvals


@test
def test_screen_reader_mode_answers_an_approval_request(ctx: Ctx):
    card = ("approval_request", {"id": "a1", "position": "writer", "text": "draft done", "is_error": False})
    done = ("turn_done", {"reason": "end_turn"})
    ctx.check("accept", _drain_with_input([card, done], ["a"]) == [("a1", {"action": "accept", "instruction": None})])
    got = _drain_with_input([card, done], ["e", "tighten the intro"])
    ctx.check(f"edit carries the instruction, got {got}",
              got == [("a1", {"action": "edit", "instruction": "tighten the intro"})])
    ctx.check("stop", _drain_with_input([card, done], ["s"])[0][1]["action"] == "stop")
    ctx.check("EOF is stop", _drain_with_input([card, done], [])[0][1]["action"] == "stop")


# ---- 156 -----------------------------------------------------------------------

@test
def test_correction_cues_match_whole_words_only(ctx: Ctx):
    from halo_harness.improve.evidence import _is_correction_text
    for text in ("Now run the tests", "Note: the file moved", "Normal mode please", "Stopwatch app",
                 "user stories", "Wrongdoing aside", "Nobody asked"):
        ctx.check(f"{text!r} is an ordinary prompt", _is_correction_text(text) is False)
    for text in ("no", "No, that's wrong", "don't do that", "Stop.", "wrong file", "Instead use the other one",
                 "actually, use pytest", "not that one", "use the other path"):
        ctx.check(f"{text!r} is a correction", _is_correction_text(text) is True)


# ---- 159 -----------------------------------------------------------------------

@test
def test_machine_name_findings_honour_the_allowlist(ctx: Ctx):
    from halo_harness import privacy_scan as ps
    saved = (ps.REMOVED_NAMES, ps.EXTENDED_SCAN_TERMS)
    ps.REMOVED_NAMES, ps.EXTENDED_SCAN_TERMS = ("AcmeHost",), ("acme",)
    try:
        text = "vendor note: AcmeHost runs here; Acme is a word\n"
        kinds = lambda allow: [f["kind"] for f in ps.scan_text_content(  # noqa: E731
            text, rel_path="docs/x.md", allowlist=allow)]
        ctx.check("without an allowlist all three hits show", kinds(set()).count("machine-name") == 3)
        ctx.check("the exact removed name can be exempted", kinds({"AcmeHost"}).count("machine-name") == 2)
        ctx.check("an extended term is exempted in any case, and it covers AcmeHost's substring too",
                  kinds({"Acme"}).count("machine-name") == 1)
        ctx.check("both exempted -> clean", kinds({"AcmeHost", "acme"}) == [])
    finally:
        ps.REMOVED_NAMES, ps.EXTENDED_SCAN_TERMS = saved


# ---- 160 -----------------------------------------------------------------------

@test
def test_gym_propose_apply_leaves_no_temp_directory_behind(ctx: Ctx):
    from halo_harness.gym_propose import apply_proposal
    with scoped_home() as home:
        scratch = Path(tempfile.mkdtemp(prefix="m160-tmp-"))
        saved = tempfile.tempdir
        tempfile.tempdir = str(scratch)
        try:
            ok, problems = apply_proposal({"small": "ol:fast-model"}, template_name="gym-leak-test")
            bad_ok, _ = apply_proposal({"Not Valid!": "ol:x"}, template_name="gym-leak-bad")
        finally:
            tempfile.tempdir = saved
        left = [p.name for p in scratch.iterdir()]
        ctx.check(f"apply succeeded, got {problems}", ok)
        ctx.check("the invalid proposal failed", not bad_ok)
        ctx.check(f"no halo-gym-propose-* left on either path, got {left}", left == [])
        ctx.check("the template landed in the state dir", any((home / "roles").glob("gym-leak-test.json"))
                  or any(home.rglob("gym-leak-test.json")))
        os.rmdir(scratch)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
