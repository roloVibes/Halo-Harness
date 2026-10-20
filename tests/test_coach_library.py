"""tests.test_coach_library -- Halo 3.1.6.0 R3: every Apply becomes an entry of
the improvement library (orchestra/coach_library.py, orchestra/coach_experience.py):

1. a plain Apply (a seeded run, tests/helpers/coach_seed.py): entry.json's shape,
   the project's remote as a path only (no user, no token), overlay.json in the
   probes' shape, files/<path> = the bio's text after the Apply, EXPERIENCE.md's
   four sections; Undo marks the entry undone and keeps it;
2. a probe adopt (tests/helpers/coach_probe_rig.py): source probe, the pick, the
   group id and every row's id, overlay.json = the composed overlay, the judge's
   why as the lesson and the contrast lines as the evidence; the group's Undo
   marks it undone;
3. the remote path rule and the files/ path check.
The citations: tests/test_coach_citations.py. No model is ever called.
Run: python -m tests.test_coach_library
"""
from __future__ import annotations

import json
import random
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_scoped_state_dir_once
from tests.helpers.runner import Ctx, new_registry, print_results, run_all
from tests.test_orchestra_coach import Home

ensure_scoped_state_dir_once()
test, TESTS = new_registry()
DENIED = [{"tool_name": "WebFetch", "reason": "denied by rule 'WebFetch'"}]


def git(root, *args) -> None:
    subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True, stdin=subprocess.DEVNULL)


def _card(h, run):
    from halo_harness.orchestra.coach import cached
    from tests.helpers import coach_seed as S
    return cached(run, catalog=S.CATALOG, state_dir=h.state)


def _all_text(folder: Path) -> str:
    return "".join(p.read_text(encoding="utf-8") for p in folder.rglob("*") if p.is_file())


@test
def test_a_plain_apply_becomes_an_entry_and_undo_marks_it(ctx: Ctx):
    from halo_harness.agents_yaml import user_agents_dir
    from halo_harness.orchestra import coach_apply as CA
    from halo_harness.orchestra import coach_library as L
    from halo_harness.orchestra import coach_record as R
    from tests.helpers import coach_seed as S
    with Home() as h:
        run = S.orchestra_run(h.root, [S.lane(1, bio="coach-deny", denied=DENIED)])
        git(h.root, "init", "-q")
        git(h.root, "remote", "add", "origin", "https://bob:tok-123@github.com:443/rolo/basket.git")
        card = _card(h, run)
        s = next(x for x in card["suggestions"] if x["id"] == "tools-1-WebFetch")
        row = CA.apply(card, s["id"], run, state_dir=h.state)
        eid = row.get("entry")
        ctx.check(f"the Apply answers its entry id, got {eid!r} {row.get('entry_error')!r}", L.valid_id(eid))
        e = L.read(eid, h.state)
        ctx.check(f"entry.json's shape, got {sorted(e)}", {"id", "ts", "run", "run_dir", "kind", "project", "lineup", "goal",
                  "source", "apply_ids", "files", "undone"} <= set(e) and e["source"] == "apply" and e["kind"] == "orchestra"
                  and e["run"] == S.RUN and e["undone"] is False and e["apply_ids"] == [row["apply_id"]])
        ctx.check(f"the project: the folder name and the remote as a path only, got {e['project']}",
                  e["project"] == {"name": h.root.resolve().name, "remote": "github.com/rolo/basket"})
        ctx.check(f"the goal and the lineup, got {e['goal']} {e['lineup']!r}", e["goal"]["what"] == S.GOAL["what"]
                  and e["goal"]["done_when"] == S.GOAL["done_when"] and e["lineup"] == "")
        bio = user_agents_dir(h.state) / "coach-deny.yaml"
        ctx.check(f"files: the bio, relative to the halo home, got {e['files']}", len(e["files"]) == 1
                  and e["files"][0]["path"] == "agents/coach-deny.yaml" and e["files"][0]["scope"] == "home"
                  and e["files"][0]["fields"] == [["tools.deny", ["Agent"]]] and e["files"][0]["kept"])
        ctx.check("files/<path> holds the bio's text after the Apply",
                  L.stored_files(eid, h.state) == {"agents/coach-deny.yaml": R.text_of(bio)})
        overlay = json.loads(L.text_of(eid, L.OVERLAY, h.state))
        ctx.check(f"overlay.json in the probes' shape with the change, got {overlay}",
                  overlay["bios"] == {"coach-deny": {"tools": {"deny": ["Agent"]}}} and overlay["changes"] == [
                      {"target": "bio", "name": "coach-deny", "field": "tools.deny", "value": ["Agent"]}])
        md = L.text_of(eid, L.EXPERIENCE, h.state).splitlines()
        ctx.check(f"EXPERIENCE.md's title is the card's text, got {md[:1]}", md[0] == f"# {s['text']}")
        heads = [x for x in md if x.startswith("## ")]
        ctx.check(f"its four sections, got {heads}", heads == ["## When it applies", "## Lessons", "## Evidence", "## Files"])
        ctx.check(f"when it applies, got {md[2]!r}", md[2] == f"project {h.root.resolve().name} (github.com/rolo/basket) · "
                  f"lineup (none) · goal \"{S.GOAL['what']}\"")
        ctx.check("the lesson is the card's text, the evidence its why lines",
                  md[md.index("## Lessons") + 1] == f"- {s['text']}" and f"- {s['why'][0]}" in md)
        ctx.check(f"the files line, got {md[-1]!r}", md[-1] == "- agents/coach-deny.yaml (tools.deny -> Agent)")
        text = _all_text(L.entry_dir(eid, h.state))
        ctx.check("no user or token from the remote anywhere in the entry", "tok-123" not in text and "bob" not in text)
        ok, msg, _ = R.undo(row["apply_id"], h.state)
        e = L.read(eid, h.state)
        ctx.check(f"Undo marks the entry undone and keeps it, got {ok} {e.get('undone')}", ok and e["undone"] is True
                  and (L.entry_dir(eid, h.state) / L.EXPERIENCE).is_file())
        again = CA.apply(_card(h, run), s["id"], run, state_dir=h.state)
        ctx.check("a second Apply is a new entry", L.valid_id(again["entry"]) and again["entry"] != eid
                  and [x["id"] for x in L.entries(h.state)][0] == again["entry"])


@test
def test_a_probe_adopt_becomes_an_entry_with_its_evidence(ctx: Ctx):
    from halo_harness.orchestra import coach_apply as CA
    from halo_harness.orchestra import coach_library as L
    from halo_harness.orchestra import coach_probe as CP
    from halo_harness.orchestra import coach_record as R
    from halo_harness.orchestra.coach import cached
    from tests.helpers.coach_probe_rig import Probe, ask
    from tests.test_coach_probe import PAIR
    with Probe(lineup=True) as p:
        CP.ASK = ask({"pairs": [PAIR]})
        data = CP.probe(p.run_dir, rng=random.Random(5))
        res = cached(p.run_dir, state_dir=p.state)
        card = res["suggestions"][0]
        row = CA.apply(res, card["id"], p.run_dir, state_dir=p.state)
        e = L.read(row["entry"], p.state) or {}
        ctx.check(f"a probe entry, got {e.get('source')} {e.get('pick')}", e.get("source") == "probe" and e.get("pick") == "invariant"
                  and e.get("lineup") == "probe-line" and e.get("card") == card["id"])
        rows = [r["apply_id"] for r in R.applies(p.state) if r.get("group") == row["apply_id"]]
        ctx.check(f"apply_ids: the group and each file's row, got {e.get('apply_ids')}",
                  e.get("apply_ids") == [row["apply_id"]] + rows and len(rows) == 2)
        ctx.check(f"two files, got {[f['path'] for f in e.get('files') or []]}",
                  sorted(f["path"] for f in e["files"]) == ["agents/coach-cheap.yaml", "agents/coach-strong.yaml"]
                  and sorted(L.stored_files(e["id"], p.state)) == ["agents/coach-cheap.yaml", "agents/coach-strong.yaml"])
        overlay = json.loads(L.text_of(e["id"], L.OVERLAY, p.state))
        ctx.check("overlay.json: the composed overlay and the writes it made",
                  {k: v for k, v in overlay.items() if k != "changes"} == data["overlay"]
                  and overlay["changes"] == data["apply"]["changes"] == e["changes"])
        md = L.text_of(e["id"], L.EXPERIENCE, p.state)
        lines = md.splitlines()
        ctx.check(f"the title, got {lines[0]!r}", lines[0] == "# adopted the invariant candidate")
        ctx.check("the lesson is the judge's why", lines[lines.index("## Lessons") + 1] == "- " + " ".join(data["judge"]["why"].split()))
        evidence = lines[lines.index("## Evidence") + 1:lines.index("## Files")]
        ctx.check(f"the evidence: the compose line, then the contrast lines, got {evidence}", evidence[0].startswith("- adopted the")
                  and len(evidence) == 1 + len(data["contrast"]) and all("ranked" in x and "steps" in x for x in evidence[1:]))
        ok, msg, _ = R.undo(row["apply_id"], p.state)
        ctx.check(f"the group's Undo marks it undone, got {msg!r}", ok and L.read(e["id"], p.state)["undone"] is True)


@test
def test_the_remote_path_rule_and_the_files_path_check(ctx: Ctx):
    from halo_harness.orchestra.coach_experience import remote_path
    from halo_harness.orchestra.coach_library import safe_rel, valid_id
    cases = {"https://user:secret@github.com/o/r.git": "github.com/o/r", "git@github.com:o/r.git": "github.com/o/r",
             "ssh://git@host.example:2222/team/r.git": "host.example/team/r", "https://github.com/o/r?token=x#y": "github.com/o/r",
             "/srv/git/r.git": "srv/git/r", "": ""}
    got = {k: remote_path(k) for k in cases}
    ctx.check(f"every remote as a path only, got {got}", got == cases)
    ctx.check("files/ takes relative posix paths only", safe_rel("agents/x.yaml") == "agents/x.yaml"
              and safe_rel("../x") is None and safe_rel("/etc/x") is None and safe_rel("C:/x") is None and safe_rel("") is None)
    ctx.check("the id shape", valid_id("e-20261020-0a1f") and not valid_id("e-2026-0a1f") and not valid_id("../e"))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="coach library tests"))
