"""halo_harness.fleet.mission_worker_run -- one mission part's run on its own
thread (Halo 3.0.6.0 "Fleet Missions" round R7; mission_worker.py starts it).

1. Place it (`place`, before the command's reply): the mission folder is the
   hub's own (`local`), the shared mount (`shared`: `fleet.shared_dir/<id>`
   exists here) or a mirror at `<home>/fleet/missions/<id>` (`hub`); a repo
   part needs a checkout of its repo here (a live session's project).
2. Prepare: the mirror pulls `MISSION.md`, the part's brief, `inputs/` and its
   dependencies' outputs (mission_files.HubFiles); a repo part gets a git
   worktree `<checkout>/.halo/missions/<id>/<part>` on branch
   `mission/<id>/<part>` from the mission's base when this checkout has it.
3. Work: the session (mission_worker.BUILD) opens as `kind: mission-worker`
   with mission / part / parent on its registry row, the claim guard
   (mission_guard.py) joins its permission engine, and one turn runs on
   MISSION.md + the brief.
4. Finish: a repo part's worktree is committed (and bundled for the hub when
   mirrored); `parts/<n>/handback.md` is the worker's last reply and
   `parts/<n>/result.json` `{ok, state: done | failed | stopped, cost_usd,
   error, session_id, harness, files, branch, head, bundle}`; a mirror pushes
   the artifacts, the bundle, the hand-back and the result (last) to the hub.
"""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Callable, Optional

from halo_harness.fleet import mission as M
from halo_harness.fleet import mission_store as S
from halo_harness.fleet.mission_worker import TaskError


class WorkerRun(threading.Thread):
    def __init__(self, f: dict, *, home, hub: str, by: str, entry: Optional[dict], origin,
                 repo_root=None, on_done: Optional[Callable] = None) -> None:
        super().__init__(daemon=True, name=f"halo-mission-{f['mission']}-{f['part']}")
        self.f, self.home, self.hub_name, self.by, self.entry, self.origin = f, Path(home), hub, by, entry, origin
        self.mode = f["mirror"]["mode"]
        self.checkout = Path(repo_root) if repo_root else None
        self.on_done = on_done
        self.folder: Optional[Path] = None
        self.cwd: Optional[Path] = None
        self.files = None
        self.session = self.act = None
        self.stopped: Optional[str] = None
        self.result: Optional[dict] = None
        self.base: Optional[str] = None
        self.guard = None
        self.run_id: Optional[str] = None  # 3.1.2.0 R2: an orchestra part's run (mission_stage_run.py)
        self.report = False

    # ---- placing -------------------------------------------------------------------------------
    def place(self) -> None:
        mid = self.f["mission"]
        if self.mode == "local":
            self.folder = S.folder(self.home, mid)
            if not self.folder.is_dir():
                raise TaskError(f"no mission folder for {mid} here")
        elif self.mode == "shared" and M.shared_dir(self.home) is not None and (M.shared_dir(self.home) / mid).is_dir():
            self.folder = M.shared_dir(self.home) / mid
        else:
            self.mode = "hub"
            if not self.entry:
                raise TaskError("no hub link to mirror the mission folder through")
            self.folder = self.home / "fleet" / "missions" / mid
        if self.f["kind"] == "repo" and self.checkout is None:
            self.checkout = self._find_repo(str(self.f["repo"]))
        if self.f["kind"] == "orchestra":
            from halo_harness.fleet.mission_stage_run import place
            place(self)

    def _find_repo(self, name: str) -> Path:
        from halo_harness.remote import fleet_identity as FI
        roots = [getattr(self.origin, "cwd", None)]
        try:
            from halo_harness.remote.registry import list_live
            roots += [e.get("cwd") for e in list_live()]
        except Exception:
            pass
        for r in [r for r in roots if r]:
            p = FI.project(r)
            if p.get("repo") and name.lower() in (str(p["repo"]).lower(), Path(str(p["root"])).name.lower()):
                return Path(p["root"])
        raise TaskError(f"no checkout of {name} here: open a session in it, then run the part again")

    # ---- the run -------------------------------------------------------------------------------
    def run(self) -> None:
        out = {"ok": False, "text": "", "cost_usd": 0.0, "error": "", "session_id": None}
        try:
            self._prepare()
            out = self._work()
        except Exception as e:  # the part fails with the reason; the thread never takes the harness down
            out["error"] = f"{type(e).__name__}: {e}"[:500]
        finally:
            try:
                self._finish(out)
            except Exception as e:
                self.result = {"ok": False, "state": "failed", "error": f"finishing failed: {e}"[:500]}

    def _prepare(self) -> None:
        from halo_harness.orchestra import gitops
        mid, n = self.f["mission"], self.f["part"]
        (self.folder / "artifacts" / n).mkdir(parents=True, exist_ok=True)
        if self.mode == "hub":
            from halo_harness.fleet.mission_files import HubFiles
            self.files = HubFiles(self.entry)
            self.files.pull(mid, self.folder)
        if self.f["kind"] == "orchestra":  # the run makes its own worktrees
            self.cwd = self.checkout or self.folder
            return
        if self.f["kind"] != "repo":
            self.cwd = self.folder
            return
        root = self.checkout / ".halo" / "missions"
        root.mkdir(parents=True, exist_ok=True)
        if not (root / ".gitignore").exists():
            (root / ".gitignore").write_text("# Mission worktrees: never committed.\n*\n", encoding="utf-8")
        def have() -> bool:
            return bool(self.f["base"]) and gitops.git(["cat-file", "-e", f"{self.f['base']}^{{commit}}"],
                                                       self.checkout).returncode == 0
        if self.f["base"] and not have():  # 3.0.9.0: a sequenced part's start comes as parts/<n>/base.bundle
            from halo_harness.fleet.mission_handoff import fetch_base
            fetch_base(self.checkout, self.folder, mid, n)
        self.base = self.f["base"] if have() else gitops.head(self.checkout)
        self.cwd = gitops.worktree_add(self.checkout, root / mid / n, self.f["branch"], self.base)

    def _prompt(self) -> str:
        n = self.f["part"]
        mission = S.read_text(self.folder, "MISSION.md") or f"Mission {self.f['mission']}"
        brief = S.read_text(self.folder, f"parts/{n}/brief.md") or self.f["brief"]
        where = (f"Your folder is a git worktree of {self.f['repo']} on branch {self.f['branch']}."
                 if self.f["kind"] == "repo" else f"Your folder is the mission folder; your outputs go in artifacts/{n}/.")
        budget = f"\nKeep this part under ${self.f['budget_usd']:.2f}." if self.f.get("budget_usd") else ""
        return f"{brief}\n\n{where}{budget}{self.handoff_line()}\n\n---\n\nMISSION.md (the whole mission, for context):\n\n{mission}"

    def handoff_line(self) -> str:
        """3.0.9.0: what the parts before this one left for it, and where a repo part starts."""
        if not self.f.get("depends_on"):
            return ""
        got = [x for x in self.f.get("handoffs") or [] if "*" in x or (self.folder / x).is_file()]
        line = (f"\nHand-offs from part(s) {', '.join(self.f['depends_on'])} in the mission folder"
                + (f" ({self.folder})" if self.f["kind"] == "repo" else "") + ": " + (", ".join(got) or "nothing yet") + ".")
        if self.f["kind"] == "repo" and self.base:
            line += f" Your worktree starts from {self.base[:12]}."
        return line

    def _work(self) -> dict:
        from halo_harness.fleet import mission_worker
        if self.f["kind"] == "orchestra":  # 3.1.2.0 R2: the run's own sessions do the work
            from halo_harness.fleet.mission_stage_run import run
            return run(self)
        from halo_harness.fleet.mission_guard import MissionClaimGuard, install
        from halo_harness.fleet.mission_worker_session import close_row, open_row
        session, run_fn, close = mission_worker.builder()(self.cwd, self.home)
        self.session = session
        try:
            self.act = open_row(session, self.cwd, mission=self.f["mission"], part=self.f["part"], title=self.f["title"])
            self.guard = install(session.permission_engine, MissionClaimGuard(
                self.cwd, self.f["claims"], mission=self.f["mission"], part=self.f["part"], on_refused=self._refused))
            if self.stopped:
                return {"ok": False, "error": self.stopped, "cost_usd": 0.0}
            out = dict(run_fn(self._prompt(), self.act.handle if self.act is not None else None) or {})
            abort = getattr(session, "abort", None)
            if not self.stopped and abort is not None and abort.is_set():  # a stop that came like any agent's
                self.stopped = "stopped while it ran (the main agent was interrupted)"
            return out
        finally:
            close_row(self.act)
            close()

    def stop(self, reason: str = "stopped") -> None:
        self.stopped = reason or "stopped"
        target = self.act.handle if self.act is not None else None
        try:
            if target is not None:
                target.interrupt()
            elif self.session is not None:
                self.session.abort.set()
        except Exception:
            pass

    def _refused(self, rel: str, tool: str, why: str) -> None:
        from halo_harness.fleet.identity import harness
        from halo_harness.fleet.mission_worker_session import frame
        data = {"mission": self.f["mission"], "part": self.f["part"], "file": rel, "tool": tool, "reason": why}
        if self.mode in ("local", "shared"):
            S.log(self.home, self.f["mission"], "claim_refused", harness=harness(self.home)["id"], **data)
        frame(self.act, {"action": "mission_claim", **data})

    # ---- finishing -----------------------------------------------------------------------------
    def _finish(self, out: dict) -> None:
        from halo_harness.fleet.identity import harness
        from halo_harness.orchestra import gitops
        mid, n = self.f["mission"], self.f["part"]
        state = "stopped" if self.stopped else ("done" if out.get("ok") else "failed")
        files, head, bundle = [], None, False
        if self.f["kind"] == "repo" and self.cwd is not None and self.base:
            head = gitops.commit_all(self.cwd, f"mission {mid} part {n}: {self.f['title']}") or gitops.head(self.cwd)
            files = [x for x in gitops.git(["diff", "--name-only", f"{self.base}..{self.f['branch']}"],
                                           self.checkout).stdout.splitlines() if x.strip()]
            if self.mode != "local" and files:  # the hub fetches the branch from this bundle
                target = self.folder / "parts" / n / "branch.bundle"
                target.parent.mkdir(parents=True, exist_ok=True)
                bundle = gitops.git(["bundle", "create", str(target), f"{self.base}..{self.f['branch']}"],
                                    self.checkout).returncode == 0
            gitops.worktree_remove(self.checkout, self.cwd)
        elif self.folder is not None:
            files = [f["path"] for f in S.files(self.folder, f"artifacts/{n}")]
        text = str(out.get("text") or "").strip() or (f"(no reply) {out.get('error') or self.stopped or ''}").strip()
        self.result = {"ok": state == "done", "state": state, "cost_usd": round(float(out.get("cost_usd") or 0.0), 6),
                       "error": None if state == "done" else (self.stopped or out.get("error") or "the part failed"),
                       "session_id": out.get("session_id") or getattr(getattr(self.session, "log", None), "session_id", None),
                       "harness": harness(self.home)["id"], "files": files[:500], "branch": self.f["branch"] if head else None,
                       "head": head, "base": self.base, "bundle": bundle, "ended": time.time(),
                       "refused": list(getattr(self.guard, "refused", []))[:50]}
        if self.run_id:
            self.result.update(run_id=self.run_id, run_kind=self.f["kind"])
        if self.folder is not None:
            S.write_text(self.folder, f"parts/{n}/handback.md", f"# Part {n} hand-back ({state})\n\n{text}\n")
            S.write_text(self.folder, f"parts/{n}/result.json", json.dumps(self.result, indent=2))
        if self.files is not None:
            rels = [f"artifacts/{n}/{x}" if not x.startswith("artifacts/") else x for x in
                    ([] if self.f["kind"] == "repo" else files)]
            rels += [f"parts/{n}/branch.bundle"] * bool(bundle) + [f"parts/{n}/report.json"] * bool(self.report)
            rels += [f"parts/{n}/handback.md", f"parts/{n}/result.json"]
            try:
                self.files.push(mid, self.folder, rels, cap=M.max_file_bytes(self.home))
            finally:
                self.files.close()
        if self.on_done is not None:
            self.on_done(self.result)
