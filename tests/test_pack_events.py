"""tests.test_pack_events -- a pack's typed events (Halo 3.2.0.0 R5;
ext/events.py, packs/events_log.py, packs/event_triggers.py): a declared
kind's data is checked against its schema and a mismatch is published with
its problems, never dropped; an undeclared kind goes out as before; every
accepted event lands in the pack's events log; a disabled pack's event is
refused with one line and nothing is kept; a bio's trigger on
`<pack>:<kind>` (or `{event: ...}`) fires once when the pack publishes it;
the registry carries a kind's view hint.

Run: python -m tests.test_pack_events
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.packs_home import PacksHome  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


class Bridge:
    def __init__(self):
        self.frames = []

    def publish_local(self, frame):
        self.frames.append(frame)


@test
def test_a_declared_kind_is_checked_and_kept(ctx: Ctx):
    from halo_harness.ext import publish_event
    from halo_harness.packs.events_log import log_path, since
    with PacksHome() as h:
        h.install(h.source(), enable=True)
        b = Bridge()
        ok = publish_event("doc-review", "review.done", {"file": "README.md", "findings": 2}, bridge=b)
        ctx.check("a matching event: published, no problems", ok and "problems" not in b.frames[0]["data"])
        publish_event("doc-review", "review.done", {"file": 3, "extra": True}, bridge=b)
        probs = b.frames[1]["data"].get("problems") or []
        ctx.check(f"a mismatch is published with its problems, got {probs}", probs == [
            "file is a string, got 3", "unknown key 'extra'; nothing reads it", "findings is required"]
            and b.frames[1]["data"]["data"] == {"file": 3, "extra": True})
        publish_event("doc-review", "review.started", {"anything": [1, 2]}, bridge=b)
        ctx.check("an undeclared kind: no schema, no problems", "problems" not in b.frames[2]["data"])
        ctx.check("no Studio: False, still kept", publish_event("doc-review", "review.done", {"file": "a", "findings": 0}) is False)
        kept = since("doc-review:review.done")
        ctx.check(f"the events log holds the three review.done, the bad one with its problems, got {len(kept)}", len(kept) == 3
                  and kept[1]["problems"] == probs and log_path("doc-review", h.state).is_file())
        ctx.check("every kind of the pack", len(since("doc-review")) == 4 and since("doc-review:review.done", kept[-1]["ts"]) == [])


@test
def test_a_disabled_pack_is_refused_with_one_line(ctx: Ctx):
    from halo_harness.ext import publish_event
    from halo_harness.packs.events_log import since
    from halo_harness.packs.grants import disable
    with PacksHome() as h:
        h.install(h.source(), enable=True)
        disable("doc-review")
        b = Bridge()
        try:
            publish_event("doc-review", "review.done", {"file": "a", "findings": 1}, bridge=b)
            why = ""
        except ValueError as e:
            why = str(e)
        ctx.check(f"refused with one line, got {why!r}", why == "pack doc-review is disabled here: its event review.done is not "
                  "published (halo pack enable doc-review)" and not b.frames and since("doc-review") == [])
        try:
            publish_event("no-such-pack", "x.y", bridge=b)
            why = ""
        except ValueError as e:
            why = str(e)
        ctx.check(f"not installed: one line, got {why!r}", "is not installed here" in why)


@test
def test_a_bios_trigger_on_a_pack_event_fires_it_once(ctx: Ctx):
    from halo_harness.agents_schedule import TeamScheduler
    from halo_harness.agents_yaml import validate_trigger_section
    from halo_harness.ext import publish_event
    ctx.check("the short form validates", validate_trigger_section([{"event": "doc-review:review.done"}]) == [])
    ctx.check("so does the long one", validate_trigger_section([{"on": "event", "name": "doc-review:review.done"}]) == [])
    with PacksHome() as h:
        h.install(h.source(), enable=True)
        fired = []
        sched = TeamScheduler(SimpleNamespace(state_dir=None), SimpleNamespace(name="review"),
                              fire_fn=lambda s, e: fired.append(e["on_value"]) or "fired", tick_s=0.05)
        armed = sched.arm_bio({"name": "doc-review--writer", "triggers": [{"event": "doc-review:review.done", "prompt": "Summarise it"},
                                                                         {"on": "event", "name": "doc-review:other.kind"}]}, "main")
        ctx.check(f"two triggers armed, got {armed}", len(armed) == 2)
        sched._poll_pack_events()
        ctx.check("nothing before the event", fired == [])
        time.sleep(0.02)
        publish_event("doc-review", "review.done", {"file": "README.md", "findings": 1})
        sched._poll_pack_events()
        sched._poll_pack_events()
        publish_event("doc-review", "review.done", {"file": "README.md", "findings": 1})
        sched._poll_pack_events()
        ctx.check(f"fired once, for its kind only, got {fired}", fired == ["doc-review:review.done"])
        sched.start()
        publish_event("doc-review", "other.kind", {})
        deadline = time.time() + 5
        while time.time() < deadline and len(fired) < 2:
            time.sleep(0.05)
        sched.stop()
        ctx.check(f"the scheduler's own tick fires the other, got {fired}", fired == ["doc-review:review.done", "doc-review:other.kind"])


@test
def test_the_registry_carries_a_kinds_view(ctx: Ctx):
    from halo_harness.packs.studio_registry import registry
    with PacksHome() as h:
        h.install(h.source(), enable=True)
        doc = registry(cwd=h.repo)["packs"][0]
        ctx.check(f"review.done's schema says keyvalue, got {doc['events']}", doc["events"]["review.done"]["view"] == "keyvalue")
        panel = next(p for p in doc["sections"][0]["panels"] if p["kind"] == "artifact")
        ctx.check(f"the artifact panel: schema, view, the latest route, got {panel}", panel["schema"] == "review-report"
                  and panel["view"] == "table" and panel["file"] == "api/pack/doc-review/artifact/review-report")


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
