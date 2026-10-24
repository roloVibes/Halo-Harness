"""tests.test_knowledge_recall -- Halo 3.1.8.0 R4: recall knows findings and
decisions (knowledge/sources.py, recall.build_index / search, recall_cli,
/recall, recall_fleet, Studio's recall route), on the fake embedder:

1. build_index indexes every current entry as kind `finding` / `decision`
   beside memory; search ranks them and carries the kind; the incremental
   rule holds (an unchanged tree embeds nothing); a superseded entry and a
   forgotten one are pruned;
2. `rank_memory_topics` stays memory-only;
3. `halo recall`, the print-mode `/recall` and the TUI's worker show the
   [finding] / [decision] chips with the id, who and when; a fleet hit and
   Studio's `GET /api/recall` carry `ref`, `by` and `when`;
4. knowledge.search: through recall when embeddings are on, the word match
   when they are off.
No model and no embedding model is called. Run: python -m tests.test_knowledge_recall
"""
from __future__ import annotations

import contextlib
import io
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_scoped_state_dir_once  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402
from tests.helpers import knowledge_rig as K  # noqa: E402

ensure_scoped_state_dir_once()
test, TESTS = new_registry()


def _seed(state: Path) -> dict:
    """A memory topic (through the settings chain) and one finding and one decision."""
    from halo_harness.knowledge import store as S
    mem = state.parent / "memory-topics"
    mem.mkdir(parents=True, exist_ok=True)
    (mem / "drum.md").write_text("# Drum practice\ndrum rudiments on the kali box", encoding="utf-8")
    settings = state.parent / ".claude" / "settings.json"
    settings.parent.mkdir(parents=True, exist_ok=True)
    settings.write_text(json.dumps({"autoMemoryDirectory": str(mem)}), encoding="utf-8")
    f = S.write("finding", "basket total rounds half up with decimal", evidence=["tests: `pytest -q` exit 0, 5 passed"],
                by="gate", run="r1", repo="basket", state_dir=state)
    d = S.write("decision", "money is decimal, never float", alternatives=["float"], by="supervisor", state_dir=state)
    return {"finding": f, "decision": d, "memory": str(mem / "drum.md")}


@test
def test_indexed_searched_incremental_and_pruned(ctx: Ctx):
    from halo_harness import recall
    from halo_harness.knowledge import store as S
    with K.home() as state, K.embedder() as fake:
        seeded = _seed(state)
        report = recall.build_index(state, cwd=state)
        index = recall._load_index(recall._index_path(state))
        kinds = {e["kind"] for e in index.values()}
        ctx.check(f"memory, finding and decision indexed, got {sorted(kinds)} {report}", {"memory", "finding", "decision"} <= kinds
                  and index[seeded["finding"]["path"]]["kind"] == "finding"
                  and index[seeded["decision"]["path"]]["title"] == "money is decimal, never float")
        hits = recall.search("basket total decimal", state_dir=state)
        ctx.check(f"the finding ranks first with its kind, got {[(h['kind'], h['title']) for h in hits[:3]]}",
                  hits and hits[0]["kind"] == "finding" and hits[0]["id"] == seeded["finding"]["path"])
        before = fake.calls
        again = recall.build_index(state, cwd=state)
        ctx.check(f"an unchanged tree embeds nothing, got {again}", again["embedded"] == 0 and fake.calls == before)
        new = S.supersede(seeded["finding"]["id"], "basket total rounds half up, checked again", state_dir=state)
        third = recall.build_index(state, cwd=state)
        index = recall._load_index(recall._index_path(state))
        ctx.check(f"the superseded entry is pruned, the new one embedded, got {third}", third["pruned"] == 1
                  and third["embedded"] == 1 and seeded["finding"]["path"] not in index and new["path"] in index)
        S.forget(seeded["decision"]["id"], state)
        fourth = recall.build_index(state, cwd=state)
        ctx.check("a forgotten entry is pruned", fourth["pruned"] == 1
                  and seeded["decision"]["path"] not in recall._load_index(recall._index_path(state)))


@test
def test_rank_memory_topics_stays_memory_only(ctx: Ctx):
    from halo_harness import recall
    with K.home() as state, K.embedder():
        seeded = _seed(state)
        ranked = recall.rank_memory_topics("drum basket total decimal money", state_dir=state)
        ctx.check(f"only memory topic ids, got {ranked}", ranked and all(Path(r).name == "drum.md" for r in ranked)
                  and seeded["finding"]["path"] not in ranked)


@test
def test_shown_with_their_kinds_everywhere(ctx: Ctx):
    from halo_harness import recall_fleet as RF
    from halo_harness.commands.builtins import _cmd_recall
    from halo_harness.recall_cli import cmd_recall
    from halo_harness.studio.recall_api import get_recall
    with K.home() as state, K.embedder():
        seeded = _seed(state)
        f, d = seeded["finding"], seeded["decision"]
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = cmd_recall(["basket", "total", "money", "decimal"])
        text = out.getvalue()
        ctx.check(f"halo recall: the chips with id, by and when, got {text!r}", rc == 0
                  and f"[finding] {f['title']}  ({f['id']}, gate, {f['when'][:10]})" in text
                  and f"[decision] {d['title']}  ({d['id']}, supervisor, " in text)
        printed = _cmd_recall("basket total", type("F", (), {"session": None})())
        ctx.check("the print-mode /recall shows the same chip", f"[finding] {f['title']}  ({f['id']}, gate," in printed)
        hits, _note = RF.local_hits("basket total decimal", 8, state)
        top = next((h for h in hits if h["kind"] == "finding"), {})
        ctx.check(f"a recall hit as the fleet sees it carries ref, by and when, got {top}", top.get("ref") == f["id"]
                  and top.get("by") == "gate" and top.get("when") == f["when"] and top.get("confidence") == "checked")
        req = type("Req", (), {"query": {"q": "money decimal"}, "state_dir": state, "server": None})()
        status, body = get_recall(req)
        rows = {h["kind"]: h for h in body.get("hits") or []}
        ctx.check(f"Studio's recall route: kind, by and when, got {status} {sorted(rows)}", status == 200
                  and rows.get("decision", {}).get("by") == "supervisor" and rows["decision"].get("ref") == d["id"]
                  and rows["decision"].get("when") == d["when"])


@test
def test_the_tui_worker_uses_the_same_lines(ctx: Ctx):
    from halo_harness.tui import slash
    notes = []
    app = type("App", (), {})()
    app.transcript = type("T", (), {"add_note": lambda self, text, kind="": notes.append(text)})()
    app.call_from_thread = lambda fn, *a, **kw: fn(*a, **kw)
    with K.home() as state, K.embedder():
        f = _seed(state)["finding"]
        slash._recall_worker(app, "basket total", None)
    ctx.check(f"the TUI's /recall note has the finding chip, got {notes}", notes
              and f"[finding] {f['title']}  ({f['id']}, gate," in notes[0])


@test
def test_knowledge_search_through_recall_or_the_words(ctx: Ctx):
    from halo_harness.knowledge.search import search
    with K.home() as state:
        seeded = _seed(state)
        words = search("money float", state_dir=state)
        ctx.check(f"embeddings off: the word match, got {words}", words and words[0]["id"] == seeded["decision"]["id"]
                  and words[0]["via"] == "words")
        with K.embedder():
            ranked = search("basket total", state_dir=state)
        ctx.check(f"embeddings on: through recall, only the knowledge kinds, got {ranked}",
                  ranked and ranked[0]["via"] == "recall" and ranked[0]["id"] == seeded["finding"]["id"]
                  and all(h["kind"] in ("finding", "decision") for h in ranked))
        only = search("basket money decimal", kinds=("decision",), state_dir=state)
        ctx.check("a kind keeps to that kind", only and all(h["kind"] == "decision" for h in only))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
