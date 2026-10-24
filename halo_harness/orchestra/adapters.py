"""halo_harness.orchestra.adapters -- the real model calls behind run.py.

* `model_call(model, role, cwd)` -> `call(prompt)`: the lead's one-shot
  call. A brand-new bare halo session (headless.build_session, no tools, one
  turn), the same in-process path `halo init`'s live check uses.
* `spawn_worker(model, role, ...)` -> `spawn(lane)`: one worker (3.0.9.0 R2:
  `--agent <bio>` / `--model <ref>` from the lane's job when a reviewed plan set them). A fresh
  `halo -p` child process in the lane's worktree, with HALO_ORCHESTRA_RUN
  and HALO_ORCHESTRA_LANE in its environment, so the claim guard and the
  Orchestra tools are live in it and its holder is its own session. (The
  in-process sub-agent path, agent/subagent.py `run_agent_call`, takes the
  parent's cwd and the process-wide environment, so it cannot give each
  lane its own folder and lane number; a child process can.) 3.1.8.0 R5: a
  lane's opt-ins (isolation, secrets, the tool list) apply right before it
  runs (isolation/lane.py `prepare`); nothing declared, nothing changes.
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


def one_shot(prompt: str, *, model: Optional[str], cwd, effort: Optional[str] = None) -> dict:
    """One turn of a brand-new bare session with no tools:
    `{text, cost_usd, session_id, messages_before, ok, error}`."""
    from halo_harness import headless
    from halo_harness.output import PrintModeSink
    build = headless.build_session(cwd=Path(cwd), model_ref_raw=model, bare=True, print_mode=True,
                                   max_turns=1, tools="", effort=effort)
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


def model_call(model: Optional[str], role: str = "main", cwd=None, effort: Optional[str] = None) -> Callable:
    """3.1.6.0 R2: `effort` (a probe's lead) rides along only when set."""
    ref, extra = role_model(role, model), ({"effort": effort} if effort else {})

    def call(prompt: str) -> dict:
        return one_shot(prompt, model=ref, cwd=cwd or Path.cwd(), **extra)
    return call


def fresh_judge(model: Optional[str], role: str = "main", cwd=None, effort: Optional[str] = None) -> Callable:
    from halo_harness.orchestra.hunks import judge_prompt
    ref, extra = role_model(role, model), ({"effort": effort} if effort else {})

    def judge(hunks: list, goal, file: str) -> dict:
        return one_shot(judge_prompt(hunks, goal, file), model=ref, cwd=cwd or Path.cwd(), **extra)
    return judge


def worker_argv(prompt: str, model: Optional[str], agent: Optional[str] = None) -> list:
    argv = [sys.executable, "-m", "halo_harness", "-p", prompt, "--output-format", "json",
            "--permission-mode", "auto"]
    return argv + (["--agent", agent] if agent else []) + (["--model", model] if model else [])


def spawn_worker(model: Optional[str], role: str = "subagent", *, run_dir, runner: Callable = subprocess.run,
                 timeout_s: int = WORKER_TIMEOUT_S, team: Optional[str] = None,
                 cwd_overlay: Optional[Callable] = None) -> Callable:
    """`spawn(lane)`: a fresh `halo -p` in the lane's worktree. 3.1.6.0 R2 (the coach's probe runs,
    orchestra/probe_overlay.py): `team` adds `--team <lineup>`; `cwd_overlay(lane)` writes an overlay into
    the worktree before the worker starts and answers extra worker flags. Both None: the argv as before."""
    from halo_harness.isolation import Stop
    from halo_harness.isolation.lane import prepare
    from halo_harness.isolation.secrets import scrub
    from halo_harness.orchestra.workers import child_env
    ref = role_model(role, model)

    def spawn(lane) -> dict:
        limit = int(getattr(lane, "timeout_s", 0) or timeout_s)  # 3.2.0.0 R5: a workflow stage's own timeout_s
        env = child_env(run_dir, lane.n, os.environ)
        env.setdefault("PYTHONIOENCODING", "utf-8")
        env.update(fleet_parent_env())
        values: tuple = ()
        try:
            job = lane.job  # 3.0.9.0 R2: a reviewed plan may give the lane its own bio and model
            argv = worker_argv(lane.prompt, getattr(job, "model", "") or ref, getattr(job, "bio", "") or None)
            argv += (["--team", team] if team else []) + (list(cwd_overlay(lane) or []) if cwd_overlay else [])
            argv, env, values = prepare(lane, argv, env, run_dir=run_dir, team=team)  # 3.1.8.0 R5 (docs/ISOLATION.md)
            proc = runner(argv, cwd=str(lane.worktree), env=env, capture_output=True,
                          text=True, encoding="utf-8", errors="replace", timeout=limit,
                          stdin=subprocess.DEVNULL)
        except Stop as e:  # 3.1.8.0 R5: the lane cannot run as declared -- its one line, like a dead harness
            return {"ok": False, "error": str(e)}
        except subprocess.TimeoutExpired:
            return {"ok": False, "error": f"the worker ran past {limit}s"}
        except OSError as e:
            return {"ok": False, "error": f"could not start the worker: {e}"}
        obj = _last_json(proc.stdout)
        if obj is None:
            tail = (proc.stderr or proc.stdout or "").strip().splitlines()[-3:]
            return {"ok": False, "error": scrub(f"the worker exited {proc.returncode} without a result: {' | '.join(tail)}",
                                                values)}
        out = {"ok": not obj.get("is_error"), "text": scrub(str(obj.get("result") or ""), values),
               "cost_usd": float(obj.get("total_cost_usd") or 0.0), "session_id": obj.get("session_id"),
               "error": "" if not obj.get("is_error") else scrub(str(obj.get("result") or "worker error")[:500], values)}
        extra = (("model", str(obj.get("model") or "")), ("denied", list(obj.get("permission_denials") or [])))
        return dict(out, **{k: v for k, v in extra if v})  # 3.0.9.0 R3: the coach's evidence, when the result has it
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
