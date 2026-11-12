"""tests.test_privacy_gate -- Halo 3.4.1.2 (disclosure audit F8): the pre-push privacy gate sees what it missed.

Before 3.4.1.2 scripts/prepush.py ran `halo audit privacy` in a scratch home, so the owner's private term list was
never loaded and every machine- and owner-name check was off in the gate (a machine name came back into the tree that
way). Pinned here, each against a real scratch git repo and a scratch term list of made-up words (never the owner's):

- the gate hands the list over by file name (`HALO_PRIVACY_TERMS_FILE`) and a term seeded in plans/ fails it, reported
  by number, never by the term;
- with no list the gate says, in one line, that the name checks are OFF (this module prints that line, so the CI log
  says it too);
- `--commits` reads author, committer and message: a non-noreply author or a term in the message fails only on a
  commit not yet on origin/master; older ones are counted, never failing;
- `/home/<a real-looking placeholder>/...` is caught unless the whole path is allowlisted; `--history` reads every ref;
  a file that is not text is counted as not checked.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))

import prepush_privacy as PP  # noqa: E402
from halo_harness import privacy_scan as ps  # noqa: E402
from halo_harness.privacy_rules import name_checks_line  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
TERM = "zephyrquill"  # a made-up word: the scratch list's only term
NOREPLY = "1+someone@users.noreply.github.com"
PERSONAL = "pat.q@personal-mail.example"


def _git(repo: Path, *args: str, email: str = NOREPLY) -> str:
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update(GIT_AUTHOR_NAME="T", GIT_AUTHOR_EMAIL=email, GIT_COMMITTER_NAME="T", GIT_COMMITTER_EMAIL=email)
    return subprocess.run(["git", *args], cwd=str(repo), env=env, capture_output=True, text=True, check=True).stdout


def _repo(files: "dict[str, str]", msg: str = "first", email: str = NOREPLY) -> Path:
    repo = Path(tempfile.mkdtemp(prefix="privacy-gate-"))
    _git(repo, "init", "-q")
    for rel, text in files.items():
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / rel).write_text(text, encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", msg, email=email)
    return repo


def _real_home(with_list: bool) -> Path:
    """A stand-in for the owner's real home: `<it>/.halo/privacy-terms.txt` holds the scratch list."""
    home = Path(tempfile.mkdtemp(prefix="privacy-gate-home-"))
    if with_list:
        (home / ".halo").mkdir()
        (home / ".halo" / "privacy-terms.txt").write_text(f"# scratch list\nci:\n{TERM}\n", encoding="utf-8")
    return home


def _audit(repo: Path, real_home: Path, *extra: str) -> "tuple[int, str]":
    """`halo audit privacy` the way scripts/prepush_privacy runs it: a scratch home, the list by file name."""
    base = {k: v for k, v in os.environ.items() if not k.startswith(("HALO_", "BRIDGE_"))}
    base.update(PYTHONPATH=str(REPO), PYTHONIOENCODING="utf-8")
    terms = PP.terms_file({"BRIDGE_TEST_HOME": str(real_home)})
    env = PP.audit_env(base, tempfile.mkdtemp(prefix="privacy-gate-scratch-"), terms)
    r = subprocess.run([sys.executable, "-m", "halo_harness", "audit", "privacy", "--cwd", str(repo), *extra],
                       env=env, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
    return r.returncode, r.stdout + r.stderr


@test
def test_this_run_says_whether_the_name_checks_are_on(ctx: Ctx):
    line = name_checks_line()
    print(f"    {line}")  # CI has no list by design: its log says OFF here
    ctx.check(f"one ON or OFF line, got {line!r}", line.startswith(("name checks: ON", "name checks: OFF")))


@test
def test_a_term_seeded_in_plans_fails_the_gate_by_number(ctx: Ctx):
    repo = _repo({"README.md": "clean\n", "plans/notes.md": f"the build box is {TERM.title()} now\n"})
    rc, out = _audit(repo, _real_home(True))
    ctx.check(f"the gate fails, got {rc}: {out[-400:]!r}", rc == 1)
    ctx.check("it says the name checks are ON", "name checks: ON (1 private term(s) from the file)" in out)
    ctx.check("plans/ is read and the hit names the term by number",
              "plans/notes.md:1: machine-name (term #1)" in out)
    ctx.check("the term itself is never printed", TERM not in out.lower())


@test
def test_no_list_means_one_line_saying_off(ctx: Ctx):
    home = _real_home(False)
    terms = PP.terms_file({"BRIDGE_TEST_HOME": str(home)})
    ctx.check("no list is found", terms is None)
    ctx.check("the gate's own line says OFF", "name checks OFF" in PP.name_line(terms, {}))
    repo = _repo({"plans/notes.md": f"{TERM}\n"})
    rc, out = _audit(repo, home)
    ctx.check(f"the audit says OFF in one line, got {out[:300]!r}", out.count("name checks: OFF") == 1)
    ctx.check(f"and the unknown name passes (nothing to check it against), got {rc}", rc == 0)


@test
def test_commits_fail_only_on_what_is_not_yet_on_origin(ctx: Ctx):
    repo = _repo({"a.txt": "a\n"}, msg=f"old work on {TERM}", email=PERSONAL)
    _git(repo, "update-ref", "refs/remotes/origin/master", "HEAD")
    (repo / "b.txt").write_text("b\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "clean and new")
    home = _real_home(True)
    rc, out = _audit(repo, home, "--commits")
    ctx.check(f"old commits only report, got {rc}: {out!r}", rc == 0)
    ctx.check("the old address is counted, masked", "address pa...@pe...: 1 commit(s), 0 not yet on origin/master" in out)
    ctx.check("the old message's term is counted by number", "term #1: in 1 older commit message(s)" in out)
    (repo / "c.txt").write_text("c\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", f"new work on {TERM.upper()}")
    rc, out = _audit(repo, home, "--commits")
    ctx.check(f"a term in a new commit's message fails, got {rc}", rc == 1 and "commit-message: the message carries term #1" in out)
    ctx.check("neither the term nor the address is printed", TERM not in out.lower() and PERSONAL not in out)


@test
def test_a_non_noreply_author_on_a_new_commit_fails(ctx: Ctx):
    repo = _repo({"a.txt": "a\n"}, email=PERSONAL)  # no origin/master: every commit is new
    rc, out = _audit(repo, _real_home(False), "--commits")
    ctx.check(f"fails, got {rc}: {out!r}", rc == 1 and "commit-email: author/committer pa...@pe... is not a noreply" in out)
    ctx.check("the address is never printed in full", PERSONAL not in out)
    rc, out = _audit(_repo({"a.txt": "a\n"}), _real_home(False), "--commits")
    ctx.check(f"a noreply author passes, got {rc}: {out!r}", rc == 0)


@test
def test_a_real_looking_home_path_is_caught_unless_allowlisted_whole(ctx: Ctx):
    path = "/home/" + "kali/notes/plan.md"  # built, so this file holds no such path
    found = ps.scan_text_content(f"see {path} here\n", rel_path="docs/x.md", allowlist=set())
    ctx.check(f"caught, got {found}", [f["kind"] for f in found] == ["home-path"])
    ctx.check("the whole path on the allowlist exempts it",
              ps.scan_text_content(f"see {path} here\n", rel_path="docs/x.md", allowlist={path}) == [])
    ctx.check("a generic placeholder stays fine",
              ps.scan_text_content("see /home/you/notes/plan.md\n", rel_path="docs/x.md", allowlist=set()) == [])
    escaped = "C:" + "\\\\Users\\\\" + "pat\\\\notes"  # the escaped form a Python string or JSON carries
    ctx.check("an escaped Windows profile path is caught too",
              [f["kind"] for f in ps.scan_text_content(escaped, rel_path="a.py", allowlist=set())] == ["home-path"])


@test
def test_history_reads_every_ref_and_images_are_counted_not_checked(ctx: Ctx):
    repo = _repo({"README.md": "clean\n"})
    _git(repo, "checkout", "-q", "-b", "side")
    (repo / "side.txt").write_text("host 192.168." + "77.5\n", encoding="utf-8")  # built: no address in this file
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "side")
    _git(repo, "checkout", "-q", "-")
    kinds = [f["kind"] for f in ps.scan_history(repo)]
    ctx.check(f"a branch HEAD does not reach is read, got {kinds}", "lan-ip" in kinds)
    (repo / "shot.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    nc: list = []
    ps.scan_working_tree(repo, nc)
    ctx.check(f"the image is listed as not checked, got {nc}", nc == ["shot.png"])
    rc, out = _audit(repo, _real_home(False))
    ctx.check(f"the CLI says how many, got {out!r}", "not checked: 1 file(s) that are not text" in out)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="privacy gate"))
