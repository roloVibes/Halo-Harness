#!/usr/bin/env python3
"""The way up from the released 3.5.0.1, measured on a throwaway machine (the CI job
`upgrade from 3.5.0.1 (<os>)` in .github/workflows/suites.yml runs it on Linux, macOS and Windows).

A person on 3.5.0.1 reaches the next version with the OLD updater, the one inside 3.5.0.1. This script
installs 3.5.0.1 the way its own installer does, then takes each way up the docs name ("From 3.5.0.1,
once" in docs/INSTALL.md), each from a fresh 3.5.0.1 install, aimed at one commit (`--sha`, the run's own):

  A  `halo update` typed in a shell, nothing else of Halo running (a clone install and a --no-clone one).
     3.5.0.1's updater is aimed with its own flags: `--to <sha>` moves the reinstall to the commit, and
     `--channel main` makes it compare with the default branch, because on the stable channel it answers
     "already up to date" while 3.5.0.1 is the newest release and never reaches the `--to`.
  B  (Windows) the same while a second halo of that install runs (`halo studio --no-open`).
  C1 the repair line: `halo studio --stop`, then `uv tool install --reinstall` of the commit with its
     requirements.lock as constraints.
  C2 this commit's own installer (scripts/install-halo.sh or .ps1) with `--ref <sha>` over the same clone.
  D  the `/update` hand-off: 3.5.0.1's own `update_detached.run_after_exit` (what `/update` calls when the
     session quits), its reinstall aimed by its own `reinstall_cmd(to=<sha>)`.

After each way: `halo --version`, the tool environment's python importing `halo_harness` (the "half install"
an update from inside a running halo once left on Windows), `halo doctor` and `halo ps` exit codes. One table
at the end (and in $GITHUB_STEP_SUMMARY). Exit 1 when a way the docs recommend leaves a halo that cannot start
or is not at the commit.

It installs and removes Halo for real, so it runs only where GITHUB_ACTIONS=true (a CI runner); anywhere else
use `--dry-run`, which prints every command and runs none.
"""
from __future__ import annotations

import argparse
import os
import re
import shlex
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

OLD_TAG = "v3.5.0.1"
OLD_VERSION = "3.5.0.1"
REPO_URL = "https://github.com/roloVibes/Halo-Harness"
RAW_URL = "https://raw.githubusercontent.com/roloVibes/Halo-Harness"
INSTALL_TIMEOUT_S = 1200
CHECK_TIMEOUT_S = 120
DETACHED_TIMEOUT_S = 1200
_VERSION_RE = re.compile(r"^halo\s+(\S+)(?:\s+\(([0-9a-fA-F]+)(?:,\s*([^)]*))?\))?")

# The `/update` hand-off of 3.5.0.1, aimed at a commit by its own `reinstall_cmd(to=...)` (argv[1]).
DETACHED_DRIVER = ("import sys; from halo_harness import update_detached as D; print('LOG=' + str(D.log_path()), flush=True); "
                   "_orig = D.reinstall_cmd; D.reinstall_cmd = lambda to=None: _orig(to=sys.argv[1]); "
                   "sys.exit(D.run_after_exit())")


@dataclass
class Way:
    key: str
    title: str
    kind: str  # the 3.5.0.1 install it starts from: "clone" (the installer's default) or "git" (--no-clone)
    recommended: bool  # the docs tell people to take it on this system
    steps: List[List[str]]  # the update itself, in order; the exit code of the last one is the update's
    background: Optional[List[str]] = None  # a second halo started before the update and stopped after it
    detached: bool = False  # the steps start the /update hand-off; wait for its log to say "=== done"
    tolerate: List[int] = field(default_factory=list)  # step indexes whose exit code is not the update's


@dataclass
class Row:
    way: str
    recommended: bool
    update_exit: Optional[int] = None
    version_line: str = ""
    at_commit: bool = False
    importable: bool = False
    doctor_exit: Optional[int] = None
    ps_exit: Optional[int] = None
    seconds: float = 0.0
    note: str = ""

    def starts(self) -> bool:
        return bool(parse_version_line(self.version_line)) and self.importable

    def ok(self) -> bool:
        return self.starts() and self.at_commit


def system_name(platform: Optional[str] = None) -> str:
    p = (platform or sys.platform).lower()
    if p.startswith("win"):
        return "windows"
    if p == "darwin" or p.startswith("mac"):
        return "macos"
    return "linux"


def parse_version_line(text: str) -> Optional[dict]:
    """`halo 3.5.0.1 (6a66b6d, v3.5.0.1)` -> {"version", "commit", "ref"}; the last line that reads like one."""
    for line in reversed((text or "").strip().splitlines()):
        m = _VERSION_RE.match(line.strip())
        if m:
            return {"version": m.group(1), "commit": (m.group(2) or "").lower() or None,
                    "ref": (m.group(3) or "").strip() or None}
    return None


def commit_matches(found: Optional[str], sha: str) -> bool:
    """A short commit from `halo --version` names `sha` when one is a prefix of the other (7 characters at least)."""
    if not found or not sha or len(found) < 7:
        return False
    a, b = found.lower(), sha.lower()
    return a.startswith(b) or b.startswith(a)


def show(argv: List[str], system: str) -> str:
    return subprocess.list2cmdline(argv) if system == "windows" else shlex.join(argv)


def tool_python(tool_dir: str, system: str) -> str:
    sub = ("Scripts", "python.exe") if system == "windows" else ("bin", "python")
    return str(Path(tool_dir, "halo-harness", *sub))


def installer_cmd(system: str, script: str, ref: str, clone_dir: str, *, no_clone: bool = False) -> List[str]:
    """Halo's installer (3.5.0.1's or this commit's), no questions, no shell-file edits, at `ref`."""
    if system == "windows":
        argv = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", script,
                "-Yes", "-NoModifyPath", "-Ref", ref, "-CloneDir", clone_dir]
        return argv + (["-NoClone"] if no_clone else [])
    argv = ["bash", script, "--yes", "--no-modify-path", "--ref", ref, f"--dir={clone_dir}"]
    return argv + (["--no-clone"] if no_clone else [])


def repair_cmd(sha: str) -> List[str]:
    """The repair line of docs/INSTALL.md, at `sha` instead of the release tag."""
    return ["uv", "tool", "install", "--reinstall", "--constraints", f"{RAW_URL}/{sha}/requirements.lock",
            f"git+{REPO_URL}@{sha}"]


def update_cmd(sha: str) -> List[str]:
    """3.5.0.1's `halo update`, aimed at `sha` with the flags it has (see the module docstring)."""
    return ["halo", "update", "--channel", "main", "--to", sha]


def plan(system: str, sha: str, *, new_script: str) -> List[Way]:
    """Every way up for `system`, in the order they run. `<clone>` and `<py>` (the tool environment's python)
    are filled in when the way runs."""
    win = system == "windows"
    ways = [
        Way("A clone", "halo update in a shell (clone install)", "clone", not win, [update_cmd(sha)]),
        Way("A git", "halo update in a shell (--no-clone install)", "git", not win, [update_cmd(sha)]),
    ]
    if win:
        ways.append(Way("B studio", "halo update while `halo studio` runs", "clone", False, [update_cmd(sha)],
                        background=["halo", "studio", "--no-open"]))
    ways += [
        Way("C1 repair", "the repair line (studio --stop, uv tool install)", "clone", True,
            [["halo", "studio", "--stop"], repair_cmd(sha)], tolerate=[0]),
        Way("C2 installer", "this commit's installer --ref <sha>", "clone", True,
            [installer_cmd(system, new_script, sha, "<clone>")]),
        Way("D /update", "the /update hand-off (runs after halo exits)", "clone", win,
            [["<py>", "-I", "-c", DETACHED_DRIVER, sha]], detached=True),
    ]
    return ways


def markdown_table(rows: List[Row], system: str, sha: str) -> str:
    out = [f"### upgrade from {OLD_VERSION} ({system}) to {sha[:12]}", "",
           "| way | docs | update exit | version after | at this commit | package importable | doctor | ps | seconds | note |",
           "|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        cell = lambda v: "-" if v is None else str(v)  # noqa: E731
        out.append(f"| {r.way} | {'recommended' if r.recommended else 'informs'} | {cell(r.update_exit)} | "
                   f"`{(r.version_line or '(none)').replace('|', '/')}` | {'yes' if r.at_commit else 'no'} | "
                   f"{'yes' if r.importable else 'NO'} | {cell(r.doctor_exit)} | {cell(r.ps_exit)} | "
                   f"{r.seconds:.0f} | {r.note.replace('|', '/')} |")
    bad = [r.way for r in rows if r.recommended and not r.ok()]
    out += ["", f"**Failed (a recommended way left a halo that cannot start or is not at this commit):** {', '.join(bad)}"
            if bad else "Every recommended way left a halo that starts at this commit."]
    return "\n".join(out) + "\n"


def verdict(rows: List[Row]) -> int:
    return 1 if any(r.recommended and not r.ok() for r in rows) else 0


# ---------------------------------------------------------------------------------------------- running it


class Runner:
    def __init__(self, system: str, sha: str, work: Path, dry: bool):
        self.system, self.sha, self.work, self.dry = system, sha, work, dry
        self.env = dict(os.environ, OLLAMA_HOST="http://127.0.0.1:9", HALO_NO_BROWSER="1", PYTHONUTF8="1")
        local_bin = str(Path.home() / ".local" / "bin")
        self.env["PATH"] = local_bin + os.pathsep + self.env.get("PATH", "")

    def say(self, text: str) -> None:
        print(text, flush=True)

    def _argv(self, argv: List[str]) -> List[str]:
        found = shutil.which(argv[0], path=self.env["PATH"])
        return [found or argv[0], *argv[1:]]

    def run(self, argv: List[str], *, timeout: int, capture: bool = False, cwd: Optional[Path] = None):
        """(exit code or None on a timeout/failure to start, captured text)."""
        self.say(f"$ {show(argv, self.system)}")
        if self.dry:
            return 0, ""
        try:
            p = subprocess.run(self._argv(argv), env=self.env, cwd=str(cwd or self.work), timeout=timeout,
                               stdout=subprocess.PIPE if capture else None,
                               stderr=subprocess.STDOUT if capture else None, text=True, errors="replace")
        except subprocess.TimeoutExpired:
            self.say(f"(timed out after {timeout} s)")
            return None, ""
        except OSError as exc:
            self.say(f"(could not start: {exc})")
            return None, ""
        text = p.stdout or ""
        if capture and text:
            self.say("\n".join(text.rstrip().splitlines()[-15:]))
        return p.returncode, text

    def tool_dir(self) -> str:
        if self.dry:
            return "<uv tool dir>"
        code, text = self.run(["uv", "tool", "dir"], timeout=CHECK_TIMEOUT_S, capture=True)
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        return lines[-1] if code == 0 and lines else str(Path.home() / ".local" / "share" / "uv" / "tools")

    def old_installer(self) -> str:
        name = "install-halo.ps1" if self.system == "windows" else "install-halo.sh"
        dest = self.work / f"old-{name}"
        argv = ["git", "show", f"{OLD_TAG}:scripts/{name}"]
        self.say(f"$ {show(argv, self.system)} > {dest}")
        if not self.dry:
            p = subprocess.run(argv, stdout=subprocess.PIPE)
            if p.returncode != 0:  # the tag was not fetched with the checkout
                subprocess.run(["git", "fetch", "origin", f"refs/tags/{OLD_TAG}:refs/tags/{OLD_TAG}"])
                p = subprocess.run(argv, stdout=subprocess.PIPE, check=True)
            dest.write_bytes(p.stdout)
        return str(dest)

    def fresh_state(self, clone: Path) -> None:
        """A person's state as a fresh 3.5.0.1 install leaves it: no ~/.halo from an earlier way, a new clone."""
        for d in (Path.home() / ".halo", clone):
            self.say(f"(remove {d})")
            if not self.dry:
                shutil.rmtree(d, ignore_errors=True)

    def wait_detached(self, text: str) -> "tuple[Optional[int], str]":
        m = re.search(r"^LOG=(.+)$", text, re.M)
        if self.dry or not m:
            return (0 if self.dry else None), ("" if self.dry else "no LOG= line from the hand-off")
        log, start = Path(m.group(1).strip()), time.time()
        while time.time() - start < DETACHED_TIMEOUT_S:
            body = log.read_text(encoding="utf-8", errors="replace") if log.is_file() else ""
            if "=== done" in body:
                self.say("\n".join(body.rstrip().splitlines()[-15:]))
                code = re.findall(r"reinstall exit code (-?\d+)", body)
                return (int(code[-1]) if code else None), ""
            time.sleep(3)
        return None, f"the hand-off did not finish in {DETACHED_TIMEOUT_S} s"

    def check(self, row: Row, py: str) -> None:
        _, text = self.run(["halo", "--version"], timeout=CHECK_TIMEOUT_S, capture=True)
        parsed = parse_version_line(text)
        lines = [ln.strip() for ln in text.strip().splitlines() if ln.strip()]
        row.version_line = next((ln for ln in reversed(lines) if _VERSION_RE.match(ln)), lines[-1] if lines else "")[:100]
        row.at_commit = bool(parsed) and commit_matches(parsed.get("commit"), self.sha)
        code, text = self.run([py, "-I", "-c", "import halo_harness, sys; print(halo_harness.__file__)"],
                              timeout=CHECK_TIMEOUT_S, capture=True)
        row.importable = code == 0 and "halo_harness" in text
        row.doctor_exit, _ = self.run(["halo", "doctor"], timeout=300, capture=True)
        row.ps_exit, _ = self.run(["halo", "ps"], timeout=CHECK_TIMEOUT_S, capture=True)

    def take(self, way: Way, old_script: str) -> Row:
        row = Row(way.key, way.recommended)
        clone = self.work / ("clone-" + re.sub(r"[^a-z0-9]+", "-", way.key.lower()).strip("-"))
        self.say(f"::group::{way.key}: {way.title}")
        try:
            self.fresh_state(clone)
            code, _ = self.run(installer_cmd(self.system, old_script, OLD_TAG, str(clone), no_clone=way.kind == "git"),
                               timeout=INSTALL_TIMEOUT_S)
            _, text = self.run(["halo", "--version"], timeout=CHECK_TIMEOUT_S, capture=True)
            parsed = parse_version_line(text)
            if not self.dry and (code != 0 or not parsed or parsed["version"] != OLD_VERSION):
                row.note = f"{OLD_VERSION} did not install (installer exit {code}); way not measured"
                return row
            py = tool_python(self.tool_dir(), self.system)
            bg = None
            if way.background:
                self.say(f"$ {show(way.background, self.system)} &")
                if not self.dry:
                    bg = subprocess.Popen(self._argv(way.background), env=self.env, cwd=str(self.work),
                                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL)
                    time.sleep(10)
                    row.note = "second halo up" if bg.poll() is None else f"second halo ended early ({bg.returncode})"
            start = time.time()
            for i, step in enumerate(way.steps):
                step = [py if a == "<py>" else a.replace("<clone>", str(clone)) for a in step]
                code, text = self.run(step, timeout=INSTALL_TIMEOUT_S, capture=way.detached)
                if way.detached:
                    code, why = self.wait_detached(text)
                    row.note = (row.note + "; " + why).strip("; ") if why else row.note
                if i not in way.tolerate:
                    row.update_exit = code
            row.seconds = time.time() - start
            if bg is not None:
                still = bg.poll() is None
                row.note += "; still running after the update, stopped" if still else "; ended by the update"
                if still:
                    bg.terminate()
                    try:
                        bg.wait(timeout=20)
                    except subprocess.TimeoutExpired:
                        bg.kill()
            self.check(row, py)
            self.run(["halo", "studio", "--stop"], timeout=CHECK_TIMEOUT_S, capture=True)
            return row
        finally:
            self.say("::endgroup::")


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="upgrade_from_3501.py", description=__doc__.split("\n\n")[0])
    ap.add_argument("--sha", default=os.environ.get("GITHUB_SHA") or "<sha>", help="the commit every way aims at")
    ap.add_argument("--work", default=None, help="a scratch folder for the installers and clones")
    ap.add_argument("--system", choices=["linux", "macos", "windows"], default=None,
                    help="(dry run) print the commands of this system")
    ap.add_argument("--only", default=None, help="comma-separated way keys' first words (A,B,C1,C2,D)")
    ap.add_argument("--dry-run", action="store_true", help="print every command, run none")
    args = ap.parse_args(argv)
    system = args.system or system_name()
    if not args.dry_run:
        if os.environ.get("GITHUB_ACTIONS") != "true":
            print("upgrade_from_3501.py installs and removes Halo for real: it runs only on a CI runner "
                  "(GITHUB_ACTIONS=true). Use --dry-run here.", file=sys.stderr)
            return 2
        if args.system and args.system != system_name():
            print("--system is for --dry-run only", file=sys.stderr)
            return 2
        if not re.fullmatch(r"[0-9a-f]{40}", args.sha):
            print(f"--sha must be a full commit sha, not {args.sha!r}", file=sys.stderr)
            return 2
    work = Path(args.work or (Path(os.environ.get("RUNNER_TEMP") or ".") / "upgrade-from-3501")).resolve()
    if not args.dry_run:
        work.mkdir(parents=True, exist_ok=True)
    r = Runner(system, args.sha, work, args.dry_run)
    old_script = r.old_installer()
    new_name = "install-halo.ps1" if system == "windows" else "install-halo.sh"
    new_script = str(Path(__file__).resolve().parent / new_name)
    ways = plan(system, args.sha, new_script=new_script)
    if args.only:
        keep = {k.strip() for k in args.only.split(",")}
        ways = [w for w in ways if w.key.split()[0] in keep]
    rows = [r.take(w, old_script) for w in ways]
    if args.dry_run:
        print(f"(dry run: {len(rows)} ways printed, nothing ran)")
        return 0
    table = markdown_table(rows, system, args.sha)
    print(table)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write(table)
    return verdict(rows)


if __name__ == "__main__":
    sys.exit(main())
