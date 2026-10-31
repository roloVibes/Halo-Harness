"""halo_harness.providers.battery_probes -- Halo 3.3.6.0 R1: the battery's
probes (plans/local-model-fit-brief.md Part E1) and how each answer is read.

Every probe is one non-streamed `/api/chat` turn at temperature 0 with
`num_predict` capped (a thinking model cannot run away). A probe whose
`content` came back empty while `thinking` holds text is asked once more at
`THINK_CAP` (a thinking model spends a small budget on thought: the empty
reply is a budget, not an answer -- Part E's reasoning split); both answers
are kept in the evidence.

    warmup       "Reply with the word ready."         never scored, never timed (Part G4)
    tools        one function schema, "use the tool"  did a `tool_calls` entry come back?
    system       system "reply exactly BANANA"        is the system role honoured?
    instruction  the same demand in the user turn     strict (exactly BANANA) or task-shaped
    json         a schema'd triage request            json / fenced-json / prose, and why not
    reference    the CWE number of "improper access control" (284)  trusted / unverified
    multitool    three tools, a task that needs two in order (3.3.6.0 R4): find_user, then get_orders with the id
                 the first returned -- two turns, scored on the right tools with the right arguments (0-1)
The reasoning split is read off every probe (any `thinking`); the speed off
the json probe (`eval_count / eval_duration`, after the warm-up).
"""

from __future__ import annotations

import json
import re
from typing import Optional

PROBE_SET = "battery-2"  # bump when a prompt or a rule changes: every cached profile re-runs
THINK_CAP = 600
TOOL = {"type": "function", "function": {
    "name": "get_weather", "description": "Get the weather for a city",
    "parameters": {"type": "object", "properties": {"city": {"type": "string"}}, "required": ["city"]}}}
BANANA = "You must reply with exactly one word and nothing else: BANANA"
TRIAGE = ("You are triaging pentest findings. Return ONLY compact JSON, no prose, with exactly these keys: "
          "severity (critical|high|medium|low), cwe, why, fix.\n"
          "Finding: The /api/v2/users endpoint returns other tenants' records when the X-Tenant header is "
          "changed; there is no authorization check on the object id.")
TRIAGE_KEYS = ("severity", "cwe", "why", "fix")
CWE_ASK = "What is the CWE identifier number for improper access control? Answer with just the number."
CWE_RIGHT = "284"

# name -> (messages, num_predict, tools?)
PROBES = {
    "warmup": ([{"role": "user", "content": "Reply with the word ready."}], 8, False),
    "tools": ([{"role": "user", "content": "What is the weather in Paris? Use the tool."}], 200, True),
    "system": ([{"role": "system", "content": BANANA}, {"role": "user", "content": "What is 2+2?"}], 60, False),
    "instruction": ([{"role": "user", "content": "Reply with exactly one word and nothing else: BANANA. "
                                                 "Now answer: what is 2+2?"}], 60, False),
    "json": ([{"role": "user", "content": TRIAGE}], 400, False),
    "reference": ([{"role": "user", "content": CWE_ASK}], 80, False),
}
ORDER = ("warmup", "tools", "system", "instruction", "json", "reference")
WORDS = {"warmup": "warm-up (never timed)", "tools": "tool call", "system": "system role",
         "instruction": "user instruction", "json": "structured output", "reference": "reference fidelity",
         "multitool": "two tools in order (tool-call accuracy)"}


def body(model: str, name: str, *, num_ctx: int, keep_alive, cap: Optional[int] = None) -> dict:
    messages, predict, tools = PROBES[name]
    out = {"model": model, "messages": messages, "stream": False, "keep_alive": keep_alive,
           "options": {"num_ctx": num_ctx, "temperature": 0, "num_predict": cap or predict}}
    if tools:
        out["tools"] = [TOOL]
    return out


def parts(reply) -> "tuple[str, str, list]":
    """(content, thinking, tool_calls) of one `/api/chat` answer."""
    msg = (reply or {}).get("message") if isinstance(reply, dict) else None
    msg = msg if isinstance(msg, dict) else {}
    calls = msg.get("tool_calls") if isinstance(msg.get("tool_calls"), list) else []
    return str(msg.get("content") or ""), str(msg.get("thinking") or ""), calls


def thinking_only(reply) -> bool:
    content, thinking, calls = parts(reply)
    return not content.strip() and bool(thinking.strip()) and not calls


def score_tools(reply) -> "tuple[str, str]":
    content, _t, calls = parts(reply)
    if calls:
        name = ((calls[0] or {}).get("function") or {}).get("name") if isinstance(calls[0], dict) else None
        return "yes", f"called {name or 'the tool'}"
    return "no", "an empty reply and no tool call" if not content.strip() else "it answered in text, no tool call"


def score_system(reply) -> str:
    return "honoured" if "BANANA" in parts(reply)[0].upper() else "weak"


def score_instruction(reply) -> str:
    words = re.findall(r"[A-Za-z0-9+]+", parts(reply)[0])
    return "strict" if [w.upper() for w in words] == ["BANANA"] else "task-shaped"


def _object_in(text: str) -> Optional[str]:
    start, end = text.find("{"), text.rfind("}")
    return text[start:end + 1] if 0 <= start < end else None


def strip_fences(text: str) -> str:
    """A ```json ... ``` (or bare ```) fence around a reply removed; text without one comes back as it was."""
    t = (text or "").strip()
    m = re.match(r"^```[A-Za-z0-9_-]*\s*\n?(.*?)\n?```\s*$", t, re.DOTALL)
    return m.group(1).strip() if m else t


def score_json(reply) -> "tuple[str, str]":
    """(output, why): output json | fenced-json | prose; why says what failed ("" when it held)."""
    content, thinking, _c = parts(reply)
    if not content.strip():
        return "prose", "empty: it answered in thinking only" if thinking.strip() else "empty: no reply at all"
    fenced = "```" in content
    cleaned = strip_fences(content)
    try:
        parsed = json.loads(cleaned)
    except ValueError as e:
        inner = _object_in(cleaned)
        if inner is None:
            return "prose", "prose: no JSON object in the reply"
        try:
            parsed = json.loads(inner)
        except ValueError:
            return "prose", f"invalid JSON: {str(e)[:80]}"
        if not fenced:
            return "prose", "prose: the JSON came wrapped in text"
    if not isinstance(parsed, dict):
        return "prose", "invalid: JSON, but not an object"
    missing = [k for k in TRIAGE_KEYS if k not in parsed]
    if missing:
        return "prose", f"keys: missing {', '.join(missing)}"
    return ("fenced-json", "") if fenced else ("json", "")


def score_reference(reply) -> "tuple[str, str]":
    content = parts(reply)[0].strip()
    nums = re.findall(r"\d+", content)
    if nums and nums[0] == CWE_RIGHT:
        return "trusted", f"answered {CWE_RIGHT} (right)"
    got = (f"CWE-{nums[0]}" if nums else content[:24]) or "nothing"
    return "unverified", f"answered {got} (right: CWE-{CWE_RIGHT})"


def speed(reply) -> "dict":
    """{tok_s, ttft_ms, load_s} from one answer's durations (nanoseconds); None where it says nothing."""
    r = reply if isinstance(reply, dict) else {}
    ev, dur = r.get("eval_count"), r.get("eval_duration")
    tok_s = round(ev / (dur / 1e9), 1) if isinstance(ev, int) and isinstance(dur, (int, float)) and dur > 0 else None
    pe, ld = r.get("prompt_eval_duration"), r.get("load_duration")
    ttft = None
    if isinstance(pe, (int, float)):
        ttft = round((pe + (ld if isinstance(ld, (int, float)) else 0)) / 1e6)
    load_s = round(ld / 1e9, 1) if isinstance(ld, (int, float)) else None
    return {"tok_s": tok_s, "ttft_ms": ttft, "load_s": load_s}


def evidence(reply, *, retried=None) -> dict:
    """What a probe's answer was, kept in the profile (trimmed)."""
    content, thinking, calls = parts(reply)
    out = {"content": content[:400], "thinking": thinking[:200], "tool_calls": calls[:2],
           "done_reason": (reply or {}).get("done_reason") if isinstance(reply, dict) else None,
           "eval_count": (reply or {}).get("eval_count") if isinstance(reply, dict) else None}
    if retried is not None:
        out["first"] = evidence(retried)
    return out
