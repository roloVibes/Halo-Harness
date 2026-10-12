"""halo_harness.paperclip.adapter -- Halo as a Paperclip agent (Halo 2.2.0
round C2). Paperclip's `process` adapter spawns `halo paperclip-run` on every
heartbeat with the `PAPERCLIP_*` environment (observed live 2026-10-11:
API URL, API key, agent id, company id, run id, scratch dirs). One run:

1. read the agent (`/agents/me`): its Paperclip name/title and, in
   `metadata`, `halo_agent` (a bio name) and `halo_lineup` (a lineup name)
   that `halo paperclip sync` wrote;
2. find the issue this run is for: the issue Paperclip already checked out
   for this run, else the agent's oldest open assigned issue (checked out
   here); none -> an idle heartbeat, exit 0, nothing posted;
3. build the prompt from the heartbeat context (identifier, title,
   description, goal and project names, the comment that woke the agent)
   and run `halo -p` in the current directory on the bio's model;
4. post the reply as an issue comment; on success mark the issue done, on
   a failed turn leave it in progress with the error in the comment and
   exit 1 so Paperclip records the run as failed.

Nothing is written outside the run's scratch dir and Halo's own state.
"""

from __future__ import annotations

import os
import subprocess
import sys
from typing import Optional

from halo_harness.paperclip.client import Paperclip, PaperclipError

OPEN_STATUSES = ("todo", "in_progress")
MAX_PROMPT_CHARS = 60_000


def pick_issue(client: Paperclip, agent_id: str, company_id: str, run_id: str) -> Optional[dict]:
    issues = [i for i in client.issues(company_id) if i.get("assigneeAgentId") == agent_id and i.get("status") in OPEN_STATUSES]
    for i in issues:
        if run_id and run_id in (i.get("executionRunId"), i.get("checkoutRunId")):
            return i
    issues.sort(key=lambda i: (i.get("status") != "in_progress", i.get("priority") or 99, i.get("createdAt") or ""))
    return issues[0] if issues else None


def build_prompt(ctx: dict, issue: dict, agent: dict) -> str:
    issue = (ctx or {}).get("issue") or issue
    lines = [f"You are {agent.get('name') or 'an agent'}" + (f", {agent.get('title')}" if agent.get("title") else "") + " in a Paperclip company.",
             "Work the issue below in the current directory and reply with what you did, what is left and anything that blocks you. "
             "Your reply is posted to the issue as a comment.", "",
             f"Issue {issue.get('identifier') or issue.get('id')}: {issue.get('title') or ''}"]
    if issue.get("description"):
        lines += ["", str(issue["description"])]
    goal, project = (ctx or {}).get("goal"), (ctx or {}).get("project")
    if goal and goal.get("title"):
        lines += ["", f"Goal: {goal.get('title')}" + (f" -- {goal.get('description')}" if goal.get("description") else "")]
    if project and project.get("name"):
        lines += [f"Project: {project.get('name')}"]
    for anc in (ctx or {}).get("ancestors") or []:
        if isinstance(anc, dict) and anc.get("title"):
            lines += [f"Parent issue: {anc.get('identifier') or ''} {anc.get('title')}"]
    wake = (ctx or {}).get("wakeComment")
    if isinstance(wake, dict) and wake.get("body"):
        lines += ["", "The comment that woke you:", str(wake["body"])]
    text = "\n".join(lines)
    return text[:MAX_PROMPT_CHARS]


def model_for(agent: dict) -> str:
    """The bio named in the agent's metadata decides the model; a missing
    bio means the session default (no --model)."""
    meta = agent.get("metadata") if isinstance(agent.get("metadata"), dict) else {}
    name = str(meta.get("halo_agent") or "")
    if not name:
        return ""
    try:
        from halo_harness.agents_yaml import resolve_agent_bio
        bio = resolve_agent_bio(name) or {}
        models = bio.get("models") or {}
        return str(models.get("preference") or models.get("fallback") or "")
    except Exception:
        return ""


def run_halo(prompt: str, model: str, cwd: str, env: dict, timeout: int = 3600) -> tuple[int, str]:
    cmd = [sys.executable, "-m", "halo_harness", "-p", prompt, "--cwd", cwd]
    if model:
        cmd += ["--model", model]
    child_env = {k: v for k, v in env.items() if k != "PAPERCLIP_API_KEY"}  # the key stays with this process
    child_env["PYTHONIOENCODING"] = "utf-8"
    try:
        r = subprocess.run(cmd, capture_output=True, encoding="utf-8", errors="replace", timeout=timeout, cwd=cwd, env=child_env)
    except subprocess.TimeoutExpired:
        return 1, f"halo timed out after {timeout} s"
    out = (r.stdout or "").strip()
    if r.returncode != 0:
        out = (out + "\n\n" + (r.stderr or "").strip()[-2000:]).strip()
    return r.returncode, out or "(no output)"


def run_heartbeat(env: Optional[dict] = None, *, runner=run_halo, out=sys.stdout) -> int:
    env = dict(os.environ if env is None else env)
    from halo_harness.paperclip.mode import org_mode_enabled
    if not org_mode_enabled():
        # 3.0.2.0: the switch is the owner's: nothing runs that was not asked for.
        print("Org mode is off on this machine (halo paperclip on turns it on): heartbeat answered idle", file=out)
        return 0
    client = Paperclip.from_env(env)
    agent_id, company_id, run_id = env.get("PAPERCLIP_AGENT_ID", ""), env.get("PAPERCLIP_COMPANY_ID", ""), env.get("PAPERCLIP_RUN_ID", "")
    if not agent_id or not company_id:
        print("halo paperclip-run: not inside a Paperclip heartbeat (PAPERCLIP_AGENT_ID/COMPANY_ID missing)", file=out)
        return 2
    try:
        agent = client.me() or client.agent(agent_id)
        issue = pick_issue(client, agent_id, company_id, run_id)
        if issue is None:
            print("idle heartbeat: no open issue assigned", file=out)
            return 0
        if issue.get("status") == "todo":
            try:
                client.checkout(issue["id"], agent_id, ["todo"])
            except PaperclipError as e:
                print(f"checkout refused: {e.message}", file=out)
                return 0
        ctx = client.heartbeat_context(issue["id"])
        prompt = build_prompt(ctx if isinstance(ctx, dict) else {}, issue, agent)
        code, reply = runner(prompt, model_for(agent), os.getcwd(), env)
        body = reply if code == 0 else f"The turn failed (exit {code}).\n\n{reply}"
        client.comment(issue["id"], body)
        if code == 0:
            try:
                client.update_issue(issue["id"], {"status": "done"})
            except PaperclipError as e:
                print(f"could not mark {issue.get('identifier')} done: {e.message}", file=out)
        print(f"{issue.get('identifier') or issue['id']}: {'done' if code == 0 else 'failed'}", file=out)
        return 0 if code == 0 else 1
    except PaperclipError as e:
        print(f"halo paperclip-run: {e}", file=out)
        return 1
