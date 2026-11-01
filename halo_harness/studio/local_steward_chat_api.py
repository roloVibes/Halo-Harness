"""halo_harness.studio.local_steward_chat_api -- the Steward page's chat box and model picker (Halo 3.3.7.0 R5;
docs/STUDIO-local-steward.md; studio/local_api.dispatch_local sends `local/steward/*` here). The same loopback /
origin / token guard as every Studio route.

    GET  local/steward/chat              {rows: the steward's session log (ollama/steward-chat.jsonl), model, why}
    POST local/steward/chat {question, bigger?}   one turn (ollama_steward/chat.ask): the steward's own model, or the
                                         session's main model once with bigger -- its answer, cost, tools and buttons
    GET  local/steward/bigger-cost?question=   what "ask a bigger model" costs, said before the button is pressed
    GET  local/steward/candidates        {candidates, line, chosen, why}: the models that could run the steward here
    POST local/steward/model {model}     the picker: ollama.steward.model (a candidate's ref, or "none")

A chat's button (retire, add, bench, battery) goes to the route that already does that one thing (the page posts it);
nothing here runs one.
"""

from __future__ import annotations


def _body(req) -> dict:
    return req.body if isinstance(req.body, dict) else {}


def get_chat(req):
    from halo_harness.ollama_steward.agent import choose_model
    from halo_harness.ollama_steward.chat_log import read
    model, why = choose_model(state_dir=req.state_dir)
    return 200, {"rows": read(req.state_dir, limit=80), "model": model, "why": why,
                 "cli": 'halo ollama steward chat "<question>"'}


def post_chat(req):
    from halo_harness.ollama_steward.chat import ask
    b = _body(req)
    q = str(b.get("question") or "").strip()
    if not q:
        return 422, {"error": "the chat takes {question}", "problems": ["question: what to ask the steward"]}
    got = ask(req.state_dir, q[:2000], bigger=b.get("bigger") is True)
    return (200 if got.get("model") else 409), got


def get_bigger_cost(req):
    from halo_harness.ollama_steward.chat import bigger_cost
    return 200, bigger_cost(req.state_dir, str((req.query or {}).get("question") or ""))


def get_candidates(req):
    from halo_harness.ollama_steward.agent import choose_model
    from halo_harness.ollama_steward.candidates import candidates, line
    cands = candidates(req.state_dir, str((req.query or {}).get("host") or "").strip() or None)
    model, why = choose_model(state_dir=req.state_dir)
    return 200, {"candidates": cands, "line": line(cands), "chosen": model, "why": why,
                 "cli": "halo ollama steward candidates"}


def post_model(req):
    from halo_harness.theme import set_config_value
    model = str(_body(req).get("model") or "").strip()
    if not model:
        return 422, {"error": "the picker takes {model}: a candidate's ref, or none", "problems": ["model"]}
    try:
        set_config_value("ollama.steward.model", model)
    except Exception as e:  # config.json does not parse: its own line
        return 422, {"error": str(e), "problems": [str(e)]}
    return 200, {"ok": True, "model": model, "line": f"ollama.steward.model = {model} (config.json): the steward's notes "
                                                     "and its chat use it from the next call"}


ROUTES = {("GET", "local/steward/chat"): get_chat, ("POST", "local/steward/chat"): post_chat,
          ("GET", "local/steward/bigger-cost"): get_bigger_cost, ("GET", "local/steward/candidates"): get_candidates,
          ("POST", "local/steward/model"): post_model}
PATHS = {p for _m, p in ROUTES}


def dispatch_steward_chat(req):
    if req.path not in PATHS:
        return None
    fn = ROUTES.get((req.method, req.path))
    return fn(req) if fn else (405, {"error": "method not allowed"})
