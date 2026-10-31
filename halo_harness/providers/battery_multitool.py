"""halo_harness.providers.battery_multitool -- Halo 3.3.6.0 R4: the battery's
multi-tool probe (plans/local-model-fit-brief.md D4 item 17: tool-call accuracy,
verified). R2's "needs a probe" for tool-call accuracy resolves here.

Three tools (`find_user`, `get_orders`, `send_email`) and one task that needs
two of them in order: look Ada Lovelace up, then list her orders. Turn one
should call `find_user` with her name; Halo answers it with `{"id": "u-42"}`;
turn two should call `get_orders` with `user_id` "u-42". A model that calls
both at once in turn one is scored on what it sent (it could not know the id).

    first_body(model, num_ctx, keep_alive, cap=None) / second_body(model, first_reply, ...)
    calls_of(reply) -> [(name, args)]
    score(first_reply, second_reply) -> (accuracy 0-1, why, checks {first_tool, first_args, second_tool,
                                         second_args, wrong_tool})

The accuracy is the share of the four checks that held, less a quarter when it
called `send_email` (a tool the task never needs), never under 0.
"""

from __future__ import annotations

import json
from typing import Optional

USER_ID = "u-42"
NAME = "Ada Lovelace"
ASK = ("Look up the user named Ada Lovelace, then list that user's orders. Use the tools, one step at a time: "
       "call a tool, wait for its result, then call the next.")


def _tool(name: str, desc: str, props: dict, required: list) -> dict:
    return {"type": "function", "function": {"name": name, "description": desc, "parameters": {
        "type": "object", "properties": {k: {"type": "string", "description": v} for k, v in props.items()},
        "required": required}}}


TOOLS = [
    _tool("find_user", "Find a user by full name; returns the user's id", {"name": "the user's full name"}, ["name"]),
    _tool("get_orders", "List the orders of one user", {"user_id": "the id find_user returned"}, ["user_id"]),
    _tool("send_email", "Send an e-mail to an address", {"to": "the address", "body": "the text"}, ["to", "body"]),
]
CAP = 300


def first_body(model: str, *, num_ctx: int, keep_alive, cap: Optional[int] = None) -> dict:
    return {"model": model, "messages": [{"role": "user", "content": ASK}], "stream": False, "keep_alive": keep_alive,
            "tools": TOOLS, "options": {"num_ctx": num_ctx, "temperature": 0, "num_predict": cap or CAP}}


def _args(raw) -> dict:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        from halo_harness.providers.battery_probes import strip_fences
        try:
            got = json.loads(strip_fences(raw))
            return got if isinstance(got, dict) else {}
        except ValueError:
            return {}
    return {}


def calls_of(reply) -> list:
    from halo_harness.providers.battery_probes import parts
    out = []
    for c in parts(reply)[2]:
        fn = (c or {}).get("function") if isinstance(c, dict) else None
        if isinstance(fn, dict) and fn.get("name"):
            out.append((str(fn["name"]), _args(fn.get("arguments"))))
    return out


def second_body(model: str, first_reply, *, num_ctx: int, keep_alive, cap: Optional[int] = None) -> dict:
    """Turn two: the task, the model's own calls, and find_user's answer."""
    body = first_body(model, num_ctx=num_ctx, keep_alive=keep_alive, cap=cap)
    msg = (first_reply or {}).get("message") if isinstance(first_reply, dict) else None
    calls = (msg or {}).get("tool_calls") if isinstance(msg, dict) else None
    body["messages"] = body["messages"] + [
        {"role": "assistant", "content": str((msg or {}).get("content") or ""), "tool_calls": calls or []},
        {"role": "tool", "tool_name": "find_user", "content": json.dumps({"id": USER_ID, "name": NAME})}]
    return body


def score(first_reply, second_reply=None) -> "tuple[float, str, dict]":
    seq = calls_of(first_reply)
    if len(seq) < 2 and second_reply is not None:
        seq = seq + calls_of(second_reply)
    checks = {"first_tool": False, "first_args": False, "second_tool": False, "second_args": False,
              "wrong_tool": any(n == "send_email" for n, _a in seq)}
    useful = [c for c in seq if c[0] != "send_email"]
    if useful:
        name, args = useful[0]
        checks["first_tool"] = name == "find_user"
        checks["first_args"] = checks["first_tool"] and NAME.lower() in str(args.get("name") or "").lower()
    if len(useful) > 1:
        name, args = useful[1]
        checks["second_tool"] = name == "get_orders"
        checks["second_args"] = checks["second_tool"] and str(args.get("user_id") or "").strip() == USER_ID
    held = sum(1 for k in ("first_tool", "first_args", "second_tool", "second_args") if checks[k])
    acc = max(0.0, held / 4 - (0.25 if checks["wrong_tool"] else 0.0))
    if not seq:
        why = "no tool call at all"
    else:
        mark = lambda ok: "right" if ok else "wrong"  # noqa: E731
        bits = [f"find_user {mark(checks['first_tool'])}" + ("" if not checks["first_tool"] else
                f", its name {mark(checks['first_args'])}")]
        bits.append(f"get_orders {mark(checks['second_tool'])}" + ("" if not checks["second_tool"] else
                    f", its user_id {mark(checks['second_args'])}") if len(useful) > 1 else "no second call")
        if checks["wrong_tool"]:
            bits.append("it also called send_email")
        why = "; ".join(bits)
    return round(acc, 2), why, checks
