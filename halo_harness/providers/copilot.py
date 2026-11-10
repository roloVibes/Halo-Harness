"""halo_harness.providers.copilot -- the `copilot` provider's adapter: a conversation with the user's work Copilot
(Halo 3.3.17.0 R1; docs/PROVIDERS-copilot.md). Built on providers/http.py only (copilot_net.request): no MSAL, no new
dependency.

Two doors, one answer shape:

* `workiq` (default): JSON-RPC `SendMessage` to the Work IQ A2A endpoint, `A2A-Version: 1.0`, the `contextId` kept per
  conversation, the time zone in the message metadata (`Location`).
* `graph-beta`: `POST /beta/copilot/conversations` once, then `POST .../conversations/{id}/chat` per turn with
  `message.text`, `locationHint.timeZone`, optional `additionalContext`, `contextualResources.files[].uri` and
  `contextualResources.webContext.isWebEnabled`.

    ask(prompt, files=[...], web=True, api="workiq", conversation=Conversation()) ->
        {"text", "citations": [{"title", "url"}], "sensitivity", "conversation", "api"}

One `Conversation` per Halo session (the session keeps it; `halo copilot ask` makes its own). Every failure is a
`CopilotError` with one plain line (copilot_errors.py). A 401 gets one fresh token and one retry; a 429 is waited out
once (`Retry-After`, at most `MAX_WAIT_S`), then said.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from typing import Callable, Optional

from halo_harness.providers import copilot_errors as E
from halo_harness.providers import copilot_parse as P
from halo_harness.providers import copilot_tokens as T
from halo_harness.providers.copilot_config import APIS, CopilotConfig, graph_url, load, workiq_url
from halo_harness.providers.copilot_net import CopilotError, Reply, request

MAX_WAIT_S = 60.0
SLEEP: Callable[[float], None] = time.sleep


@dataclass
class Conversation:
    """One Copilot conversation: the Work IQ `contextId` or the Graph conversation id (whichever door it used)."""
    api: str = ""
    context_id: str = ""
    conversation_id: str = ""

    @property
    def id(self) -> str:
        return self.context_id or self.conversation_id


def _retry_after(reply: Reply) -> float:
    try:
        return max(0.0, min(MAX_WAIT_S, float(reply.header("Retry-After") or 5)))
    except ValueError:
        return 5.0


def _call(cfg: CopilotConfig, api: str, method: str, url: str, body: dict, extra: Optional[dict] = None) -> Reply:
    """One authorized call: a 401 gets one fresh token and one retry, a 429 one wait; any other failure is said."""
    refreshed, waited = False, 0.0
    while True:
        token = T.access_token(cfg, api)
        reply = request(method, url, body=body, headers={"Authorization": f"Bearer {token}", **(extra or {})})
        if 200 <= reply.status < 300:
            return reply
        if reply.status == 401 and not refreshed:
            refreshed = True
            T.forget_access(cfg, api)
            continue
        if reply.status == 429 and not waited:
            waited = _retry_after(reply) or 0.001
            SLEEP(waited)
            continue
        err = E.api_error(reply, api, cfg.consent_scopes(api), waited=waited)
        from halo_harness.providers import copilot_account as A
        A.note_error(err.kind, err.line)
        raise err


def _workiq(cfg: CopilotConfig, prompt: str, files: list, web: bool, conv: Conversation) -> dict:
    message = {"role": "ROLE_USER", "messageId": str(uuid.uuid4()), "parts": [{"text": P.with_files(prompt, files)}]}
    if conv.context_id:
        message["contextId"] = conv.context_id
    body = {"jsonrpc": "2.0", "id": str(uuid.uuid4()), "method": "SendMessage",
            "params": {"message": message, "metadata": {"Location": {"timeZone": cfg.timezone}, "webSearch": bool(web)}}}
    reply = _call(cfg, "workiq", "POST", workiq_url(), body, {"A2A-Version": "1.0"})
    data = reply.data if isinstance(reply.data, dict) else {}
    if isinstance(data.get("error"), dict):
        raise E.api_error(Reply(_rpc_status(data["error"]), {}, data, reply.text), "workiq", cfg.consent_scopes("workiq"))
    got = P.workiq_answer(data.get("result"))
    conv.context_id = got.pop("context_id", "") or conv.context_id
    return got


def _rpc_status(err: dict) -> int:
    """A JSON-RPC error's HTTP-like status, when its data names one (else 400)."""
    data = err.get("data") if isinstance(err.get("data"), dict) else {}
    try:
        return int(data.get("status") or data.get("httpStatus") or 400)
    except (TypeError, ValueError):
        return 400


def _graph(cfg: CopilotConfig, prompt: str, files: list, web: bool, conv: Conversation, context: str) -> dict:
    base = f"{graph_url()}/beta/copilot/conversations"
    if not conv.conversation_id:
        made = _call(cfg, "graph-beta", "POST", base, {})
        conv.conversation_id = str((made.data or {}).get("id") or "") if isinstance(made.data, dict) else ""
        if not conv.conversation_id:
            raise CopilotError("Copilot: graph-beta made no conversation (the answer had no id) -- try again.", "answer")
    body: dict = {"message": {"text": prompt}, "locationHint": {"timeZone": cfg.timezone},
                  "contextualResources": {"webContext": {"isWebEnabled": bool(web)}}}
    if files:
        body["contextualResources"]["files"] = [{"uri": f} for f in files]
    if context:
        body["additionalContext"] = [{"text": context}]
    reply = _call(cfg, "graph-beta", "POST", f"{base}/{conv.conversation_id}/chat", body)
    return P.graph_answer(reply.data, prompt)


def ask(prompt: str, *, files=(), web: Optional[bool] = None, api: Optional[str] = None,
        conversation: Optional[Conversation] = None, context: str = "", cfg: Optional[CopilotConfig] = None) -> dict:
    """One turn of the conversation; the one answer shape. Raises CopilotError."""
    cfg = cfg or load()
    if not cfg.configured:
        raise E.not_set_up()
    api = api if api in APIS else cfg.api
    conv = conversation if conversation is not None else Conversation()
    if conv.api and conv.api != api:
        conv.context_id = conv.conversation_id = ""
    conv.api = api
    web = cfg.web if web is None else bool(web)
    files = [str(f).strip() for f in files or () if str(f).strip()]
    prompt = str(prompt or "").strip()
    if not prompt:
        raise CopilotError("Copilot: the prompt is empty -- say what to ask.", "answer")
    got = _workiq(cfg, prompt, files, web, conv) if api == "workiq" else _graph(cfg, prompt, files, web, conv, context)
    return {"text": got.get("text") or "", "citations": got.get("citations") or [], "sensitivity": got.get("sensitivity") or "",
            "conversation": conv.id, "api": api}


def format_answer(answer: dict) -> str:
    """The answer, then its citations numbered (`[1] title -- url`), then the sensitivity label when there is one."""
    lines = [str(answer.get("text") or "(Copilot answered with no text)").rstrip()]
    cites = answer.get("citations") or []
    if cites:
        lines.append("")
        lines += [f"[{i}] {c.get('title') or c.get('url') or '(untitled)'}" + (f" -- {c['url']}" if c.get("url") else "")
                  for i, c in enumerate(cites, 1)]
    if answer.get("sensitivity"):
        lines.append(f"Sensitivity: {answer['sensitivity']}")
    return "\n".join(lines)
