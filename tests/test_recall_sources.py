"""tests.test_recall_sources -- Halo 3.1.8.0 R4: the owner's own notes as a
recall source (`recall.sources`, knowledge/sources.py, recall.build_index,
`halo recall sources`), on the fake embedder, over a vault folder outside the
home (an Obsidian vault is one; the user named it, so no grant is asked):

1. every `.md` file under the folder is indexed as kind `note`, its front
   matter stripped from the embedded text, its title the front matter's
   `title`, else its first `# ` heading, else its file name; `.obsidian/` and
   every other dot-folder are skipped, a non-Markdown file too;
2. the vault is never written: every file's bytes and mtime and the folder's
   listing are the same after a build and a search;
3. an unchanged vault embeds nothing; a note that vanished is pruned, and so
   is every note of a folder taken out of `recall.sources`;
4. `halo recall sources` lists the folders with their note counts (`--json`;
   a folder that is not there says so); a hit shows the [note] chip; `~` is
   your home.
No model and no embedding model is called. Run: python -m tests.test_recall_sources
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

from tests.helpers.provider_env_defaults import ensure_scoped_state_dir_once  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402
from tests.helpers import knowledge_rig as K  # noqa: E402

ensure_scoped_state_dir_once()
test, TESTS = new_registry()


def _vault() -> Path:
    v = Path(tempfile.mkdtemp(prefix="vault-")) / "Notes vault"
    (v / "kitchen").mkdir(parents=True)
    (v / ".obsidian").mkdir()
    (v / ".trash").mkdir()
    (v / "soup.md").write_text("---\ntitle: Tomato soup\ntags: [recipe]\naliases: [soup]\n---\n# Ignored heading\n"
                               "tomatoes, basil, a pinch of salt; simmer the soup.\n", encoding="utf-8")
    (v / "kitchen" / "bread.md").write_text("Some words first.\n# Garden bread\nflour and garden herbs\n", encoding="utf-8")
    (v / "kitchen" / "kali-box.md").write_text("drum kit notes for the kali box\n", encoding="utf-8")
    (v / ".obsidian" / "workspace.md").write_text("# workspace\nobsidian vault settings\n", encoding="utf-8")
    (v / ".trash" / "old.md").write_text("# Old\nobsidian vault trash\n", encoding="utf-8")
    (v / "kitchen" / "photo.txt").write_text("not markdown, soup", encoding="utf-8")
    return v


def _snapshot(folder: Path) -> dict:
    out = {}
    for dirpath, dirnames, filenames in os.walk(folder):
        out[dirpath] = sorted(dirnames)
        for f in filenames:
            p = Path(dirpath) / f
            out[str(p)] = (p.read_bytes(), p.stat().st_mtime_ns)
    return out


@test
def test_a_vault_is_indexed_as_notes(ctx: Ctx):
    from halo_harness import recall
    with K.home() as state, K.embedder() as fake:
        vault = _vault()
        K.config(state, **{"recall.sources": [str(vault)]})
        before = _snapshot(vault)
        report = recall.build_index(state, cwd=state)
        index = recall._load_index(recall._index_path(state))
        notes = {Path(i).relative_to(vault).as_posix(): e for i, e in index.items() if e["kind"] == "note"}
        ctx.check(f"three notes, the dot-folders and the .txt left out, got {sorted(notes)} {report}",
                  sorted(notes) == ["kitchen/bread.md", "kitchen/kali-box.md", "soup.md"])
        ctx.check(f"titles: front matter, then the first heading, then the file name, got "
                  f"{[notes[k]['title'] for k in sorted(notes)]}", notes["soup.md"]["title"] == "Tomato soup"
                  and notes["kitchen/bread.md"]["title"] == "Garden bread" and notes["kitchen/kali-box.md"]["title"] == "kali-box")
        soup = next((t for t in fake.texts if t.startswith("Tomato soup\n")), "")
        ctx.check(f"the front matter is stripped from the embedded text, got {soup!r}", soup and "aliases" not in soup
                  and "title:" not in soup and "simmer the soup" in soup)
        hits = recall.search("tomatoes soup recipe", state_dir=state)
        ctx.check(f"search finds it as a note, got {[(h['kind'], h['title']) for h in hits[:2]]}", hits
                  and hits[0]["kind"] == "note" and hits[0]["title"] == "Tomato soup")
        ctx.check("the vault is never written", _snapshot(vault) == before)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            from halo_harness.recall_cli import cmd_recall
            cmd_recall(["tomatoes", "soup"])
        ctx.check(f"halo recall shows the [note] chip and the file, got {out.getvalue()!r}",
                  f"[note] Tomato soup  ({vault / 'soup.md'})" in out.getvalue())


@test
def test_incremental_and_pruned(ctx: Ctx):
    from halo_harness import recall
    with K.home() as state, K.embedder() as fake:
        vault = _vault()
        K.config(state, **{"recall.sources": [str(vault)]})
        recall.build_index(state, cwd=state)
        calls = fake.calls
        again = recall.build_index(state, cwd=state)
        ctx.check(f"an unchanged vault embeds nothing, got {again}", again["embedded"] == 0 and fake.calls == calls)
        (vault / "kitchen" / "bread.md").unlink()
        gone = recall.build_index(state, cwd=state)
        index = recall._load_index(recall._index_path(state))
        ctx.check(f"a note that vanished is pruned, got {gone}", gone["pruned"] == 1
                  and str(vault / "kitchen" / "bread.md") not in index)
        K.config(state, **{"recall.sources": []})
        out = recall.build_index(state, cwd=state)
        index = recall._load_index(recall._index_path(state))
        ctx.check(f"a folder taken out of recall.sources: its notes are pruned, its files kept, got {out}",
                  out["pruned"] == 2 and not any(e["kind"] == "note" for e in index.values()) and (vault / "soup.md").exists())


@test
def test_halo_recall_sources_and_the_home(ctx: Ctx):
    from halo_harness.knowledge.sources import configured
    from halo_harness.recall_cli import cmd_recall
    with K.home() as state:
        vault = _vault()
        (state.parent / "notes").mkdir()
        (state.parent / "notes" / "a.md").write_text("# A\n", encoding="utf-8")
        K.config(state, **{"recall.sources": [str(vault), "~/notes", str(vault.parent / "gone")]})
        ctx.check(f"~ is your home, got {configured()}", configured()[1] == state.parent / "notes")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = cmd_recall(["sources", "--json"])
        rows = json.loads(out.getvalue())["sources"]
        ctx.check(f"each folder with its note count, got {rows}", rc == 0 and [r["notes"] for r in rows] == [3, 1, 0]
                  and [r["exists"] for r in rows] == [True, True, False])
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            cmd_recall(["sources"])
        ctx.check(f"the table says which is not there, got {out.getvalue()!r}", "  (not there)" in out.getvalue()
                  and f"     3 notes  {vault}" in out.getvalue())
        K.config(state, **{"recall.sources": "~/notes"})
        ctx.check("one folder as a string", configured() == [state.parent / "notes"])


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
