"""halo_harness.fleet.mission_run -- a mission run, end to end, on the hub
(Halo 3.0.6.0 "Fleet Missions" round R7).

    approved -> running: parts start by the DAG as their dependencies finish, at most
                fleet.mission.max_parallel at once (default: the number of harnesses),
                each on its harness (mission_dispatch.py)
             -> merging: the repo parts merged one at a time in merge_order (mission_merge.py),
                the files parts' outputs checked in artifacts/
             -> done | failed | stopped, with report.md (mission_report.py)

A part that fails (or is refused, or its harness goes offline) skips every
part that waits for it, directly or not, and the mission ends `failed` with
the reasons in the report. `stop` stops every running part. Every change is
logged (`log.jsonl`), journaled (`mission_*`) and published as a `fleet`
frame `{action: "mission", id, state, part?, part_state?}`. One Runner
thread per mission (`ensure`); after the hub restarts, `run` on a mission
still `running` starts its runner again where its parts are (a part that
ran in the hub's own process and left no result then counts as failed).
"""

from __future__ import annotations

import threading
import time
from typing import Callable, Optional

from halo_harness.fleet import journal
from halo_harness.fleet import mission as M
from halo_harness.fleet import mission_store as S
from halo_harness.fleet.mission_dispatch import Dispatch

TICK_S = 0.5
_runners: dict = {}
_lock = threading.Lock()


def frame(publish: Optional[Callable], hid, data: dict) -> None:
    if publish is None:
        return
    try:
        publish({"session_id": None, "harness": hid, "event": "fleet", "turn": None, "agent_id": None, "ts": time.time(),
                 "data": {"action": "mission", **data}})
    except Exception:
        pass


class Runner(threading.Thread):
    def __init__(self, home, mid: str, dispatch: Dispatch, *, publish: Optional[Callable] = None,
                 judge: Optional[Callable] = None, by: str = "") -> None:
        super().__init__(daemon=True, name=f"halo-mission-run-{mid}")
        self.home, self.mid, self.dispatch, self.publish, self.judge, self.by = home, mid, dispatch, publish, judge, by
        self.stop_reason: Optional[str] = None
        self.started_order: list = []

    def request_stop(self, reason: str) -> None:
        self.stop_reason = reason or "stopped by the owner"

    def _emit(self, state: str, **extra) -> None:
        frame(self.publish, self.dispatch.local_id(), {"id": self.mid, "state": state, **extra})

    def _part(self, pid: str, fields: dict) -> dict:
        def apply(doc: dict) -> None:
            doc["parts"].setdefault(pid, {}).update(fields)
        doc = S.update(self.home, self.mid, apply)
        st = doc["parts"][pid]
        S.log(self.home, self.mid, "part", part=pid, state=st.get("state"), error=st.get("error"))
        hub = doc.get("hub") or {}
        journal.append(self.home, "mission_part", harness=hub.get("id"), harness_name=hub.get("name"), mission=self.mid,
                       part=pid, state=st.get("state"), on=st.get("harness_name"), cost_usd=st.get("cost_usd") or None,
                       error=st.get("error"))
        self._emit(doc["state"], part=pid, part_state=st.get("state"))
        return doc

    def _end(self, state: str, why: str) -> None:
        from halo_harness.fleet import mission_report

        def apply(doc: dict) -> None:
            if doc["state"] not in M.FINAL:
                M.move(doc, state, why, self.by)
                doc["stop_reason"] = why if state != "done" else None
        S.update(self.home, self.mid, apply)
        S.log(self.home, self.mid, state, why=why)
        mission_report.write(self.home, self.mid)
        self._emit(state)

    def run(self) -> None:
        try:
            self._loop()
        except Exception as e:  # a runner bug ends the mission with the reason, never the hub
            try:
                self._end("failed", f"the mission runner stopped: {type(e).__name__}: {e}")
            except Exception:
                pass
        finally:
            with _lock:
                if _runners.get((str(self.home), self.mid)) is self:
                    _runners.pop((str(self.home), self.mid), None)

    def _skip_after_failures(self, doc: dict, plan: dict) -> dict:
        bad = {pid for pid, ps in doc["parts"].items() if ps.get("state") in ("failed", "stopped", "skipped")}
        for p in plan["parts"]:
            ps = doc["parts"].get(p["id"]) or {}
            hit = next((d for d in p.get("depends_on") or [] if d in bad), None)
            if ps.get("state") == "pending" and hit:
                doc = self._part(p["id"], {"state": "skipped", "error": f"part {hit} did not finish", "ended": time.time()})
                bad.add(p["id"])
        return doc

    def _loop(self) -> None:
        from halo_harness.fleet.mission_plan import load_plan
        plan = load_plan(self.home, self.mid) or {"parts": []}
        by_id = {p["id"]: p for p in plan["parts"]}
        maxp = M.max_parallel(self.home, max(1, len(plan.get("harnesses") or []) or len({p.get("harness") for p in plan["parts"]})))
        while True:
            doc = S.need(self.home, self.mid)
            if doc["state"] in M.FINAL:
                return
            if self.stop_reason:
                for pid, ps in doc["parts"].items():
                    if ps.get("state") in M.PART_LIVE:
                        self.dispatch.stop(doc, pid, ps, self.stop_reason)
                        doc = self._part(pid, {"state": "stopped", "error": self.stop_reason, "ended": time.time()})
                    elif ps.get("state") == "pending":
                        doc = self._part(pid, {"state": "skipped", "error": self.stop_reason})
                return self._end("stopped", self.stop_reason)
            for pid, ps in list(doc["parts"].items()):
                if ps.get("state") in M.PART_LIVE:
                    upd = self.dispatch.poll(doc, pid, ps)
                    if upd:
                        refused = upd.pop("refused_list", [])
                        for r in refused:  # what a frame did not carry in time (a member's frames are best effort)
                            note_claim(self.home, {"harness": ps.get("harness"), "data": {"mission": self.mid, "part": pid, **r}},
                                       self.publish)
                        doc = self._part(pid, {**upd, "refused": len(refused)} if refused else upd)
            doc = self._skip_after_failures(doc, plan)
            live = sum(1 for ps in doc["parts"].values() if ps.get("state") in M.PART_LIVE)
            ready = [p["id"] for p in plan["parts"] if (doc["parts"].get(p["id"]) or {}).get("state") == "pending"
                     and all((doc["parts"].get(d) or {}).get("state") == "done" for d in p.get("depends_on") or [])]
            for pid in ready[:max(0, maxp - live)]:
                self.started_order.append(pid)
                S.log(self.home, self.mid, "dispatch", part=pid, harness=by_id[pid].get("harness"))
                doc = self._part(pid, self.dispatch.start(doc, by_id[pid], plan))
            states = [ps.get("state") for ps in doc["parts"].values()]
            if not any(s in M.PART_LIVE for s in states) and not ready:
                break
            time.sleep(TICK_S)
        doc = S.need(self.home, self.mid)
        failed = [f"part {pid} {ps.get('state')}: {ps.get('error') or ''}".strip() for pid, ps in doc["parts"].items()
                  if ps.get("state") in ("failed", "stopped")]
        if failed or any(ps.get("state") != "done" for ps in doc["parts"].values()):
            return self._end("failed", "; ".join(failed) or "not every part finished")
        self._merge(doc, plan)

    def _merge(self, doc: dict, plan: dict) -> None:
        from halo_harness.fleet.mission_merge import merge
        S.update(self.home, self.mid, lambda d: M.move(d, "merging", "every part finished", self.by))
        self._emit("merging")
        result = merge(self.home, S.need(self.home, self.mid), plan, self.judge)
        S.update(self.home, self.mid, lambda d: d.update(merge=result))
        for pid in result.get("merged") or []:
            self._part(pid, {"state": "merged"})
        if not result.get("ok"):
            return self._end("failed", result.get("error") or "the merge failed")
        return self._end("done", f"{len(result.get('merged') or [])} repo part(s) merged" if result.get("branch")
                         else "every part finished")


def get(home, mid: str) -> Optional[Runner]:
    with _lock:
        r = _runners.get((str(home), mid))
    return r if r is not None and r.is_alive() else None


def ensure(home, mid: str, dispatch: Dispatch, **kw) -> Runner:
    """The mission's one runner, started when it is not running yet."""
    with _lock:
        r = _runners.get((str(home), mid))
        if r is not None and r.is_alive():
            return r
        r = _runners[(str(home), mid)] = Runner(home, mid, dispatch, **kw)
    r.start()
    return r


def note_claim(home, frame_: dict, publish: Optional[Callable] = None) -> bool:
    """A member's `fleet` frame {action: mission_claim, ...}: logged in the mission folder and journaled."""
    data = frame_.get("data") if isinstance(frame_.get("data"), dict) else {}
    mid, hid = str(data.get("mission") or ""), str(frame_.get("harness") or "")
    doc = S.load(home, mid) if M.valid_id(mid) else None
    if doc is None or str((doc.get("parts") or {}).get(str(data.get("part")), {}).get("harness")) != hid:
        return False
    fields = {k: str(data.get(k) or "")[:300] for k in ("part", "file", "tool", "reason")}
    seen = {(r.get("part"), r.get("file"), r.get("tool")) for r in S.read_log(home, mid, ("claim_refused",))}
    if (fields["part"], fields["file"], fields["tool"]) in seen:
        return False  # logged already: by its worker (here or on a shared mount), or by an earlier frame
    S.log(home, mid, "claim_refused", harness=hid, **fields)
    hub = doc.get("hub") or {}
    journal.append(home, "mission_claim", harness=hub.get("id"), harness_name=hub.get("name"), mission=mid,
                   **{k: fields[k] for k in ("part", "file", "tool")})
    frame(publish, hub.get("id"), {"id": mid, "state": doc.get("state"), "part": fields["part"], "claim": fields["file"]})
    return True
