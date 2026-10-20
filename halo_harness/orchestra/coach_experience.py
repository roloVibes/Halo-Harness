"""halo_harness.orchestra.coach_experience -- what a library entry says (Halo
3.1.6.0 R3, after Harness²'s EXPERIENCE file; orchestra/coach_library.py
keeps the entries):

    # <the card's text, or "adopted the <kind> candidate" for a probe>
    ## When it applies
    project <name> (<remote path, userinfo stripped>) · lineup <name> · goal "<what, <= 200 chars>"
    ## Lessons
    - <the card's text and the lead's paragraph; for a probe the judge's why>
    ## Evidence
    - <the card's why lines; for a probe the contrast lines (tests, rank, cost, steps)>
    ## Files
    - <path> (<field> -> <value>)

`project_of(run_dir, kind, cwd)` is `{name, remote}`: the repo's folder name
and `git remote get-url origin` as a path only (`github.com/owner/repo`: no
scheme, user, token, port, query or `.git`). `context_of` is the run's lineup
and goal; `overlay_of` the portable overlay an entry keeps (a probe's
composed overlay; for one card the same shape built from its change, with the
resolved `changes` beside it).
"""

from __future__ import annotations

import re
import subprocess
import time
from pathlib import Path
from typing import Optional

from halo_harness.orchestra import jsonl

GOAL_CHARS, LINE_CHARS = 200, 600
_REMOTES: dict = {}  # repo path -> (monotonic ts, remote path): git runs at most once a minute per repo
_INVERSE = {"context.prompt_notes": "prompt_notes", "models.preference": "model", "models.effort": "effort",
            "limits.max_iterations": "max_iterations"}


def flat(text, n: int = LINE_CHARS) -> str:
    return " ".join(str(text or "").split())[:n]


def remote_path(url: str) -> str:
    """`https://user:token@github.com:443/o/r.git?x#y` and `git@github.com:o/r.git` -> `github.com/o/r`."""
    url = str(url or "").strip().split("?")[0].split("#")[0]
    if not url:
        return ""
    if url.lower().startswith("file://"):
        url = url[len("file://"):]
    m = re.match(r"^[A-Za-z][A-Za-z0-9+.-]*://(?:[^@/]*@)?([^/:]+)(?::\d+)?(/.*)?$", url)
    if m:
        host, path = m.group(1), m.group(2) or ""
    elif re.match(r"^[^/@:]+@[^/:]+:", url) or re.match(r"^[^/:\\]{2,}:[^/\\]", url):  # scp-like: [user@]host:path
        host, path = url.split("@", 1)[-1].split(":", 1)
    else:  # a local path remote
        host, path = "", url.replace("\\", "/")
    path = re.sub(r"\.git$", "", path.strip("/"))
    return f"{host}/{path}".strip("/") if host else path


def repo_of(run_dir, kind: str, cwd=None) -> Optional[Path]:
    """The repo a run belongs to: an Orchestra run's repo_root, a team run's root, else `cwd` (a mission)."""
    run_dir = Path(run_dir)
    if kind == "orchestra":
        from halo_harness.orchestra.goal import repo_root_of
        return Path(repo_root_of(run_dir))
    if kind == "team":
        root = (jsonl.read_json(run_dir / "run.json", {}) or {}).get("root")
        return Path(root) if root else run_dir.resolve().parents[2]
    return Path(cwd) if cwd else None


def _remote(repo: Path) -> str:
    key = str(repo)
    hit = _REMOTES.get(key)
    if hit and time.monotonic() - hit[0] < 60:
        return hit[1]
    try:
        r = subprocess.run(["git", "-C", key, "remote", "get-url", "origin"], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=10, stdin=subprocess.DEVNULL)
        out = remote_path(r.stdout.strip()) if r.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError, ValueError):
        out = ""
    _REMOTES[key] = (time.monotonic(), out)
    return out


def project_of(run_dir, kind: str, cwd=None) -> dict:
    repo = repo_of(run_dir, kind, cwd)
    if kind == "mission" and repo is None:
        named = ((jsonl.read_json(Path(run_dir) / "mission.json", {}) or {}).get("repo") or {}).get("name")
        return {"name": str(named or ""), "remote": ""}
    if repo is None or not repo.is_dir():
        return {"name": repo.name if repo else "", "remote": ""}
    return {"name": repo.resolve().name, "remote": _remote(repo)}


def context_of(run_dir, kind: str) -> dict:
    """{lineup, goal: {what, done_when}} of the run."""
    run_dir = Path(run_dir)
    if kind == "orchestra":
        g = jsonl.read_json(run_dir / "goal.json", {}) or {}
        return {"lineup": str(g.get("lineup") or ""), "goal": {"what": flat(g.get("what"), GOAL_CHARS),
                                                               "done_when": flat(g.get("done_when"), GOAL_CHARS)}}
    if kind == "mission":
        m = jsonl.read_json(run_dir / "mission.json", {}) or {}
        return {"lineup": "", "goal": {"what": flat(m.get("goal"), GOAL_CHARS), "done_when": flat(m.get("test"), GOAL_CHARS)}}
    b = jsonl.read_json(run_dir / "board.json", {}) or {}
    return {"lineup": str(b.get("team") or ""), "goal": {"what": f"team {b.get('team') or ''}".strip(), "done_when": ""}}


def _single(change: dict) -> dict:
    """One card's change in the probes' overlay shape (`bios`, `plan`; a lineup role as `roles`)."""
    target, name, field, value = change["target"], change.get("name") or "", change["field"], change.get("value")
    if target == "bio" and field in _INVERSE:
        return {"bios": {name: {_INVERSE[field]: value}}}
    if target == "bio" and field in ("tools.allow", "tools.deny"):
        return {"bios": {name: {"tools": {field.split(".")[1]: value}}}}
    if target == "lineup" and field.startswith("agents.") and field.endswith(".use_for"):
        return {"bios": {field[len("agents."):-len(".use_for")]: {"use_for": value}}}
    if target == "lineup" and field.startswith("roles."):
        return {"roles": {field[len("roles."):]: value}}
    if target == "plan":
        job, key = (field.split(".", 1) + [""])[:2]
        return {"plan": [{"job": job, "drop": True} if key == "drop" else {"job": job, "after": list(value or [])}]}
    return {}


def overlay_of(s: dict, changes: list, probe: Optional[dict]) -> dict:
    if probe is not None:
        return dict(probe.get("overlay") or {}, changes=changes)
    out: dict = {}
    for c in changes:
        for k, v in _single(c).items():
            if k == "plan":
                out.setdefault("plan", []).extend(v)
            elif k == "roles":
                out.setdefault("roles", {}).update(v)
            else:
                for name, part in v.items():
                    cur = out.setdefault("bios", {}).setdefault(name, {})
                    if "tools" in part:
                        cur.setdefault("tools", {}).update(part["tools"])
                    else:
                        cur.update(part)
    return dict(out, why=flat(s.get("text")), changes=changes)


def title_of(s: dict, probe: Optional[dict]) -> str:
    if probe is not None:
        pick = str(probe.get("pick") or "")
        return f"adopted the {pick} candidate" + (" (invariant + domain)" if pick == "merged" else "")
    return flat(s.get("text"), 200)


def shown(value) -> str:
    return flat(", ".join(str(v) for v in value) if isinstance(value, list) else value, 80)


def when_line(project: dict, lineup: str, goal: dict) -> str:
    where = f"project {project.get('name') or '(none)'} ({project.get('remote') or 'no remote'})"
    return f"{where} · lineup {lineup or '(none)'} · goal \"{flat(goal.get('what'), GOAL_CHARS)}\""


def markdown(entry: dict, s: dict, probe: Optional[dict]) -> str:
    """EXPERIENCE.md for one entry (entry.json's fields, the card, the probe when it is one)."""
    if probe is not None:
        lessons = [flat((probe.get("judge") or {}).get("why")) or flat(probe.get("why"))]
        from halo_harness.orchestra.coach_compose import row_line
        rows, ref = probe.get("contrast") or [], probe.get("reference") or {}
        evidence = [flat(probe.get("why"))] + [flat(row_line(r, ref, len(rows) + 1)) for r in rows]
    else:
        lessons = [flat(s.get("text")), flat(s.get("paragraph"))]
        evidence = [flat(w) for w in s.get("why") or []]
    files = [f"- {f['path']} (" + "; ".join(f"{k} -> {shown(v)}" for k, v in f.get("fields") or []) + ")"
             + ("" if f.get("kept", True) else f" (not kept: {f.get('bytes')} bytes)") for f in entry.get("files") or []]
    lessons = [f"- {x}" for x in lessons if x] or ["- (none)"]
    evidence = [f"- {x}" for x in evidence if x] or ["- (none)"]
    return "\n".join([f"# {entry['title']}", "## When it applies",
                      when_line(entry.get("project") or {}, entry.get("lineup") or "", entry.get("goal") or {}),
                      "## Lessons", *lessons, "## Evidence", *evidence, "## Files", *(files or ["- (none)"])]) + "\n"


def section(text: str, heading: str) -> str:
    """The body of `## <heading>` in an EXPERIENCE.md, bullets joined (no heading, no marks)."""
    out, inside = [], False
    for line in str(text or "").splitlines():
        if line.startswith("## "):
            inside = line[3:].strip().lower() == heading.lower()
            continue
        if inside and line.strip():
            out.append(line.strip()[2:] if line.strip().startswith("- ") else line.strip())
    return " ".join(out)
