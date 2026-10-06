"""tests.test_invariants -- two unrelated meanings of "invariant" share
this one file (the name was already taken when 2.0.4 round 0 needed it;
see the brief's own WHAT YOU FOUND for why it was kept rather than
renamed):

(1) agent/invariants.py: unpaired tool_use detection, synthetic result
    writing, well-formed-text repair (the original content below).
(2) The house-wide standing rules collected from plans/ROADMAP.md's old
    hardening list plus plans/WORKER-RULES.md (2.0.4 round 0 tooling,
    "House invariants (a)-(f)" section near the bottom of this file):
    no safety/refusal language, the network choke point, no file under
    halo_harness/ bypassing BRIDGE_TEST_HOME, every slash command/CLI
    flag documented, the privacy scan, and no test module exporting
    BRIDGE_STATE_DIR for its whole run. Several of these already exist as
    their own, more complete modules (tests/test_offline_mode.py,
    tests/test_privacy_scan.py, tests/test_docs_slash_commands.py,
    tests/test_docs_commands.py) -- referenced here (imported and
    re-run), never duplicated, so the actual scan logic/allow-lists stay
    defined in exactly one place each.

H15 Part D2.1: `SessionLog.__init__` ALWAYS resolves its own storage root
via `bridge_home()` (`BRIDGE_STATE_DIR`, else `BRIDGE_TEST_HOME`-derived,
else the REAL `~/.halo`) -- completely independent of whatever
`cwd` is passed to it, and `.mkdir(parents=True, exist_ok=True)` runs
UNCONDITIONALLY at construction time, before a single node is ever
appended. Every `@test` here is therefore transparently wrapped in an
isolated, per-test `BRIDGE_STATE_DIR` (found leaking real empty
`invariants-test-*` slug directories into `~/.halo/sessions` during
the H15 fix pass -- invisible to the OLD file-only REAL SESSIONS GUARD,
closed by D2.2), same pattern `tests/test_log_derive.py` already uses --
harmless, and still correctly isolated, for the house-wide invariants
below too, even though most of them never touch `~/.halo` at all.
"""
import ast
import functools
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all
from halo_harness.agent.log import SessionLog
from halo_harness.agent.invariants import (
    ABORTED_BEFORE_DISPATCH, INTERRUPTED_MESSAGE, find_unpaired_tool_use_ids,
    highest_kimi_functions_idx, repair_truncated_text, synthesize_missing_results, validate_tool_use,
)

REPO_DIR = Path(__file__).resolve().parent.parent
_register, TESTS = new_registry()


def test(fn):
    @functools.wraps(fn)
    def wrapper(ctx):
        old = os.environ.get("BRIDGE_STATE_DIR")
        os.environ["BRIDGE_STATE_DIR"] = str(Path(tempfile.mkdtemp(prefix="invariants-test-state-")))
        try:
            return fn(ctx)
        finally:
            if old is None:
                os.environ.pop("BRIDGE_STATE_DIR", None)
            else:
                os.environ["BRIDGE_STATE_DIR"] = old
    return _register(wrapper)


def _fresh_log() -> SessionLog:
    d = Path(tempfile.mkdtemp(prefix="invariants-test-"))
    return SessionLog(d, session_id="test-session")


@test
def test_h9_highest_kimi_functions_idx_empty_log_is_minus_one(ctx: Ctx):
    log = _fresh_log()
    log.append_system("sys")
    ctx.check("no functions.*:N ids anywhere -> -1 (caller starts fresh at 0)",
              highest_kimi_functions_idx(log) == -1)


@test
def test_h9_highest_kimi_functions_idx_finds_the_max_across_every_assistant_node(ctx: Ctx):
    """H9 critical review finding 1 repro: 6 Reads across 6 SEPARATE
    assistant nodes (i.e. 6 separate model-call steps, exactly the
    real-world shape) must all be seen, not just the last node -- an id
    minted several steps ago is exactly the one a reset-to-0 counter would
    collide with next."""
    log = _fresh_log()
    log.append_system("sys")
    log.append_user([{"type": "text", "text": "go"}])
    for i in range(6):
        log.append_assistant(content=[{"type": "tool_use", "id": f"functions.Read:{i}", "name": "Read", "input": {}}],
                              stop_reason="tool_use")
        log.append_tool_result(tool_use_id=f"functions.Read:{i}", content=f"file {i} contents")
    ctx.check(f"highest idx across all 6 steps is 5, got {highest_kimi_functions_idx(log)}",
              highest_kimi_functions_idx(log) == 5)


@test
def test_h9_highest_kimi_functions_idx_ignores_non_kimi_shaped_ids(ctx: Ctx):
    log = _fresh_log()
    log.append_system("sys")
    log.append_user([{"type": "text", "text": "go"}])
    log.append_assistant(content=[{"type": "tool_use", "id": "call_abc123", "name": "Read", "input": {}}],
                          stop_reason="tool_use")
    log.append_tool_result(tool_use_id="call_abc123", content="x")
    log.append_assistant(content=[{"type": "tool_use", "id": "functions.Grep:2", "name": "Grep", "input": {}}],
                          stop_reason="tool_use")
    log.append_tool_result(tool_use_id="functions.Grep:2", content="y")
    ctx.check(f"only the native-shaped id counts, got {highest_kimi_functions_idx(log)}",
              highest_kimi_functions_idx(log) == 2)


@test
def test_fully_paired_turn_has_no_unpaired_ids(ctx: Ctx):
    log = _fresh_log()
    log.append_system("sys")
    log.append_user([{"type": "text", "text": "hi"}])
    log.append_assistant(content=[{"type": "tool_use", "id": "call_1", "name": "Read", "input": {}}], stop_reason="tool_use")
    log.append_tool_result(tool_use_id="call_1", content="file contents")
    ctx.check("no unpaired ids", find_unpaired_tool_use_ids(log) == [])
    ctx.check("synthesize is a no-op on an already-paired log", synthesize_missing_results(log) == [])


@test
def test_interrupted_turn_gets_synthetic_results(ctx: Ctx):
    log = _fresh_log()
    log.append_system("sys")
    log.append_user([{"type": "text", "text": "hi"}])
    log.append_assistant(
        content=[
            {"type": "tool_use", "id": "call_1", "name": "Read", "input": {}},
            {"type": "tool_use", "id": "call_2", "name": "Read", "input": {}},
        ],
        stop_reason="tool_use",
    )
    # crash/interrupt before either tool_result is written
    missing = find_unpaired_tool_use_ids(log)
    ctx.check(f"both ids detected as unpaired, got {missing}", set(missing) == {"call_1", "call_2"})

    synthesized = synthesize_missing_results(log, reason=INTERRUPTED_MESSAGE)
    ctx.check(f"synthesize_missing_results returns both ids, got {synthesized}", set(synthesized) == {"call_1", "call_2"})
    ctx.check("no unpaired ids remain", find_unpaired_tool_use_ids(log) == [])

    results = [n for n in log.nodes() if n.get("type") == "tool_result"]
    ctx.check("two synthetic tool_result nodes written", len(results) == 2)
    ctx.check("synthetic results are marked is_error", all(r["is_error"] for r in results))
    ctx.check("synthetic results carry the interrupted message", all(r["content"] == INTERRUPTED_MESSAGE for r in results))


@test
def test_partially_answered_turn_only_synthesizes_the_gap(ctx: Ctx):
    log = _fresh_log()
    log.append_system("sys")
    log.append_user([{"type": "text", "text": "hi"}])
    log.append_assistant(
        content=[
            {"type": "tool_use", "id": "call_a", "name": "Read", "input": {}},
            {"type": "tool_use", "id": "call_b", "name": "Read", "input": {}},
        ],
        stop_reason="tool_use",
    )
    log.append_tool_result(tool_use_id="call_a", content="ok")  # call_b never answered (crash mid-dispatch)
    synthesized = synthesize_missing_results(log, reason=ABORTED_BEFORE_DISPATCH)
    ctx.check(f"only call_b synthesized, got {synthesized}", synthesized == ["call_b"])
    total_results = [n for n in log.nodes() if n.get("type") == "tool_result"]
    ctx.check("exactly 2 tool_result nodes total (1 real + 1 synthetic)", len(total_results) == 2)


@test
def test_a_fully_paired_multi_turn_history_has_no_unpaired_ids(ctx: Ctx):
    """A normal, tool-free (or fully-paired) multi-turn history never
    false-positives, regardless of how many assistant nodes precede the
    current one."""
    log = _fresh_log()
    log.append_system("sys")
    log.append_user([{"type": "text", "text": "hi"}])
    log.append_assistant(content=[{"type": "text", "text": "no tools this turn"}], stop_reason="end_turn")
    log.append_user([{"type": "text", "text": "again"}])
    log.append_assistant(content=[{"type": "text", "text": "still no tools"}], stop_reason="end_turn")
    ctx.check("no unpaired ids across a tool-free history", find_unpaired_tool_use_ids(log) == [])


@test
def test_h5b_f03_an_earlier_non_last_assistant_node_left_unpaired_is_still_detected(ctx: Ctx):
    """finding 3 (h4-h5-h3c review): the pre-fix version only ever checked
    the LAST assistant node, reasoning every earlier one is a completed,
    already-paired turn by construction. That reasoning broke once a steer
    noticed mid-`_dispatch_tools` could leave an EARLIER assistant node's
    tool_use unanswered while the turn kept going and appended FURTHER
    turns afterward (finding 3's own steering fix) -- this is the case
    that broke silently before: an unpaired id sitting behind later,
    unrelated assistant/user turns, never self-healed by
    `synthesize_missing_results` (which itself calls this function),
    corrupting every subsequent request on `ant:`/Databricks Claude
    routes forever after."""
    log = _fresh_log()
    log.append_system("sys")
    log.append_user([{"type": "text", "text": "first"}])
    log.append_assistant(
        content=[
            {"type": "tool_use", "id": "call_early_1", "name": "Write", "input": {}},
            {"type": "tool_use", "id": "call_early_2", "name": "Write", "input": {}},
        ],
        stop_reason="tool_use",
    )
    # Only the FIRST call got a result -- the second was never dispatched
    # (the bug finding 3 fixes) -- then the turn kept going regardless.
    log.append_tool_result(tool_use_id="call_early_1", content="wrote a")
    log.append_user([{"type": "text", "text": "a later, unrelated turn"}])
    log.append_assistant(content=[{"type": "text", "text": "a normal reply, no tools"}], stop_reason="end_turn")

    missing = find_unpaired_tool_use_ids(log)
    ctx.check(f"the EARLIER node's dangling tool_use is still found, got {missing}", missing == ["call_early_2"])

    synthesized = synthesize_missing_results(log, reason=ABORTED_BEFORE_DISPATCH)
    ctx.check(f"synthesize_missing_results fixes it even though it isn't in the last assistant node, got {synthesized}",
              synthesized == ["call_early_2"])
    ctx.check("nothing left unpaired afterward", find_unpaired_tool_use_ids(log) == [])


@test
def test_validate_tool_use(ctx: Ctx):
    ctx.check("well-formed block passes", validate_tool_use({"id": "x", "name": "Read", "input": {"a": 1}}) is None)
    ctx.check("empty id rejected", validate_tool_use({"id": "", "name": "Read"}) is not None)
    ctx.check("missing id rejected", validate_tool_use({"name": "Read"}) is not None)
    ctx.check("missing name rejected", validate_tool_use({"id": "x"}) is not None)
    ctx.check("non-dict input rejected", validate_tool_use({"id": "x", "name": "Read", "input": "not-a-dict"}) is not None)
    ctx.check("non-dict block rejected", validate_tool_use("not-a-dict") is not None)


@test
def test_repair_truncated_text_well_formed_passthrough(ctx: Ctx):
    ctx.check("ordinary text unchanged", repair_truncated_text("hello world") == "hello world")
    ctx.check("empty string unchanged", repair_truncated_text("") == "")
    ctx.check("unicode text unchanged", repair_truncated_text("café \U0001F600") == "café \U0001F600")


@test
def test_repair_truncated_text_lone_surrogate(ctx: Ctx):
    lone_high_surrogate = "before" + chr(0xD83D) + "after"  # half of an emoji surrogate pair, truncated
    try:
        lone_high_surrogate.encode("utf-8")
        ctx.check("test setup: a lone surrogate must be unencodable in plain utf-8", False)
    except UnicodeEncodeError:
        pass
    repaired = repair_truncated_text(lone_high_surrogate)
    try:
        repaired.encode("utf-8")
        ctx.check("repaired text is now well-formed UTF-8", True)
    except UnicodeEncodeError:
        ctx.check("repaired text must be encodable as UTF-8", False)
    ctx.check("surrounding text survives", "before" in repaired and "after" in repaired)


# =============================================================================
# House invariants (a)-(f) -- 2.0.4 round 0 tooling. plans/ROADMAP.md's
# "REORDERED 2026-10-05" section (the authority) names "the invariants
# from the old hardening list" as part of round 0; every line in ROADMAP.md
# mentioning "invariant" (grepped before writing these) only ever talks
# about WHEN the invariants doc+test work happens (2.0.4 round 0 writes
# them, 2.0.6 "extends" them later) -- the actual list of six come from
# this round's own brief, which already derived them from that history
# plus plans/WORKER-RULES.md's standing rules. One @test per invariant;
# each docstring says what it protects.
# =============================================================================

@test
def test_invariant_b_raw_network_calls_go_through_the_http_choke_point(ctx: Ctx):
    """Protects: every call capable of opening a raw socket anywhere in
    halo_harness/ goes through providers/http.py's open_upstream/
    urlopen_tls (the one place offline mode, proxy bypass, and the TLS/CA
    policy are all enforced), or is one of the three named, reasoned
    exceptions tests/test_offline_mode.py's own _ALLOWED_RAW_NETWORK_
    CALLERS table lists. The regex, the allow-list, and its own staleness
    check all live in tests/test_offline_mode.py -- referenced here (run
    again, not re-implemented) so there is exactly one place to update
    either."""
    from tests.test_offline_mode import test_every_raw_network_call_is_the_choke_point_or_a_named_exception as _scan
    _scan(ctx)


@test
def test_invariant_e_the_privacy_scan_passes(ctx: Ctx):
    """Protects: the tracked tree carries no LAN address, real home path,
    removed machine/project name, hobby-gear/vendor/owner-name term, or
    key-shaped fragment outside tests/privacy_scan_allowlist.txt --
    already wired into tests/run_all.py as its own module; every one of
    its checks is re-run here (not duplicated: the patterns and allow-list
    stay defined once, in tests/test_privacy_scan.py) so a release-
    tooling-only invocation of just this file still proves it."""
    from tests.test_privacy_scan import TESTS as _PRIVACY_TESTS
    results, _passed, _failed, _skipped = run_all(_PRIVACY_TESTS, Ctx())
    problems = [f"{name}: {detail}" for name, status, detail, _dt in results if status != "PASS"]
    ctx.check("every tests.test_privacy_scan check passes:\n  " + "\n  ".join(problems), not problems)


@test
def test_invariant_d_docs_cover_every_slash_command_and_cli_flag(ctx: Ctx):
    """Protects: every built-in /command has a heading in docs/SLASH-
    COMMANDS.md and no fictional one is documented there either (tests/
    test_docs_slash_commands.py); every real CLI subcommand/flag has a
    mention in docs/COMMANDS.md and no fictional one is documented there
    either, including the "not supported yet" ones being listed honestly
    (tests/test_docs_commands.py). The brief for this round named only the
    slash-command half as already covered -- the CLI-flag half turned out
    to already be fully covered too, by a second existing module the brief
    didn't name; both are referenced here, neither is duplicated."""
    from tests.test_docs_slash_commands import TESTS as _SLASH_TESTS
    from tests.test_docs_commands import TESTS as _CLI_TESTS
    problems = []
    for label, tests_list in (("slash-commands", _SLASH_TESTS), ("cli-flags", _CLI_TESTS)):
        results, _passed, _failed, _skipped = run_all(tests_list, Ctx())
        problems += [f"{label}/{name}: {detail}" for name, status, detail, _dt in results if status != "PASS"]
    ctx.check("docs coverage for slash commands and CLI flags:\n  " + "\n  ".join(problems), not problems)


# No existing scan covers invariant (a) (tests/test_privacy_scan.py scans
# for secrets/identifying content, never safety/refusal wording) -- a
# plain word list, case-insensitive, scoped to the three directories the
# brief names. The allow-list is an inline dict (the SAME convention
# tests/test_offline_mode.py's own _ALLOWED_RAW_NETWORK_CALLERS already
# uses for invariant (b)), not a separate file: this round's own hard
# constraints list the exact files this worker may touch, and a new
# tests/*.txt file is not one of them -- see WHAT YOU FOUND.
_BANNED_SAFETY_PHRASES = (
    "for safety", "dangerous command", "not allowed in auto mode",
    "i can't do that", "i cannot do that",
)
_SAFETY_SCAN_ROOTS = ("halo_harness/", "docs/", "tests/")
# (relative_path, lowercased banned phrase) -> why this is a MENTION of the
# rule (quoting the phrase to explain it is avoided), never a real use of
# it. Confirmed by hand (grep across halo_harness/, docs/, tests/ for each
# exact phrase, case-insensitive) to be the ONLY match anywhere in the
# tree before this test was written.
_SAFETY_LANGUAGE_ALLOWED_MENTIONS = {
    ("halo_harness/tui/keys.py", "for safety"):
        "MODE_DESCRIPTIONS' own comment documents the house rule by quoting the banned phrase it "
        "deliberately avoids; the actual mode description strings never use it",
}
# This file itself is the one place in the tree that is SUPPOSED to spell
# out every banned phrase -- the word list just above, and this docstring
# quoting plans/WORKER-RULES.md to explain it -- so every phrase gets its
# own entry here too, scoped to this one file, added after the first real
# run of this test found exactly these (and no other) self-matches.
for _phrase in _BANNED_SAFETY_PHRASES:
    _SAFETY_LANGUAGE_ALLOWED_MENTIONS[("tests/test_invariants.py", _phrase)] = (
        "this test's own word list (_BANNED_SAFETY_PHRASES) and docstring (quoting WORKER-RULES.md) "
        "both necessarily spell out the phrase being banned")
del _phrase


@test
def test_invariant_a_no_safety_or_refusal_language(ctx: Ctx):
    """Protects: no safety-classifier/refusal wording ever ships in a
    prompt, tool description, UI string, doc, or test (plans/WORKER-
    RULES.md's standing rule: "No safety, refusal, 'for safety', 'not
    allowed in auto mode' or 'I can't do that' wording anywhere ... Auto
    mode allows everything except the user's own deny/ask rules and
    hooks. Describe behaviour; never gate it."). Case-insensitive, scoped
    to halo_harness/, docs/, tests/ -- the same tree the brief names."""
    from tests.test_privacy_scan import REPO_DIR as _REPO, _read_text, _tracked_files
    problems = []
    for path in _tracked_files():
        try:
            rel = path.resolve().relative_to(_REPO).as_posix()
        except ValueError:
            continue
        if not any(rel.startswith(root) for root in _SAFETY_SCAN_ROOTS):
            continue
        text = _read_text(path)
        if not text:
            continue
        lower = text.lower()
        for phrase in _BANNED_SAFETY_PHRASES:
            idx = lower.find(phrase)
            while idx != -1:
                if (rel, phrase) not in _SAFETY_LANGUAGE_ALLOWED_MENTIONS:
                    line_no = text.count("\n", 0, idx) + 1
                    problems.append(f"{rel}:{line_no}: banned phrase {phrase!r} found "
                                     f"(not in _SAFETY_LANGUAGE_ALLOWED_MENTIONS)")
                idx = lower.find(phrase, idx + 1)
    for (rel, phrase) in _SAFETY_LANGUAGE_ALLOWED_MENTIONS:
        path = REPO_DIR / rel
        if not (path.exists() and phrase in path.read_text(encoding="utf-8", errors="replace").lower()):
            problems.append(f"{rel}: allow-listed for {phrase!r} but that phrase was not found any more -- "
                             f"remove the entry")
    ctx.check("no safety/refusal language found:\n  " + "\n  ".join(problems), not problems)


# halo_harness/config/paths.py::home()/bridge_home() are the ONLY
# functions that check BRIDGE_TEST_HOME/BRIDGE_STATE_DIR before falling
# back to the real machine home -- every other halo_harness/ call to the
# bare Path.home() bypasses that, so each one found by hand (grepped
# before writing this test) is named here with why it is not the bug
# invariant (c) guards against: either it reads/writes an EXTERNAL
# program's own real path (never halo's own state, so BRIDGE_TEST_HOME
# has no reason to redirect it), or the real machine home IS deliberately
# the feature's own target (the Linux PATH fix), gated behind confirmation
# or its own override.
_PATH_HOME_ALLOWED_CALLERS = {
    "halo_harness/bugreport.py":
        "reads the Databricks CLI's OWN ~/.databrickscfg marker (an external tool's config) to report "
        "provider enablement; never written",
    "halo_harness/init_cli.py":
        "the Linux PATH-fix step's own target IS the real ~/.local/bin (fixing the real system PATH is "
        "the feature itself), gated behind an interactive confirm before anything is written",
    "halo_harness/linux_fixes.py":
        "rc_file_for_shell's own target IS the real ~/.zshenv/~/.profile (fixing the real shell rc is "
        "the feature); takes an explicit home= override its own tests pass",
    "halo_harness/mcp_cli.py":
        "Claude Desktop's OWN config path on macOS (an external application's file, read-only) -- has "
        "its own BRIDGE_TEST_CLAUDE_DESKTOP_CONFIG override",
    "halo_harness/providers/codex_settings.py":
        "Codex CLI's OWN $CODEX_HOME default (an external tool's config, read-only) -- checks CODEX_HOME first",
    "halo_harness/providers/config.py":
        "this module's own home(): already BRIDGE_TEST_HOME-first, the identical pattern config.paths.home() "
        "defines, re-declared here to avoid a dependency cycle (providers/config.py cannot import config/paths.py)",
    "halo_harness/providers/huggingface_hub_cache.py":
        "Hugging Face Hub's OWN cache directory (an external tool's download cache, read-only discovery) -- "
        "checks HF_HUB_CACHE/HF_HOME first",
    "halo_harness/providers/lmstudio_cache.py":
        "LM Studio's OWN models directory (an external tool's data, read-only discovery) -- checks the "
        "huggingface.lmstudio_models_dir config override first",
    "halo_harness/tui/dialogs/init_wizard.py":
        "the init wizard's Linux-fixes commit step -- same deliberate real ~/.local/bin target as "
        "init_cli.py's own ripgrep-install step above",
}


@test
def test_invariant_c_path_home_outside_paths_py_is_a_reasoned_exception(ctx: Ctx):
    """Protects: BRIDGE_TEST_HOME actually isolates every test from the
    real machine home -- a NEW halo_harness/ call to the bare Path.home()
    (bypassing config.paths.home()/bridge_home(), the only functions that
    check BRIDGE_TEST_HOME/BRIDGE_STATE_DIR first) could silently read or
    write the real ~/.something even while a test believes it is scoped.
    Every existing exception is named above with why it is not that bug;
    a new, unlisted one fails this test until it is either routed through
    config.paths or added above with a real reason."""
    from tests.test_offline_mode import _tracked_py_files
    problems = []
    for path in _tracked_py_files():
        try:
            rel = path.resolve().relative_to(REPO_DIR).as_posix()
        except ValueError:
            continue
        if rel == "halo_harness/config/paths.py":
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if "Path.home()" not in text:
            continue
        if rel not in _PATH_HOME_ALLOWED_CALLERS:
            problems.append(f"{rel}: calls Path.home() directly, outside config/paths.py, and is not in "
                             f"_PATH_HOME_ALLOWED_CALLERS")
    for rel in _PATH_HOME_ALLOWED_CALLERS:
        path = REPO_DIR / rel
        if not (path.exists() and "Path.home()" in path.read_text(encoding="utf-8", errors="replace")):
            problems.append(f"{rel}: allow-listed but no Path.home() call found any more -- remove the entry")
    ctx.check("Path.home() usage outside config/paths.py:\n  " + "\n  ".join(problems), not problems)


def _is_main_guard(node) -> bool:
    """True for the canonical `if __name__ == "__main__":` guard -- its
    body never runs on import (only on direct execution), so a module-
    level assignment inside one is not the bug invariant (f) guards
    against, unlike a bare module-level `if`/`with`/`try` block (which
    DOES run at import time)."""
    if not isinstance(node, ast.If):
        return False
    test = node.test
    return (isinstance(test, ast.Compare) and isinstance(test.left, ast.Name) and test.left.id == "__name__"
            and len(test.ops) == 1 and isinstance(test.ops[0], ast.Eq) and len(test.comparators) == 1
            and isinstance(test.comparators[0], ast.Constant) and test.comparators[0].value == "__main__")


def _module_level_bridge_state_dir_assignments(path: Path) -> "list[int]":
    """Line numbers of every `os.environ["BRIDGE_STATE_DIR"] = ...`-shaped
    assignment that executes at IMPORT time -- i.e. not nested inside any
    FunctionDef/AsyncFunctionDef/ClassDef/Lambda or an `if __name__ ==
    "__main__":` guard, however deeply, regardless of how many spaces of
    indentation it happens to have (a module-level `if`/`with`/`try`
    block's own body still runs on import, at ANY indentation, so this is
    AST-based -- a parent-chain walk -- never indentation-based)."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, UnicodeDecodeError, SyntaxError):
        return []
    parent: dict = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parent[child] = node

    def _is_scoped(node) -> bool:
        current = node
        while current in parent:
            current = parent[current]
            if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
                return True
            if _is_main_guard(current):
                return True
        return False

    def _targets_bridge_state_dir(target) -> bool:
        return (isinstance(target, ast.Subscript)
                and isinstance(target.value, ast.Attribute) and target.value.attr == "environ"
                and isinstance(target.value.value, ast.Name) and target.value.value.id == "os"
                and isinstance(target.slice, ast.Constant) and target.slice.value == "BRIDGE_STATE_DIR")

    hits = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and not _is_scoped(node):
            if any(_targets_bridge_state_dir(t) for t in node.targets):
                hits.append(node.lineno)
    return hits


@test
def test_invariant_f_no_test_module_sets_bridge_state_dir_at_module_level(ctx: Ctx):
    """Protects: a test module's own per-test state-dir helper (every
    existing one -- `_fresh_state_dir(prefix)` and its siblings -- only
    ever assigns os.environ["BRIDGE_STATE_DIR"] from INSIDE a function a
    test calls) never regresses into a bare module-level assignment that
    would apply for that module's WHOLE run (every test in it, not just
    the one that needs it) and would never be restored between modules if
    tests/run_all.py's own per-module env snapshot/restore were ever
    bypassed (a standalone `python tests/test_x.py` run). tests/
    test_sessions_h6.py's own module-level `_ORIGINAL_BRIDGE_STATE_DIR =
    os.environ.get(...)` is a READ, not a set, and is correctly
    unaffected by this check."""
    problems = []
    candidates = [REPO_DIR / "test_bridge.py", REPO_DIR / "test_tui.py"] + \
        sorted((REPO_DIR / "tests").glob("test_*.py"))
    for path in candidates:
        if not path.exists():
            continue
        rel = path.resolve().relative_to(REPO_DIR).as_posix()
        for line_no in _module_level_bridge_state_dir_assignments(path):
            problems.append(f"{rel}:{line_no}: os.environ['BRIDGE_STATE_DIR'] is set at module level "
                             f"(import time), not inside a single test")
    ctx.check("no test module sets BRIDGE_STATE_DIR at module level:\n  " + "\n  ".join(problems), not problems)


@test
def test_invariant_g_no_test_pins_the_package_version_as_a_literal(ctx: Ctx):
    """House invariant (g), added after the first CI run following the
    v2.0.4 tag went red: a 2.0.3.1-era test asserted `__version__ ==
    "2.0.3.1"`. `scripts/release.py` bumps the version AFTER every suite
    has run, so a literal pin can only ever fail on the push right after a
    release -- and no earlier run can catch it. The version check lives in
    tests/test_quickstart_docs.py and derives the expected value from the
    newest dated CHANGELOG section; this invariant keeps a literal from
    creeping back in anywhere."""
    import re
    pin = re.compile(r"""__version__\s*(?:==|!=)\s*["']\d""")
    problems = []
    candidates = [REPO_DIR / "test_bridge.py", REPO_DIR / "test_tui.py"] + \
        sorted((REPO_DIR / "tests").glob("test_*.py"))
    for path in candidates:
        if not path.exists():
            continue
        rel = path.resolve().relative_to(REPO_DIR).as_posix()
        for line_no, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            if pin.search(line):
                problems.append(f"{rel}:{line_no}: compares __version__ to a literal; derive it from the CHANGELOG instead")
    ctx.check("no test pins the package version as a literal:\n  " + "\n  ".join(problems), not problems)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
