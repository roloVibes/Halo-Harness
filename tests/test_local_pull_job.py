"""tests.test_local_pull_job -- Halo 3.3.5.0 R3: studio/local_pull_job.py, Local's pull jobs, with a scripted
stream (the `pull=` seam) and against the fake Ollama: the `pull` frames (status, digest, total, completed, percent
rising to 100, a speed, an eta), a second request for the same name joining the job, a cancel (the frame says Ollama
keeps its layers), the catalog caches dropped after a success, `current()` for a page that opens later, the jobs
file a member's push reads, and a fleet member's job followed from its relayed views. No real server.
Run: python -m tests.test_local_pull_job
"""
from __future__ import annotations

import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.control_env import Box  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
GB = 1024 ** 3
LINES = ([{"status": "pulling manifest"}] +
         [{"status": "pulling aaaa", "digest": "sha256:aaaa", "total": 4 * GB, "completed": i * GB} for i in range(1, 5)] +
         [{"status": "pulling bbbb", "digest": "sha256:bbbb", "total": GB, "completed": GB},
          {"status": "verifying sha256 digest"}, {"status": "writing manifest"}, {"status": "success"}])


def scripted(gap: float = 0.06, gate: "threading.Event | None" = None):
    def fn(host, name, on_status=None, cancel=None):
        for i, line in enumerate(LINES):
            if gate is not None and i == 3:
                gate.wait(5)
            if cancel is not None and cancel.is_set():
                return {"ok": False, "cancelled": True, "say": f"the pull of {name} on {host.name} was cancelled: Ollama keeps the layers"}
            on_status(dict(line))
            time.sleep(gap)
        return {"ok": True, "say": f"{name} pulled on {host.name}"}
    return fn


def _wait_done(job_id: str, s: float = 10.0) -> dict:
    from halo_harness.studio import local_pull_job as J
    end = time.monotonic() + s
    while time.monotonic() < end:
        v = J.get(job_id)
        if v and v["done"]:
            return v
        time.sleep(0.03)
    return J.get(job_id) or {}


class _Jobs(Box):
    def __enter__(self):
        super().__enter__()
        from halo_harness.studio import local_pull_job as J
        J.reset()
        self.frames = []
        return self

    def __exit__(self, *exc):
        from halo_harness.studio import local_pull_job as J
        J.reset()
        return super().__exit__(*exc)


@test
def test_frames_carry_progress_speed_and_eta(ctx: Ctx):
    from halo_harness.studio import local_pull_job as J
    with _Jobs() as b:
        v = J.start(b.host, "qwen3.5:9b", b.frames.append, pull=scripted(gap=0.3))
        end = _wait_done(v["job"])
        data = [f["data"] for f in b.frames]
        ctx.check(f"every frame is a `pull` frame for box/qwen3.5:9b, got {b.frames[:1]}",
                  all(f["event"] == "pull" and f["session_id"] == "local" for f in b.frames)
                  and all(d["host"] == "box" and d["name"] == "qwen3.5:9b" for d in data))
        pcts = [d["percent"] for d in data if d["percent"] is not None]
        ctx.check(f"percent rises to 100, got {pcts}", pcts == sorted(pcts) and pcts[-1] == 100.0 and pcts[0] < 100)
        mid = next((d for d in data if d["percent"] and 0 < d["percent"] < 100 and d["speed"]), None)
        ctx.check(f"a speed and an eta while it moves, got {mid}", mid is not None and mid["speed"] > 0 and mid["eta"] is not None)
        ctx.check(f"total counts both layers, got {end.get('total')}", end.get("total") == 5 * GB)
        ctx.check(f"the end: ok, success, eta 0, got {end}", end["ok"] and end["status"] == "success" and end["eta"] == 0
                  and end["say"] == "qwen3.5:9b pulled on box" and data[-1]["done"])
        ctx.check(f"statuses include the manifest and the writing, got {[d['status'] for d in data]}",
                  "pulling manifest" in [d["status"] for d in data] and data[-1]["status"] == "success")


@test
def test_a_second_request_joins_and_cancel_stops(ctx: Ctx):
    from halo_harness.studio import local_pull_job as J
    with _Jobs() as b:
        gate = threading.Event()
        first = J.start(b.host, "qwen3.5:9b", b.frames.append, pull=scripted(gate=gate))
        again = J.start(b.host, "qwen3.5:9b", b.frames.append, pull=scripted())
        ctx.check(f"joined the running job, got {again}", again["joined"] and again["job"] == first["job"])
        other = J.start(b.host, "nomic-embed-text", None, pull=scripted(gap=0.0))
        ctx.check("another name is its own job", other["job"] != first["job"] and not other["joined"])
        cur = J.current()
        ctx.check(f"current() lists both, newest first, got {cur}", [j["job"] for j in cur["jobs"]][:2] == [other["job"], first["job"]]
                  or {j["job"] for j in cur["jobs"]} == {other["job"], first["job"]})
        J.cancel(first["job"])
        gate.set()
        end = _wait_done(first["job"])
        ctx.check(f"cancelled, said, got {end}", end["cancelled"] and not end["ok"] and "keeps the layers" in end["say"]
                  and any(f["data"].get("cancelled") for f in b.frames))
        ctx.check("cancel of an unknown job: None", J.cancel("pull-nope") is None)


@test
def test_success_drops_the_catalog_caches(ctx: Ctx):
    from halo_harness.providers import ollama as O
    from halo_harness.studio import local_catalog, local_pull_job as J, ollama_hosts_view as V
    with _Jobs() as b:
        with O._CATALOG_LOCK:
            O._CATALOG_CACHE[b.host.url] = (time.monotonic(), {"models": []})
        local_catalog._CACHE[b.host.url] = {"sig": None, "catalog": {"models": []}, "tags_at": time.monotonic()}
        V._CACHE[("catalog", b.host.url)] = (time.monotonic(), {"models": []})
        v = J.start(b.host, "qwen3.5:9b", None, pull=scripted(gap=0.0))
        _wait_done(v["job"])
        ctx.check("every catalog cache is dropped", not O._CATALOG_CACHE and not local_catalog._CACHE and not V._CACHE)


@test
def test_a_real_pull_through_the_fake_and_the_jobs_file(ctx: Ctx):
    from halo_harness.fleet.control_pulls import read_pulls
    from halo_harness.studio import local_pull_job as J
    with _Jobs() as b:
        v = J.start(b.host, "qwen3.5:9b", b.frames.append, state_dir=b.state)
        end = _wait_done(v["job"])
        ctx.check(f"pulled through the fake, got {end.get('say')}", end.get("ok") and "qwen3.5:9b" in b.mock.pulled)
        rows = read_pulls(b.state)
        ctx.check(f"the jobs file has it for a member's push, got {rows}", rows and rows[0]["name"] == "qwen3.5:9b" and rows[0]["done"])


@test
def test_a_members_job_followed_from_its_push(ctx: Ctx):
    from halo_harness.fleet.control_pulls import take_pulls
    from halo_harness.studio import local_pull_job as J
    with _Jobs() as b:
        sent = []

        def send(extra):
            sent.append(extra)
            return 200, {"ok": True, "result": {"ok": True, "job": "pull-x"}}
        code, v = J.start_remote("mac", "qwen3.5:9b", send, "fleet member mac@studio", b.frames.append,
                                 member="mac@studio", member_host="local")
        ctx.check(f"started through the member, got {code} {v} {sent}", code == 200 and v["remote"] and sent == [{}])
        n = take_pulls("mac@studio", [{"host": "local", "name": "qwen3.5:9b", "status": "pulling aaaa", "percent": 40.0,
                                       "total": 10, "completed": 4, "done": False}])
        ctx.check(f"a relayed view moves the hub's job, got {n} {J.get(v['job'])}", n == 1 and J.get(v["job"])["percent"] == 40.0)
        ctx.check("another member's view is not this job", take_pulls("other@x", [{"host": "local", "name": "qwen3.5:9b"}]) == 0)
        take_pulls("mac@studio", [{"host": "local", "name": "qwen3.5:9b", "status": "success", "done": True, "ok": True,
                                   "say": "qwen3.5:9b pulled on local"}])
        end = J.get(v["job"])
        ctx.check(f"the end relayed, got {end}", end["done"] and end["ok"] and b.frames[-1]["data"]["done"])
        J.start_remote("mac", "gemma3:4b", send, "fleet member mac@studio", None, member="mac@studio", member_host="local")
        job = next(j for j in J.current()["jobs"] if j["name"] == "gemma3:4b")
        J.cancel(job["job"])
        ctx.check(f"a cancel goes to the member, got {sent}", sent[-1] == {"cancel": True})
        code, err = J.start_remote("mac", "x:1b", lambda e: (403, {"error": "mac has fleet.allow_control: none"}), "", None)
        ctx.check(f"a refusal is the member's answer, got {code} {err}", code == 403 and "allow_control" in err["error"])


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
