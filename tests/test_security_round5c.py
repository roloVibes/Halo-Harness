"""tests.test_security_round5c -- 2.0.10 round 5, security fix pass 3 (supply
chain), findings 26-27 of docs/harness/SECURITY-REVIEW-2.0.10.md.

26  the install scripts install the newest TAG (or --ref), print the tag and
    the commit, pin the uv bootstrap and the dependency versions; the README
    one-liner fetches the script from a tag URL, not from master
27  requirements.lock carries hashes for every pin and every runtime
    dependency; CI installs from it with hashes enforced and runs pip-audit
    with an allowlist file

Siblings: test_security_round5 (1-5), test_security_round5b (21-23).
"""
from __future__ import annotations

import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, SkipTest, new_registry, print_results, run_all

test, TESTS = new_registry()
REPO = Path(__file__).resolve().parent.parent
SH, PS1 = REPO / "scripts" / "install-halo.sh", REPO / "scripts" / "install-halo.ps1"
SHA = "1d001be2ee06da53a9420f8266e7124b79c5600f"
LS_REMOTE = "\n".join([
    "aaaa000000000000000000000000000000000001\trefs/tags/v2.0.9", "bbbb000000000000000000000000000000000002\trefs/tags/v2.0.9^{}",
    f"cccc000000000000000000000000000000000003\trefs/tags/v2.0.10", f"{SHA}\trefs/tags/v2.0.10^{{}}",
    "dddd000000000000000000000000000000000004\trefs/tags/v2.0.8", "eeee000000000000000000000000000000000005\trefs/tags/v2.0.11rc1",
    "ffff000000000000000000000000000000000006\trefs/tags/v1.9.0", ""])


def _bash() -> str:
    b = shutil.which("bash")
    if not b:
        raise SkipTest("no bash on PATH")
    return b


NL = chr(10)
HALO_STUB = "#!/bin/sh" + NL + 'echo "halo $*" >> "%s"' + NL + 'echo "halo 0.0.0"' + NL + "exit 0" + NL


def _stub_dir(log: Path) -> Path:
    d = Path(tempfile.mkdtemp(prefix="sec5c-stubs-"))
    ls = d / "ls-remote.txt"
    ls.write_text(LS_REMOTE, encoding="utf-8", newline="\n")
    body = ('#!/bin/sh\necho "git $*" >> "%s"\nfor a in "$@"; do last="$a"; done\n'
            'case "$1" in\n  ls-remote) if [ "$2" = "--tags" ]; then cat "%s"; else shift 2; '
            'for r in "$@"; do awk -v r="$r" \'$2==r\' "%s"; done; fi ;;\n  clone) mkdir -p "$last/.git" ;;\n'
            '  -C) case "$3" in rev-parse) [ "$4" = "HEAD" ] && echo "%s" || exit 1 ;; esac ;;\nesac\nexit 0\n'
            ) % (log.as_posix(), ls.as_posix(), ls.as_posix(), SHA)
    (d / "git").write_text(body, encoding="utf-8", newline="\n")
    (d / "uv").write_text('#!/bin/sh\necho "uv $*" >> "%s"\nexit 0\n' % log.as_posix(), encoding="utf-8", newline="\n")
    (d / "halo").write_text(HALO_STUB % log.as_posix(), encoding="utf-8", newline=NL)
    for n in ("git", "uv", "halo"):
        (d / n).chmod((d / n).stat().st_mode | stat.S_IEXEC)
    return d


def _dry(*args) -> tuple:
    scratch = Path(tempfile.mkdtemp(prefix="sec5c-home-"))
    log = scratch / "calls.log"
    stubs = _stub_dir(log)
    env = {"HOME": str(scratch), "HALO_CLONE_DIR": str(scratch / "clone"), "PATH": str(stubs) + os.pathsep + os.environ.get("PATH", "")}
    res = subprocess.run([_bash(), str(SH), "--dry-run", *args], capture_output=True, text=True, timeout=60, env=env)
    return res, log


@test
def test_f26_default_is_the_newest_tag_and_dry_run_touches_nothing(ctx: Ctx):
    res, log = _dry()
    out = res.stdout
    ctx.check("f26 dry run exits 0", res.returncode == 0)
    ctx.check("f26 it resolves the newest tag instead of pulling a branch",
              "git ls-remote --tags" in out and "checkout --detach <latest-tag>" in out and "pull" not in out)
    ctx.check("f26 dry run ran no git (no network)", not log.exists() or "git ls-remote" not in log.read_text(encoding="utf-8"))
    ctx.check("f26 the install uses the pinned lock", "uv tool install --reinstall --constraints requirements.lock ." in out)
    res, _ = _dry("--ref", "v2.0.7")
    ctx.check("f26 --ref v2.0.7 is used verbatim", "checkout --detach v2.0.7" in res.stdout and "<latest-tag>" not in res.stdout)
    res, _ = _dry("--no-clone", "--ref=v2.0.7")
    ctx.check("f26 --no-clone installs git+URL@ref with that ref's lock as constraints",
              "git+https://github.com/roloVibes/Halo-Harness@v2.0.7" in res.stdout
              and "--constraints https://raw.githubusercontent.com/roloVibes/Halo-Harness/v2.0.7/requirements.lock" in res.stdout)
    res = subprocess.run([_bash(), str(SH), "--dry-run", "--ref"], capture_output=True, text=True, timeout=30)
    ctx.check("f26 --ref without a value is a usage error", res.returncode == 2 and "--ref needs a value" in res.stdout)


@test
def test_f26_real_resolution_picks_the_highest_release_tag(ctx: Ctx):
    scratch = Path(tempfile.mkdtemp(prefix="sec5c-real-"))
    log = scratch / "calls.log"
    stubs = _stub_dir(log)
    env = {"HOME": str(scratch), "HALO_CLONE_DIR": str(scratch / "clone"), "PATH": str(stubs) + os.pathsep + os.environ.get("PATH", "")}
    res = subprocess.run([_bash(), str(SH), "--yes"], capture_output=True, text=True, timeout=90, env=env)
    calls = log.read_text(encoding="utf-8") if log.exists() else ""
    ctx.check("f26 the newest vX.Y.Z (2.0.10, not 2.0.9, not the rc) is chosen and printed with its peeled commit",
              f"Installing v2.0.10 (commit {SHA})" in res.stdout)
    ctx.check("f26 the clone is checked out detached at that tag", "checkout --detach v2.0.10" in calls)
    ctx.check("f26 the commit actually checked out is printed", f"Checked out v2.0.10 at commit {SHA}" in res.stdout)
    ctx.check("f26 the dependencies are pinned by the lock", "uv tool install --reinstall --constraints requirements.lock ." in calls)
    ctx.check("f26 no branch pull anywhere", "pull" not in calls)


@test
def test_f26_script_text_pins_the_bootstrap_and_the_readme_uses_a_tag(ctx: Ctx):
    sh, ps1 = SH.read_text(encoding="utf-8"), PS1.read_text(encoding="utf-8")
    ctx.check("f26 the uv bootstrap is version-pinned in both scripts",
              "astral.sh/uv/${UV_INSTALLER_VERSION}/install.sh" in sh and "astral.sh/uv/$UvInstallerVersion/install.ps1" in ps1
              and "astral.sh/uv/install" not in sh and "astral.sh/uv/install" not in ps1)
    readme = (REPO / "README.md").read_text(encoding="utf-8")
    ctx.check("f26 the README one-liners fetch the scripts from a tag URL, not master",
              re.search(r"Halo-Harness/v\d+\.\d+\.\d+[^/]*/scripts/install-halo\.sh \| bash", readme)
              and re.search(r"Halo-Harness/v\d+\.\d+\.\d+[^/]*/scripts/install-halo\.ps1", readme)
              and "master/scripts/install-halo" not in readme)
    ctx.check("f26 --ref is documented in README, INSTALL.md and COMMANDS.md",
              all("--ref" in (REPO / f).read_text(encoding="utf-8") for f in ("README.md", "docs/INSTALL.md", "docs/COMMANDS.md")))


@test
def test_f26_powershell_script_resolves_and_prints_the_ref(ctx: Ctx):
    exe = next((e for e in ("pwsh", "powershell") if shutil.which(e)), None)
    if not exe:
        raise SkipTest("no pwsh/powershell on PATH")
    d = Path(tempfile.mkdtemp(prefix="sec5c-ps-"))
    base = [exe, "-NoProfile", "-File", str(PS1), "-DryRun", "-CloneDir", str(d / "clone")]
    out = subprocess.run(base, capture_output=True, text=True, timeout=90).stdout
    ctx.check("f26 ps1 default resolves the newest tag", "git ls-remote --tags" in out and "checkout --detach <latest-tag>" in out)
    out = subprocess.run(base + ["-Ref", "v2.0.7"], capture_output=True, text=True, timeout=90).stdout
    ctx.check("f26 ps1 -Ref is used verbatim and the lock constrains the install",
              "checkout --detach v2.0.7" in out and "--constraints requirements.lock" in out)


# ---- 27 ---------------------------------------------------------------------------------

@test
def test_f27_lock_has_hashes_for_every_pin_and_every_runtime_dependency(ctx: Ctx):
    text = (REPO / "requirements.lock").read_text(encoding="utf-8")
    ctx.check("f27 the header documents the regeneration command",
              "uv pip compile pyproject.toml --universal --generate-hashes -o requirements.lock" in text.splitlines()[1])
    blocks = re.split(r"\n(?=[A-Za-z0-9_.-]+==)", text)[1:]
    ctx.check("f27 the lock pins a real set of packages", len(blocks) > 30)
    unhashed = [b.splitlines()[0] for b in blocks if not re.search(r"--hash=sha256:[0-9a-f]{64}", b)]
    ctx.check(f"f27 every pin has at least one sha256 hash, missing: {unhashed[:3]}", unhashed == [])
    names = {m.group(1).lower().replace("_", "-") for m in re.finditer(r"^([A-Za-z0-9_.-]+)==", text, re.M)}
    pyproject = (REPO / "pyproject.toml").read_text(encoding="utf-8")
    deps = re.search(r"dependencies = \[(.*?)\]", pyproject, re.S).group(1)
    wanted = {m.group(1).lower() for m in re.finditer(r'"([A-Za-z0-9_.-]+)\s*[<>=]', deps)}
    ctx.check(f"f27 every runtime dependency is in the lock, missing: {sorted(wanted - names)}", wanted <= names)


@test
def test_f27_ci_installs_from_the_lock_and_audits_it_in_both_jobs(ctx: Ctx):
    import yaml
    wf = yaml.safe_load((REPO / ".github" / "workflows" / "suites.yml").read_text(encoding="utf-8"))
    for job in ("linux", "windows"):
        runs = [str(s.get("run") or "") for s in wf["jobs"][job]["steps"]]
        ctx.check(f"f27 {job}: hashed install from requirements.lock", any("--require-hashes" in r and "requirements.lock" in r for r in runs))
        ctx.check(f"f27 {job}: pip-audit runs through the gate script", any("scripts/pip_audit_gate.py" in r for r in runs)
                  and any("requirements-ci.lock" in r and "--require-hashes" in r for r in runs))
    ctx.check("f27 the allowlist file exists", (REPO / ".github" / "pip-audit-allowlist.txt").is_file())


@test
def test_f27_audit_gate_builds_the_ignore_list_from_the_allowlist(ctx: Ctx):
    sys.path.insert(0, str(REPO / "scripts"))
    import pip_audit_gate as gate
    allow = Path(tempfile.mkdtemp(prefix="sec5c-allow-")) / "allow.txt"
    allow.write_text("# header\nGHSA-aaaa-bbbb-cccc  # not reachable from Halo, review 2027-01\n\nPYSEC-2026-1\n", encoding="utf-8")
    argv = gate.audit_argv(Path("requirements.lock"), allow)
    ctx.check("f27 allowlisted ids become --ignore-vuln pairs, comments ignored",
              [argv[i + 1] for i, a in enumerate(argv) if a == "--ignore-vuln"] == ["GHSA-aaaa-bbbb-cccc", "PYSEC-2026-1"])
    ctx.check("f27 the audit runs against the lock without resolving anything", "--disable-pip" in argv and "--requirement" in argv)
    ctx.check("f27 a missing allowlist means no ignores", "--ignore-vuln" not in gate.audit_argv(Path("x"), allow.with_name("none.txt")))
    ctx.check("f27 the committed allowlist is parseable (no accepted ids yet)", isinstance(gate.read_allowlist(REPO / ".github" / "pip-audit-allowlist.txt"), list))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
