"""halo_harness.ollama_steward.chat -- the steward's chat: the 3.3.4.0 steward agent run as a conversation over the
host's findings (Halo 3.3.7.0 R5; ROADMAP "the steward's chat"; the Steward page's chat box, `halo ollama steward
chat "<question>"`).

    ask(state_dir, question, *, bigger=False, caller=None, readers=None, model=None) -> Answer
    Answer = {answer, model, cost, seconds, tools [{tool, args, ok, text}], buttons [button], left_out [section],
              context_tokens, usage}
    bigger_cost(state_dir, question="") -> {model, line, tokens}   what "ask a bigger model" costs, said first

The model is the steward's own (agent.choose_model); "ask a bigger model" sends the same context once to the session's
main model (the configured `model`) and nothing else ever calls it. Each round the model answers one JSON object --
{"tool": <name>, "args": {...}} to use a tool (ollama_steward/chat_tools.py: the reads, propose, apply, bench,
battery), or {"answer": "..."} -- at most ROUNDS rounds. Its context: the job's (agent_prompt.context: the cards, the
calls, the events, the findings -- a paired host's folded in -- the fit plans), the reservations and the bundles'
verdict lines, the adviser's top suggestions with their ids, and the last turns; held under the token budget
(`ollama.steward.chat_tokens`, 6,000), the events, then the calls, then the cards left out first and said so. Every
row goes to the steward's session log (ollama_steward/chat_log.py); each answer carries its cost: "local, 4 s" or
the dollars.
"""

from __future__ import annotations

import json
import re
import time
from typing import Callable, Optional

ROUNDS = 4
TOKENS = 6000
_FENCE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.S)
_THINK = re.compile(r"<think>.*?</think>", re.S | re.I)

HEAD = """You are Halo's Ollama steward, talking with the person who runs these machines. Answer in plain words, at \
most six short lines, using only the numbers you are given or a tool returns. Each reply is ONE JSON object and \
nothing else:
  {"tool": "<name>", "args": {...}}   to read or do one thing (you see its answer, then reply again)
  {"answer": "<your answer>"}        when you can answer
A change is Halo-side only (a profile field), one per answer, and names the finding it acts on (its id). Retiring, \
downloading, a bench or the battery become a button the person presses; say what it costs. The tools:"""


def tokens_budget() -> int:
    try:
        from halo_harness.theme import get_config_value
        v = get_config_value("ollama.steward.chat_tokens", default=TOKENS)
        return int(v) if isinstance(v, int) and not isinstance(v, bool) and v >= 1000 else TOKENS
    except Exception:
        return TOKENS


def guide(*, bigger: bool = False) -> str:
    from halo_harness.ollama_steward.chat_tools import TOOLS
    if bigger:
        return HEAD.split(" Each reply is ONE")[0] + " Reply with your answer only (no tools: the steward's own model " \
            "read them; their answers are below)."
    return HEAD + "\n" + "\n".join(f"  {n} {a}: {w}" for n, (a, w) in TOOLS.items())


def env_for(state_dir, readers: Optional[dict] = None) -> dict:
    from halo_harness.ollama_steward import steward
    from halo_harness.ollama_steward.host_fold import fold
    from halo_harness.ollama_steward.rules import gather, run_rules
    from halo_harness.providers.ollama import resolve_ollama_hosts
    from halo_harness.studio import ollama_hosts_view as V  # the cached views (60 s): a conversation reads no host twice
    ctx = gather(state_dir, **(readers if readers is not None else V.readers()))
    found = fold(state_dir, run_rules(ctx))
    return {"state": state_dir, "ctx": ctx, "found": found, "hosts": list(resolve_ollama_hosts()), "mode": steward.mode()}


def _sections(env: dict) -> list:
    """[(name, text)] in the order they are kept; the last ones are left out first when the budget is short."""
    from halo_harness.ollama_steward import agent_prompt as P
    from halo_harness.ollama_steward.rules import format_finding
    found = env["found"]
    out = [("findings", "Findings (here and on the paired hosts):\n" + ("\n".join(
        f"  {x}" for f in found for x in format_finding(f)) or "  none"))]
    try:
        from halo_harness.local_sched.reserve import all_lines
        held = all_lines(env["state"])
        out.append(("reservations", "Reservations:\n" + ("\n".join(f"  {r['host']}: {r['line']}" for r in held) or
                                                         "  none")))
    except Exception:
        pass
    try:
        from halo_harness.models_library.advise import advise
        got = advise(env["state"])
        env["advice"] = got["suggestions"]
        out.append(("adviser", "The roster adviser: " + got["head"] + "".join(
            f"\n  [{s['id']}] {s['line']}" for s in got["suggestions"][:4])))
    except Exception:
        pass
    full = P.context(env["ctx"], {"mode": env["mode"], "findings": found})
    parts = full.split("\n\n")
    out.append(("cards", "\n\n".join(p for p in parts if p.startswith(("Mode:", "Hardware")))))
    out.append(("calls", "\n\n".join(p for p in parts if p.startswith(("Calls per model", "Machines")))))
    out.append(("events", "\n\n".join(p for p in parts if p.startswith("The last"))))
    return [(n, t) for n, t in out if t.strip()]


def context(env: dict, question: str, history: list, *, budget: Optional[int] = None) -> "tuple[str, list, int]":
    from halo_harness.ollama_steward.agent_prompt import tokens
    budget = tokens_budget() if budget is None else budget
    head = "".join(f"Earlier -- Q: {q}\nA: {a}\n" for q, a in history) + f"The question: {question}"
    kept = _sections(env)
    left: list = []
    text = "\n\n".join([t for _n, t in kept] + [head])
    while kept and tokens(guide()) + tokens(text) > budget:
        left.insert(0, kept.pop()[0])
        text = "\n\n".join([t for _n, t in kept] + [head])
    return text, left, tokens(guide()) + tokens(text)


def parse(text: str) -> dict:
    """{"tool", "args"} or {"answer"}; a reply that is not one JSON object is the answer as it is."""
    raw = _THINK.sub("", str(text or "")).strip()
    m = _FENCE.search(raw)
    body = m.group(1) if m else raw[raw.find("{"):raw.rfind("}") + 1] if "{" in raw and "}" in raw else ""
    try:
        got = json.loads(body) if body else None
    except ValueError:
        got = None
    if isinstance(got, dict) and isinstance(got.get("tool"), str):
        return {"tool": got["tool"].strip(), "args": got.get("args") if isinstance(got.get("args"), dict) else {}}
    if isinstance(got, dict) and isinstance(got.get("answer"), str):
        return {"answer": got["answer"].strip()}
    return {"answer": raw[:2000]}


def cost_words(usage: dict, model: str, seconds: float) -> str:
    from halo_harness.ollama_steward.agent import _is_local
    if usage.get("local") or _is_local(model):
        return f"local, {max(1, round(seconds))} s"
    if isinstance(usage.get("cost_usd"), (int, float)):
        return f"${usage['cost_usd']:.4f}"
    return f"{usage.get('input_tokens') or '?'} in / {usage.get('output_tokens') or '?'} out tokens, no price known"


def _model(state_dir, bigger: bool, model: Optional[str]) -> "tuple[Optional[str], str]":
    if model:
        return model, "given"
    if bigger:
        from halo_harness.start.provider import default_model
        m = default_model()
        return (m or None), "the session's main model" if m else "no main model: set `model` in config.json"
    from halo_harness.ollama_steward.agent import choose_model
    return choose_model(state_dir=state_dir)


def ask(state_dir, question: str, *, bigger: bool = False, caller: Optional[Callable] = None,
        readers: Optional[dict] = None, model: Optional[str] = None) -> dict:
    from halo_harness.ollama_steward import chat_log, chat_tools
    from halo_harness.ollama_steward.agent import live_call
    caller = caller or live_call
    model, why = _model(state_dir, bigger, model)
    question = str(question or "").strip()
    chat_log.append(state_dir, {"role": "user", "text": question})
    out = {"answer": "", "model": model, "cost": "", "seconds": 0.0, "tools": [], "buttons": [], "left_out": [],
           "context_tokens": 0, "usage": {}}
    if not model:
        out["answer"] = f"no model to answer: {why}"
        chat_log.append(state_dir, {"role": "steward", "text": out["answer"], "model": None, "cost": ""})
        return out
    env = env_for(state_dir, readers)
    text, out["left_out"], out["context_tokens"] = context(env, question, chat_log.turns(state_dir))
    usage = {"input_tokens": 0, "output_tokens": 0, "cost_usd": None, "local": None}
    t0, answer = time.monotonic(), ""
    for i in range(1 if bigger else ROUNDS):
        try:
            reply = caller(model, guide(bigger=bigger), text, state_dir=state_dir) or {}
        except Exception as e:
            answer = f"the model did not answer ({type(e).__name__}: {str(e)[:160]})"
            break
        for k in ("input_tokens", "output_tokens"):
            usage[k] += int(reply.get(k) or 0)
        if isinstance(reply.get("cost_usd"), (int, float)):
            usage["cost_usd"] = (usage["cost_usd"] or 0.0) + reply["cost_usd"]
        usage["local"] = reply.get("local")
        p = parse(reply.get("text"))
        if "tool" not in p or bigger or i == ROUNDS - 1:
            answer = p.get("answer") or "the model answered with a tool on its last round"
            break
        got = chat_tools.run(env, p["tool"], p["args"])
        row = {"tool": p["tool"], "args": p["args"], "ok": got.get("ok"), "text": str(got.get("text") or "")[:1200]}
        if got.get("button"):
            b = chat_log.append(state_dir, {"role": "button", "text": got["text"], "action": got["button"]})
            out["buttons"].append({**got["button"], "id": b["id"]})
        out["tools"].append(row)
        chat_log.append(state_dir, {"role": "tool", **row})
        text += f"\n\nTOOL {p['tool']} {json.dumps(p['args'])}:\n{row['text']}"
    out["seconds"] = round(time.monotonic() - t0, 1)
    out.update(answer=answer, usage=usage, cost=cost_words(usage, model, out["seconds"]))
    chat_log.append(state_dir, {"role": "bigger" if bigger else "steward", "text": answer, "model": model,
                                "cost": out["cost"], "seconds": out["seconds"], "usage": usage,
                                "left_out": out["left_out"], "context_tokens": out["context_tokens"]})
    return out


def bigger_cost(state_dir, question: str = "", *, readers: Optional[dict] = None, env: Optional[dict] = None) -> dict:
    from halo_harness.ollama_steward import chat_log
    from halo_harness.start.checks_run import call_price
    model, why = _model(state_dir, True, None)
    if not model:
        return {"model": None, "line": why, "tokens": 0}
    _text, _left, n = context(env or env_for(state_dir, readers), question or "(your question)", chat_log.turns(state_dir))
    return {"model": model, "tokens": n, "line": f"ask {model} once: ~{n:,} tokens in -- {call_price(model, n, 600)}"}
