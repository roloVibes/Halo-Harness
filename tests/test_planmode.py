"""tests.test_planmode -- H6 scope C: plan file helpers (agent/planmode.py)
and the PermissionEngine plan-file write exception (permissions.py) that
makes the plan file the ONLY writable path while `mode == "plan"`.
"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all
from halo_harness.agent.planmode import (
    PLAN_MODE_NOTE, EnterPlanModeTool, ExitPlanModeTool, ensure_plan_file, plans_directory, write_plan,
)
from halo_harness.permissions import PermissionEngine
from halo_harness.tools.base import ToolContext

test, TESTS = new_registry()


# ---- plans_directory ---------------------------------------------------------

@test
def test_plans_directory_default(ctx: Ctx):
    from halo_harness.config.paths import plans_dir
    ctx.check("default matches config.paths.plans_dir()", plans_directory(None) == plans_dir())


@test
def test_plans_directory_settings_object_override(ctx: Ctx):
    class _Settings:
        plans_directory = str(Path(tempfile.mkdtemp(prefix="rc-plansdir-")) / "custom-plans")
    result = plans_directory(_Settings())
    ctx.check("override honoured", str(result) == _Settings.plans_directory)


@test
def test_plans_directory_dict_override(ctx: Ctx):
    custom = str(Path(tempfile.mkdtemp(prefix="rc-plansdir2-")) / "custom")
    result = plans_directory({"plansDirectory": custom})
    ctx.check("dict-shaped settings honoured", str(result) == custom)


# ---- ensure_plan_file / write_plan -------------------------------------------

@test
def test_ensure_plan_file_creates_three_word_md_name(ctx: Ctx):
    cwd = Path(tempfile.mkdtemp(prefix="rc-cwd-"))
    settings_dir = Path(tempfile.mkdtemp(prefix="rc-plans-"))

    class _Settings:
        plans_directory = str(settings_dir)
    path = ensure_plan_file(cwd, _Settings())
    ctx.check("file exists", path.exists())
    ctx.check("under the configured directory", path.parent == settings_dir)
    ctx.check("ends in .md", path.suffix == ".md")
    stem_parts = path.stem.split("-")
    ctx.check("three-word stem", len(stem_parts) == 3)
    ctx.check("lowercase words", all(p.islower() for p in stem_parts))


@test
def test_ensure_plan_file_reuses_existing_when_given(ctx: Ctx):
    settings_dir = Path(tempfile.mkdtemp(prefix="rc-plans3-"))

    class _Settings:
        plans_directory = str(settings_dir)
    first = ensure_plan_file(Path(tempfile.mkdtemp()), _Settings())
    second = ensure_plan_file(Path(tempfile.mkdtemp()), _Settings(), existing=first)
    ctx.check("same path returned when reused", first == second)


@test
def test_ensure_plan_file_ignores_existing_when_file_gone(ctx: Ctx):
    settings_dir = Path(tempfile.mkdtemp(prefix="rc-plans4-"))

    class _Settings:
        plans_directory = str(settings_dir)
    fake_existing = settings_dir / "does-not-exist-anymore.md"
    result = ensure_plan_file(Path(tempfile.mkdtemp()), _Settings(), existing=fake_existing)
    ctx.check("a fresh file is created instead", result != fake_existing)
    ctx.check("new file actually exists", result.exists())


@test
def test_ensure_plan_file_generates_unique_names(ctx: Ctx):
    settings_dir = Path(tempfile.mkdtemp(prefix="rc-plans5-"))

    class _Settings:
        plans_directory = str(settings_dir)
    paths = {ensure_plan_file(Path(tempfile.mkdtemp()), _Settings()) for _ in range(5)}
    ctx.check("5 distinct plan files", len(paths) == 5)


@test
def test_write_plan_writes_text(ctx: Ctx):
    path = Path(tempfile.mkdtemp(prefix="rc-writeplan-")) / "plan.md"
    write_plan(path, "## My Plan\n\nStep 1.\n")
    ctx.check("content written", path.read_text(encoding="utf-8") == "## My Plan\n\nStep 1.\n")


@test
def test_write_plan_overwrites(ctx: Ctx):
    path = Path(tempfile.mkdtemp(prefix="rc-writeplan2-")) / "plan.md"
    write_plan(path, "first")
    write_plan(path, "second")
    ctx.check("overwritten, not appended", path.read_text(encoding="utf-8") == "second")


@test
def test_write_plan_empty_text_ok(ctx: Ctx):
    path = Path(tempfile.mkdtemp(prefix="rc-writeplan3-")) / "plan.md"
    write_plan(path, None)
    ctx.check("None -> empty file, no crash", path.read_text(encoding="utf-8") == "")


# ---- EnterPlanMode / ExitPlanMode tool defs ----------------------------------

@test
def test_enter_plan_mode_tool_shape(ctx: Ctx):
    t = EnterPlanModeTool()
    ctx.check("name", t.name == "EnterPlanMode")
    ctx.check("no required args", t.input_schema.get("properties") == {})
    ctx.check("summary", t.summary({}) == "EnterPlanMode()")


@test
def test_exit_plan_mode_tool_shape(ctx: Ctx):
    t = ExitPlanModeTool()
    ctx.check("name", t.name == "ExitPlanMode")
    ctx.check("plan is required", "plan" in t.input_schema.get("required", []))
    ctx.check("summary includes first line", "Do X" in t.summary({"plan": "Do X\nDo Y"}))


@test
def test_exit_plan_mode_fallback_run_requires_plan(ctx: Ctx):
    t = ExitPlanModeTool()
    ctx.check("missing plan -> conceptual error",
              t.run({}, ToolContext(cwd=Path("."))).is_error is True)


@test
def test_plan_mode_note_mentions_exit_plan_mode(ctx: Ctx):
    ctx.check("PLAN_MODE_NOTE tells the model to call ExitPlanMode", "ExitPlanMode" in PLAN_MODE_NOTE)


# ---- PermissionEngine plan-file write exception ------------------------------

@test
def test_plan_mode_denies_ordinary_write_with_no_plan_file_set(ctx: Ctx):
    cwd = Path(tempfile.mkdtemp(prefix="rc-pe1-"))
    engine = PermissionEngine(mode="plan", cwd=cwd)
    decision = engine.decide("Write", {"file_path": str(cwd / "some.py")})
    ctx.check("denied (no plan file registered)", decision.action == "deny")


@test
def test_plan_mode_allows_write_to_the_plan_file(ctx: Ctx):
    cwd = Path(tempfile.mkdtemp(prefix="rc-pe2-"))
    plan_path = Path(tempfile.mkdtemp(prefix="rc-plans6-")) / "typed-tickling-squirrel.md"
    plan_path.write_text("", encoding="utf-8")
    engine = PermissionEngine(mode="plan", cwd=cwd)
    engine.set_plan_file(plan_path)
    decision = engine.decide("Write", {"file_path": str(plan_path)})
    ctx.check("allowed", decision.action == "allow")
    ctx.check("category mentioned", "plan" in decision.reason.lower())


@test
def test_plan_mode_allows_edit_to_the_plan_file_too(ctx: Ctx):
    cwd = Path(tempfile.mkdtemp(prefix="rc-pe3-"))
    plan_path = Path(tempfile.mkdtemp(prefix="rc-plans7-")) / "misty-harbor-echo.md"
    plan_path.write_text("", encoding="utf-8")
    engine = PermissionEngine(mode="plan", cwd=cwd)
    engine.set_plan_file(plan_path)
    decision = engine.decide("Edit", {"file_path": str(plan_path)})
    ctx.check("Edit to plan file also allowed", decision.action == "allow")


@test
def test_plan_mode_still_denies_every_other_write(ctx: Ctx):
    cwd = Path(tempfile.mkdtemp(prefix="rc-pe4-"))
    (cwd / "real.py").write_text("x = 1\n", encoding="utf-8")
    plan_path = Path(tempfile.mkdtemp(prefix="rc-plans8-")) / "quiet-cedar-dawn.md"
    plan_path.write_text("", encoding="utf-8")
    engine = PermissionEngine(mode="plan", cwd=cwd)
    engine.set_plan_file(plan_path)
    decision = engine.decide("Write", {"file_path": str(cwd / "real.py")})
    ctx.check("a normal in-cwd file is still denied in plan mode", decision.action == "deny")


@test
def test_plan_file_exception_only_applies_in_plan_mode(ctx: Ctx):
    cwd = Path(tempfile.mkdtemp(prefix="rc-pe5-"))
    plan_path = Path(tempfile.mkdtemp(prefix="rc-plans9-")) / "gold-ridge-fable.md"
    plan_path.write_text("", encoding="utf-8")
    engine = PermissionEngine(mode="acceptEdits", cwd=cwd)
    engine.set_plan_file(plan_path)
    decision = engine.decide("Write", {"file_path": str(plan_path)})
    # acceptEdits allows outright anyway (edit_write_in_workdir -- but the
    # plan file is normally OUTSIDE cwd, so this exercises "other": ask).
    ctx.check("no crash outside plan mode", decision.action in ("allow", "ask", "deny"))


@test
def test_set_plan_file_mutates_in_place(ctx: Ctx):
    cwd = Path(tempfile.mkdtemp(prefix="rc-pe6-"))
    engine = PermissionEngine(mode="plan", cwd=cwd)
    ctx.check("starts unset", engine.plan_file is None)
    p = Path(tempfile.mkdtemp()) / "a.md"
    engine.set_plan_file(p)
    ctx.check("now set", engine.plan_file == p)
    engine.set_plan_file(None)
    ctx.check("clearable", engine.plan_file is None)


@test
def test_plan_mode_bash_still_gated_normally(ctx: Ctx):
    """The plan-file exception is Write/Edit-only -- Bash in plan mode
    keeps its own (read-only-allowed, everything-else-denied) rule."""
    cwd = Path(tempfile.mkdtemp(prefix="rc-pe7-"))
    engine = PermissionEngine(mode="plan", cwd=cwd)
    readonly = engine.decide("Bash", {"command": "ls"})
    other = engine.decide("Bash", {"command": "rm file.txt"})
    ctx.check("read-only bash allowed in plan mode", readonly.action == "allow")
    ctx.check("mutating bash denied in plan mode", other.action == "deny")


# ---- Halo 3.2.2.0 R4: plan mode lets every read through ------------------------

def _mcp(read_only: bool):
    from types import SimpleNamespace
    return SimpleNamespace(is_read_only=read_only, read_only=read_only)


_REFUSAL_TAIL = ("writes; research with the read tools and the web, then call ExitPlanMode with the plan "
                 "(Shift+Tab or /plan off leaves plan mode)")


@test
def test_plan_mode_lets_every_read_through(ctx: Ctx):
    cwd = Path(tempfile.mkdtemp(prefix="rc-r4-reads-"))
    engine = PermissionEngine(mode="plan", cwd=cwd)
    calls = [("WebFetch", {"url": "https://docs.example.com/x", "prompt": "summarize"}, None),
             ("WebSearch", {"query": "textual pager"}, None), ("BashOutput", {"bash_id": "1"}, None),
             ("Skill", {"skill": "review"}, None), ("knowledge_search", {"query": "x"}, None),
             ("ToolSearch", {"query": "select:a"}, None), ("recall", {"query": "x"}, None),
             ("mcp__docs__search", {"q": "x"}, _mcp(True)), ("Bash", {"command": "git log --oneline -3"}, None)]
    for name, inp, tool in calls:
        d = engine.decide(name, inp, tool=tool)
        ctx.check(f"{name} runs in plan mode, got {d.action}: {d.reason}", d.action == "allow")


@test
def test_plan_mode_refuses_a_write_in_plain_words(ctx: Ctx):
    from halo_harness.permissions import parse_rule
    cwd = Path(tempfile.mkdtemp(prefix="rc-r4-writes-"))
    engine = PermissionEngine(mode="plan", cwd=cwd)
    write = engine.decide("Write", {"file_path": str(cwd / "a.py"), "content": "x"})
    ctx.check(f"Write refused with the tool named and the way out, got {write.reason!r}",
              write.action == "deny" and write.reason == f"plan mode: Write {_REFUSAL_TAIL}")
    mcp = engine.decide("mcp__docs__write", {"q": "x"}, tool=_mcp(False))
    ctx.check(f"an MCP tool with no readOnlyHint stays a write, got {mcp.reason!r}",
              mcp.action == "deny" and mcp.reason == f"plan mode: mcp__docs__write {_REFUSAL_TAIL}")
    bash = engine.decide("Bash", {"command": "rm file.txt"})
    ctx.check(f"the Bash line has the same shape, got {bash.reason!r}",
              bash.reason == f"plan mode: this Bash command {_REFUSAL_TAIL}")
    ruled = PermissionEngine(mode="plan", cwd=cwd, allow_rules=[parse_rule("Bash(rm:*)", action="allow")])
    d = ruled.decide("Bash", {"command": "rm file.txt"})
    ctx.check(f"an allow rule gets the same text, got {d.reason!r}", d.reason == f"plan mode: this Bash command {_REFUSAL_TAIL}")
    for reason in (write.reason, mcp.reason, bash.reason, d.reason):
        ctx.check(f"no jargon in {reason!r}", "banned" not in reason and "cannot lift" not in reason)


@test
def test_other_modes_keep_their_web_decision_and_reads_run(ctx: Ctx):
    cwd = Path(tempfile.mkdtemp(prefix="rc-r4-modes-"))
    fetch = {"url": "https://docs.example.com/x", "prompt": "p"}
    for mode, want in (("default", "ask"), ("acceptEdits", "ask"), ("dontAsk", "deny"), ("auto", "allow")):
        d = PermissionEngine(mode=mode, cwd=cwd).decide("WebFetch", fetch)
        ctx.check(f"{mode}: WebFetch {want} as before, got {d.action}", d.action == want)
    default = PermissionEngine(mode="default", cwd=cwd)
    ctx.check("default: BashOutput runs", default.decide("BashOutput", {"bash_id": "1"}).action == "allow")
    ctx.check("default: a readOnlyHint MCP tool runs", default.decide("mcp__d__s", {}, tool=_mcp(True)).action == "allow")
    ctx.check("default: any other MCP tool asks", default.decide("mcp__d__w", {}, tool=_mcp(False)).action == "ask")


@test
def test_mcp_tool_record_and_cache_keep_read_only(ctx: Ctx):
    from types import SimpleNamespace
    from halo_harness.mcp.tools_cache import tool_from_dict, tool_to_dict
    from halo_harness.tools.mcp_tool import McpTool
    sdk = SimpleNamespace(name="search", description="d", input_schema={"type": "object", "properties": {}},
                          annotations=SimpleNamespace(read_only_hint=True, destructive_hint=False), meta=None)
    ctx.check("the live record keeps read_only", McpTool("docs", sdk, manager=None).read_only is True)
    cached = tool_from_dict(tool_to_dict(sdk))
    ctx.check("the tools cache keeps it", McpTool("docs", cached, manager=None).read_only is True)
    bare = SimpleNamespace(name="w", description="d", input_schema={}, annotations=None, meta=None)
    ctx.check("no annotations: not a read", McpTool("docs", tool_from_dict(tool_to_dict(bare)), manager=None).read_only is False)


# ---- Halo 3.2.2.0 R4: the model is told the mode (agent/mode_notice.py) ---------

class _Log:
    def __init__(self):
        self.snapshots = []

    def append_snapshot(self, content, *, kind):
        self.snapshots.append((kind, content[0]["text"]))


def _notice_session(mode):
    import os
    from types import SimpleNamespace
    os.environ["BRIDGE_TEST_HOME"] = str(Path(tempfile.mkdtemp(prefix="rc-r4-notice-home-")))
    cwd = Path(tempfile.mkdtemp(prefix="rc-r4-notice-"))
    return SimpleNamespace(cwd=cwd, session_context=None, log=_Log(),
                           permission_engine=PermissionEngine(mode=mode, cwd=cwd))


@test
def test_mode_notice_in_and_out_of_plan_mode(ctx: Ctx):
    from halo_harness.agent import mode_notice
    s = _notice_session("default")
    text = mode_notice.sync(s, turn_start=True)
    ctx.check(f"a turn states the mode in one line, got {text!r}",
              text == "permission mode: default (edits and commands ask first)")
    ctx.check("nothing more before the next call", mode_notice.sync(s) is None)
    s.permission_engine.mode = "plan"  # Shift+Tab / `/plan on`
    text = mode_notice.sync(s)
    path = s.permission_engine.plan_file
    ctx.check(f"the plan-mode note with the plan file's path, got {text!r}",
              PLAN_MODE_NOTE in text and f"Plan file: {path}" in text and path is not None and Path(path).exists())
    ctx.check("and the mode line", "permission mode: plan (read-only; call ExitPlanMode with the plan)" in text)
    ctx.check("the mode before plan is kept for /plan off", s._mode_before_plan == "default")
    ctx.check("told once", mode_notice.sync(s) is None)
    s.permission_engine.mode = "acceptEdits"  # Shift+Tab out, or the card's approve
    text = mode_notice.sync(s)
    ctx.check(f"leaving says implement the plan, got {text!r}", text.startswith(mode_notice.PLAN_OFF_NOTE))
    ctx.check("all of them are user-role snapshots", [k for k, _ in s.log.snapshots] == ["permission_mode"] * 3)


@test
def test_plan_at_startup_and_enter_plan_mode_are_told_once(ctx: Ctx):
    from halo_harness.agent import mode_notice
    s = _notice_session("plan")  # --permission-mode plan / config
    text = mode_notice.sync(s, turn_start=True)
    ctx.check(f"the first turn carries the note, got {text!r}", text and PLAN_MODE_NOTE in text)
    s2 = _notice_session("default")
    mode_notice.sync(s2, turn_start=True)
    s2.permission_engine.mode = "plan"
    mode_notice.told_plan(s2)  # EnterPlanMode logged it itself
    ctx.check("no second copy after EnterPlanMode", mode_notice.sync(s2) is None)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
