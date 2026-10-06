"""tests.test_audit_privacy -- 2.0.4 round 1: `halo audit privacy` against
a REAL scratch git repo (never this repo -- same precedent as tests/
test_release_script.py's own `_scratch_repo`). Nothing here is stubbed:
every `git init`/`add`/`commit`/`rm` below is a real subprocess call
against a throwaway temp directory, because the whole point of this
command is to behave correctly against real git plumbing (blob dedup,
`--raw` attribution, `rev-list --objects`).

The scratch repo plants one fixture of EVERY finding kind, half of them
only reachable through an earlier commit whose file was later deleted
with a plain `git rm` (never purged) -- exactly Halo's own real history
incident (plans/2.0.4-history-rewrite-plan.md), so `--history` has
something true to find that working-tree mode structurally cannot.
"""
from __future__ import annotations

import contextlib
import io
import json
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all
from halo_harness.audit_cli import cmd_audit
from halo_harness.privacy_scan import scan_history, scan_working_tree, summarize_history

test, TESTS = new_registry()

# The exact secret-shaped literals planted below -- used only to assert
# NONE of them ever survive into a finding's excerpt, never compared
# against for anything else.
_PLANTED_SECRETS = (
    "morgan", "192.168.77.5", "169.254.5.5", "leaky-mirror.local",
    "sk-or-v1-REALLOOKINGKEYSHAPEDVALUE1234567890",
    "sk-ant-ALLOWLISTEDFAKEVALUE1234567890AB",
    "morgan.test@personalmailbox.io",
)

_NOTES_TXT = (
    "Contact backup admin at C:\\Users\\morgan\\Documents for the old export.\n"
    "LAN node: 192.168.77.5\n"
    "Link-local fallback: 169.254.5.5\n"
    "Mirror: http://leaky-mirror.local:9999/status\n"
    "Known real key-shaped value (should be flagged): sk-or-v1-REALLOOKINGKEYSHAPEDVALUE1234567890\n"
    "Allowlisted key-shaped value (should be suppressed): sk-ant-ALLOWLISTEDFAKEVALUE1234567890AB\n"
    "Machine name (should be flagged): REDACTED-HOSTNAME\n"
    "Contact: morgan.test@personalmailbox.io\n"
)
_ALLOWLIST_TXT = "# scratch allowlist\nsk-ant-ALLOWLISTEDFAKEVALUE1234567890AB\n"
_JUNK_REL = "%SystemDrive%/cache/junk.db"


def _run(cmd: list, cwd: Path) -> None:
    subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, check=True)


def _dirty_scratch_repo() -> Path:
    """Commit 1 plants only the junk cache path, then DELETES it (plain
    `git rm`, never a history rewrite) in commit 2, which also plants one
    live fixture of every other finding kind plus the scratch allowlist."""
    repo = Path(tempfile.mkdtemp(prefix="audit-privacy-test-"))
    _run(["git", "init", "-q"], repo)
    _run(["git", "config", "user.email", "test@example.invalid"], repo)
    _run(["git", "config", "user.name", "Test"], repo)

    (repo / "README.md").write_text("scratch repo for test_audit_privacy.py\n", encoding="utf-8")
    junk_path = repo / _JUNK_REL
    junk_path.parent.mkdir(parents=True, exist_ok=True)
    junk_path.write_text("stray cache bytes\n", encoding="utf-8")
    _run(["git", "add", "-A"], repo)
    _run(["git", "commit", "-q", "-m", "commit 1: plants the stray cache file"], repo)

    _run(["git", "rm", "-q", _JUNK_REL], repo)
    (repo / "notes.txt").write_text(_NOTES_TXT, encoding="utf-8")
    (repo / "tests").mkdir(parents=True, exist_ok=True)
    (repo / "tests" / "privacy_scan_allowlist.txt").write_text(_ALLOWLIST_TXT, encoding="utf-8")
    _run(["git", "add", "-A"], repo)
    _run(["git", "commit", "-q", "-m", "commit 2: deletes the cache file, plants the live fixtures"], repo)
    return repo


def _clean_scratch_repo() -> Path:
    repo = Path(tempfile.mkdtemp(prefix="audit-privacy-clean-test-"))
    _run(["git", "init", "-q"], repo)
    _run(["git", "config", "user.email", "test@example.invalid"], repo)
    _run(["git", "config", "user.name", "Test"], repo)
    (repo / "README.md").write_text("nothing to see here\n", encoding="utf-8")
    _run(["git", "add", "-A"], repo)
    _run(["git", "commit", "-q", "-m", "clean"], repo)
    return repo


def _capture_stdout(fn, argv) -> "tuple[str, int]":
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = fn(argv)
    return buf.getvalue(), rc


def _assert_no_secret_leaked(ctx: Ctx, findings: list, *, label: str) -> None:
    blob = json.dumps(findings, ensure_ascii=False)
    for secret in _PLANTED_SECRETS:
        ctx.check(f"{label}: planted secret {secret!r} never appears verbatim in any excerpt",
                  secret not in blob)


@test
def test_working_tree_mode_finds_the_live_fixtures_and_exits_1(ctx: Ctx):
    repo = _dirty_scratch_repo()
    findings = scan_working_tree(repo)
    kinds = {f["kind"] for f in findings}
    for expected in ("home-path", "lan-ip", "link-local-ip", "dot-local-hostname", "token", "machine-name", "email"):
        ctx.check(f"working-tree mode finds a {expected!r} finding, got kinds {kinds}", expected in kinds)
    ctx.check("working-tree mode does NOT find the already-deleted junk path",
              "junk-path" not in kinds)
    _assert_no_secret_leaked(ctx, findings, label="working-tree")

    out, rc = _capture_stdout(cmd_audit, ["privacy", "--cwd", str(repo)])
    ctx.check(f"CLI exits 1 when findings exist, got {rc}", rc == 1)
    ctx.check("CLI text output never contains a planted secret verbatim",
              not any(secret in out for secret in _PLANTED_SECRETS))


@test
def test_allowlist_suppresses_the_allowlisted_fixture_only(ctx: Ctx):
    repo = _dirty_scratch_repo()
    findings = scan_working_tree(repo)
    tokens = [f for f in findings if f["kind"] == "token"]
    ctx.check(f"exactly one (non-allowlisted) token finding survives, got {len(tokens)}: {tokens}",
              len(tokens) == 1)


@test
def test_history_mode_finds_the_deleted_junk_path_and_lists_it_to_purge(ctx: Ctx):
    repo = _dirty_scratch_repo()
    findings = scan_history(repo)
    junk = [f for f in findings if f["kind"] == "junk-path"]
    ctx.check(f"--history finds the deleted junk-cache path, got {junk}", len(junk) == 1)
    ctx.check("the junk-path finding names the real planted path (not sensitive -- a generic OS cache path)",
              junk and junk[0]["path"] == _JUNK_REL)
    ctx.check("the junk-path finding is attributed to a real commit",
              junk and junk[0]["commit"] and len(junk[0]["commit"]) == 40)

    summary = summarize_history(findings)
    purge_paths = {item["path"] for item in summary["purge_entirely"]}
    ctx.check(f"the summary's purge_entirely bucket lists the junk path, got {purge_paths}",
              _JUNK_REL in purge_paths)
    replace_paths = {item["path"] for item in summary["text_replacements"]}
    ctx.check("notes.txt (the live fixtures) lands in text_replacements, not purge_entirely",
              "notes.txt" in replace_paths and "notes.txt" not in purge_paths)
    _assert_no_secret_leaked(ctx, findings, label="history")


@test
def test_json_mode_round_trips_through_cmd_audit(ctx: Ctx):
    repo = _dirty_scratch_repo()
    out, rc = _capture_stdout(cmd_audit, ["privacy", "--history", "--json", "--cwd", str(repo)])
    ctx.check(f"--history --json exits 1 on a dirty scratch repo, got {rc}", rc == 1)
    payload = json.loads(out)  # must be valid JSON -- the round-trip itself
    ctx.check("payload mode is 'history'", payload["mode"] == "history")
    ctx.check("payload.clean is False", payload["clean"] is False)
    ctx.check("payload carries a findings list", isinstance(payload["findings"], list) and payload["findings"])
    ctx.check("payload carries a summary with both buckets",
              "purge_entirely" in payload["summary"] and "text_replacements" in payload["summary"])
    ctx.check("no planted secret appears anywhere in the serialized JSON",
              not any(secret in out for secret in _PLANTED_SECRETS))


@test
def test_clean_repo_exits_0_in_both_modes(ctx: Ctx):
    repo = _clean_scratch_repo()
    out_wt, rc_wt = _capture_stdout(cmd_audit, ["privacy", "--cwd", str(repo)])
    ctx.check(f"working-tree mode exits 0 on a clean repo, got {rc_wt}: {out_wt!r}", rc_wt == 0)
    out_hist, rc_hist = _capture_stdout(cmd_audit, ["privacy", "--history", "--cwd", str(repo)])
    ctx.check(f"--history exits 0 on a clean repo's full history, got {rc_hist}: {out_hist!r}", rc_hist == 0)


@test
def test_since_narrows_history_to_the_given_range(ctx: Ctx):
    """`--since <rev>` must exclude the junk-path commit once that commit
    is itself the boundary (REV..HEAD never includes REV)."""
    repo = _dirty_scratch_repo()
    first_commit = subprocess.run(["git", "rev-list", "--max-parents=0", "HEAD"], cwd=str(repo),
                                   capture_output=True, text=True, check=True).stdout.strip()
    findings = scan_history(repo, since=first_commit)
    kinds = {f["kind"] for f in findings}
    ctx.check("--since <the first commit> excludes the junk path that commit itself introduced",
              "junk-path" not in kinds)
    ctx.check("--since <the first commit> still finds commit 2's own live fixtures",
              "lan-ip" in kinds)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
