"""tests.test_update_extras -- 3.6.0.0 fix package update-install: the lines halo prints to add an extra (voice,
mlx, images, tls) work, and `halo update` keeps the extras an install was made with.

Halo is installed from GitHub; `halo-harness` is not on PyPI. The old lines (`uv tool install --reinstall
"halo-harness[voice]"`, `uv tool install "halo-harness[mlx]"`, `pip install 'halo-harness[tls]'`) could only fail
("there are no versions of halo-harness[voice]"), and a reinstall that names no extra drops one installed by hand.

1. update.extra_install_line builds the line from the install's own record: the installer (uv receipt, pipx
   metadata, else this interpreter's pip), the source (a git install's tag or exact commit, a checkout's folder),
   the extras already asked for;
2. install_kind's reinstall command carries the extras of a uv or pipx install, and `--to` still retargets it;
3. no line in the package, the README or docs/ names a bare `halo-harness[<extra>]` to install.
"""
from __future__ import annotations

import json
import re
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402
from tests.helpers.provider_env_defaults import ensure_scoped_state_dir_once  # noqa: E402

ensure_scoped_state_dir_once()

from halo_harness import update as upd  # noqa: E402

test, TESTS = new_registry()
REPO = Path(__file__).resolve().parent.parent
GIT = {"url": "https://github.com/roloVibes/Halo-Harness",
       "vcs_info": {"vcs": "git", "commit_id": "6a66b6d97c9e6c864cc61a09dd04b66af147672c", "requested_revision": "v3.5.0.1"}}


def _prefix(kind: str, extras=()) -> str:
    p = Path(tempfile.mkdtemp(prefix="halo-extras-"))
    if kind == "uv":
        ex = f', extras = [{", ".join(json.dumps(e) for e in extras)}]' if extras else ""
        (p / "uv-receipt.toml").write_text(
            '[tool]\nrequirements = [{ name = "halo-harness", git = "https://github.com/roloVibes/Halo-Harness?rev='
            f'v3.5.0.1"{ex} }}]\nconstraints = [\n    {{ name = "rich", specifier = "==15.0.0" }},\n]\n', encoding="utf-8")
    elif kind == "pipx":
        spec = "git+https://github.com/roloVibes/Halo-Harness@v3.5.0.1"
        main = f"halo-harness[{','.join(extras)}] @ {spec}" if extras else spec
        (p / "pipx_metadata.json").write_text(json.dumps({"main_package": {"package_or_url": main,
                                                                            "package": "halo-harness"}}), encoding="utf-8")
    return str(p)


@test
def test_the_extra_line_names_this_install_never_a_bare_pypi_name(ctx: Ctx):
    line = upd.extra_install_line("voice", direct_url=GIT, prefix=_prefix("uv", ["tls"]))
    ctx.check(f"uv, git install at a tag: the tag, the lock of that tag, the extras kept, got {line!r}",
              line == ('uv tool install --reinstall --constraints https://raw.githubusercontent.com/roloVibes/'
                       'Halo-Harness/v3.5.0.1/requirements.lock "halo-harness[tls,voice] @ '
                       'git+https://github.com/roloVibes/Halo-Harness@v3.5.0.1"'))
    on_main = {**GIT, "vcs_info": {**GIT["vcs_info"], "requested_revision": "master"}}
    line = upd.extra_install_line("mlx", direct_url=on_main, prefix=_prefix("uv"))
    ctx.check(f"a main-line install is pinned to its exact commit (adding an extra is not an update), got {line!r}",
              '"halo-harness[mlx] @ git+https://github.com/roloVibes/Halo-Harness@6a66b6d97c9e' in line)
    clone = Path(tempfile.mkdtemp(prefix="halo-extras-clone-"))
    (clone / "requirements.lock").write_text("rich==15.0.0\n", encoding="utf-8")
    line = upd.extra_install_line("voice", direct_url={"url": clone.as_uri(), "dir_info": {"editable": True}},
                                  prefix=_prefix("uv"))
    ctx.check(f"an editable checkout: its folder, its lock, --editable, got {line!r}",
              line.startswith("uv tool install --reinstall --constraints ") and "--editable" in line
              and line.endswith(f'"{clone}[voice]"') and str(clone / "requirements.lock") in line)
    line = upd.extra_install_line("images", direct_url=GIT, prefix=_prefix("pipx", ["voice"]))
    ctx.check(f"pipx: pipx, the extras it was installed with kept, got {line!r}",
              line == 'pipx install --force "halo-harness[images,voice] @ git+https://github.com/roloVibes/Halo-Harness@v3.5.0.1"')
    line = upd.extra_install_line("tls", direct_url=GIT, prefix=_prefix("pip"))
    ctx.check(f"pip: this interpreter's pip, got {line!r}", " -m pip install " in line and sys.executable in line
              and line.endswith('"halo-harness[tls] @ git+https://github.com/roloVibes/Halo-Harness@v3.5.0.1"'))
    ctx.check("an install with no record falls back to the repository, never the bare name",
              '"halo-harness[voice] @ git+https://github.com/roloVibes/Halo-Harness"' in
              upd.extra_install_line("voice", direct_url={}, prefix=_prefix("pip")))


@test
def test_halo_update_keeps_the_extras_the_install_was_made_with(ctx: Ctx):
    import subprocess
    from halo_harness import update_cli

    def nothing_listed(cmd, **kw):  # `uv tool list` / `pipx list` name nothing: the marker files decide
        return subprocess.CompletedProcess(cmd, 1, "", "")
    for kind, want in (("uv", "uv tool install --reinstall"), ("pipx", "pipx install --force")):
        got = upd.install_kind(direct_url=GIT, prefix=_prefix(kind, ["voice"]), run_fn=nothing_listed)
        cmd = got["reinstall_cmd"]
        ctx.check(f"{kind}: the reinstall names the voice extra, got {cmd!r}", cmd.startswith(want)
                  and cmd.endswith('"halo-harness[voice] @ git+https://github.com/roloVibes/Halo-Harness@v3.5.0.1"'))
        moved = update_cli._retarget_cmd(cmd, got["spec"], "v3.6.0.0")
        ctx.check(f"{kind}: --to moves the ref inside it, got {moved!r}",
                  moved.endswith('"halo-harness[voice] @ git+https://github.com/roloVibes/Halo-Harness@v3.6.0.0"'))
    got = upd.install_kind(direct_url=GIT, prefix=_prefix("uv"), run_fn=nothing_listed)
    ctx.check(f"no extra asked for: the command is as before, got {got['reinstall_cmd']!r}",
              got["reinstall_cmd"].endswith(" git+https://github.com/roloVibes/Halo-Harness@v3.5.0.1"))
    ctx.check("the receipt's extras are read", upd.requested_extras(_prefix("uv", ["mlx", "voice"])) == ["mlx", "voice"])


@test
def test_the_printed_lines_come_from_the_install(ctx: Ctx):
    from halo_harness import voice  # 3.6.0.3 B: the clip's Pillow line left with the clip; no kept code prints the images one
    # voice reads its line ONCE per process (voice.install_line), so in a shard where an earlier module had already
    # asked for it, this compared a line made THEN with one made NOW; when a module in between leaves the process
    # looking like another install, the two differ (the release gate of 3.6.0.5, on Linux, Windows and macOS, the
    # day a new test module moved this one to another shard). The check is that voice's line IS the install's line:
    # both are made now.
    voice._LINE.clear()
    want = upd.extra_install_line("voice")
    ctx.check(f"voice's line, got {voice.INSTALL_LINE!r}, the install's {want!r}", voice.INSTALL_LINE == want)
    bare = re.compile(r"""halo-harness\[[\w,]+\]["'`]""")
    hits, unpinned = [], []
    # checker, batch 1: the steward's knowledge (*.md under halo_harness) too, and a line broken after `install`
    for path in (list((REPO / "halo_harness").rglob("*.py")) + list((REPO / "halo_harness").rglob("*.md"))
                 + [REPO / "README.md"] + list((REPO / "docs").rglob("*.md"))):
        text = path.read_text(encoding="utf-8", errors="replace")
        for m in bare.finditer(text):
            if re.search(r"\binstall\b", text[max(0, m.start() - 120):m.start()]):
                hits.append(f"{path.relative_to(REPO)}:{text.count(chr(10), 0, m.start()) + 1}")
        if path.suffix == ".md":  # a pasted doc line keeps the dependency pins, as the install line itself does
            for m in re.finditer(r"install [^`\n]*\"halo-harness\[[\w,]+\] @ git\+[^`\n]*", text):
                if "--constraints" not in m.group(0):
                    unpinned.append(f"{path.relative_to(REPO)}:{text.count(chr(10), 0, m.start()) + 1}")
    ctx.check(f"no install line names a bare `halo-harness[<extra>]`, got {hits}", hits == [])
    ctx.check(f"every doc line that adds an extra carries the lock (--constraints), got {unpinned}", unpinned == [])


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
