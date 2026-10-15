"""halo_harness.orchestra.adapters -- the real model calls behind run.py.

* `model_call(model, role, cwd)` -> `call(prompt)`: the lead's one-shot
  call. A brand-new bare halo session (headless.build_session, no tools, one
  turn), the same in-process path `halo init`'s live check uses.
* `spawn_worker(model, role, ...)` -> `spawn(lane)`: one worker. A fresh
  `halo -p` child process in the lane's worktree, with HALO_ORCHESTRA_RUN
  and HALO_ORCHESTRA_LANE in its environment, so the claim guard and the
  Orchestra tools are live in it and its holder is its own session. (The
  in-process sub-agent path, agent/subagent.py `run_agent_call`, takes the
  parent's cwd and the process-wide environment, so it cannot give each
  lane its own folder and lane number; a child process can.)
* `fresh_judge(model, role, cwd)` -> `judge(hunks, goal, file)`: a
  brand-new bare session per conflict whose whole input is the judge prompt
  (the goal and the hunks). It reports how many messages its log held
  before the prompt (0: no parent transcript) and its session id.

Model refs: `--model REF` when given, else the role's entry in the role
table (`halo roles`), else the configured default model.
"""

from __future__ import annotations

import io
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Callable, Optional

WORKER_TIMEOUT_S = 3600


def role_model(role: str, model: Optional[str] = None) -> Optional[str]:
    if model:
        return model
    try:
        from halo_harness.roles import configured_role_table, role_value_parts
        ref, _effort = role_value_parts(configured_role_table().get(role))
        return ref or None
    except Exception:
        return None


def one_shot(prompt: str, *, model: Optional[str], cwd) -> dict:
    """One turn of a brand-new bare session with no tools:
    `{text, cost_usd, session_id, messages_before, ok, error}`."""
    from halo_harness import headless
    from halo_harness.output import PrintModeSink
    build = headless.build_session(cwd=Path(cwd), model_ref_raw=model, bare=True, print_mode=True,
                                   max_turns=1, tools="")
    session = build.session
    try:
        messages_before = len([n for n in session.log.nodes() if n.get("type") in ("user", "assistant")])
    except Exception:
        messages_before = 0
    stream = io.StringIO()
    sink = PrintModeSink(output_format="json", session_id=build.session_log.session_id, model=build.model_ref.raw,
                         stream=stream, permission_denials=session.permission_denials)
    try:
        sink.consume(session.turn(prompt))
    finally:
        for close in (lambda: session._fire_session_end("other"), session.job_registry.kill_all,
                      getattr(build.mcp_manager, "close_all", lambda: None)):
            try:
                close()
            except Exception:
                pass
    try:
        obj = json.loads(stream.getvalue())
    except ValueError:
        obj = {}
    return {"text": str(obj.get("result") or ""), "cost_usd": float(obj.get("total_cost_usd") or 0.0),
            "session_id": obj.get("session_id") or build.session_log.session_id,
            "messages_before": messages_before, "ok": not obj.get("is_error", True),
            "error": "" if obj else "no result from the model"}


def model_call(model: Optional[str], role: str = "main", cwd=None) -> Callable:
    ref = role_model(role, model)

    def call(prompt: str) -> dict:
        return one_shot(prompt, model=ref, cwd=cwd or Path.cwd())
    return call


def fresh_judge(model: Optional[str], role: str = "main", cwd=None) -> Callable:
    from halo_harness.orchestra.hunks import judge_prompt
    ref = role_model(role, model)

    def judge(hunks: list, goal, file: str) -> dict:
        return one_shot(judge_prompt(hunks, goal, file), model=ref, cwd=cwd or Path.cwd())
    return judge


def worker_argv(prompt: str, model: Optional[str]) -> list:
    argv = [sys.executable, "-m", "halo_harness", "-p", prompt, "--output-format", "json",
            "--permission-mode", "auto"]
    return argv + (["--model", model] if model else [])


def spawn_worker(model: Optional[str], role: str = "subagent", *, run_dir,
                 runner: Callable = subprocess.run, timeout_s: int = WORKER_TIMEOUT_S) -> Callable:
    """`spawn(lane)`: a fresh `halo -p` in the lane's worktree."""
    from halo_harness.orchestra.workers import child_env
    ref = role_model(role, model)

    def spawn(lane) -> dict:
        env = child_env(run_dir, lane.n, os.environ)
        env.setdefault("PYTHONIOENCODING", "utf-8")
        env.update(fleet_parent_env())
        try:
            proc = runner(worker_argv(lane.prompt, ref), cwd=str(lane.worktree), env=env, capture_output=True,
                          text=True, encoding="utf-8", errors="replace", timeout=timeout_s,
                          stdin=subprocess.DEVNULL)
        except subprocess.TimeoutExpired:
            return {"ok": False, "error": f"the worker ran past {timeout_s}s"}
        except OSError as e:
            return {"ok": False, "error": f"could not start the worker: {e}"}
        obj = _last_json(proc.stdout)
        if obj is None:
            tail = (proc.stderr or proc.stdout or "").strip().splitlines()[-3:]
            return {"ok": False, "error": f"the worker exited {proc.returncode} without a result: {' | '.join(tail)}"}
        return {"ok": not obj.get("is_error"), "text": str(obj.get("result") or ""),
                "cost_usd": float(obj.get("total_cost_usd") or 0.0), "session_id": obj.get("session_id"),
                "error": "" if not obj.get("is_error") else str(obj.get("result") or "worker error")[:500]}
    return spawn


def fleet_parent_env() -> dict:
    """3.0.5.0 (Fleet): a worker's registry entry names the session that started
    the run (`parent`), when this process has one with a control socket."""
    try:
        from halo_harness.remote import fleet_identity, runtime
        act = runtime.active()
        return fleet_identity.parent_env(act.session_id if act is not None else None)
    except Exception:
        return {}


def _last_json(text: str) -> Optional[dict]:
    for line in reversed(str(text or "").strip().splitlines()):
        line = line.strip()
        if line.startswith("{"):
            try:
                obj = json.loads(line)
            except ValueError:
                continue
            if isinstance(obj, dict) and obj.get("type") == "result":
                return obj
    try:
        obj = json.loads(text)
        return obj if isinstance(obj, dict) else None
    except ValueError:
        return None


def real_adapters(run_dir, goal, model: Optional[str] = None) -> dict:
    """The keyword arguments `run()` takes, wired to real sessions."""
    run_dir = Path(run_dir)
    return {"model_calls": model_call(model, goal.lead, cwd=run_dir),
            "spawn": spawn_worker(model, goal.worker, run_dir=run_dir),
            "judge": fresh_judge(model, goal.lead, cwd=run_dir)}
