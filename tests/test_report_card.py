"""tests.test_report_card -- Halo 3.4.1.0 R3 "Time": the run report card (live/report_card.py, report_card_sections.py,
report_card_text.py), rendered from the record with no model call: its sections from a seeded session (a failure, two
asks, three models, files written), the same card from that session's saved `.halo-replay`, a goal run's card, honest
figures (an unpriced call; a file saved before R2 / R3 says what it cannot show), `halo report` and Studio's
`GET replays/report`.

Seed: tests/helpers/card_seed.py. Run: python -m tests.test_report_card
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.card_seed import OUTSIDE, RUN, SID, SID_B, seed_all  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
SECTIONS = ("story", "story_more", "time", "money", "failures", "failed_calls", "retries", "waits", "waited_s", "models", "artefacts", "cells")


@contextlib.contextmanager
def _home():
    saved = {k: os.environ.get(k) for k in ("BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR")}
    cwd = os.getcwd()
    with tempfile.TemporaryDirectory(prefix="halo-card-") as d:
        os.environ["BRIDGE_TEST_HOME"] = d
        os.environ.pop("BRIDGE_STATE_DIR", None)
        try:
            from halo_harness.config.paths import bridge_home
            state = bridge_home()
            yield state, seed_all(state)
        finally:
            os.chdir(cwd)
            for k, v in saved.items():
                os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)


def _card(state, repo, ref: str) -> dict:
    from halo_harness.live import report_card
    p, from_file = report_card.resolve(state, ref, cwd=repo)
    return report_card.card(p, ref, from_file)


@test
def test_the_cards_sections_from_a_seeded_session(ctx: Ctx):
    with _home() as (state, repo):
        c = _card(state, repo, f"session:{SID}")
        story = [s["text"] for s in c["story"]]
        ctx.check(f"the story in order, who was asked what and what each handed back: {story}", len(story) == 9
                  and story[0] == "You asked main (lead): Ship the basket fix" and "main asked scout (scout): find the bug" in story[2]
                  and story[5].startswith("scout handed back to main: Found it") and story[7] == "fixer failed"
                  and story[8] == "main finished and answered: All done." and [s["at"] for s in c["story"]][-1] == "1:40")
        ctx.check("an ask says how long it waited", story[6].endswith("(waited 10 s)") and "answered allow after 6 s" in story[3])
        ph = {p["phase"]: p["secs"] for p in c["time"]["phases"]}
        ctx.check(f"where the time went, by phase (it sums to the wall time): {ph}", ph.get("waiting") == 16 and ph.get("tool") == 44
                  and abs(sum(ph.values()) - 100) < 0.5)
        ctx.check(f"by block: {c['time']['blocks']}", [(b["block"], b["agents"]) for b in c["time"]["blocks"]] == [("dev", 2), ("session", 1)])
        m = c["money"]
        ctx.check(f"where the money went, by model and by block: {m}", m["total"] == 0.03 and m["known"]
                  and [(x["model"], x["cost_usd"]) for x in m["models"]] == [("or:mock/lead", 0.02), ("or:mock/scout", 0.01)]
                  and [(b["block"], b["cost_usd"]) for b in m["blocks"]] == [("session", 0.02), ("dev", 0.01)])
        f = c["failures"]
        ctx.check(f"what failed and what happened next: {f}", len(f) == 1 and f[0]["who"] == "fixer (fixer)" and f[0]["at"] == "1:30"
                  and f[0]["next"] == "1:40 main finished and answered: All done.")
        ctx.check(f"what waited on you and for how long: {c['waits']}", [w["secs"] for w in c["waits"]] == [6.0, 10.0] and c["waited_s"] == 16)
        models = {x["model"]: [a["name"] for a in x["agents"]] for x in c["models"]}
        ctx.check(f"which model did what (three models): {models}", models == {"or:mock/lead": ["main"], "or:mock/scout": ["scout"], "or:mock/fixer": ["fixer"]})
        arts = {a["rel"]: a for a in c["artefacts"]}
        ctx.check(f"the files it wrote, inside the project as a path, outside by name, a failed edit left out: {arts}",
                  set(arts) == {"src/basket.py", OUTSIDE.rsplit("/", 1)[-1]} and arts["src/basket.py"]["by"] == ["fixer"]
                  and arts["notes-outside.md"].get("outside"))
        ctx.check(f"the nine cells are R2's: {c['cells']['cost']}", c["cells"]["cost"]["text"] == "$0.0300" and c["cells"]["asks"]["value"] == 2)
        ctx.check(f"what it cannot show, in words: {c['cannot']}", any(x.startswith("The tokens are not in this record") for x in c["cannot"])
                  and any("not in the record" in x for x in c["cannot"]) and c["file"] is None)
        from halo_harness.live.report_card_text import markdown
        md = markdown(c)
        heads = [line for line in md.splitlines() if line.startswith("## ")]
        ctx.check(f"the Markdown's sections: {heads}", heads == ["## The figures", "## The story", "## Where the time went", "## Where the money went",
                  "## What failed and what happened next", "## What waited on you", "## Which model did what", "## Artefacts",
                  "## What this record cannot show"] and "- `src/basket.py` -- fixer" in md and "no model call" in md)


@test
def test_the_same_card_from_its_saved_file(ctx: Ctx):
    from halo_harness.live import replay_file as RF
    with _home() as (state, repo):
        live = _card(state, repo, SID)
        path = RF.save(state, RF.build(state, SID))
        raw = path.read_bytes().decode("utf-8")
        ctx.check("the file names the files by their path inside the project, never the project's own path",
                  "src/basket.py" in raw and "secret-project" not in raw and "Elsewhere" not in raw)
        got = _card(state, repo, str(path))
        same = [k for k in SECTIONS if got[k] != live[k]]
        ctx.check(f"a file gives the same card (sections that differ: {same})", not same and got["file"] == path.stem)
        ctx.check("the saved id resolves as a file too", _card(state, repo, f"file:{path.stem}")["story"] == live["story"])


@test
def test_a_goal_runs_card(ctx: Ctx):
    with _home() as (state, repo):
        c = _card(state, repo, f"run:{RUN}")
        story = [s["text"] for s in c["story"]]
        ctx.check(f"the goal, the plan review, the lanes, the end: {story}", story[0].startswith("You set the goal, for lead (lead):")
                  and "lead asked you: the plan review (approved)" in story and "lane 2 failed" in story and story[-1] == "The run ended: finished")
        ctx.check(f"what merged is the artefact: {c['artefacts']}", c["artefacts"] == [{"rel": "basket.py", "by": ["lane 1"]}])
        ctx.check("the gate's sent-back pieces", c["retries"] == 1 and c["failures"][0]["who"] == "lane 2 (worker)")
        ctx.check(f"a goal run's record is coarse, said: {c['cannot'][0]}", c["cannot"][0].startswith("A goal run's record holds each lane's state changes"))
        ctx.check("the plan review's wait is not timed: said, never 0 s", c["waits"][0]["secs"] is None
                  and any("How long some asks waited" in x for x in c["cannot"]))


@test
def test_honest_figures_and_what_an_older_record_cannot_show(ctx: Ctx):
    from halo_harness.live import replay_file as RF
    from halo_harness.live.card_data import build
    from halo_harness.live.report_card_text import markdown
    with _home() as (state, repo):
        c = _card(state, repo, SID_B)
        md = markdown(c)
        ctx.check(f"a cost Halo cannot price: the priced part with a +, never $0: {c['cells']['cost']}",
                  c["cells"]["cost"]["text"] == "$0.0120+" and "- free: unknown (no price)" in md and "Total $0.0120+." in md)
        ctx.check("said in plain words", any(x.startswith("Halo could not price every call (free)") for x in c["cannot"]))
        p = build(state, SID)
        p.pop("facts")
        p["id"] = "r1-file"
        RF.save(state, p)
        old = _card(state, repo, "file:r1-file")
        ctx.check(f"a file saved before R2 says what it lacks: {old['cannot']}", old["artefacts"] is None
                  and any("saved before 3.4.1.0 R2" in x for x in old["cannot"]) and any("before 3.4.1.0 R3" in x for x in old["cannot"])
                  and "Not in this record" in markdown(old))
        none = __import__("halo_harness.live.card_data", fromlist=["cells"]).cells({"cost_usd": 0.0, "cost_known": False, "cost_unknown": ["x"], "models": []})
        ctx.check("nothing priced reads unknown", none["cost"]["text"].startswith("unknown"))


def _cli(argv: list, cwd: Path) -> "tuple[int, str]":
    from halo_harness.report_cli import cmd_report
    out = io.StringIO()
    os.chdir(cwd)
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
        try:
            code = cmd_report(argv)
        except SystemExit as e:
            code = e.code
    return int(code or 0), out.getvalue()


@test
def test_halo_report(ctx: Ctx):
    with _home() as (state, repo):
        code, text = _cli([SID], repo)
        ctx.check(f"the Markdown: {text[:120]!r}", code == 0 and text.startswith("# Report card:") and "## The story" in text)
        code, text = _cli([RUN, "--json"], repo)
        got = json.loads(text)
        ctx.check("--json: the card's data; a goal run id of this repo", code == 0 and got["format"] == "halo-report-card" and got["kind"] == "run")
        code, text = _cli(["nope"], repo)
        ctx.check(f"an unknown run: one line, exit 2: {text!r}", code == 2 and text.startswith("halo report:"))
        from halo_harness.cli_commands import BY_NAME  # 3.6.0.0 R16: cli.py dispatches from the one registry
        ctx.check("`halo report` is dispatched by halo's own CLI",
                  BY_NAME["report"].target == "halo_harness.report_cli:cmd_report"
                  and BY_NAME["replay"].target == "halo_harness.replay_cli:cmd_replay")
        ctx.check("nothing written", not (state / "replays").exists())


@test
def test_studio_report_route(ctx: Ctx):
    from halo_harness.studio.replays_api import dispatch_replays
    with _home() as (state, repo):
        def call(query):
            return dispatch_replays(SimpleNamespace(method="GET", path="replays/report", query=query, body=None, state_dir=state, cwd=repo, server=None, params={}))
        code, got = call({"ref": f"session:{SID}"})
        ctx.check(f"the card and its Markdown, one data: {code}", code == 200 and got["card"]["kind"] == "session"
                  and got["markdown"].startswith("# Report card:") and got["card"]["story"][0]["text"] in got["markdown"])
        ctx.check("a goal run", call({"ref": f"run:{RUN}"})[0] == 200)
        ctx.check("no ref: 422; an unknown one: 404", call({})[0] == 422 and call({"ref": "session:nope"})[0] == 404)
        ctx.check("nothing written", not (state / "replays").exists())


@test
def test_studio_reads_the_card_at_live_report(ctx: Ctx):
    """3.6.0.3 B (R-B12, Z3): the card's route is `GET live/report` (studio/live_report_api.py, dispatched with the other
    `live/*` routes); `replays/report` points at the same handler until the server batch deletes replays_api.py."""
    from halo_harness.studio.live_api import dispatch_live
    from halo_harness.studio.replays_api import dispatch_replays
    with _home() as (state, repo):
        def call(fn, path, query):
            return fn(SimpleNamespace(method="GET", path=path, query=query, body=None, state_dir=state, cwd=repo, server=None, params={}))
        for ref in (f"session:{SID}", f"run:{RUN}"):
            code, got = call(dispatch_live, "live/report", {"ref": ref})
            old = call(dispatch_replays, "replays/report", {"ref": ref})[1]
            ctx.check(f"{ref}: 200 with the same card and Markdown as before: {code}",
                      code == 200 and got.get("card") == old.get("card") and got.get("markdown") == old.get("markdown"))
        ctx.check("no ref: 422; an unknown one: 404",
                  call(dispatch_live, "live/report", {})[0] == 422 and call(dispatch_live, "live/report", {"ref": "session:nope"})[0] == 404)
        ctx.check("nothing written", not (state / "replays").exists())


@test
def test_the_cards_page_gets_every_step(ctx: Ctx):
    """3.6.0.3 B (Z10 as ruled): the text card keeps about ten steps ("...and N more steps"), so Studio's card page shows
    the whole story: `GET live/report` answers every step as `story_all` beside {card, markdown}; card(), its Markdown
    and `halo report --json` are unchanged (the same `story` and `story_more`)."""
    from halo_harness.live import report_card
    from halo_harness.live.report_card_text import markdown
    from halo_harness.studio.live_api import dispatch_live
    with _home() as (state, repo):
        def call(ref):
            return dispatch_live(SimpleNamespace(method="GET", path="live/report", query={"ref": ref}, body=None, state_dir=state, cwd=repo, server=None, params={}))
        for ref in (f"session:{SID}", f"run:{RUN}"):
            code, got = call(ref)
            c = _card(state, repo, ref)
            ctx.check(f"{ref}: story_all is every step of a short story (the card's own), got {code} {len(got.get('story_all') or [])}",
                      code == 200 and got.get("story_all") == c["story"] and c["story_more"] == 0)
            ctx.check(f"{ref}: the card and its Markdown as card() gives them", got.get("card") == c and got.get("markdown") == markdown(c))
        p, _ff = report_card.resolve(state, f"session:{SID}", cwd=repo)
        t = p["started"]
        p["marks"] = list(p.get("marks") or []) + [{"t": t + 101 + i, "kind": "fail", "agent_id": "main"} for i in range(6)]
        c = report_card.card(p, f"session:{SID}")
        every = report_card.story_all(p)
        ctx.check(f"a long story: the card keeps {report_card.STORY_MAX} and counts the rest, got {len(c['story'])} + {c['story_more']}",
                  len(c["story"]) == report_card.STORY_MAX and c["story_more"] == len(every) - report_card.STORY_MAX > 0)
        ctx.check(f"story_all holds every step in time order, the card's among them, got {len(every)}",
                  all(s in every for s in c["story"]) and [s["t"] for s in every] == sorted(s["t"] for s in every))
        ctx.check("the text card still says how many more", f"...and {c['story_more']} more step" in markdown(c))
        ctx.check("nothing written", not (state / "replays").exists())


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="report card"))
