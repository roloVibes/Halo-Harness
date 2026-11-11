"""tests.test_knowledge_relevance -- knowledge that answers the question (Halo 3.3.16.2, "from a session's own
review": a search for "halo harness update new features version" came back with 4 of 5 hits gate records of the
guided first run's sample repo, matched on the tool venv's python path in their test command):

(a) the sample's records are tagged sample and never answer a search from another project; the start card
    says what it writes to your knowledge;
(b) relevance first (paths and commands are not words a record says; no shared content word, no hit), this
    project first at equal relevance, another project's marked; a passed gate ranks under findings unless the
    query names its unit; a failed gate keeps its rank; re-runs collapse to the newest with "x N";
(c) each hit says why it is there;
(d) `halo knowledge list --kind gate --project`, `prune --older-than ... [--dry-run] [--yes]`, `forget`, and the
    cap on passed-gate records per project (`knowledge.gate_keep`).
The owner's exact scenario is the first test. No model call. Run: python -m tests.test_knowledge_relevance
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
PY = "/home/kali/.local/share/uv/tools/halo-harness/bin/python"
QUERY = "halo harness update new features version"


def _state() -> Path:
    base = os.environ.get("BRIDGE_TEST_HOME") or None
    return Path(tempfile.mkdtemp(prefix="know-rel-", dir=base)) / ".halo"


def _gate(state, unit: str, sha: str, when: str, repo: str = "basket", tags=("orchestra", "gate")):
    from halo_harness.knowledge.store import write
    return write("finding", f"{unit} passes `\"{PY}\" -m unittest -q test_basket` at {sha}", by="gate", repo=repo,
                 evidence=[f"tests: `\"{PY}\" -m unittest -q test_basket` exit 0"], tags=list(tags), when=when,
                 body=f"What: lane 1's piece is merged.\n\nWhere: orchestra/run1 at {sha}; the units {unit}.",
                 run="run1", state_dir=state)


def _owner_store(state):
    """As the owner's was: findings about Halo, and the basket gate records of a `halo start` run (before
    3.3.16.2, so not tagged sample: its folder under <state>/start/<day>/ is what marks it)."""
    from halo_harness.knowledge.store import write
    (state / "start" / "2026-11-09" / "basket").mkdir(parents=True)
    ids = [write("finding", "Halo 3.3.16 adds workflow squares and the Workflow tool", by="agent:s1", repo="",
                 body="New features in this version: squares, the router, receipts.", when="2026-11-08T10:00:00Z",
                 state_dir=state)["id"],
           write("decision", "update the harness with halo update before a release check", by="user", repo="",
                 when="2026-11-07T10:00:00Z", state_dir=state)["id"]]
    for i, unit in enumerate(("basket.py#apply_discount", "basket.py#total", "basket.py#subtotal", "basket.py#add_item")):
        _gate(state, unit, f"{i}abcdef12345", f"2026-11-09T1{i}:00:00Z")
    return ids


@test
def test_the_owners_search_returns_the_halo_findings_and_no_basket_gate(ctx: Ctx):
    from halo_harness.knowledge.search import search
    state = _state()
    halo_ids = _owner_store(state)
    other = state.parent / "work" / "Halo-Harness"
    (other / ".git").mkdir(parents=True)
    hits = search(QUERY, k=5, state_dir=state, cwd=other)
    ctx.check(f"no basket gate record comes back, got {[h['title'][:40] for h in hits]}",
              not any("basket" in h["title"] for h in hits))
    ctx.check(f"the Halo findings do, got {[h['id'] for h in hits]}", set(halo_ids) <= {h["id"] for h in hits})
    ctx.check(f"each says why, got {[h['why'] for h in hits]}", all(h["why"] and "words:" in h["why"] for h in hits))
    sample = state.parent / "work2" / "basket"
    (sample / ".git").mkdir(parents=True)
    hits = search("apply_discount total", k=5, state_dir=state, cwd=sample)
    ctx.check(f"from the sample repo itself they answer, got {[h['title'][:30] for h in hits]}",
              any(h["title"].startswith("basket.py#apply_discount") for h in hits))


@test
def test_relevance_first_scope_gates_and_duplicates(ctx: Ctx):
    from halo_harness.knowledge.rank import content_words
    from halo_harness.knowledge.search import search
    from halo_harness.knowledge.store import write
    state = _state()
    ctx.check(f"a path and a sha are not words a record says, got {sorted(content_words(PY + ' at 0abc1234 fixed'))}",
              content_words(f"`{PY}` at 0abc1234 fixed") == {"fixed"})
    write("finding", "the parser drops trailing commas", by="user", repo="api", when="2026-11-01T00:00:00Z", state_dir=state)
    write("finding", "the parser keeps trailing commas in lists", by="user", repo="web", when="2026-11-02T00:00:00Z",
          state_dir=state)
    write("finding", "deploy notes for the release", by="user", repo="api", when="2026-11-09T00:00:00Z", state_dir=state)
    here = state.parent / "api"
    (here / ".git").mkdir(parents=True)
    hits = search("parser trailing commas", k=5, state_dir=state, cwd=here)
    ctx.check(f"no shared word, no hit, however new, got {[h['title'] for h in hits]}",
              all("deploy" not in h["title"] for h in hits) and len(hits) == 2)
    ctx.check(f"equal relevance: this project first, the other marked, got {[(h['project'], h['why']) for h in hits]}",
              hits[0]["project"] == "api" and "this project" in hits[0]["why"] and "project web" in hits[1]["why"])
    _gate(state, "parser.py#parse", "aaaaaaa1111", "2026-11-09T01:00:00Z", repo="api")
    _gate(state, "parser.py#parse", "bbbbbbb2222", "2026-11-09T02:00:00Z", repo="api")
    _gate(state, "parser.py#parse", "ccccccc3333", "2026-11-09T03:00:00Z", repo="api")
    write("decision", "lane 1 sent back: parser.py#parse fails test_parser", by="gate", repo="api",
          when="2026-11-09T04:00:00Z", state_dir=state)
    hits = search("commas fails merged", k=5, state_dir=state, cwd=here)  # "merged" is in a gate's body
    ids = [h["title"][:30] for h in hits]
    ctx.check(f"a failed gate keeps its rank, got {ids}", hits[0]["title"].startswith("lane 1 sent back"))
    gates = [h for h in hits if " passes " in h["title"]]
    ctx.check(f"re-runs collapse to the newest, x3, under the findings, got {[(h['title'][-12:], h['n'], h['why']) for h in gates]}",
              len(gates) == 1 and gates[0]["n"] == 3 and gates[0]["title"].endswith("ccccccc3333")
              and "x3 (re-run)" in gates[0]["why"] and "a passed gate, ranked under findings" in gates[0]["why"]
              and hits.index(gates[0]) > [h["title"] for h in hits].index("the parser drops trailing commas"))
    hits = search("parse passes", k=5, state_dir=state, cwd=here)
    ctx.check(f"a query naming the gate's symbol keeps its rank, got {[h['why'] for h in hits]}",
              " passes " in hits[0]["title"] and "ranked under" not in hits[0]["why"])


def _cli(*argv, cwd=None) -> "tuple[int, str]":
    from halo_harness.knowledge.cli import cmd_knowledge
    out = io.StringIO()
    old = Path.cwd()
    try:
        if cwd:
            os.chdir(cwd)
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            code = cmd_knowledge(list(argv))
    finally:
        os.chdir(old)
    return code, out.getvalue()


@test
def test_list_prune_forget_and_the_cap(ctx: Ctx):
    from halo_harness.knowledge import curate
    from halo_harness.knowledge.store import current, write
    state = Path(os.environ["BRIDGE_TEST_HOME"]) / ".halo-curate"
    os.environ["BRIDGE_STATE_DIR"] = str(state)
    try:
        old = [_gate(state, f"m.py#f{i}", f"{i}0000000aaa", "2026-10-01T00:00:00Z", repo="proj") for i in range(3)]
        _gate(state, "m.py#g", "9999999bbbb", "2099-01-01T00:00:00Z", repo="proj")
        keep = write("finding", "a finding to keep", by="user", repo="proj", when="2026-10-01T00:00:00Z", state_dir=state)
        code, out = _cli("list", "--kind", "gate", "--project", "proj")
        ctx.check(f"list --kind gate --project: the four gate records, got {out!r}", code == 0 and out.count(" passes ") == 4)
        code, out = _cli("prune", "--kind", "gate", "--older-than", "7d")
        ctx.check(f"prune without --yes: what it would remove and the count, nothing removed, got {out!r}",
                  code == 0 and out.startswith("would remove 3 gate entries older than 7d") and "add --yes" in out
                  and len(current(state)) == 5)
        code, out = _cli("prune", "--kind", "gate", "--older-than", "7d", "--yes", "--dry-run")
        ctx.check("--dry-run wins over --yes", "dry run: nothing removed" in out and len(current(state)) == 5)
        code, out = _cli("prune", "--kind", "gate", "--older-than", "7d", "--yes")
        left = {e["id"] for e in current(state)}
        ctx.check(f"--yes removes them, the finding stays, got {out!r}", "removed 3" in out
                  and not ({e["id"] for e in old} & left) and keep["id"] in left)
        code, out = _cli("forget", keep["id"])
        ctx.check("forget one", code == 0 and keep["id"] not in {e["id"] for e in current(state)})
        code, _out = _cli("prune", "--kind", "gate", "--older-than", "soon")
        ctx.check("a bad age is a usage error", code == 2)
        for i in range(5):
            _gate(state, f"c.py#h{i}", f"{i}1111111ccc", f"2026-11-0{i + 1}T00:00:00Z", repo="capped")
        gone = curate.cap_passed_gates("capped", state_dir=state, keep=2)
        mine = [e for e in current(state) if e["repo"] == "capped"]
        ctx.check(f"the cap keeps the newest two, got {[e['title'][:8] for e in mine]} gone {len(gone)}",
                  len(gone) == 3 and sorted(e["title"][:7] for e in mine) == ["c.py#h3", "c.py#h4"])
        (state / "config.json").write_text(json.dumps({"knowledge": {"gate_keep": 7}}), encoding="utf-8")
        ctx.check(f"knowledge.gate_keep is the default cap, got {curate.gate_keep()}", curate.gate_keep() == 7)
    finally:
        os.environ.pop("BRIDGE_STATE_DIR", None)


@test
def test_the_sample_run_tags_what_it_writes_and_the_card_says_so(ctx: Ctx):
    from halo_harness.config.paths import bridge_home
    from halo_harness.knowledge import writers as W
    from halo_harness.start.sample_repo import start_root
    run_dir = start_root(bridge_home()) / "2026-11-10" / "basket" / ".halo" / "orchestra" / "run1"
    run_dir.mkdir(parents=True)
    ctx.check(f"a run in the sample repo is the sample, got {W._sample(run_dir)}",
              W._sample(run_dir) == {"tags": ["sample"], "meta": {"sample": True}})
    mine = Path(tempfile.mkdtemp(dir=os.environ.get("BRIDGE_TEST_HOME") or None)) / "proj" / ".halo" / "orchestra" / "r"
    mine.mkdir(parents=True)
    ctx.check("a run in a repo of yours is not", W._sample(mine) == {})
    from halo_harness.knowledge.rank import is_sample
    ctx.check("a record tagged sample is the sample", is_sample({"tags": ["sample"], "by": "user"}))
    from halo_harness.start.card import writes
    text = "\n".join(writes(state_dir=_state(), today="2026-11-10"))
    ctx.check(f"the card says what it writes to your knowledge, got {text!r}",
              "your knowledge: nothing beyond the sample's own gate records, tagged sample" in text)
    ctx.check("a run in your own repo writes no such line", "your knowledge" not in "\n".join(writes(state_dir=_state(), repo="/r")))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
