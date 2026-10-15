"""halo_harness.fleet.conflicts -- project rooms and conflict warnings (Halo
3.0.5.0 "Fleet" round R4, D1). Pure, in code: who is editing which file, and
when two agents of DIFFERENT sessions (any harness) touch the same file of
the same repo, a conflict, before the merge conflict happens.

Sources, merged by the hub (studio/fleet_watch.py keeps the `Touches`):
* each agent's Edit / Write calls: the agent row's `current` ("Edit: src/a.py",
  in every `agent_state` frame and on every view) and a followed agent's
  `tool_call` entries;
* the Orchestra claims (orchestra/claims.py) of every live run: this
  machine's runs from the repos its sessions work in, and a member's from
  the `claims` its Orchestra workers announce (`own_claims`).

A path is made repo-relative (the project root, else the repo's folder name
inside the path), so `/home/kali/shop/basket.py` and `C:\\src\\shop\\basket.py`
are the same `basket.py` of repo `shop`. An edit counts for TOUCH_TTL_S.
"""

from __future__ import annotations

import os
import re
import threading
import time
from pathlib import Path
from typing import Optional

from halo_harness.fleet.caps import project_key

TOUCH_TTL_S = 900.0
EDIT_RE = re.compile(r"^(Edit|Write|MultiEdit|NotebookEdit|ApplyPatch):\s*(.+)$")
EDIT_TOOLS = ("Edit", "Write", "MultiEdit", "NotebookEdit", "ApplyPatch")


def edited(current) -> Optional[str]:
    m = EDIT_RE.match(str(current or "").strip())
    if not m or m.group(2).endswith("..."):
        return None
    return m.group(2).strip()


def _base(p) -> str:
    return str(p or "").replace("\\", "/").rstrip("/").split("/")[-1]


def rel(path: str, row: dict) -> str:
    """`path` relative to the session's repo when it can be told, else as given (slashes forward)."""
    p = str(path or "").replace("\\", "/")
    proj = row.get("project") if isinstance(row.get("project"), dict) else {}
    root = str(proj.get("root") or "").replace("\\", "/").rstrip("/")
    if root and "/" in root and p.lower().startswith(root.lower() + "/"):
        return p[len(root) + 1:]
    for name in [n for n in (proj.get("repo"), _base(root), _base(row.get("cwd"))) if n]:
        i = p.rfind("/" + name + "/")
        if i >= 0:
            return p[i + len(name) + 2:]
    absolute = p.startswith("/") or re.match(r"^[A-Za-z]:/", p)
    return p if absolute else re.sub(r"^(\./)+", "", p)


class Touches:
    """Who touched which file, and when: (harness, session, agent) -> {file: (ts, repo)}."""

    def __init__(self) -> None:
        self._t: dict = {}
        self._lock = threading.Lock()

    def note(self, hid: str, sid: str, aid: str, file: str, repo: str, ts: Optional[float] = None) -> bool:
        if not file:
            return False
        with self._lock:
            mine = self._t.setdefault((hid, sid, aid or "main"), {})
            new = file not in mine
            mine[file] = (ts or time.time(), repo)
        return new

    def items(self, now: Optional[float] = None) -> list:
        now = now or time.time()
        with self._lock:
            for k in list(self._t):
                self._t[k] = {f: v for f, v in self._t[k].items() if now - v[0] < TOUCH_TTL_S}
                if not self._t[k]:
                    del self._t[k]
            return [(h, s, a, f, repo, ts) for (h, s, a), files in self._t.items() for f, (ts, repo) in files.items()]

    def files_of(self, hid: str, sid: str, aid: str) -> list:
        with self._lock:
            return sorted(self._t.get((hid, sid, aid or "main"), {}))


def note_view(touches: Touches, view: dict) -> list:
    """Every agent whose row says it edits a file right now; returns the new (harness, session, agent, file)."""
    out = []
    for h in view.get("harnesses") or []:
        for s in h.get("sessions") or []:
            for a in s.get("agents") or []:
                f = edited(a.get("current"))
                if f and touches.note(str(h.get("id")), str(s.get("session_id")), str(a.get("agent_id")), rel(f, s), project_key(s)):
                    out.append((h.get("id"), s.get("session_id"), a.get("agent_id"), rel(f, s)))
    return out


def run_claims(roots) -> list:
    """The live claims of the newest runs of each repo in `roots` (this machine's)."""
    from halo_harness.orchestra.claims import ClaimLog
    from halo_harness.orchestra.goal import list_runs
    out, seen = [], set()
    for root in roots:
        if not root or str(root) in seen or not Path(root).is_dir():
            continue
        seen.add(str(root))
        for run in list_runs(root)[-5:]:
            try:
                active = ClaimLog(run).active()
            except Exception:
                continue
            for c in active.values():
                out.append({"repo": _base(root), "run": run.name, "key": c.key, "file": c.key.split("#")[0],
                            "holder": c.holder, "state": c.state, "ts": c.ts})
    return out


def own_claims(env=None) -> list:
    """In an Orchestra worker (HALO_ORCHESTRA_RUN): its run's live claims, for its relay's announce."""
    from halo_harness.orchestra.guard import run_dir_from_env
    run_dir = run_dir_from_env(env if env is not None else os.environ)
    if run_dir is None:
        return []
    from halo_harness.orchestra.goal import repo_root_of
    return [c for c in run_claims([repo_root_of(run_dir)]) if c["run"] == run_dir.name][:200]


def _ref(h: dict, s: dict, aid: str) -> dict:
    row = next((a for a in s.get("agents") or [] if a.get("agent_id") == aid), {})
    return {"key": f"{h.get('id')}|{s.get('session_id')}|{aid}", "harness": h.get("id"), "harness_name": h.get("name"),
            "session_id": s.get("session_id"), "agent_id": aid, "name": row.get("name") or row.get("role") or aid}


def find(view: dict, touches: Touches, claims: list, now: Optional[float] = None) -> list:
    """`[{id, repo, file, a, b, since, source}]`: two agents of different sessions on one file."""
    sessions = {(str(h.get("id")), str(s.get("session_id"))): (h, s) for h in view.get("harnesses") or []
                for s in h.get("sessions") or []}
    by_sid = {sid: hs for (_h, sid), hs in sessions.items()}
    on: dict = {}
    for hid, sid, aid, f, repo, ts in touches.items(now):
        if (hid, sid) in sessions:
            on.setdefault((repo, f), {})[f"{hid}|{sid}|{aid}"] = (_ref(*sessions[(hid, sid)], aid), ts, "edit")
    for c in claims:
        sid, _, aid = str(c.get("holder") or "").partition("/")
        hs = by_sid.get(sid)
        ref = _ref(hs[0], hs[1], aid or "main") if hs else {"key": f"claim|{sid}|{aid}", "harness": None, "harness_name": "Orchestra",
                                                              "session_id": sid, "agent_id": aid or "main", "name": f"lane {aid or sid[:8]}"}
        on.setdefault((str(c.get("repo")), str(c.get("file"))), {}).setdefault(ref["key"], (ref, c.get("ts") or 0, "claim"))
    out = []
    for (repo, f), who in on.items():
        refs = sorted(who.values(), key=lambda x: x[0]["key"])
        for i, (a, ta, sa) in enumerate(refs):
            for b, tb, sb in refs[i + 1:]:
                if (a.get("harness"), a.get("session_id")) == (b.get("harness"), b.get("session_id")):
                    continue
                out.append({"id": f"conflict:{repo}:{f}:{a['key']}:{b['key']}", "repo": repo, "file": f, "a": a, "b": b,
                            "since": max(ta or 0, tb or 0), "source": "claim" if "claim" in (sa, sb) else "edit"})
    return sorted(out, key=lambda c: (c["repo"], c["file"]))


def rooms(view: dict) -> list:
    """One room per repo: every card on it with its branch, dirty / ahead / behind and worktree."""
    out: dict = {}
    for h in view.get("harnesses") or []:
        for s in h.get("sessions") or []:
            p = s.get("project") if isinstance(s.get("project"), dict) else {}
            k = project_key(s)
            out.setdefault(k, {"key": k, "label": k, "cards": []})["cards"].append({
                "harness": h.get("id"), "harness_name": h.get("name"), "session_id": s.get("session_id"),
                "branch": p.get("branch"), "dirty": p.get("dirty"), "ahead": p.get("ahead"), "behind": p.get("behind"),
                "worktree": p.get("worktree") or _base(p.get("root")), "linked": bool(p.get("linked"))})
    return sorted(out.values(), key=lambda r: r["key"])
