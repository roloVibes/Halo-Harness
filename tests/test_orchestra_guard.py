"""tests.test_orchestra_guard -- Halo 3.0.3.0 round R1: the claim guard on a
real PermissionEngine (orchestra/guard.py + PermissionEngine.guards) in every
mode: a foreign claim denies and names the holder, no claim asks, your own
claim allows and logs an events line, a deny always stands, a file outside
the goal keeps the base decision, Edit claims only the function it touches,
a worker's worktree path matches; plus the claim tools and their holder,
install_from_env, and the tools' registration inside a run only.
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials, ensure_scoped_state_dir_once
from tests.helpers.runner import Ctx, new_registry, print_results, run_all

ensure_scoped_state_dir_once()
ensure_default_provider_credentials()
from halo_harness import permissions as P  # noqa: E402

test, TESTS = new_registry()
MODES = ("default", "acceptEdits", "plan", "auto", "dontAsk", "bypassPermissions")
BASE = {"default": "ask", "acceptEdits": "allow", "plan": "deny", "auto": "allow", "dontAsk": "deny",
        "bypassPermissions": "allow"}
SRC = "def add_item(b, i):\n    b.append(i)\n\n\ndef total(b):\n    return 0\n"


def _setup():
    from halo_harness.orchestra.goal import Goal, new_run
    repo = Path(tempfile.mkdtemp(prefix="orch-guard-"))
    (repo / "basket.py").write_text(SRC, encoding="utf-8")
    (repo / "other.py").write_text("x = 1\n", encoding="utf-8")
    run = new_run(repo, Goal(what="w", done_when="d", stop_when="s", files=["basket.py"]))
    return repo, run


def _engine(repo, mode, holder, run, **kw):
    from halo_harness.orchestra.guard import ClaimGuard
    eng = P.PermissionEngine(mode=mode, cwd=repo, **kw)
    eng.guards.append(ClaimGuard(run, holder))
    return eng


def _write(repo, name="basket.py"):
    return {"file_path": str(repo / name), "content": "x\n"}


@test
def test_every_mode_foreign_none_own_and_outside(ctx: Ctx):
    from halo_harness.orchestra import events as run_events
    from halo_harness.orchestra.claims import ClaimLog
    for mode in MODES:
        repo, run = _setup()
        me = _engine(repo, mode, "s/me", run)
        outside = me.decide("Write", _write(repo, "other.py"))
        ctx.check(f"{mode}: a file outside the goal keeps the base decision ({outside.action})",
                  outside.action == BASE[mode] and outside.source != "orchestra")
        none = me.decide("Write", _write(repo))
        want_none = "deny" if BASE[mode] == "deny" else "ask"
        ctx.check(f"{mode}: no claim -> {want_none}, got {none.action}: {none.reason}", none.action == want_none)
        if want_none == "ask":
            ctx.check(f"{mode}: the ask says to claim first", "no claim on `basket.py`" in none.reason
                      and "OrchestraClaim" in none.reason)
        log = ClaimLog(run)
        log.claim("s/other", "basket.py#total")
        foreign = me.decide("Write", _write(repo))
        ctx.check(f"{mode}: a foreign claim denies, got {foreign.action}", foreign.action == "deny")
        if BASE[mode] != "deny":
            ctx.check(f"{mode}: the deny names the holder, got {foreign.reason!r}",
                      "`s/other`" in foreign.reason and "basket.py#total" in foreign.reason and "until" in foreign.reason)
        log.release("s/other", "basket.py#total")
        log.claim("s/me", "basket.py")
        before = len(run_events.read(run))
        own = me.decide("Write", _write(repo))
        want_own = "deny" if BASE[mode] == "deny" else "allow"
        ctx.check(f"{mode}: own claim -> {want_own}, got {own.action}", own.action == want_own)
        if want_own == "allow":
            new = run_events.read(run, since=before)
            ctx.check(f"{mode}: an events line for the write", any("writing basket.py" in e["text"] for e in new))
            ctx.check(f"{mode}: the claim is now writing", log.active()["basket.py"].state == "writing")


@test
def test_edit_claims_only_the_function_it_touches(ctx: Ctx):
    from halo_harness.orchestra.claims import ClaimLog
    repo, run = _setup()
    log = ClaimLog(run)
    log.claim("s/other", "basket.py#total")
    log.claim("s/me", "basket.py#add_item")
    eng = _engine(repo, "auto", "s/me", run)
    mine = eng.decide("Edit", {"file_path": str(repo / "basket.py"), "old_string": "b.append(i)", "new_string": "y"})
    ctx.check(f"editing my function is allowed, got {mine.reason}", mine.action == "allow")
    theirs = eng.decide("Edit", {"file_path": str(repo / "basket.py"), "old_string": "return 0", "new_string": "y"})
    ctx.check("editing theirs is denied", theirs.action == "deny" and "s/other" in theirs.reason)
    multi = eng.decide("MultiEdit", {"file_path": str(repo / "basket.py"),
                                      "edits": [{"old_string": "b.append(i)", "new_string": "a"},
                                                {"old_string": "return 0", "new_string": "b"}]})
    ctx.check("a MultiEdit touching both is denied", multi.action == "deny")
    nomatch = eng.decide("Edit", {"file_path": str(repo / "basket.py"), "old_string": "absent", "new_string": "y"})
    ctx.check("an old_string that is not there counts as the whole file", nomatch.action == "deny")
    nb = eng.decide("NotebookEdit", {"notebook_path": str(repo / "other.py"), "new_source": "x"})
    ctx.check("NotebookEdit on a file outside the goal keeps auto's allow", nb.action == "allow")


@test
def test_deny_rule_ask_rule_and_print_mode(ctx: Ctx):
    from halo_harness.orchestra.claims import ClaimLog
    repo, run = _setup()
    ClaimLog(run).claim("s/me", "basket.py")
    deny = P.parse_rule("Write", source="user", base_dir=repo, action="deny")
    eng = _engine(repo, "auto", "s/me", run, deny_rules=[deny])
    ctx.check("a deny rule always stands", eng.decide("Write", _write(repo)).action == "deny")
    ask = P.parse_rule("Write", source="user", base_dir=repo, action="ask")
    eng = _engine(repo, "default", "s/me", run, ask_rules=[ask])
    d = eng.decide("Write", _write(repo))
    ctx.check(f"the user's own ask rule still asks with a claim, got {d.action}", d.action == "ask")
    repo2, run2 = _setup()
    eng = _engine(repo2, "auto", "s/me", run2, print_mode=True)
    d = eng.decide("Write", _write(repo2))
    ctx.check(f"print mode: the guard's ask becomes a deny, got {d.action}",
              d.action == "deny" and "no claim" in d.reason and d.permission_denial is not None)


@test
def test_a_worker_worktree_path_matches(ctx: Ctx):
    from halo_harness.orchestra.claims import ClaimLog
    repo, run = _setup()
    tree = Path(tempfile.mkdtemp(prefix="orch-tree-"))
    shutil.copy(repo / "basket.py", tree / "basket.py")
    ClaimLog(run).claim("s/other", "basket.py#total")
    eng = _engine(tree, "auto", "s/me", run)
    d = eng.decide("Edit", {"file_path": str(tree / "basket.py"), "old_string": "return 0", "new_string": "1"})
    ctx.check("the same file in a worker's worktree is guarded", d.action == "deny")


@test
def test_tools_use_the_guard_holder_and_register_only_in_a_run(ctx: Ctx):
    from halo_harness.orchestra.claims import holder_for
    from halo_harness.orchestra.guard import install_from_env
    from halo_harness.tools import orchestra_claims as T
    from halo_harness.tools.base import ToolContext
    from halo_harness.tools.registry import default_tools
    repo, run = _setup()
    sdir = Path(tempfile.mkdtemp(prefix="orch-sess-")) / "sid9" / "subagents" / "agent-w1"
    tctx = ToolContext(cwd=repo, session_dir=sdir, env={"HALO_ORCHESTRA_RUN": str(run)})
    ctx.check("outside a run the tools are an error",
              T.OrchestraClaimTool().run({"key": "basket.py#total"}, ToolContext(cwd=repo, session_dir=sdir, env={})).is_error
              or os.environ.get("HALO_ORCHESTRA_RUN"))
    r = T.OrchestraClaimTool().run({"key": "basket.py#total"}, tctx)
    ctx.check(f"claim ok, got {r.content!r}", not r.is_error and "sid9/w1" in r.content)
    other = ToolContext(cwd=repo, session_dir=sdir.parent / "agent-w2", env={"HALO_ORCHESTRA_RUN": str(run)})
    refused = T.OrchestraClaimTool().run({"key": "basket.py"}, other)
    ctx.check(f"another worker is refused with what to do, got {refused.content!r}",
              refused.is_error and "sid9/w1" in refused.content and "OrchestraClaims" in refused.content)
    listing = T.OrchestraClaimsTool().run({}, tctx).content
    ctx.check("the listing shows the claim and the units", "basket.py#total" in listing and "(yours)" in listing
              and "basket.py#add_item  lines 1-2" in listing)
    eng = P.PermissionEngine(mode="auto", cwd=repo)
    g = install_from_env(eng, sdir, env={"HALO_ORCHESTRA_RUN": str(run)})
    ctx.check("install_from_env uses the same holder", g is not None and g.holder == holder_for(sdir) == "sid9/w1")
    ctx.check("installing twice adds one guard", install_from_env(eng, sdir, env={"HALO_ORCHESTRA_RUN": str(run)}) is g
              and len(eng.guards) == 1)
    ctx.check("no run -> no guard", install_from_env(eng, sdir, env={}) is None)
    edit = eng.decide("Edit", {"file_path": str(repo / "basket.py"), "old_string": "return 0", "new_string": "1"})
    ctx.check("the claimed function is allowed through the engine", edit.action == "allow")
    note = T.OrchestraNoteTool().run({"text": "total returns 0 for now"}, tctx)
    ctx.check("a note lands in the log", not note.is_error)
    rel = T.OrchestraReleaseTool().run({"key": "basket.py#total"}, tctx)
    ctx.check(f"release ok, got {rel.content!r}", not rel.is_error)
    ctx.check("the four tools are permission-free",
              all(eng.decide(n, {}).action == "allow" for n in ("OrchestraClaim", "OrchestraNote")))
    saved = os.environ.get("HALO_ORCHESTRA_RUN")
    try:
        os.environ.pop("HALO_ORCHESTRA_RUN", None)
        ctx.check("not registered outside a run", "OrchestraClaim" not in {t.name for t in default_tools()})
        os.environ["HALO_ORCHESTRA_RUN"] = str(run)
        names = {t.name for t in default_tools()}
        ctx.check("registered inside a run", {"OrchestraClaim", "OrchestraRelease", "OrchestraClaims",
                                              "OrchestraNote"} <= names)
    finally:
        if saved is None:
            os.environ.pop("HALO_ORCHESTRA_RUN", None)
        else:
            os.environ["HALO_ORCHESTRA_RUN"] = saved


@test
def test_a_session_inside_a_run_installs_its_guard(ctx: Ctx):
    from halo_harness.agent.assemble import SessionContext
    from halo_harness.agent.loop import Session
    from halo_harness.model import ModelProfile, parse_model_ref
    from halo_harness.orchestra.guard import ClaimGuard
    from halo_harness.providers.stream import ProviderCreds
    repo, run = _setup()
    saved = os.environ.get("HALO_ORCHESTRA_RUN")

    def make():
        return Session(cwd=repo, model_ref=parse_model_ref("or:mock/x"), model_profile=ModelProfile(),
                       creds=ProviderCreds(base_url="http://127.0.0.1:1", api_key="k"),
                       state_dir=Path(tempfile.mkdtemp(prefix="orch-sess-state-")), model_label="mock/x",
                       session_context=SessionContext(cwd=repo, model_label="mock/x"),
                       permission_engine=P.PermissionEngine(mode="auto", cwd=repo))
    try:
        os.environ.pop("HALO_ORCHESTRA_RUN", None)
        ctx.check("outside a run a session has no guard", make().permission_engine.guards == [])
        os.environ["HALO_ORCHESTRA_RUN"] = str(run)
        s = make()
        guards = s.permission_engine.guards
        ctx.check(f"inside a run: one ClaimGuard for <session>/main, got {[getattr(g, 'holder', g) for g in guards]}",
                  len(guards) == 1 and isinstance(guards[0], ClaimGuard)
                  and guards[0].holder == f"{s.log.session_id}/main")
    finally:
        if saved is None:
            os.environ.pop("HALO_ORCHESTRA_RUN", None)
        else:
            os.environ["HALO_ORCHESTRA_RUN"] = saved


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
