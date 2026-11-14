"""halo_harness.packs.policy -- the armed policy hooks and the verdict runner (Halo 3.3.10.0 R1; R2: a session asks
them before every tool call, agent/policy_gate.py; docs/EXTENSION_API.md "Policy hooks").

    armed(state_dir=None, cwd=None) -> [Policy]   the policies that answer now: the pack runs here with the hooks
                                                  grant, mode.json arms the policy, its when.modes takes the mode
    request(policy, tool, tool_input, cwd=, session=, agent=, mode=, permission_mode=) -> the request line's dict
    ask(policy, request, budget_ms=None, keep=True, log=True) -> Verdict (budget_ms: packs.policy.budget_ms, 2000)
    ask_after(policy, request, result, ms) -> (Verdict, result | None)   the post-call verdict (packs/policy_after.py)
    winner(verdicts) -> the one that counts: deny over ask over allow (None for none)

`ask` filters by `when.tools` first (a call it does not name never reaches the process, nor the log), takes out the
`redact` values, asks the policy's one process and reads `{id, verdict, reason, rule, scope?}`; a late, malformed or
missing answer is the policy's `on_error`. Every verdict is a `policy` row in the pack's events log (the gate writes
its own, the winner named), a process start / stop a `policy_proc` row; the tool input is never written there."""

from __future__ import annotations

import atexit
import logging
import os
import threading
from dataclasses import dataclass, field

from halo_harness.packs.policy_redact import redact  # noqa: F401  (re-exported: R1's name)

log = logging.getLogger(__name__)
VERDICTS = ("allow", "deny", "ask")
SCOPES = ("session", "machine")
EVENT = "policy"
PROC_EVENT = "policy_proc"
BUDGET_KEY = "packs.policy.budget_ms"
BUDGET_MS = 2000
_procs, _last = {}, []  # the running processes; 3.3.10.0 R3: the last list armed() read in this process
_lock = threading.Lock()


@dataclass(frozen=True)
class Verdict:
    """A policy's answer in `permissions.Decision`'s words: `action` allow | deny | ask (after the call: pass |
    redact | drop), `reason` (the pack's own line), `source` ("pack:<id>/<policy>"); plus the rule that fired, the
    scope, the time and, when the policy did not answer, `error` (and `action` is then its on_error)."""
    action: str
    reason: str
    source: str = ""
    rule: str = ""
    scope: str = "session"
    pack: str = ""
    policy: str = ""
    ms: int = 0
    error: str = ""
    asked: bool = True

    def line(self) -> str:
        return f"{self.action} -- {self.policy}: {self.reason} ({self.ms} ms)"


@dataclass(frozen=True)
class Policy:
    pack: str
    id: str
    root: str
    argv: tuple
    tools: tuple = ()
    modes: tuple = ()
    impact: str = "medium"
    on_error: str = "allow"
    redact: tuple = ()
    after: bool = False
    config: dict = field(default_factory=dict, hash=False, compare=False)

    @property
    def key(self) -> tuple:
        return (self.pack, self.id, self.root)


def declared(pack) -> "list[Policy]":
    """Every policy the pack's manifest declares, as it would run from the pack's folder."""
    from halo_harness.packs import manifest_policy as MP
    from halo_harness.packs.settings import values
    out = []
    for e in MP.policies_of(pack.manifest):
        tools, modes = MP.when_of(e)
        out.append(Policy(pack=pack.id, id=str(e.get("id")), root=str(pack.root), argv=tuple(MP.run_argv(e, pack.root)),
                          tools=tuple(tools), modes=tuple(modes), impact=str(e.get("impact") or "medium"),
                          on_error=e.get("on_error") if e.get("on_error") in ("allow", "deny") else "allow",
                          redact=tuple(r for r in e.get("redact") or [] if isinstance(r, str)),
                          after=e.get("after") is True, config=values(pack)))
    return out


def armed(state_dir=None, *, cwd=None) -> "list[Policy]":
    """The policies that answer now, in the packs' run order; mode.json is read at each call, so a mode switched in
    another process counts at the next verdict. 3.3.10.0 R3: the list is kept (`_last`); a read that raises leaves it."""
    from halo_harness.packs import mode_state as M
    from halo_harness.packs import state as S
    from halo_harness.packs.registry import snapshot
    snap = snapshot(cwd=cwd, state_dir=state_dir)
    out = []
    for pack in snap.active:
        pols = declared(pack)
        if not pols or "hooks" not in S.granted(pack.id, snap.state):
            continue
        rec = M.read(pack.id, state_dir)
        out += [p for p in pols if p.id in rec["armed"] and (not p.modes or rec["mode"] in p.modes)]
    live = {p.key for p in out}
    for key in [k for k in list(_procs) if k not in live]:  # disarmed elsewhere (another terminal): its process stops
        stop(key[0], key[1])
    _last[:] = out
    return out


def matches(policy: Policy, tool: str) -> bool:
    return not policy.tools or "*" in policy.tools or tool in policy.tools


def request(policy: Policy, tool: str, tool_input, *, cwd, session: str = "", agent: str = "", mode=None,
            permission_mode: str = "default") -> dict:
    return {"tool": tool, "input": tool_input if isinstance(tool_input, dict) else {}, "cwd": str(cwd),
            "session": session, "agent": agent, "mode": mode, "permission_mode": permission_mode,
            "config": dict(policy.config), "policy": policy.id}


def default_budget_ms() -> int:
    """`packs.policy.budget_ms` (2000 when unset or not a whole number from 1 to 60000)."""
    from halo_harness.theme import get_config_value
    try:
        v = get_config_value(BUDGET_KEY, default=None)
    except Exception:
        v = None
    return v if isinstance(v, int) and not isinstance(v, bool) and 0 < v <= 60000 else BUDGET_MS


def _env(policy: Policy) -> dict:
    from halo_harness.packs.interpreter import pack_env
    from halo_harness.providers.config import tool_child_env
    env = tool_child_env(dict(os.environ))  # the provider keys Halo holds stay out, as for every hook
    env.update({"CLAUDE_PLUGIN_ROOT": policy.root, "HALO_PACK_ID": policy.pack, "HALO_POLICY_ID": policy.id})
    return pack_env(policy.root, env)


def _proc_row(policy: Policy, state_dir=None):
    def tell(change: str, pid) -> None:
        from halo_harness.packs.events_log import append
        append(policy.pack, PROC_EVENT, {"policy": policy.id, "change": change, "pid": pid, "by": os.getpid()},
               state_dir=state_dir)
    return tell


def process(policy: Policy, *, new: bool = False):
    from halo_harness.packs.policy_proc import PolicyProcess
    with _lock:
        p = None if new else _procs.get(policy.key)
        if p is None:
            p = PolicyProcess(policy.argv, cwd=policy.root, env=_env(policy), label=f"{policy.pack}/{policy.id}",
                              on_change=None if new else _proc_row(policy))
            if not new:
                _procs[policy.key] = p
        return p


def start(policy: Policy) -> str:
    """Start the policy's process now (R2: when it is armed and at session start, before the first tool call)."""
    return process(policy).start()


def _verdict(policy: Policy, answer, why: str, ms: int) -> Verdict:
    src = f"pack:{policy.pack}/{policy.id}"
    if answer is not None and not why:
        v, scope = answer.get("verdict"), answer.get("scope") or "session"
        if v not in VERDICTS:
            why = f"a malformed answer: verdict {v!r} is not allow, deny or ask"
        elif scope not in SCOPES:
            why = f"a malformed answer: scope {scope!r} is not session or machine"
        else:
            reason, rule = answer.get("reason"), answer.get("rule")
            return Verdict(v, reason if isinstance(reason, str) else "", src, rule if isinstance(rule, str) else "",
                           scope, policy.pack, policy.id, ms)
    return Verdict(policy.on_error, f"on_error {policy.on_error} ({why})", src, "on_error", "session", policy.pack,
                   policy.id, ms, error=why)


def log_row(policy: Policy, v: Verdict, req: dict, *, state_dir=None, **extra) -> dict:
    """The verdict's `policy` row in the pack's events log (never the tool input)."""
    from halo_harness.packs.events_log import append
    row = {"policy": policy.id, "tool": str(req.get("tool") or ""), "verdict": v.action, "reason": v.reason,
           "rule": v.rule, "scope": v.scope, "ms": v.ms, "session": req.get("session") or "", "agent": req.get("agent") or ""}
    return append(policy.pack, EVENT, {**row, **({"error": v.error} if v.error else {}), **extra}, state_dir=state_dir)


def ask(policy: Policy, req: dict, *, budget_ms: "int | None" = None, keep: bool = True, log: bool = True,
        state_dir=None) -> Verdict:
    """One verdict. `keep=False` (the dry run) uses a process of its own and stops it after the answer; `log=False`
    leaves the row to the caller (the session's gate names the winner on it)."""
    tool = str(req.get("tool") or "")
    if not matches(policy, tool):
        return Verdict("allow", f"not asked: {tool} is not in when.tools", f"pack:{policy.pack}/{policy.id}", "",
                       "session", policy.pack, policy.id, 0, asked=False)
    req = {**req, "input": redact(req.get("input"), policy.redact)}
    budget = budget_ms if budget_ms is not None else default_budget_ms()
    proc = process(policy, new=not keep)
    try:
        answer, why, ms = proc.ask(req, budget / 1000.0)
    finally:
        if not keep:
            proc.stop()
    v = _verdict(policy, answer, why, ms)
    if v.error:
        logging.getLogger(__name__).warning("policy %s/%s: %s", policy.pack, policy.id, v.reason)
    if log:
        log_row(policy, v, req, state_dir=state_dir)
    return v


def ask_after(policy: Policy, req: dict, result, ms, **kw):
    from halo_harness.packs.policy_after import ask_after as after
    return after(policy, req, result, ms, **kw)


def winner(verdicts) -> "Verdict | None":
    """deny wins over ask over allow (after the call: drop over redact over pass); among equals the first."""
    rank = {"deny": 0, "ask": 1, "allow": 2, "drop": 0, "redact": 1, "pass": 2}
    vs = [v for v in verdicts or [] if isinstance(v, Verdict)]
    return min(vs, key=lambda v: rank.get(v.action, 3)) if vs else None


def stop(pack_id: str, policy_id=None) -> int:
    """Stop the processes of a pack's policies (one, or every one); how many were running."""
    with _lock:
        keys = [k for k in _procs if k[0] == pack_id and (policy_id is None or k[1] == policy_id)]
        procs = [_procs.pop(k) for k in keys]
    for p in procs:
        p.stop()
    return len(procs)


def reconcile(pack_id: str, armed_ids) -> None:
    """mode.json changed: a process of a policy no longer armed stops (mode_state calls this)."""
    with _lock:
        gone = [k[1] for k in _procs if k[0] == pack_id and k[1] not in set(armed_ids or [])]
    for pid in gone:
        stop(pack_id, pid)


@atexit.register
def stop_all() -> None:
    with _lock:
        procs = list(_procs.values())
        _procs.clear()
    for p in procs:
        p.stop()
