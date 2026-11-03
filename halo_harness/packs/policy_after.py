"""halo_harness.packs.policy_after -- the post-call verdict (Halo 3.3.10.0 R2; docs/EXTENSION_API.md "Policy hooks").

A policy that declares `after: true` is asked once more after the tool ran, on the same long-lived process, within
the same budget, with the same `on_error` (allow reads as pass, deny as drop):

    request  {... every pre-call field ..., "after": true, "result": "<the tool's result as text>", "ms": 41}
    answer   {"id": ..., "verdict": "pass" | "redact" | "drop", "reason": "...", "rule": "...", "result": "..."}

`pass` keeps the result; `redact` replaces it with the answer's `result` (a string: the model and the transcript see
that one, the audit row keeps the sha256 of the original); `drop` replaces it with the reason line. `redact: [env
names]` takes the named secrets out of the input and the result before the request leaves Halo.

    ask_after(policy, req, result, ms, budget_ms=None, log=True, state_dir=None) -> (Verdict, kept | None)
                                                 kept: the redacted result (redact), else None
    digest(text) -> "sha256:<hex>"
"""

from __future__ import annotations

import hashlib
import logging

AFTER = ("pass", "redact", "drop")
ON_ERROR = {"allow": "pass", "deny": "drop"}
log = logging.getLogger(__name__)


def digest(text) -> str:
    raw = text if isinstance(text, str) else str(text)
    return "sha256:" + hashlib.sha256(raw.encode("utf-8", "replace")).hexdigest()


def as_text(content) -> str:
    """A tool result as the text a policy reads: a string as it is, a block list's text blocks joined."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for b in content:
            if isinstance(b, dict) and b.get("type") == "text":
                parts.append(str(b.get("text") or ""))
            elif isinstance(b, dict):
                parts.append(f"[{b.get('type', 'content')} block]")
            else:
                parts.append(str(b))
        return "\n".join(parts)
    return str(content)


def _verdict(policy, answer, why: str, ms: int):
    from halo_harness.packs.policy import Verdict
    src = f"pack:{policy.pack}/{policy.id}"
    if answer is not None and not why:
        v = answer.get("verdict")
        kept = answer.get("result")
        if v not in AFTER:
            why = f"a malformed answer: verdict {v!r} is not pass, redact or drop"
        elif v == "redact" and not isinstance(kept, str):
            why = "a malformed answer: redact needs the result to keep, as a string"
        else:
            reason, rule = answer.get("reason"), answer.get("rule")
            return Verdict(v, reason if isinstance(reason, str) else "", src, rule if isinstance(rule, str) else "",
                           "session", policy.pack, policy.id, ms), (kept if v == "redact" else None)
    action = ON_ERROR.get(policy.on_error, "pass")
    return Verdict(action, f"on_error {policy.on_error} ({why})", src, "on_error", "session", policy.pack, policy.id, ms,
                   error=why), None


def ask_after(policy, req: dict, result, ms, *, budget_ms=None, log: bool = True, state_dir=None):
    """The post-call verdict for one call that ran: `(Verdict, kept)`. A policy without `after`, or a tool its
    `when.tools` does not name, is not asked (`asked=False`, `pass`)."""
    from halo_harness.packs import policy as P
    from halo_harness.packs.policy_redact import redact
    tool = str(req.get("tool") or "")
    if not policy.after or not P.matches(policy, tool):
        return P.Verdict("pass", "not asked", f"pack:{policy.pack}/{policy.id}", "", "session", policy.pack, policy.id,
                         0, asked=False), None
    text = as_text(result)
    req = {**req, "input": redact(req.get("input"), policy.redact), "after": True,
           "result": redact(text, policy.redact), "ms": int(ms or 0)}
    budget = budget_ms if budget_ms is not None else P.default_budget_ms()
    answer, why, took = P.process(policy).ask(req, budget / 1000.0)
    v, kept = _verdict(policy, answer, why, took)
    if v.error:
        logging.getLogger(__name__).warning("policy %s/%s (after): %s", policy.pack, policy.id, v.reason)
    if log:
        extra = {"sha256": digest(text)} if v.action != "pass" else {}
        P.log_row(policy, v, req, state_dir=state_dir, at="after", **extra)
    return v, kept
