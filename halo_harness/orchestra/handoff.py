"""halo_harness.orchestra.handoff -- per-lane context control (Halo 3.0.9.0
round R1). What a lane declares is in handoff_spec.py; this is what the run
does with it.

* Base. A lane with upstreams (its `after` plus each `needs.from`) starts
  only when they are written, from their finished head: one upstream = its
  `head`; two or more = the merge of their heads (merge.merge_heads, a
  scratch branch `orchestra/<run>-base-<n>`; a conflict leaves the lane
  `waiting` with the reason). A lane without upstreams starts from the
  split's base, as before.
* Prompt. A lane with `needs` gets a "Hand-offs" section: `take: summary`
  the upstream's final reply, `take: all` the reply plus its written keys
  and its artifacts, `take: <name>` just that give. Artifacts are copied
  into the lane's worktree under `.halo/handoff/<job>/` (git-ignored, never
  committed). A lane with no `needs` sees nothing from other lanes.
* Gave. When a lane is written, `gave` lists what it produced: the summary
  (`lanes/<n>/summary.md`, its final reply), one `files` row per written
  key, one `artifact` row per file it saved under `lanes/<n>/artifacts/`.
"""

from __future__ import annotations

import fnmatch
import shutil
from pathlib import Path
from typing import Optional

from halo_harness.orchestra import events as run_events
from halo_harness.orchestra import gitops
from halo_harness.orchestra.lanes import lanes_dir, list_lanes

SUMMARY_MAX = 20000
WRITTEN = ("written", "in_review", "merged")
IMPLICIT_GIVES = [{"name": "summary", "kind": "summary"}, {"name": "files", "kind": "files"}]


def lane_folder(run_dir, n: int) -> Path:
    return lanes_dir(run_dir) / str(int(n))


def artifacts_dir(run_dir, n: int) -> Path:
    return lane_folder(run_dir, n) / "artifacts"


def _rel(run_dir, path: Path) -> str:
    return Path(path).resolve().relative_to(Path(run_dir).resolve()).as_posix()


def upstream_lanes(run_dir, lane) -> list:
    """The lanes this lane starts after, in the order declared."""
    by_job = {other.job.id: other for other in list_lanes(run_dir)}
    return [by_job[j] for j in lane.job.upstreams if j in by_job]


def unfinished(ups: list) -> Optional[str]:
    """Why the lane does not start yet from these upstreams, or None."""
    bad = [u for u in ups if u.state not in WRITTEN]
    return ", ".join(f"lane {u.n} is {u.state or 'not started'}" for u in bad) if bad else None


def start_base(run_dir, lane, split_base: str) -> "tuple[Optional[str], str]":
    """`(base, "")` the commit the lane starts from, or `(None, reason)`."""
    ups = upstream_lanes(run_dir, lane)
    if not ups:
        return split_base, ""
    from halo_harness.orchestra.goal import repo_root_of
    repo = repo_root_of(run_dir)
    heads: list = []
    for u in sorted(ups, key=lambda x: -float(x.data().get("ended") or 0)):  # the last finished first
        sha = str(u.data().get("head") or u.data().get("base") or split_base)
        if sha not in heads:
            heads.append(sha)
    keep = [h for h in heads if not any(o != h and gitops.is_ancestor(repo, h, o) for o in heads)]
    if len(keep) == 1:
        return keep[0], ""
    from halo_harness.orchestra.merge import merge_heads
    return merge_heads(run_dir, lane.n, keep)


def _matches(key: str, paths: list) -> bool:
    rel = key.split("#", 1)[0]
    return not paths or any(key == p or rel == p or fnmatch.fnmatchcase(rel, p) or rel.startswith(p.rstrip("/") + "/")
                            for p in paths)


def record_gave(run_dir, lane, reply: str) -> list:
    """Write the lane's summary and fill `gave` (see the module doc)."""
    folder = lane_folder(run_dir, lane.n)
    folder.mkdir(parents=True, exist_ok=True)
    summary = folder / "summary.md"
    summary.write_text(str(reply or "")[-SUMMARY_MAX:], encoding="utf-8", newline="\n")
    art = artifacts_dir(run_dir, lane.n)
    files = sorted(p for p in art.rglob("*") if p.is_file()) if art.is_dir() else []
    written = lane.written
    declared = list((lane.job.handoff or {}).get("gives") or [])
    gave = []
    for give in declared or IMPLICIT_GIVES:
        name, kind, paths = give["name"], give.get("kind"), list(give.get("paths") or [])
        if kind == "summary":
            gave.append({"name": name, "kind": kind, "path": _rel(run_dir, summary), "bytes": summary.stat().st_size})
        elif kind == "files":
            gave += [{"name": name, "kind": kind, "path": key, "bytes": len(text.encode("utf-8"))}
                     for key, text in sorted(written.items()) if _matches(key, paths)]
        elif kind == "artifact":
            want = paths or [name]
            for p in files:
                rel = p.relative_to(art).as_posix()
                if rel in want or p.name in want or p.stem in want:
                    gave.append({"name": name, "kind": kind, "path": _rel(run_dir, p), "bytes": p.stat().st_size})
            if not any(g["name"] == name for g in gave):
                run_events.log(run_dir, "note", f"lane {lane.n} did not save its artifact {name!r} "
                               f"under lanes/{lane.n}/artifacts/", lane=lane.n, step=f"worker-{lane.n}")
    if not declared:
        gave += [{"name": p.name, "kind": "artifact", "path": _rel(run_dir, p), "bytes": p.stat().st_size} for p in files]
    lane.update(gave=gave)
    return gave


def take_rows(up, take: str) -> list:
    gave = list(up.data().get("gave") or [])
    if take == "all":
        return gave
    if take == "summary":
        return [g for g in gave if g.get("kind") == "summary"][:1]
    return [g for g in gave if g.get("name") == take]


def gives_text(run_dir, lane) -> str:
    """What the lane is asked to hand on (only when it declares gives)."""
    gives = list((lane.job.handoff or {}).get("gives") or [])
    if not gives:
        return ""
    art = artifacts_dir(run_dir, lane.n).resolve()
    lines = ["Hand on (later jobs take these from you):"]
    for g in gives:
        if g.get("kind") == "artifact":
            name = (g.get("paths") or [g["name"]])[0]
            lines.append(f"- {g['name']}: save it as {art / name} (outside your folder; the run keeps it)")
        elif g.get("kind") == "summary":
            lines.append(f"- {g['name']}: your final reply is the summary later jobs read; make it say what they need")
        else:
            lines.append(f"- {g['name']}: the units you write" + (f" under {', '.join(g['paths'])}" if g.get("paths") else ""))
    return "\n".join(lines)


def _indent(text: str) -> str:
    return "\n".join("    " + line for line in str(text).splitlines()) or "    (empty)"


def deliver(run_dir, lane) -> str:
    """Copy the taken artifacts into the worktree and return the prompt's
    "Hand-offs" section ("" for a lane with no `needs`)."""
    needs = list((lane.job.handoff or {}).get("needs") or [])
    if not needs:
        return ""
    by_job = {other.job.id: other for other in list_lanes(run_dir)}
    root = Path(lane.worktree) / ".halo" / "handoff"
    root.mkdir(parents=True, exist_ok=True)
    (root / ".gitignore").write_text("# Orchestra hand-offs: never committed.\n*\n", encoding="utf-8")
    lines = ["Hand-offs (what earlier jobs left for you; nothing else from other jobs reaches you):"]
    for need in needs:
        up = by_job.get(need["from"])
        if up is None:
            lines.append(f"- {need['from']}: not a lane of this run")
            continue
        rows = take_rows(up, need["take"])
        lines.append(f"- From {up.job.id} (lane {up.n}: {up.job.title}), take {need['take']}:")
        if not rows:
            lines.append(f"    (lane {up.n} left nothing under that name)")
        for row in [r for r in rows if r.get("kind") == "summary"]:
            text = (Path(run_dir) / row["path"]).read_text(encoding="utf-8") if (Path(run_dir) / row["path"]).is_file() else ""
            lines += ["  its summary:", _indent(text)]
        keys = [r["path"] for r in rows if r.get("kind") == "files"]
        if keys:
            lines.append("  the units it wrote (already in your files): " + ", ".join(f"`{k}`" for k in keys))
        for row in [r for r in rows if r.get("kind") == "artifact"]:
            src = Path(run_dir) / row["path"]
            dest = root / up.job.id / src.name
            dest.parent.mkdir(parents=True, exist_ok=True)
            if src.is_file():
                shutil.copyfile(src, dest)
            lines.append(f"  its artifact {row['name']}: .halo/handoff/{up.job.id}/{src.name} in your folder")
    return "\n".join(lines)
