"""halo_harness.guest.hand_out -- Claude Code, as main, hands one bounded task to an agent Halo runs on the person's
OWN local model (Halo 3.6.0.26 H; docs/GUEST.md "Hand-outs"). OFF until he sets `guest.hand_out local`.

    setting() -> (value, raw)         read once by the bridge at its start: "off" | "local" (anything else reads "off")
    choose(model, state_dir) -> (ref, host, line)   the model checked as his own (model.is_own_local_ref); line '' = ok
    on_host(ref, host) -> line        one read of the host's model list before a start ('' = it is there)
    models(state_dir) -> rows         what Halo KNOWS of each allowed model (never a guess), <= MAX_ROWS, <= MAX_BYTES
    frame(goal, acceptance, files, mode) -> the worker's user prompt (the session's system prompt is never touched)
    HandOuts                          the bridge's jobs: start, state, result in parts, stop; its child rows in the tree

A worker is `halo -p --output-format json --strict-mcp-config --offline` (no tool server, nothing but loopback and his
own local hosts on the network), a CHILD of the bridge started through subprocess_safe.Popen after the bridge ran
closing.install() (Windows: born in the bridge's Job; POSIX: its own session, watching the bridge) and recorded in the
children ledger as the bridge's. Its prompt goes on stdin. `none` = `--tools ""`, `read_only` = `--permission-mode
plan`: a print run turns every ask into a recorded denial, so nothing waits for a person. The wall clock is this
module's timer: the polite `shutdown` on the worker's socket, then closing's stop of the pid (children_stop). A job's
record lives in this process and in `<guest dir>/<claude pid>.job.<id>.json` (0600) while the bridge lives; the
bridge's end removes it, guest.sweep_dead removes a dead bridge's.
"""

from __future__ import annotations

import json
import os
import threading
import time
import uuid
from collections import deque
from pathlib import Path
from typing import Callable, Optional

SETTING = "guest.hand_out"
VALUES = ("off", "local")
TURNS, TURNS_CAP = 12, 40
MINUTES, MINUTES_CAP = 10, 60
JOBS_CAP, HOST_CAP = 2, 1
PART = 20_000  # characters of the answer per part
MAX_ROWS, MAX_BYTES = 40, 8192
MINUTE_S = 60.0  # the wall clock's minute (a test's clock is shorter)
POLL_S = 1.0  # the worker's socket read, and at most one progress notification, per second
POLITE_S = 10.0  # after the polite shutdown, closing's stop of the pid
PAIR_NS = 5_000_000_000  # a hook line of the call and the call itself land this close together
LOG_LINES = 20
TOOL = "halo_hand_out"  # its hook line names it mcp__plugin_halo-guest_halo-guest__halo_hand_out
COST = "free (local)"
ALLOWED = ("allowed: ol:<model> or ol:<model>@<host> on an Ollama host entry with no key (your own machine or network), "
           "hf:local/<model>, hf:mlx/<model>")
OFF_LINE = "hand-outs are off: `halo config set guest.hand_out local` turns them on (then reconnect this server)"


def setting() -> "tuple[str, object]":
    try:
        from halo_harness.theme import get_config_value
        raw = get_config_value(SETTING, None)
    except Exception:
        raw = None
    value = raw.strip().lower() if isinstance(raw, str) else "off"
    return (value if value in VALUES else "off"), raw


def setting_line() -> str:
    """`halo doctor`'s and `halo guest status`' words for the setting."""
    value, raw = setting()
    if raw is not None and value == "off" and not (isinstance(raw, str) and raw.strip().lower() == "off"):
        return f"hand-outs: off ({SETTING} is {raw!r}: only off or local are read)"
    return ("hand-outs: local (Claude Code may hand bounded tasks to your own local models)" if value == "local"
            else "hand-outs: off")


# ---- the model ------------------------------------------------------------------------------------------------------
def _routes(state_dir) -> dict:
    try:
        from halo_harness.providers.config import load_routes
        path = Path(state_dir) / "routes.json"
        return load_routes(path if path.exists() else None) or {}
    except Exception:
        return {}


def choose(model, state_dir) -> "tuple[str, object, str]":
    """(the ref the worker runs, its parsed ModelRef, '') or ('', None, the one line said)."""
    from halo_harness.model import is_own_local_ref, parse_model_ref, resolve_default_model_raw
    routes = _routes(state_dir)
    given = " ".join(str(model or "").split())[:200]
    default = not given
    if default:
        try:
            given = str(resolve_default_model_raw(routes) or "")
        except Exception:
            given = ""
        if not given:
            return "", None, f"no model given and Halo has no default model; {ALLOWED}"
    if given.startswith("-"):
        return "", None, f"{given} is not a model ref; {ALLOWED}"
    try:
        ref = parse_model_ref(given, routes)
        mine = is_own_local_ref(ref)
    except Exception:
        ref, mine = None, False
    if not mine:
        head = f"no model given and Halo's default model {given} is not local" if default else f"{given} is not local"
        return "", None, f"{head}; {ALLOWED}"
    return given, ref, ""


def _host(ref):
    from halo_harness.providers.ollama import resolve_ollama_host
    return resolve_ollama_host(ref.host) if ref.provider == "ollama" else None


def host_key(ref) -> str:
    host = _host(ref)
    return f"ollama:{host.name}" if host is not None else f"{ref.provider}:local"


def _names(host) -> Optional[set]:
    from halo_harness.providers import ollama as O
    if O.host_is_openai_dialect(host):
        payload = O.probe_openai_models(host, timeout=5.0)
        tags = None if payload is None else {"models": O._openai_models_as_tags(payload)}  # noqa: SLF001 (its catalog's reader)
    else:
        tags = O.fetch_tags(host, timeout=5.0)
    if not isinstance(tags, dict):
        return None
    return {str(m.get("name") or m.get("model") or "") for m in tags.get("models") or [] if isinstance(m, dict)}


def on_host(ref) -> str:
    """'' when the model is on its host; else the line said before anything starts (hf: has no list to read)."""
    host = _host(ref)
    if host is None:
        return ""
    try:
        names = _names(host)
    except Exception:
        names = None
    if names is None:
        return f"the Ollama host {host.name} does not answer: nothing was started"
    if ref.model not in names and f"{ref.model}:latest" not in names:
        return f"{ref.model} is not on {host.name}: nothing was started (halo_models lists what is)"
    return ""


def _yes_no(value) -> str:
    return "yes" if value is True else "no" if value is False else "not known"


def _known(m: dict, key: str):
    v = ((m or {}).get(key) or {}).get("value")
    return v if v is not None else "not known"


def models(state_dir) -> dict:
    """{models: [...], more?, note}: the models of his keyless Ollama hosts, each with what Halo knows of it."""
    from halo_harness.model import is_own_local_ref, parse_model_ref
    from halo_harness.providers.measured import measured_for
    from halo_harness.providers.ollama import get_catalog, resolve_ollama_hosts
    from halo_harness.ollama_steward.tuner_notes import by_line, read as read_notes
    rows = []
    for host in resolve_ollama_hosts():
        ref_tail = "" if getattr(host, "synthesized", False) else f"@{host.name}"
        try:
            if not is_own_local_ref(parse_model_ref(f"ol:x{ref_tail}", {})):
                continue
            catalog = get_catalog(host)
        except Exception:
            continue
        for entry in catalog.get("models") or []:
            name = str((entry or {}).get("name") or (entry or {}).get("model") or "")
            if not name:
                continue
            caps = entry.get("capabilities") or []
            info = entry.get("model_info") or {}
            trained = next((v for k, v in info.items() if str(k).endswith(".context_length") and isinstance(v, int)), None)
            m = measured_for(host, name, state_dir=state_dir)
            window = _known(m, "window")
            row = {"ref": f"ol:{name}{ref_tail}", "host": host.name,
                   "trained_window": trained if trained else "not known",
                   "verified_window": window.get("verified") or "not known" if isinstance(window, dict) else window,
                   "tok_s": _known(m, "tok_s"), "cold_load_s": _known(m, "load_s"),
                   "tool_calling": _yes_no(True if "tools" in caps else False if caps else None), "cost": COST}
            guide = read_notes(state_dir, host.name, name, digest=entry.get("digest")).get("guide")
            if guide and guide.get("text"):
                row["tuner_guide"] = f"the tuner's guide ({by_line(guide)}): {str(guide['text'])[:300]}"
            rows.append(row)
    out = {"models": rows[:MAX_ROWS], "note": "hf:local/<model> and hf:mlx/<model> are allowed too (not listed here)"}
    if len(rows) > MAX_ROWS:
        out["more"] = len(rows) - MAX_ROWS
    while out["models"] and len(json.dumps(out)) > MAX_BYTES:
        out["models"].pop()
        out["more"] = len(rows) - len(out["models"])
    return out


# ---- what the worker is sent ----------------------------------------------------------------------------------------
def frame(goal: str, acceptance: list, files: list, mode: str) -> str:
    """The worker's user prompt: the goal, the files, the checks and the one JSON line that answers them."""
    lines = ["Halo hands you one task from a Claude Code session. Do only this task, then answer in plain text.",
             "You have no tools: answer from what is written here." if mode == "none" else
             "You may read and search files in the project folder; you change nothing and run no command.",
             "", "The task:", goal.strip()]
    if files:
        lines += ["", "Files the task is about:"] + [f"- {f}" for f in files]
    if acceptance:
        lines += ["", "Checks your answer must meet:"] + [f"{i}. {c}" for i, c in enumerate(acceptance, 1)]
        lines += ["", "End your answer with one line of JSON that answers each check, in order, like this:",
                  '{"acceptance": [{"n": 1, "met": "yes", "why": "one short line"}]}']
    return "\n".join(lines) + "\n"


def answers(text: str, checks: list) -> list:
    """Each check with the worker's answer when its last JSON line gave all of them in the asked shape; else every
    one "not answered" (never invented)."""
    for line in reversed((text or "").strip().splitlines()):
        s = line.strip().strip("`").strip()
        if not (s.startswith("{") and '"acceptance"' in s):
            continue
        try:
            got = json.loads(s).get("acceptance")
        except (ValueError, AttributeError):
            break
        if (isinstance(got, list) and len(got) == len(checks)
                and all(isinstance(g, dict) and str(g.get("met") or "").lower() in ("yes", "no") for g in got)):
            return [{"check": c, "answer": f"{str(g['met']).lower()}: {' '.join(str(g.get('why') or '').split())[:300]}"}
                    for c, g in zip(checks, got)]
        break
    return [{"check": c, "answer": "not answered"} for c in checks]


def argv_of(model: str, project, turns: int, mode: str) -> list:
    """The worker's command line, from the helper Studio's new-session start uses (selfexec.python_argv)."""
    from halo_harness.selfexec import python_argv
    argv = [*python_argv(unbuffered=True), "-p", "--output-format", "json", "--strict-mcp-config", "--offline",
            "--model", model, "--cwd", str(project), "--max-turns", str(turns)]
    return argv + (["--tools", ""] if mode == "none" else ["--permission-mode", "plan"])


# ---- the arguments ---------------------------------------------------------------------------------------------------
def _int(args: dict, key: str, default: int, cap: int) -> int:
    v = args.get(key)
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return default
    return max(1, min(cap, int(v)))


def _strs(value, most: int, each: int) -> "Optional[list]":
    if value is None:
        return []
    if not isinstance(value, list) or len(value) > most or not all(isinstance(x, str) for x in value):
        return None
    return [" ".join(x.split())[:each] for x in value if x.strip()]


def task_of(args: dict) -> "tuple[Optional[dict], str]":
    goal = args.get("goal")
    if not isinstance(goal, str) or not goal.strip():
        return None, "goal is the task in plain words (at most 4,000 characters)"
    mode = args.get("mode")
    if mode not in ("none", "read_only"):
        return None, "mode is none (no tools) or read_only (reads in the project folder); nothing else in this release"
    acceptance, files = _strs(args.get("acceptance"), 10, 300), _strs(args.get("files"), 50, 500)
    if acceptance is None:
        return None, "acceptance is a list of at most 10 checks, each at most 300 characters"
    if files is None:
        return None, "files is a list of at most 50 paths"
    return {"goal": goal.strip()[:4000], "mode": mode, "acceptance": acceptance, "files": files,
            "turns": _int(args, "max_turns", TURNS, TURNS_CAP), "minutes": _int(args, "max_minutes", MINUTES, MINUTES_CAP),
            "wait": args.get("wait") is not False}, ""


# ---- one job ----------------------------------------------------------------------------------------------------------
def _private(path: Path, data: dict) -> None:
    from halo_harness.guest.bridge import _private_file
    try:
        _private_file(path, json.dumps(data).encode("utf-8"))
    except OSError:
        pass


class Job:
    def __init__(self, owner: "HandOuts", task: dict, model: str, key: str, args: dict) -> None:
        self.id = uuid.uuid4().hex
        self.owner, self.task, self.model, self.key = owner, task, model, key
        self.aid = f"halo-{self.id[:12]}"
        self.state = "running"
        self.t0, self.t_ns = time.monotonic(), time.time_ns()
        self.t1: Optional[float] = None
        from halo_harness.guest.note import cut_input
        self.cut = cut_input(f"mcp__plugin_halo-guest_halo-guest__{TOOL}", args)  # as the hook cuts the call's input
        self.parent = "main"
        self.proc = None
        self.entry: Optional[dict] = None
        self.live: dict = {"current": "starting", "turns": 0, "tokens_in": 0, "tokens_out": 0, "last_text": ""}
        self.result: Optional[dict] = None  # the worker's json line
        self.log: deque = deque(maxlen=LOG_LINES)
        self.why = ""  # why it was stopped
        self.done = threading.Event()
        self.step = 0  # progress, increasing
        self._stop_asked = threading.Event()
        self._client = None

    # what is said of it
    def minutes(self) -> float:
        return round(((self.t1 or time.monotonic()) - self.t0) / 60.0, 2)

    def brief(self) -> dict:
        return {"job_id": self.id, "state": self.state, "model": self.model, "mode": self.task["mode"],
                "goal": self.task["goal"][:200], "step": self.live.get("current") or "", "turns": self.live.get("turns") or 0,
                "tokens": {"in": self.live.get("tokens_in") or 0, "out": self.live.get("tokens_out") or 0},
                "minutes": self.minutes(), **({"stopped_by": self.why} if self.why else {})}

    def text(self) -> str:
        return str((self.result or {}).get("result") or self.live.get("last_text") or "")

    def packet(self, part: int = 1) -> dict:
        text = self.text()
        parts = max(1, -(-len(text) // PART))
        part = max(1, min(part, parts))
        r = self.result or {}
        usage = r.get("usage") if isinstance(r.get("usage"), dict) else {}
        out = {**self.brief(), "summary": text[(part - 1) * PART:part * PART], "part": part, "parts": parts,
               "acceptance": answers(text, self.task["acceptance"]) if self.done.is_set() else [],
               "permission_denials": r.get("permission_denials") or [], "num_turns": r.get("num_turns", self.live.get("turns")),
               "usage": usage, "total_cost_usd": r.get("total_cost_usd"), "cost_complete": r.get("cost_complete"),
               "cost": COST, "stop_reason": r.get("stop_reason"), "subtype": r.get("subtype")}
        if parts > 1:
            more = f"; call halo_job_result with part {part + 1} for the next" if part < parts else ""
            out["cut"] = (f"the answer is {len(text):,} characters, cut into {parts} parts of {PART:,}: this is part "
                          f"{part} (characters {(part - 1) * PART + 1:,} to {min(len(text), part * PART):,}){more}")
        if self.state == "failed":
            out["exit_code"] = self.proc.returncode if self.proc is not None else None
            out["log_tail"] = "\n".join(self.log)[-2048:]
        return out

    # its life
    def run(self) -> None:
        try:
            self._start()
            self._watch()
        except Exception as e:  # never a hang: a job that could not run says so
            self.log.append(f"{type(e).__name__}: {e}")
            self.state = "failed"
        finally:
            self._end()

    def _start(self) -> None:
        from halo_harness import subprocess_safe as subprocess
        from halo_harness.remote.session_identity import PARENT_ENV
        argv = argv_of(self.model, self.owner.project, self.task["turns"], self.task["mode"])
        env = {k: v for k, v in os.environ.items() if k not in ("HALO_ORCHESTRA_RUN", PARENT_ENV)}
        env.update({PARENT_ENV: f"guest:{self.owner.sid}", "PYTHONIOENCODING": "utf-8"})
        kw: dict = {"stdin": subprocess.PIPE, "stdout": subprocess.PIPE, "stderr": subprocess.PIPE,
                    "cwd": str(self.owner.project), "env": env}
        if os.name == "nt":
            kw["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP | getattr(subprocess, "CREATE_NO_WINDOW", 0)
        else:
            kw["start_new_session"] = True  # its own session: a signal to the bridge's group is not its end
        self.proc = subprocess.Popen(argv, **kw)
        from halo_harness import children
        self.entry = children.register(self.proc.pid, "guest-worker", argv, job=self.id)
        self.owner.save(self)
        self._out = []
        self._readers = [threading.Thread(target=fn, daemon=True, name=f"halo-handout-{what}-{self.id[:8]}")
                         for fn, what in ((self._read_out, "out"), (self._read_err, "err"))]
        for t in self._readers:
            t.start()
        prompt = frame(self.task["goal"], self.task["acceptance"], self.task["files"], self.task["mode"])
        try:
            self.proc.stdin.write(prompt.encode("utf-8"))
            self.proc.stdin.close()
        except OSError:
            pass

    def _read_out(self) -> None:
        try:
            self._out.append(self.proc.stdout.read())
        except (OSError, ValueError):
            pass

    def _read_err(self) -> None:
        try:
            for raw in iter(self.proc.stderr.readline, b""):
                self.log.append(raw.decode("utf-8", "replace").rstrip()[:200])
        except (OSError, ValueError):
            pass

    def _watch(self) -> None:
        limit = self.t0 + self.task["minutes"] * MINUTE_S
        while self.proc.poll() is None:
            if time.monotonic() >= limit and not self._stop_asked.is_set():
                self.stop(f"the wall clock ({self.task['minutes']} minutes)")
            self._read_socket()
            self.owner.tick(self)
            try:
                self.proc.wait(POLL_S)
            except Exception:
                pass

    def _read_socket(self) -> None:
        """The worker's main row from its own socket's `agents` (its tool now, turns, tokens, last words)."""
        try:
            if self._client is None:
                from halo_harness.remote import registry
                from halo_harness.remote.client import ControlClient, default_token_for
                row = next((r for r in registry.list_live() if isinstance(r, dict) and r.get("pid") == self.proc.pid), None)
                if row is None:
                    return
                self._client = ControlClient(str(row.get("endpoint") or ""), default_token_for(row), timeout=2.0)
            rows = (self._client.call("agents").get("result") or {}).get("agents") or []
        except Exception:
            self._drop_client()
            return
        main = next((r for r in rows if isinstance(r, dict) and not r.get("parent")), None)
        if main:
            for k in ("current", "turns", "tokens_in", "tokens_out", "last_text"):
                if main.get(k) is not None:
                    self.live[k] = main[k]

    def _drop_client(self) -> None:
        client, self._client = self._client, None
        if client is not None:
            try:
                client.close()
            except Exception:
                pass

    def stop(self, why: str, polite_s: Optional[float] = None) -> str:
        """The polite `shutdown` on its socket, then (POLITE_S later) closing's stop of the pid. Its words."""
        if self.done.is_set():
            return f"the job has ended ({self.state})"
        if self._stop_asked.is_set():
            return "the stop was asked already; the job has not ended yet"
        self._stop_asked.set()
        self.why = why
        threading.Thread(target=self._stop_now, args=(why, POLITE_S if polite_s is None else polite_s), daemon=True,
                         name=f"halo-handout-stop-{self.id[:8]}").start()
        return "the stop is asked: the agent ends at its next step, its process within seconds"

    def _stop_now(self, why: str, polite_s: float) -> None:
        try:
            if self._client is None:
                self._read_socket()
            if self._client is not None:
                self._client.call("shutdown", via="halo guest", reason=f"hand-out stopped: {why}")
        except Exception:
            pass
        if self.done.wait(polite_s):
            return
        self.end_hard()

    def end_hard(self) -> None:
        proc = self.proc
        if proc is None or proc.poll() is not None:
            return
        try:
            if self.entry is not None:
                from halo_harness.children_stop import stop_entry
                stop_entry(self.entry, timeout=5.0)
            if proc.poll() is None:
                proc.kill()
        except Exception:
            pass

    def _end(self) -> None:
        proc = self.proc
        if proc is not None:
            try:
                proc.wait(30)
            except Exception:
                self.end_hard()
        for t in getattr(self, "_readers", ()):
            t.join(5.0)
        raw = b"".join(getattr(self, "_out", []) or [])
        for line in reversed(raw.decode("utf-8", "replace").splitlines()):
            if line.startswith("{"):
                try:
                    got = json.loads(line)
                except ValueError:
                    continue
                if isinstance(got, dict) and got.get("type") == "result":
                    self.result = got
                    break
        self._drop_client()
        self.t1 = time.monotonic()
        r = self.result or {}
        if self._stop_asked.is_set() or r.get("stop_reason") == "max_turns":
            self.state = "stopped"
            self.why = self.why or f"the turn cap ({self.task['turns']} turns)"
        elif self.state != "failed":
            self.state = "done" if r and not r.get("is_error") else "failed"
        if self.proc is not None:
            from halo_harness import children
            children.unregister(self.proc.pid)
        self.done.set()
        self.owner.ended(self)


class HandOuts:
    """The jobs of one bridge. `tree`/`feed` None: no Studio rows (sessions open no socket here)."""

    def __init__(self, project, *, sid: str, directory: Path, claude_pid: int, tree=None, state_dir=None,
                 notify: Optional[Callable] = None) -> None:
        self.project, self.sid, self.dir, self.claude_pid = Path(project), sid, Path(directory), int(claude_pid)
        self.tree = tree
        self.notify = notify  # (job) -> None: a progress notification for a waiting call, at most one a second
        if state_dir is None:
            from halo_harness.providers.config import default_state_dir
            state_dir = default_state_dir()
        self.state_dir = Path(state_dir)
        self.jobs: "dict[str, Job]" = {}
        self.lines: deque = deque(maxlen=64)  # the hook lines of hand-out calls: {agent, input, ts}
        self._lock = threading.RLock()

    def running(self) -> list:
        with self._lock:
            return [j for j in self.jobs.values() if not j.done.is_set()]

    def path(self, job: Job) -> Path:
        return self.dir / f"{self.claude_pid}.job.{job.id}.json"

    def save(self, job: Job) -> None:
        _private(self.path(job), {"job": job.brief(), **({"result": job.result} if job.result else {})})

    def start(self, args: dict) -> "tuple[Optional[Job], str]":
        task, why = task_of(args if isinstance(args, dict) else {})
        if task is None:
            return None, why
        model, ref, why = choose(args.get("model"), self.state_dir)
        if not model:
            return None, why
        key = host_key(ref)
        with self._lock:
            live = self.running()
            if len(live) >= JOBS_CAP:
                return None, f"{JOBS_CAP} hand-outs run now: wait for one to end (halo_job), or stop one (halo_job_stop)"
            if any(j.key == key for j in live):
                return None, f"a hand-out runs on {key.split(':', 1)[1]} now: one job per host at a time"
            job = Job(self, task, model, key, args)
            self.jobs[job.id] = job  # held before the host is read: a third call meanwhile is refused
        why = on_host(ref)
        if why:
            with self._lock:
                self.jobs.pop(job.id, None)
            return None, why
        self._row(job)
        threading.Thread(target=job.run, daemon=True, name=f"halo-handout-{job.id[:8]}").start()
        return job, ""

    def get(self, job_id) -> Optional[Job]:
        with self._lock:
            return self.jobs.get(str(job_id or ""))

    def by_row(self, aid: str) -> Optional[Job]:
        with self._lock:
            return next((j for j in self.jobs.values() if j.aid == aid), None)

    # ---- the rows --------------------------------------------------------------------------------------------------
    def _row(self, job: Job) -> None:
        if self.tree is None:
            return
        from halo_harness.agent.agent_hooks import spawn_of
        from halo_harness.guest import WORKER_KIND
        self.tree.add(job.aid, parent="main", name=f"Halo: {job.model}", role="Halo", kind=WORKER_KIND,
                      model=job.model, task=job.task["goal"].splitlines()[0][:200],
                      spawn=spawn_of(self.tree, "main", job.task["goal"]), state="running", current="starting",
                      since=time.time())
        self.tree.helper_started(job.aid)
        self.pair()

    def tick(self, job: Job) -> None:
        if self.tree is not None:
            live = job.live
            self.tree.update(job.aid, current=str(live.get("current") or "thinking")[:200], turns=live.get("turns"),
                             tokens_in=live.get("tokens_in"), tokens_out=live.get("tokens_out"))
        self.pair()
        job.step += 1
        if self.notify is not None:
            self.notify(job)

    def ended(self, job: Job) -> None:
        self.save(job)
        if self.tree is not None:
            r = job.result or {}
            usage = r.get("usage") if isinstance(r.get("usage"), dict) else {}
            self.tree.update(job.aid, state=job.state, current="", ended=time.time(), last_text=job.text()[-2048:],
                             turns=r.get("num_turns", job.live.get("turns")),
                             tokens_in=usage.get("input_tokens", job.live.get("tokens_in")),
                             tokens_out=usage.get("output_tokens", job.live.get("tokens_out")),
                             **({"cost_usd": r["total_cost_usd"]} if isinstance(r.get("total_cost_usd"), (int, float)) else {}))

    def saw_call(self, agent: str, given: dict, ts: int) -> None:
        """The feed read a hook line of a hand-out call (who called it, its cut input, its stamp)."""
        with self._lock:
            self.lines.append({"agent": agent or "main", "input": given, "ts": int(ts or 0)})
        self.pair()

    def pair(self) -> None:
        """A worker's row goes under the calling sub-agent only when sure: exactly one hook line of the same cut
        arguments within PAIR_NS of the call, that line matching no other call; else under main."""
        if self.tree is None:
            return
        with self._lock:
            jobs = [j for j in self.jobs.values() if time.time_ns() - j.t_ns <= 4 * PAIR_NS]
            near = lambda j, ln: ln["input"] == j.cut and abs(ln["ts"] - j.t_ns) <= PAIR_NS  # noqa: E731
            for j in jobs:
                mine = [ln for ln in self.lines if near(j, ln)]
                twins = [k for k in self.jobs.values() if k is not j and k.cut == j.cut and abs(k.t_ns - j.t_ns) <= PAIR_NS]
                sure = len(mine) == 1 and not twins
                parent = mine[0]["agent"] if sure else "main"
                if parent != "main" and self.tree.row(parent) is None:
                    parent = "main"
                if parent != j.parent:
                    from halo_harness.agent.agent_hooks import spawn_of
                    j.parent = parent
                    self.tree.update(j.aid, parent=parent, spawn=spawn_of(self.tree, parent, j.task["goal"]))

    # ---- the end -----------------------------------------------------------------------------------------------------
    def close(self, polite_s: float = 1.0, wait_s: float = 8.0) -> None:
        """The bridge ends (Claude Code gives a stdio server well under a second before its signals): every job is
        stopped (politely, then by closing's stop) and its file removed."""
        live = self.running()
        for job in live:
            job.stop("the bridge is ending", polite_s=polite_s)
        end = time.monotonic() + wait_s
        for job in live:
            job.done.wait(max(0.0, end - time.monotonic()))
            if not job.done.is_set():
                job.end_hard()
        with self._lock:
            jobs = list(self.jobs.values())
        for job in jobs:
            try:
                os.unlink(self.path(job))
            except OSError:
                pass
