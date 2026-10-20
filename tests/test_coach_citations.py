"""tests.test_coach_citations -- Halo 3.1.6.0 R3: the coach cites its library
(orchestra/coach_citations.py, coach.overlay, format_card), over seeded runs in
a scratch home (tests/helpers/coach_seed.py):

1. an entry born from one run is cited for a later run of the same project (the
   result's `library`, `library_line`, the matching card's `library_hits`, the
   text card's line and `[lib e-...]`), never for its own run, never once undone;
2. another project's entry only when its EXPERIENCE.md ranks for the goal words
   (score >= 0.35, the `SEARCH` seam); at most three, newest first;
3. `coach.library.cite: false` turns the citations off;
4. the probe draft's prompt carries "What earlier runs like this learned";
5. Studio: the coach GET carries `library`; `POST coach/library/<entry>/forget`.
No model is ever called. Run: python -m tests.test_coach_citations
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_scoped_state_dir_once
from tests.helpers.runner import Ctx, new_registry, print_results, run_all
from tests.test_orchestra_coach import Home

ensure_scoped_state_dir_once()
test, TESTS = new_registry()
DENIED = [{"tool_name": "WebFetch", "reason": "denied by rule 'WebFetch'"}]
LATER = "20261018-090000-c0b2"


def _card(h, run):
    from halo_harness.orchestra.coach import cached
    from tests.helpers import coach_seed as S
    return cached(run, catalog=S.CATALOG, state_dir=h.state)


def _two_runs(h):
    """Run A applies the tools card (one entry); run B is a later run of the same project with the same finding."""
    from halo_harness.agents_yaml import user_agents_dir
    from halo_harness.orchestra import coach_apply as CA
    from halo_harness.orchestra import coach_record as R
    from tests.helpers import coach_seed as S
    run_a = S.orchestra_run(h.root, [S.lane(1, bio="coach-deny", denied=DENIED)])
    bio = user_agents_dir(h.state) / "coach-deny.yaml"
    before = R.text_of(bio)
    row = CA.apply(_card(h, run_a), "tools-1-WebFetch", run_a, state_dir=h.state)
    R.write_exact(bio, before)  # put back by hand: the entry stays live and run B shows the same card
    run_b = S.orchestra_run(h.root, [S.lane(1, bio="coach-deny", denied=DENIED)], run=LATER)
    return run_a, run_b, row["entry"]


def _seed(h, eid: str, project: dict, ts: float, changes=None) -> str:
    from halo_harness.orchestra import coach_library as L
    doc = {"id": eid, "ts": ts, "run": "x", "run_dir": str(h.root / "elsewhere" / eid), "kind": "orchestra",
           "project": project, "lineup": "", "goal": {"what": "a goal", "done_when": ""}, "source": "apply",
           "title": f"title {eid}", "apply_ids": [f"a-{eid[-4:]}"], "files": [], "undone": False,
           "changes": changes or [{"target": "bio", "name": "coach-cheap", "field": "models.preference", "value": "or:vendor/mid"}]}
    L.write(doc, f"# title {eid}\n## Lessons\n- lesson of {eid}\n", {}, {}, h.state)
    return str(L.entry_dir(eid, h.state) / L.EXPERIENCE)


@test
def test_an_entry_is_cited_for_a_later_run_of_the_same_project(ctx: Ctx):
    from halo_harness.orchestra import coach_library as L
    from halo_harness.orchestra.coach import format_card
    with Home() as h:
        run_a, run_b, eid = _two_runs(h)
        res = _card(h, run_b)
        lib = res.get("library") or []
        ctx.check(f"run B cites the entry, got {[r['entry'] for r in lib]}", [r["entry"] for r in lib] == [eid]
                  and lib[0]["same_project"] is True and lib[0]["fields"][0]["field"] == "tools.deny")
        line = f"the library: 1 earlier run like this adopted bio coach-deny tools.deny -> Agent ({eid})"
        ctx.check(f"the line, got {res.get('library_line')!r}", res.get("library_line") == line)
        s = next(x for x in res["suggestions"] if x["id"] == "tools-1-WebFetch")
        ctx.check(f"the matching card's hits, got {s.get('library_hits')}", s.get("library_hits") == [eid])
        text = format_card(res).splitlines()
        ctx.check(f"the text card: the line under the head, [lib ...] after the severity, got {text[:4]}", text[1] == line
                  and any(t.startswith(f"[{s['severity']}] [lib {eid}] tools") for t in text))
        ctx.check("never for its own run", _card(h, run_a).get("library") == [] and not _card(h, run_a).get("library_line"))
        L.mark_undone(L.read(eid, h.state)["apply_ids"][0], h.state)
        ctx.check("never once undone", _card(h, run_b)["library"] == [] and "[lib" not in format_card(_card(h, run_b)))


@test
def test_another_projects_entry_through_recall_and_the_limit(ctx: Ctx):
    from halo_harness.orchestra import coach_citations as CC
    from halo_harness.orchestra import coach_library as L
    from tests.helpers import coach_seed as S
    with Home() as h:
        run = S.orchestra_run(h.root, [S.lane(1)])
        far = {"name": "other", "remote": "github.com/x/other"}
        hit = _seed(h, "e-20261001-aaa1", far, 1000.0)
        low = _seed(h, "e-20261001-aaa2", far, 1001.0)
        asked = []
        CC.SEARCH = lambda q, state_dir, k: asked.append(q) or [
            {"id": hit, "kind": "coach_library", "score": 0.5}, {"id": low, "kind": "coach_library", "score": 0.2},
            {"id": "/x/note.md", "kind": "memory", "score": 0.9}]
        try:
            got = [e["id"] for e in L.matches(run, h.state)]
            ctx.check(f"only the entry that ranks >= 0.35, got {got}", got == ["e-20261001-aaa1"])
            ctx.check(f"recall was asked the goal's words, got {asked}", asked and asked[0].startswith(S.GOAL["what"]))
            near = {"name": h.root.resolve().name, "remote": ""}
            for i in range(4):
                _seed(h, f"e-20261002-bbb{i}", near, 2000.0 + i)
            got = [e["id"] for e in L.matches(run, h.state)]
            ctx.check(f"at most three, newest first, got {got}", got == ["e-20261002-bbb3", "e-20261002-bbb2", "e-20261002-bbb1"])
            line = _card(h, run)["library_line"]
            ctx.check(f"three adopted the same change, got {line!r}", line.startswith(
                "the library: 3 earlier runs like this adopted bio coach-cheap models.preference -> or:vendor/mid ("))
        finally:
            CC.SEARCH = None


@test
def test_cite_false_turns_the_citations_off(ctx: Ctx):
    from halo_harness.orchestra import coach_library as L
    from halo_harness.theme import set_config_value
    with Home() as h:
        _a, run_b, eid = _two_runs(h)
        ctx.check("cited by default", [e["id"] for e in L.matches(run_b, h.state)] == [eid])
        set_config_value("coach.library.cite", False)
        res = _card(h, run_b)
        ctx.check(f"off: no library, no line, no hits, got {res.get('library')}", res["library"] == []
                  and res["library_line"] == "" and all(not s["library_hits"] for s in res["suggestions"]))
        ctx.check("the entry itself stays", L.read(eid, h.state) is not None)


@test
def test_the_probe_draft_reads_what_earlier_runs_learned(ctx: Ctx):
    from halo_harness.orchestra import coach_probe as CP
    with Home() as h:
        _a, run_b, eid = _two_runs(h)
        prompts = []
        CP.draft(run_b, 1, ask=lambda prompt, model, cwd: prompts.append(prompt) or {"text": "{}", "ok": True},
                 state_dir=h.state)
        ctx.check("the lessons come in as proposals", prompts and "What earlier runs like this learned" in prompts[0]
                  and f"{eid} (project " in prompts[0] and "nothing is inherited" in prompts[0])


@test
def test_studio_carries_the_library_and_forgets_an_entry(ctx: Ctx):
    from halo_harness.orchestra import coach_library as L
    from halo_harness.studio.api import Request
    from halo_harness.studio.coach_api import dispatch_coach
    with Home() as h:
        _a, run_b, eid = _two_runs(h)
        req = lambda method, path: Request(method=method, path=path, query={}, body={}, cwd=h.root, state_dir=h.state)  # noqa: E731
        status, body = dispatch_coach(req("GET", f"orchestra/{LATER}/coach"))
        ctx.check(f"the GET carries library, got {status} {body.get('library_line')!r}", status == 200
                  and [r["entry"] for r in body["library"]] == [eid] and body["library_line"].startswith("the library: 1 "))
        ctx.check("forget is POST only", dispatch_coach(req("GET", f"coach/library/{eid}/forget"))[0] == 405)
        status, body = dispatch_coach(req("POST", f"coach/library/{eid}/forget"))
        ctx.check(f"forget deletes the folder, got {status} {body}", status == 200 and body["ok"] and L.read(eid, h.state) is None
                  and not L.entry_dir(eid, h.state).exists())
        ctx.check("a second forget is 404", dispatch_coach(req("POST", f"coach/library/{eid}/forget"))[0] == 404)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="coach citation tests"))
