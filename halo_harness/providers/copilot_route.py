"""halo_harness.providers.copilot_route -- `cp:work` as a model a session or a lineup role runs on (Halo 3.3.17.0 R2).

* `parse_cp`: `cp:work` is the one ref (provider `copilot`, dialect `copilot`); any other `cp:` name is refused.
* `creds_for`: a ProviderCreds (the door's URL; the token is fetched per call) once Copilot is set up and a refresh
  token is stored, else None -- the session's ordinary "not configured" path.
* `stream_copilot`: one turn. The session's latest user text goes to the session's conversation (one per Halo
  session, kept on the session as `_copilot_conversation`); Copilot's answer comes back as the Anthropic events every
  dialect yields (one text block, its citations numbered under it, `end_turn`). The call runs on a thread and pings
  while it waits, so the loop's silence watch never resends it; an abort stops waiting. Usage carries no price, so
  the cost meter marks the session's cost incomplete (copilot_cost.py says why). No tool is ever offered: the loop
  sends `cp:work` an empty tool list (agent/loop.py `_derive_and_build`) and this door sends none.
"""

from __future__ import annotations

import threading
import uuid
from typing import Iterator, Optional

from halo_harness.providers.copilot_config import REF

DIALECT = "copilot"


def parse_cp(raw: str, name: str, model_ref_cls):
    from halo_harness.providers.routing import InvalidModelError
    if name.strip().lower() != "work":
        raise InvalidModelError(f"no route: {raw!r} (cp: has one model, cp:work -- your work's Copilot; "
                                "docs/PROVIDERS-copilot.md)")
    return model_ref_cls(raw=raw, provider="copilot", model="work", dialect=DIALECT)


def signed_in() -> bool:
    from halo_harness.providers.copilot_config import load
    from halo_harness.providers.copilot_tokens import refresh_token
    try:
        return load().configured and bool(refresh_token())
    except Exception:
        return False


def creds_for(ref):
    if getattr(ref, "provider", "") != "copilot" or not signed_in():
        return None
    from halo_harness.providers.copilot_config import graph_url, load, workiq_url
    from halo_harness.providers.stream import ProviderCreds
    return ProviderCreds(base_url=workiq_url() if load().api == "workiq" else graph_url(), api_key="")


def last_user_text(body: Optional[dict]) -> str:
    """The newest user message's text (an OpenAI-chat or Anthropic-shaped body)."""
    for m in reversed((body or {}).get("messages") or []):
        if not isinstance(m, dict) or m.get("role") != "user":
            continue
        c = m.get("content")
        if isinstance(c, str):
            return c.strip()
        parts = [str(p.get("text") or "") for p in c or [] if isinstance(p, dict) and p.get("type") in ("text", None)]
        text = "\n".join(p for p in parts if p).strip()
        if text:
            return text
    return ""


def last_prompt(session) -> str:
    """What the user (or the spawning agent) last said, from the session's log: the newest `user` node that is a
    real prompt or a steer, its text blocks only -- never the environment and permission snapshots the wire copy
    folds into the same message."""
    try:
        nodes = session.log.nodes()
    except Exception:
        return ""
    for n in reversed(nodes or []):
        if isinstance(n, dict) and n.get("type") == "user" and n.get("kind") in (None, "steer"):
            c = n.get("content")
            if isinstance(c, str):
                return c.strip()
            text = "\n".join(str(b.get("text") or "") for b in c or [] if isinstance(b, dict) and b.get("type") == "text")
            if text.strip():
                return text.strip()
    return ""


def _events(label: str, text: str) -> Iterator[dict]:
    yield {"type": "message_start", "message": {"id": f"msg_cp_{uuid.uuid4().hex[:12]}", "type": "message",
                                                "role": "assistant", "model": label, "content": [], "stop_reason": None,
                                                "stop_sequence": None, "usage": {"input_tokens": 0, "output_tokens": 0}}}
    yield {"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}}
    yield {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": text}}
    yield {"type": "content_block_stop", "index": 0}
    yield {"type": "message_delta", "delta": {"stop_reason": "end_turn", "stop_sequence": None},
           "usage": {"output_tokens": 0}}
    yield {"type": "message_stop"}


def stream_copilot(session, req, abort: Optional[threading.Event] = None, kind: str = "turn") -> Iterator[dict]:
    """A `turn` is the session's conversation with the log's last prompt; any other call on this route (a
    compaction, a small-model call) is its own one-off conversation with the request's own text, so it never lands
    in the session's conversation."""
    from halo_harness.providers.copilot import Conversation, ask, format_answer
    from halo_harness.providers.copilot_net import CopilotError
    from halo_harness.providers.stream import ProviderNotConfigured
    wire = last_user_text(getattr(req, "prebuilt_oai_body", None) or getattr(req, "body", None))
    conv = getattr(session, "_copilot_conversation", None) if kind == "turn" else Conversation()
    if not isinstance(conv, Conversation):
        conv = Conversation()
        try:
            session._copilot_conversation = conv
        except Exception:
            pass
    prompt = (last_prompt(session) or wire) if kind == "turn" else wire
    box: dict = {}

    def work() -> None:
        try:
            box["answer"] = ask(prompt, conversation=conv)
        except CopilotError as e:
            box["error"] = e
        except Exception as e:  # a bug here is one line too, never a traceback in the transcript
            box["error"] = CopilotError(f"Copilot: the call failed ({type(e).__name__}: {e})", "answer")

    t = threading.Thread(target=work, daemon=True, name="halo-copilot-turn")
    t.start()
    while t.is_alive():
        if abort is not None and abort.is_set():
            return
        t.join(0.5)
        if t.is_alive():
            yield {"type": "ping"}
    err = box.get("error")
    if err is not None:  # the line as it is (no "HTTP 400:" in front of a line no HTTP call made), never retried
        raise ProviderNotConfigured(err.line)
    yield from _events(getattr(req, "model_label", REF) or REF, format_answer(box.get("answer") or {}))
