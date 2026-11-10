"""halo_harness.providers.copilot_parse -- reading the two doors' answers into one shape (Halo 3.3.17.0 R1).

Work IQ's A2A `SendMessage` result is a Message or a Task (A2A 1.0: `{"message": {...}}` / `{"task": {...}}`, or the
object itself with `kind`); its text is the `text` parts of the message, or of the task's artifacts and status
message; citations are read from any `data` part or metadata that carries `citations` / `attributions` (each
`{title|providerDisplayName|name, url|uri|seeMoreWebUrl}`). Graph's chat answer is a conversation whose `messages[]`
end with Copilot's reply: `text`, `attributions[]` (`providerDisplayName`, `seeMoreWebUrl`), `sensitivityLabel`.

Read leniently: a field that is missing is left empty, never guessed. The live shapes are pinned only by the mock
(tests/helpers/mock_copilot.py); docs/PROVIDERS-copilot.md says what a real tenant has not yet confirmed.
"""

from __future__ import annotations

from typing import Optional


def with_files(prompt: str, files: list) -> str:
    """Work IQ's turn names the OneDrive / SharePoint files in its text (the A2A door takes no file field Halo knows)."""
    return prompt if not files else prompt + "\n\nFiles: " + ", ".join(files)


def _cite(item) -> Optional[dict]:
    if not isinstance(item, dict):
        return None
    title = item.get("title") or item.get("providerDisplayName") or item.get("name") or ""
    url = item.get("url") or item.get("uri") or item.get("seeMoreWebUrl") or item.get("attributionSource") or ""
    url = url if isinstance(url, str) and url.startswith(("http://", "https://")) else ""
    if not title and not url:
        return None
    return {"title": str(title), "url": str(url)}


def _cites_in(obj) -> list:
    out: list = []
    if not isinstance(obj, dict):
        return out
    for key in ("citations", "attributions", "references"):
        for item in obj.get(key) or []:
            c = _cite(item)
            if c and c not in out:
                out.append(c)
    return out


def _parts(msg) -> "tuple[list, list]":
    """(texts, citations) of an A2A message's parts and metadata."""
    texts, cites = [], []
    if not isinstance(msg, dict):
        return texts, cites
    for part in msg.get("parts") or []:
        if not isinstance(part, dict):
            continue
        if isinstance(part.get("text"), str):
            texts.append(part["text"])
        cites += _cites_in(part.get("data")) + _cites_in(part.get("metadata"))
    cites += _cites_in(msg.get("metadata"))
    return texts, cites


def _dedupe(cites: list) -> list:
    out: list = []
    for c in cites:
        if c not in out:
            out.append(c)
    return out


def workiq_answer(result) -> dict:
    """{text, citations, sensitivity, context_id} from a `SendMessage` result."""
    if not isinstance(result, dict):
        return {"text": "", "citations": [], "sensitivity": "", "context_id": ""}
    msg = result.get("message") if isinstance(result.get("message"), dict) else None
    task = result.get("task") if isinstance(result.get("task"), dict) else None
    if msg is None and task is None:
        if result.get("kind") == "task" or "artifacts" in result:
            task = result
        else:
            msg = result
    texts, cites = [], []
    context_id = ""
    if msg is not None:
        texts, cites = _parts(msg)
        context_id = str(msg.get("contextId") or "")
    if task is not None:
        for art in task.get("artifacts") or []:
            t, c = _parts(art)
            texts += t
            cites += c
        status_msg = (task.get("status") or {}).get("message") if isinstance(task.get("status"), dict) else None
        if not texts and status_msg:
            texts, c = _parts(status_msg)
            cites += c
        cites += _cites_in(task.get("metadata"))
        context_id = str(task.get("contextId") or context_id)
    meta = (msg or task or {}).get("metadata") if isinstance((msg or task or {}).get("metadata"), dict) else {}
    label = meta.get("sensitivityLabel") or meta.get("sensitivity") or ""
    if isinstance(label, dict):
        label = label.get("displayName") or label.get("name") or ""
    return {"text": "\n".join(t for t in texts if t).strip(), "citations": _dedupe(cites), "sensitivity": str(label or ""),
            "context_id": context_id}


def graph_answer(data, prompt: str = "") -> dict:
    """{text, citations, sensitivity} from a Graph chat answer: Copilot's message is the last one that is not the
    user's own prompt echoed back."""
    msgs = data.get("messages") if isinstance(data, dict) else None
    msgs = [m for m in msgs or [] if isinstance(m, dict)]
    reply = None
    for m in reversed(msgs):
        kind = str(m.get("@odata.type") or "")
        if "ResponseMessage" in kind or (m.get("text") or "") != prompt:
            reply = m
            break
    reply = reply or (msgs[-1] if msgs else {})
    label = reply.get("sensitivityLabel")
    if isinstance(label, dict):
        label = label.get("displayName") or label.get("name") or ""
    return {"text": str(reply.get("text") or "").strip(), "citations": _dedupe(_cites_in(reply)),
            "sensitivity": str(label or "")}
