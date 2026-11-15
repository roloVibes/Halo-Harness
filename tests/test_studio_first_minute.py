"""tests.test_studio_first_minute -- Studio's first minute in a home like the owner's (Halo 3.6.0.0 R14).

`halo init` from the home folder: the project IS the home (its `.halo` is the state dir), a big pack enabled at project
scope, two Ollama hosts that do not answer, a megabyte of ~/.claude.json, past transcripts. The owner's laptop sat at
110% of a core for a minute. The real server is started here as `halo init` starts it (`halo studio --cwd <home>
--edit setup:first --no-open`), the Setup page's first requests are sent the way a browser sends them (five
connections at once and the event stream, then the second wave, then live/attention + live/conflicts every 6 s) with
`halo init`'s own wait polling beside them once a second, and the server's own CPU counter (`GET studio/timings`:
user + system time of the whole process, all threads -- never wall time, so a slow runner does not fail it) is held
to the budgets:

1. launch to idle: at most 5 CPU-seconds; the address printed at most 2 CPU-seconds into the process (its own phase
   record); setup/state's answer (the Setup page's first read) at most 2 s of its thread's CPU; idle for 30 s with
   the page open (event stream, the 6 s polls, init's wait): under 2% of a core;
2. a project tree of 50,000 files in 2,000 folders planted in the home: the start costs at most 25% + 0.5 CPU-s more
   than the same home without it (nothing at start walks the project tree).

The fixture is one pack of the owner's two (doc-review grown to 51 bios and 9 workflows with 54 stage roles: the
shape that cost seconds -- every bio read again for every stage), so the budgets are the brief's own, unscaled: the
fixture is no bigger than the owner's home and the budget no smaller. Nothing leaves 127.0.0.1; no model is called.
Run: python -m tests.test_studio_first_minute
"""
from __future__ import annotations

import http.client
import json
import os
import queue
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()

CPU_TO_IDLE_S = 5.0
ADDRESS_CPU_S = 2.0
FIRST_READ_CPU_S = 2.0
IDLE_SHARE = 0.02
IDLE_WINDOW_S = 30.0
TREE_FILES, TREE_DIRS = 50_000, 2_000
FIRST = ["live", "live/attention", "live/conflicts", "setup/state", "settings/themes", "pack/registry", "settings/catalog",
         "settings/values"]
SECOND = ["ollama/steward", "setup/ollama/scan", "setup/ollama/measure", "setup/copilot", "live"]
_BASE: dict = {}  # test 1's start cost, test 2's baseline


# ---- the home ---------------------------------------------------------------------------------------------------
def _big_pack(packs: Path) -> None:
    """doc-review, grown: 48 more bios and 8 more workflows of 6 stages, every stage naming a bio by its kind."""
    src = REPO / "halo_harness" / "templates" / "packs" / "doc-review"
    dst = packs / "doc-review"
    shutil.copytree(src, dst)
    bio = (dst / "agents" / "reviewer.yaml").read_text(encoding="utf-8")
    names = []
    for i in range(48):
        name = f"r{i:02d}"
        (dst / "agents" / f"{name}.yaml").write_text(bio.replace("name: reviewer", f"name: {name}")
                                                     .replace("kind: reviewer", f"kind: k{i:02d}"), encoding="utf-8")
        names.append(f"agents/{name}.yaml")
    flows = []
    for w in range(8):
        stages = []
        for k in range(6):
            stages.append({"id": f"s{k}", "title": f"Step {k}", "brief": f"Do step {k}.", "role": f"k{(w * 6 + k) % 48:02d}",
                           **({"after": [f"s{k - 1}"]} if k else {}), "gives": [{"name": "notes", "kind": "summary"}]})
        (dst / "workflows" / f"flow{w}.yaml").write_text(json.dumps({"name": f"flow{w}", "description": "a test flow",
                                                                     "stages": stages}), encoding="utf-8")
        flows.append(f"flow{w}")
    manifest = (dst / "pack.yaml").read_text(encoding="utf-8")
    manifest = manifest.replace("  agents: [agents/reviewer.yaml, agents/writer.yaml, agents/helper.md]",
                                "  agents: [agents/reviewer.yaml, agents/writer.yaml, agents/helper.md, " + ", ".join(names) + "]")
    manifest = manifest.replace("  workflows: [review]", "  workflows: [review, " + ", ".join(flows) + "]")
    (dst / "pack.yaml").write_text(manifest, encoding="utf-8")
    old = os.path.getmtime(dst / "pack.yaml") - 3600  # installed an hour ago (a file younger than 3 s is never kept)
    for p in dst.rglob("*"):
        os.utime(p, (old, old))
    (packs / "state.json").write_text(json.dumps({"version": 1, "installed": {"doc-review": {
        "version": "1.0.0", "source": str(src), "installed": "2026-11-01T00:00:00Z", "enabled": True,
        "granted": ["mcp:lint", "hooks", "bash"], "scope": "project", "root": str(dst)}}}, indent=2), encoding="utf-8")


def _home(root: Path) -> Path:
    home = root / "home"
    halo = home / ".halo"
    (halo / "packs").mkdir(parents=True)
    _big_pack(halo / "packs")
    (halo / "config.json").write_text(json.dumps({
        "ollama": {"hosts": [{"name": "lan", "url": "http://127.0.0.1:9"}, {"name": "local", "url": "http://127.0.0.1:9"}],
                   "discover": {"ports": [9]}, "steward": {"job": False}},
        "huggingface": {"local_probe_ports": [9]}}, indent=2), encoding="utf-8")
    projects = {str(home): {"hasTrustDialogAccepted": True, "history": []}}
    for i in range(120):  # a long-time Claude Code user's ~/.claude.json: about a megabyte
        projects[str(home / "src" / f"repo{i}")] = {"hasTrustDialogAccepted": True,
                                                    "history": [{"display": "x" * 200, "pastedContents": {}}] * 40}
    (home / ".claude.json").write_text(json.dumps({"numStartups": 900, "projects": projects}), encoding="utf-8")
    for i in range(150):
        d = home / ".claude" / "projects" / f"-src-repo{i % 15}"
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{i:08d}-0000-0000-0000-000000000000.jsonl").write_text(
            "\n".join(json.dumps({"type": "user", "message": {"role": "user", "content": "word " * 40}}) for _ in range(20)),
            encoding="utf-8")
    return home


def _plant_tree(home: Path) -> None:
    per = TREE_FILES // TREE_DIRS
    tops = ["src", "Library/Caches", "Documents", ".cache/pip", "node_modules", "work/.git/objects"]
    for d in range(TREE_DIRS):
        folder = home / tops[d % len(tops)] / f"d{d // 40}" / f"e{d}"
        folder.mkdir(parents=True, exist_ok=True)
        for f in range(per):
            with open(folder / f"f{f}.txt", "wb") as fh:
                fh.write(b"x")


# ---- the server and the page ----------------------------------------------------------------------------------
class Studio:
    def __init__(self, home: Path) -> None:
        self.home = home
        env = {k: v for k, v in os.environ.items() if not k.startswith(("BRIDGE_", "HALO_", "OLLAMA_", "HF_", "CLAUDE_"))}
        env.update({"BRIDGE_TEST_HOME": str(home), "HOME": str(home), "USERPROFILE": str(home),
                    "OLLAMA_HOST": "http://127.0.0.1:9", "HF_HOME": str(home / ".cache" / "huggingface"),
                    "PYTHONPATH": str(REPO), "PYTHONIOENCODING": "utf-8"})
        self.proc = subprocess.Popen([sys.executable, "-u", "-m", "halo_harness", "studio", "--cwd", str(home), "--edit",
                                      "setup:first", "--no-open"], cwd=str(home), env=env, stdin=subprocess.DEVNULL,
                                     stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, encoding="utf-8",
                                     errors="replace")
        self.url = ""
        got = threading.Event()

        def read() -> None:
            for line in self.proc.stdout:  # type: ignore[union-attr]
                if "Halo Studio is at " in line and not self.url:
                    self.url = line.split("Halo Studio is at ", 1)[1].strip()
                    got.set()
        threading.Thread(target=read, daemon=True).start()
        got.wait(120)
        if not self.url:
            raise RuntimeError("Studio printed no address in 120 s")
        from urllib.parse import urlsplit
        u = urlsplit(self.url)
        self.port, self.token, self.query = u.port, u.fragment.split("t=", 1)[1], u.query
        self.stop_flag = threading.Event()
        self.done: list = []

    def get(self, path: str, conn=None):
        c = conn or http.client.HTTPConnection("127.0.0.1", self.port, timeout=120)
        c.request("GET", "/api/" + path, headers={"Authorization": f"Bearer {self.token}"})
        r = c.getresponse()
        body = r.read()
        if conn is None:
            c.close()
        return r.status, body

    def timings(self) -> dict:
        status, body = self.get("studio/timings")
        return json.loads(body) if status == 200 else {}

    def page(self) -> None:
        """The Setup page's load as a browser sends it, then its polls and init's wait (threads, until close)."""
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=120)
        c.request("GET", "/?" + self.query)
        c.getresponse().read()
        q: "queue.Queue" = queue.Queue()
        for p in FIRST:
            q.put(p)

        def worker() -> None:
            conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=120)
            while True:
                try:
                    p = q.get_nowait()
                except queue.Empty:
                    return
                self.done.append((p, self.get(p, conn)[0]))

        def sse() -> None:
            try:
                conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=300)
                conn.request("GET", f"/api/events?t={self.token}&sessions=all")
                r = conn.getresponse()
                while not self.stop_flag.is_set() and r.fp.readline():
                    pass
            except Exception:
                pass

        def polls() -> None:
            conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=120)
            while not self.stop_flag.wait(6.0):
                for p in ("live/attention", "live/conflicts"):
                    self.get(p, conn)

        def init_wait() -> None:  # `halo init` waiting for Done (init_wait.POLL_PATH), a new connection each time
            from halo_harness.init_wait import POLL_PATH
            while not self.stop_flag.wait(1.0):
                self.get(POLL_PATH)

        threading.Thread(target=sse, daemon=True).start()
        ws = [threading.Thread(target=worker, daemon=True) for _ in range(5)]
        for w in ws:
            w.start()
        for w in ws:
            w.join(180)
        for p in SECOND:
            q.put(p)
        ws = [threading.Thread(target=worker, daemon=True) for _ in range(5)]
        for w in ws:
            w.start()
        for w in ws:
            w.join(180)
        threading.Thread(target=polls, daemon=True).start()
        threading.Thread(target=init_wait, daemon=True).start()

    def idle(self, limit_s: float = 120.0) -> dict:
        """The timings record once the server is idle: a 5 s span that cost under 0.1 CPU-s (or `limit_s`)."""
        end = time.monotonic() + limit_s
        prev = self.timings()
        while time.monotonic() < end:
            time.sleep(5.0)
            now = self.timings()
            if now.get("cpu_s", 0) - prev.get("cpu_s", 0) < 0.1:
                return now
            prev = now
        return prev

    def close(self) -> None:
        self.stop_flag.set()
        try:
            self.proc.terminate()
            self.proc.wait(timeout=20)
        except Exception:
            try:
                self.proc.kill()
            except Exception:
                pass


def _start_cost(home: Path) -> "tuple[dict, Studio]":
    s = Studio(home)
    s.page()
    return s.idle(), s


# ---- the tests -------------------------------------------------------------------------------------------------
@test
def test_launch_to_idle_and_idle_cost_in_an_owner_shaped_home(ctx: Ctx):
    root = Path(tempfile.mkdtemp(prefix="studio-first-minute-"))
    s = None
    try:
        home = _home(root)
        rec, s = _start_cost(home)
        ctx.check(f"every page request answered 200, got {[d for d in s.done if d[1] != 200]}",
                  len(s.done) == len(FIRST) + len(SECOND) and all(st == 200 for _p, st in s.done))
        cpu = rec.get("cpu_s")
        _BASE["cpu"] = cpu
        ctx.check(f"launch to idle costs at most {CPU_TO_IDLE_S} CPU-s (the process's own counter), got {cpu}",
                  isinstance(cpu, (int, float)) and cpu <= CPU_TO_IDLE_S)
        printed = next((p for p in rec.get("phases") or [] if p["phase"] == "address printed"), None)
        ctx.check(f"the address is printed at most {ADDRESS_CPU_S} CPU-s into the process, got {printed}",
                  printed is not None and printed["cpu_s"] <= ADDRESS_CPU_S)
        first = next((r for r in rec.get("requests") or [] if r["path"] == "/api/setup/state"), None)
        ctx.check(f"setup/state (the page's first read) takes at most {FIRST_READ_CPU_S} s of its thread's CPU, got {first}",
                  first is not None and first["cpu_s"] <= FIRST_READ_CPU_S and first["status"] == 200)
        a = s.timings()
        time.sleep(IDLE_WINDOW_S)
        b = s.timings()
        share = (b["cpu_s"] - a["cpu_s"]) / max(1e-6, b["up_s"] - a["up_s"])
        ctx.check(f"idle for {IDLE_WINDOW_S:.0f} s with the page open (its stream, its polls, init's wait) costs under "
                  f"{IDLE_SHARE:.0%} of a core, got {share:.2%} ({b['cpu_s'] - a['cpu_s']:.3f} CPU-s)", share < IDLE_SHARE)
    finally:
        if s is not None:
            s.close()
        shutil.rmtree(root, ignore_errors=True)


@test
def test_a_big_project_tree_does_not_grow_the_start_cost(ctx: Ctx):
    root = Path(tempfile.mkdtemp(prefix="studio-first-minute-tree-"))
    s = None
    try:
        home = _home(root)
        base = _BASE.get("cpu")
        if base is None:
            rec, s = _start_cost(home)
            s.close()
            s = None
            base = rec.get("cpu_s")
            shutil.rmtree(home / ".halo" / "run", ignore_errors=True)
        _plant_tree(home)
        n = sum(len(files) for _r, _d, files in os.walk(home / "src")) if (home / "src").is_dir() else 0
        ctx.check(f"the tree is planted ({TREE_FILES} files), got {n} under src/ alone", n > 0)
        rec, s = _start_cost(home)
        cpu = rec.get("cpu_s")
        bound = base * 1.25 + 0.5 if isinstance(base, (int, float)) else None
        ctx.check(f"with {TREE_FILES} files in {TREE_DIRS} folders the start costs at most 25% + 0.5 CPU-s more than "
                  f"without ({base}): got {cpu}", bound is not None and isinstance(cpu, (int, float)) and cpu <= bound)
    finally:
        if s is not None:
            s.close()
        shutil.rmtree(root, ignore_errors=True)


@test
def test_studio_timings_flag_prints_phases_and_requests(ctx: Ctx):
    """`halo studio --timings`: a `timings:` line per start phase and per first request, as they happen."""
    root = Path(tempfile.mkdtemp(prefix="studio-timings-"))
    proc = None
    try:
        home = root / "home"
        (home / ".halo").mkdir(parents=True)
        env = {k: v for k, v in os.environ.items() if not k.startswith(("BRIDGE_", "HALO_", "OLLAMA_"))}
        env.update({"BRIDGE_TEST_HOME": str(home), "BRIDGE_TEST_NO_BACKGROUND_NET": "1", "PYTHONPATH": str(REPO),
                    "OLLAMA_HOST": "http://127.0.0.1:9", "PYTHONIOENCODING": "utf-8"})
        proc = subprocess.Popen([sys.executable, "-u", "-m", "halo_harness", "studio", "--cwd", str(home), "--no-open",
                                 "--timings"], cwd=str(home), env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                stderr=subprocess.DEVNULL, text=True, encoding="utf-8", errors="replace")
        lines: list = []
        url = threading.Event()

        def read() -> None:
            for line in proc.stdout:  # type: ignore[union-attr]
                lines.append(line.rstrip("\n"))
                if "Halo Studio is at " in line:
                    url.set()
        threading.Thread(target=read, daemon=True).start()
        url.wait(120)
        addr = next((ln.split("Halo Studio is at ", 1)[1] for ln in lines if "Halo Studio is at " in ln), "")
        from urllib.parse import urlsplit
        u = urlsplit(addr)
        c = http.client.HTTPConnection("127.0.0.1", u.port, timeout=60)
        c.request("GET", "/api/settings/themes", headers={"Authorization": "Bearer " + u.fragment.split("t=", 1)[1]})
        c.getresponse().read()
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline and not any("GET /api/settings/themes" in ln for ln in lines):
            time.sleep(0.2)
        t = [ln for ln in lines if ln.startswith("timings: ")]
        ctx.check(f"the three start phases, each with wall and cpu, got {t[:4]}",
                  all(any(ln.startswith(f"timings: {ph}") and " s wall, " in ln and " s cpu " in ln for ln in t)
                      for ph in ("command started", "server bound", "address printed")))
        ctx.check(f"the request's own line with its status, wall and cpu, got {[ln for ln in t if 'GET' in ln]}",
                  any("GET /api/settings/themes (200)" in ln and " s wall, " in ln and "s cpu (its thread)" in ln for ln in t))
    finally:
        if proc is not None:
            proc.terminate()
            try:
                proc.wait(timeout=20)
            except Exception:
                proc.kill()
        shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="studio first minute"))
