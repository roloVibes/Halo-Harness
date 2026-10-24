"""halo_harness.outcomes.evidence -- what an agent's task left behind, read out of
its transcript (Halo 3.1.8.0 R3, docs/OUTCOMES.md "Evidence").

`gather(transcript, bio, *, cwd)` -> `Evidence`: the task's `kind` and the
items found in its tool calls -- nothing is asked of the model, and the
agent's own final text is kept apart as `summary` (a verdict never reads it):

    tests        [{command, exit, passed, failed: [names], tail}]  a shell call that runs tests
                 (outcomes.kinds.is_test_command), or the bio's `acceptance.test` / the goal's test
    diff         {files, added, removed}   the files it wrote, `git diff --numstat` when cwd is a repo
    sources      [{kind: fetch|search|read, target, when}]  WebFetch / curl, WebSearch, Read / Grep
    reproduction [{command, exit, tail}]   a check's shell calls that are not test runs
    written      [paths]                   Write / Edit / NotebookEdit targets
    acceptance   {expect, met, why} | None the bio's acceptance on the final text (or the caller's verdict)

A failed call is not evidence (an error result reads no source and writes no
file); a shell call's exit is its `[exit code N]` note (none: 0; a timeout,
an abort or a capped result: unknown). `write(path, ev)` is `evidence.json`.
"""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional

from halo_harness.outcomes.kinds import is_test_command, kind_of
from halo_harness.outcomes.transcript import calls as transcript_calls

SHELL_TOOLS = ("Bash", "PowerShell")
WRITE_TOOLS = ("Write", "Edit", "NotebookEdit", "MultiEdit")
TAIL_LINES, TAIL_CHARS, REPRO_MAX = 12, 1500, 10
_EXIT = re.compile(r"\[exit code (-?\d+)\]\s*$")
_URL = re.compile(r"\b(?:curl|wget|Invoke-WebRequest|iwr)\b[^\n]*?(https?://[^\s'\"<>]+)", re.I)


@dataclass
class Evidence:
    kind: str = "other"
    bio: str = ""
    model: str = ""
    cost_usd: float = 0.0
    summary: str = ""
    transcript: bool = False                         # a transcript was read (no transcript: nothing to judge)
    tests: list = field(default_factory=list)
    diff: dict = field(default_factory=lambda: {"files": [], "added": 0, "removed": 0})
    sources: list = field(default_factory=list)
    reproduction: list = field(default_factory=list)
    written: list = field(default_factory=list)
    acceptance: Optional[dict] = None
    sessions: list = field(default_factory=list)
    ts: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data) -> "Evidence":
        data = data if isinstance(data, dict) else {}
        return cls(**{k: data[k] for k in cls.__dataclass_fields__ if k in data})

    @property
    def tests_passed(self) -> int:
        return sum(int(t.get("passed") or 0) for t in self.tests)

    @property
    def tests_failed(self) -> int:
        return sum(len(t.get("failed") or []) for t in self.tests)


def exit_of(call: dict) -> Optional[int]:
    text = str(call.get("text") or "").rstrip()
    m = _EXIT.search(text)
    if m:
        return int(m.group(1))
    if call.get("cut") or not call.get("done") or "[command timed out" in text or text.endswith("[command aborted]"):
        return None
    return None if call.get("is_error") else 0


def tail_of(text: str) -> str:
    lines = [ln for ln in str(text or "").replace("\r\n", "\n").split("\n") if not _EXIT.match(ln.strip())]
    while lines and not lines[-1].strip():
        lines.pop()
    out = "\n".join(lines[-TAIL_LINES:])
    return out if len(out) <= TAIL_CHARS else "..." + out[-TAIL_CHARS:]


def _test_item(command: str, call: dict) -> dict:
    from halo_harness.orchestra.gate import failing_tests, passed_count
    text = str(call.get("text") or "")
    return {"command": command, "exit": exit_of(call), "passed": passed_count(text),
            "failed": list(failing_tests(text) or []), "tail": tail_of(text)}


def _bio_parts(bio) -> "tuple[dict, str]":
    if isinstance(bio, dict):
        return bio, str(bio.get("name") or "")
    return {}, str(bio or "")


def _source(call: dict) -> Optional[dict]:
    name, args = call["name"], call.get("input") or {}
    when = call.get("result_ts") or call.get("ts")
    if name == "WebFetch" and args.get("url"):
        return {"kind": "fetch", "target": str(args["url"]), "when": when}
    if name == "WebSearch" and args.get("query"):
        return {"kind": "search", "target": str(args["query"]), "when": when}
    if name == "Read" and (args.get("file_path") or args.get("path")):
        return {"kind": "read", "target": str(args.get("file_path") or args.get("path")), "when": when}
    if name == "Grep" and args.get("pattern"):
        where = args.get("path") or args.get("glob") or ""
        return {"kind": "read", "target": f"grep {args['pattern']}" + (f" in {where}" if where else ""), "when": when}
    if name in SHELL_TOOLS:
        m = _URL.search(str(args.get("command") or ""))
        if m and exit_of(call) == 0:
            return {"kind": "fetch", "target": m.group(1), "when": when}
    return None


def rel_path(path: str, cwd) -> str:
    """`path` relative to `cwd` (forward slashes) when it lies under it, else as given."""
    if cwd is None or not os.path.isabs(path):
        return str(path).replace("\\", "/")
    try:
        rel = os.path.relpath(path, cwd)
    except ValueError:  # another drive (Windows)
        return path
    return path if rel.startswith("..") else rel.replace("\\", "/")


def diff_stat(cwd, files: list, base: Optional[str] = None) -> dict:
    """`{files, added, removed}` for the written files: `git diff --numstat <base or HEAD>` in cwd's repo,
    a new (untracked) file counted as all added; just the file list when cwd is no repo."""
    out = {"files": list(files), "added": 0, "removed": 0}
    if not files or cwd is None or not any((p / ".git").exists() for p in (Path(cwd), *Path(cwd).parents)):
        return out
    rel = [rel_path(f, cwd) for f in files]
    for line in _git(cwd, "diff", "--numstat", "--relative", base or "HEAD", "--", *rel).splitlines():
        parts = line.split("\t")
        if len(parts) == 3 and parts[0].isdigit() and parts[1].isdigit():
            out["added"] += int(parts[0])
            out["removed"] += int(parts[1])
    for r in _git(cwd, "ls-files", "--others", "--exclude-standard", "--", *rel).splitlines():
        try:
            out["added"] += len((Path(cwd) / r.strip()).read_text(encoding="utf-8", errors="replace").splitlines())
        except OSError:
            pass
    return out


def _git(cwd, *args) -> str:
    import subprocess
    try:
        proc = subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=30, stdin=subprocess.DEVNULL)
    except (OSError, subprocess.SubprocessError):
        return ""
    return (proc.stdout or "") if proc.returncode == 0 else ""


def _acceptance(bio: dict, summary: str, tests: list) -> Optional[dict]:
    acc = bio.get("acceptance") if isinstance(bio.get("acceptance"), dict) else None
    if not acc:
        return None
    from halo_harness.agents_doctor import check_expectation
    expect = str(acc.get("expect") or "non-empty")
    met = bool(check_expectation(summary or "", expect))
    why = f"acceptance {expect!r} on the final text: {'met' if met else 'not met'}"
    test = str(acc.get("test") or "").strip()
    if test:
        ran = [t for t in tests if test in t["command"]]
        ok = bool(ran) and ran[-1]["exit"] == 0
        met = met and ok
        why += f"; `{test}` " + ("passed" if ok else "exited " + str(ran[-1]["exit"]) if ran else "was not run")
    return {"expect": expect, "met": met, "why": why}


def gather(transcript, bio=None, *, cwd=None, words: str = "", default_kind: str = "other", test_command: str = "",
           model: str = "", cost_usd: float = 0.0, acceptance: Optional[dict] = None, base: Optional[str] = None,
           sessions=()) -> Evidence:
    """The evidence of one agent's task (see the module docstring). `bio`: the resolved bio (a dict) or its
    name; `words`: the names around the agent (its role, alias) for its kind; `test_command`: a test command
    of the task (the goal's); `acceptance`: the caller's own verdict, which wins over the bio's check."""
    bio_data, bio_name = _bio_parts(bio)
    found, final = transcript_calls(transcript)
    acc = bio_data.get("acceptance") if isinstance(bio_data.get("acceptance"), dict) else {}
    tests_cmds = [str(c).strip() for c in (test_command, acc.get("test")) if isinstance(c, str) and c.strip()]
    kind = kind_of(bio_data.get("kind"), " ".join([words, bio_name]), default=default_kind)
    ev = Evidence(kind=kind, bio=bio_name, model=str(model or ""), cost_usd=round(float(cost_usd or 0.0), 6),
                  summary=final[-4000:], transcript=bool(transcript), sessions=list(sessions), ts=round(time.time(), 3))
    repro = []
    for call in found:
        name, args = call["name"], call.get("input") or {}
        if name in SHELL_TOOLS and str(args.get("command") or "").strip() and call.get("done"):
            command = str(args["command"]).strip()
            if is_test_command(command) or any(t in command for t in tests_cmds):
                ev.tests.append(_test_item(command, call))
            else:
                repro.append({"command": command, "exit": exit_of(call), "tail": tail_of(call.get("text"))})
        if call.get("is_error") is not False:
            continue
        if name in WRITE_TOOLS:
            path = rel_path(str(args.get("file_path") or args.get("notebook_path") or args.get("path") or ""), cwd)
            if path and path not in ev.written:
                ev.written.append(path)
        src = _source(call)
        if src and src not in ev.sources:
            ev.sources.append(src)
    ev.reproduction = repro[-REPRO_MAX:] if kind == "check" else []
    ev.diff = diff_stat(cwd, ev.written, base)
    ev.acceptance = acceptance if acceptance is not None else _acceptance(bio_data, final, ev.tests)
    return ev


def write(path, ev: Evidence) -> Optional[Path]:
    """`ev` as JSON at `path` (its folder made); None when it cannot be written."""
    path = Path(path)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
        tmp.write_text(json.dumps(ev.to_dict(), ensure_ascii=False, indent=1, default=str), encoding="utf-8")
        os.replace(tmp, path)
    except OSError:
        return None
    return path


def load(path) -> Optional[Evidence]:
    try:
        return Evidence.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))
    except (OSError, ValueError, TypeError):
        return None
