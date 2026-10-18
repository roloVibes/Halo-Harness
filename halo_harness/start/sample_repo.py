"""halo_harness.start.sample_repo -- step 2 of `halo start`: the sample repo
(Halo 3.1.1.0 R1).

`make_sample_repo(state_dir)` writes `<state dir>/start/<yyyy-mm-dd>/basket/`
(`basket-2`, `basket-3`, ... when today's is already there): the shipped
Orchestra sample (templates/orchestra/basket.py, five functions whose bodies
raise NotImplementedError, and test_basket.py), a .gitignore, `git init` and one commit.
`use_repo(path, files)` checks a repo of your own (`--repo`): a git repo
that holds every file the goal names.
"""

from __future__ import annotations

import datetime as _dt
import subprocess
import sys
from pathlib import Path

TEMPLATES = Path(__file__).resolve().parent.parent / "templates" / "orchestra"
SAMPLE_FILES = ("basket.py", "test_basket.py")


class RepoError(ValueError):
    pass


def start_root(state_dir) -> Path:
    return Path(state_dir) / "start"


def _git(repo: Path, *args: str) -> str:
    try:
        out = subprocess.run(["git", *args], cwd=str(repo), capture_output=True, text=True, encoding="utf-8",
                             errors="replace")
    except OSError as e:
        raise RepoError(f"git is not available ({e}): install git, then run halo start again")
    if out.returncode != 0:
        raise RepoError(f"git {' '.join(args)}: {out.stderr.strip() or out.stdout.strip()}")
    return out.stdout


def _free_folder(day: Path) -> Path:
    path, n = day / "basket", 2
    while path.exists():
        path, n = day / f"basket-{n}", n + 1
    return path


def make_sample_repo(state_dir, today=None) -> Path:
    """The new sample repo's folder (a git repo with one commit)."""
    day = start_root(state_dir) / (today or _dt.date.today().isoformat())
    repo = _free_folder(day)
    repo.mkdir(parents=True)
    for name in SAMPLE_FILES:
        text = (TEMPLATES / name).read_text(encoding="utf-8")
        (repo / name).write_text(text, encoding="utf-8", newline="\n")
    (repo / ".gitignore").write_text("__pycache__/\n", encoding="utf-8", newline="\n")
    _git(repo, "init", "-q")
    for key, value in (("user.name", "halo start"), ("user.email", "start@halo.invalid"), ("core.autocrlf", "false"),
                       ("commit.gpgsign", "false")):
        _git(repo, "config", key, value)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "basket: five functions to write")
    return repo


def use_repo(path, files) -> Path:
    """Your own repo for `--repo`: its git root, when it holds every file in `files`."""
    from halo_harness.worktree import repo_root
    root = repo_root(Path(path).resolve())
    if root is None:
        raise RepoError(f"{path} is not in a git repo: give --repo a git repo, or leave it out for the sample")
    missing = [f for f in files if not (Path(root) / f).is_file()]
    if missing:
        raise RepoError(f"{root} has no {', '.join(missing)}: the start's goal writes them; give --file for "
                        "the files your goal shares, or leave --repo out for the sample")
    return Path(root)


def test_command() -> str:
    """The test the gate runs on the sample repo."""
    return f'"{sys.executable}" -m unittest -q test_basket'


def describe(repo: Path) -> "list[str]":
    lines = [f"the sample repo: {repo}"]
    for name in SAMPLE_FILES:
        if (repo / name).is_file():
            lines.append(f"  {name}  ({len((repo / name).read_text(encoding='utf-8').splitlines())} lines)")
    lines.append("  basket.py has five functions with no body yet; test_basket.py checks all five")
    return lines
