"""tests.test_knowledge_store -- Halo 3.1.8.0 R4: the knowledge store
(knowledge/store.py, knowledge/frontmatter.py), `halo knowledge`
(knowledge/cli.py) and the agents' tools (tools/knowledge.py):

1. write -> `<state>/knowledge/<kind>/<yyyy-mm>/<id>.md` with its front matter
   (id, kind, title, when, by, run, repo, evidence, confidence | alternatives,
   tags) and body, and `<id>._meta.json` in a pack memory entry's shape; read
   gives it back; an id is never overwritten; what a write refuses;
2. confidence: checked when an evidence line names a test run or a
   reproduction, else said;
3. supersede writes a new entry naming the old (the old one is never edited,
   listed as superseded, left out of `current`); forget removes both files;
4. `halo knowledge add|list|show|search|supersede|forget --json`, exit codes;
5. the `knowledge_add` / `knowledge_search` tools: in the registry and the
   tool list, always allowed, by `agent:<session>/<agent>`, the search answer
   tells the agent to cite the id.
No model call. Run: python -m tests.test_knowledge_store
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

ensure_scoped_state_dir_once()
test, TESTS = new_registry()


def _state() -> Path:
    return Path(tempfile.mkdtemp(prefix="know-store-")) / ".halo"


@test
def test_write_read_the_front_matter_and_the_meta(ctx: Ctx):
    from halo_harness.knowledge import store as S
    state = _state()
    e = S.write("finding", "basket.py#total rounds half up", body="What: total() rounds.\n\nWhy: the test says so.",
                evidence=["tests: `python -m pytest -q` exit 0, 12 passed"], by="gate", run="20261024-090000-b0b1",
                repo="basket", tags=["Orchestra", "gate"], state_dir=state)
    path = Path(e["path"])
    ctx.check(f"the file lives under <kind>/<yyyy-mm>/<id>.md, got {path}", S.valid_id(e["id"]) and e["id"].startswith("f-")
              and path.name == f"{e['id']}.md" and path.parent.name == f"{e['id'][2:6]}-{e['id'][6:8]}"
              and path.parent.parent == state / "knowledge" / "finding")
    front, body = S.parse(path.read_text(encoding="utf-8"))
    ctx.check(f"the front matter, got {sorted(front)}", list(front) == ["id", "kind", "title", "when", "by", "run", "repo",
                                                                       "evidence", "confidence", "tags"]
              and front["by"] == "gate" and front["tags"] == ["orchestra", "gate"] and front["when"].endswith("Z"))
    ctx.check("the body after it", body == "What: total() rounds.\n\nWhy: the test says so.")
    meta = json.loads(S.meta_path(path).read_text(encoding="utf-8"))
    ctx.check(f"_meta.json in the pack memory shape, got {meta}", sorted(meta) == ["retention", "run", "shared", "source",
                                                                                  "stage", "written"]
              and meta["source"] == "gate" and meta["run"] == "20261024-090000-b0b1" and meta["retention"] == "keep")
    back = S.read(e["id"], state)
    ctx.check("read gives it back", back["title"] == e["title"] and back["evidence"] == e["evidence"] and not back["read_only"])
    d = S.write("decision", "money is Decimal", alternatives=["float", "int cents"], by="agent:abcd1234/main", state_dir=state)
    ctx.check("a decision carries alternatives, no confidence", d["alternatives"] == ["float", "int cents"]
              and d["confidence"] == "" and d["id"].startswith("d-"))

    def refused(**kw) -> str:
        try:
            S.write(**dict({"kind": "finding", "title": "t", "state_dir": state}, **kw))
        except S.KnowledgeError as err:
            return str(err)
        return ""
    ctx.check("never over an id that is here", "never overwritten" in refused(eid=e["id"]))
    ctx.check("a kind, a title and a by it knows", "finding or a decision" in refused(kind="note")
              and "needs a title" in refused(title="  ") and "by is one of" in refused(by="a-person"))
    ctx.check("an id of the other kind is refused", "is not a finding id" in refused(eid="d-20261024-abcdef"))


@test
def test_confidence_checked_or_said(ctx: Ctx):
    from halo_harness.knowledge.frontmatter import confidence
    ctx.check("a test run line", confidence(["tests: `npm test` exit 1, 3 passed"]) == "checked")
    ctx.check("a reproduction line", confidence(["reproduction: `curl -sI localhost:8080` exit 0 -- 200 OK"]) == "checked")
    ctx.check("a test runner's command", confidence(["ran python -m pytest -q: 12 passed"]) == "checked")
    ctx.check("none run, a read, no evidence: said", confidence(["tests: none run", "read basket.py:40"]) == "said"
              and confidence([]) == "said")


@test
def test_supersede_and_forget(ctx: Ctx):
    from halo_harness.knowledge import store as S
    state = _state()
    old = S.write("finding", "total() uses ROUND_DOWN", evidence=["read basket.py:12"], run="r1", repo="basket", state_dir=state)
    text_before = Path(old["path"]).read_text(encoding="utf-8")
    new = S.supersede(old["id"], "total() uses ROUND_HALF_UP", evidence=["tests: `pytest` exit 0, 5 passed"], state_dir=state)
    ctx.check("a new entry of the old kind naming it, its run and repo kept", new["supersedes"] == old["id"]
              and new["kind"] == "finding" and new["run"] == "r1" and new["repo"] == "basket")
    ctx.check("the old file is never edited", Path(old["path"]).read_text(encoding="utf-8") == text_before)
    rows = {r["id"]: r for r in S.entries(state)}
    ctx.check("listed as superseded, left out of current", rows[old["id"]]["superseded_by"] == new["id"]
              and [r["id"] for r in S.current(state)] == [new["id"]])
    try:
        S.supersede(old["id"], "again", state_dir=state)
        again = ""
    except S.KnowledgeError as err:
        again = str(err)
    ctx.check("superseding it twice points at the newer one", f"supersede {new['id']} instead" in again)
    ctx.check("forget removes the file and its _meta.json", S.forget(new["id"], state) and not Path(new["path"]).exists()
              and not S.meta_path(new["path"]).exists() and S.read(new["id"], state) is None)
    ctx.check("forgetting what is not here is False", S.forget(new["id"], state) is False and S.forget("x", state) is False)


def _cli(argv, stdin: str = "") -> "tuple[int, str, str]":
    from halo_harness.knowledge.cli import cmd_knowledge
    out, err = io.StringIO(), io.StringIO()
    saved = sys.stdin
    sys.stdin = io.StringIO(stdin)
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                rc = cmd_knowledge(argv)
            except SystemExit as e:
                rc = int(e.code or 0)
    finally:
        sys.stdin = saved
    return rc, out.getvalue(), err.getvalue()


@test
def test_the_cli(ctx: Ctx):
    saved = {k: os.environ.get(k) for k in ("BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR")}
    os.environ["BRIDGE_TEST_HOME"] = tempfile.mkdtemp(prefix="know-cli-")
    os.environ.pop("BRIDGE_STATE_DIR", None)
    try:
        rc, out, _ = _cli(["add", "decision", "use Decimal for money", "--body", "-", "--alternative", "float",
                           "--evidence", "read basket.py:3", "--tag", "money", "--json"], "What: Decimal. Why: floats drift.")
        e = json.loads(out)["entry"] if rc == 0 else {}
        ctx.check(f"add writes by user, the body from stdin, got {rc}", rc == 0 and e["by"] == "user"
                  and e["body"] == "What: Decimal. Why: floats drift." and e["alternatives"] == ["float"])
        rc, out, _ = _cli(["supersede", e["id"], "use Decimal with ROUND_HALF_UP", "--json"])
        new = json.loads(out)["entry"]["id"] if rc == 0 else ""
        rc, out, _ = _cli(["list"])
        ctx.check(f"list leaves the superseded one out, got {out!r}", rc == 0 and new in out and e["id"] not in out)
        rc, out, _ = _cli(["list", "--all"])
        ctx.check("--all shows it, marked", f"(superseded by {new})" in out)
        rc, out, _ = _cli(["show", e["id"]])
        ctx.check(f"show prints the entry and who reused it, got {out!r}", rc == 0 and "alternatives:\n    - float" in out
                  and f"superseded by {new}" in out and "reused by: no agent task cited it yet" in out)
        rc, out, _ = _cli(["search", "ROUND_HALF_UP", "--json"])
        ctx.check(f"search finds the new one by its words, got {out}", rc == 0 and json.loads(out)["hits"][0]["id"] == new)
        ctx.check("an unknown id exits 1", _cli(["show", "d-20000101-000000"])[0] == 1)
        rc, out, _ = _cli(["forget", new, "--json"])
        ctx.check("forget", rc == 0 and json.loads(out)["forgotten"] == new)
        ctx.check("no verb exits 2", _cli([])[0] == 2)
    finally:
        for k, v in saved.items():
            os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)


@test
def test_the_tools(ctx: Ctx):
    from halo_harness.permissions import PermissionEngine
    from halo_harness.tools.base import ToolContext
    from halo_harness.tools.registry import ToolRegistry, known_tool_names
    saved = {k: os.environ.get(k) for k in ("BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR")}
    os.environ["BRIDGE_TEST_HOME"] = tempfile.mkdtemp(prefix="know-tool-")
    os.environ.pop("BRIDGE_STATE_DIR", None)
    try:
        reg = ToolRegistry()
        ctx.check("both tools are in the registry and the tool list", {"knowledge_add", "knowledge_search"} <= set(reg.names())
                  and {"knowledge_add", "knowledge_search"} <= set(known_tool_names()))
        ctx.check("search is read-only", reg.is_read_only("knowledge_search") and not reg.is_read_only("knowledge_add"))
        cwd = Path(tempfile.mkdtemp(prefix="basket-"))
        tctx = ToolContext(cwd=cwd, session_dir=cwd / "sessions" / "3f2a1b9c0d4e5f60" / "subagents" / "agent-a1")
        res = reg.dispatch("knowledge_add", {"kind": "finding", "title": "basket.py#total passes",
                                             "evidence": ["`python -m pytest -q` exit 0, 5 passed"]}, tctx)
        ctx.check(f"knowledge_add saves it, got {res.content!r}", not res.is_error and "Saved finding f-" in str(res.content)
                  and "confidence checked" in str(res.content))
        from halo_harness.knowledge.store import entries
        e = entries()[0]
        ctx.check(f"by the agent, the repo the folder, got {e['by']} {e['repo']}", e["by"] == "agent:3f2a1b9c/a1"
                  and e["repo"] == cwd.name)
        bad = reg.dispatch("knowledge_add", {"kind": "rumor", "title": "x"}, tctx)
        ctx.check("a kind it does not know is an error with the reason", bad.is_error and "finding or a decision" in str(bad.content))
        found = str(reg.dispatch("knowledge_search", {"query": "basket total"}, tctx).content)
        ctx.check(f"knowledge_search lists it with the cite line, got {found!r}", f"- {e['id']} (finding, agent:3f2a1b9c/a1, "
                  in found and "cite its id in your answer" in found)
        engine = PermissionEngine(mode="default", cwd=cwd)
        ctx.check("always allowed, like TodoWrite", all(engine.decide(n, {}, reg.get(n)).action == "allow"
                                                        for n in ("knowledge_add", "knowledge_search")))
    finally:
        for k, v in saved.items():
            os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
