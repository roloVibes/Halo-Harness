"""tests.helpers.fake_llama_chat -- Halo 3.3.8.0 R4: the chat half of tests/helpers/fake_llama_server.py (it imports
this file from its own folder). It loads no model and generates nothing: an answer's numbers are arithmetic.

    key_of(argv, arg) -> (key | None, line)   `--api-key-file <path>` read (the first line), else `--api-key <key>`;
        the line it prints never carries the key. FAKE_LLAMA_NO_KEY_FILE=1 makes it refuse the flag the way a build
        without it does ("error: invalid argument: --api-key-file")
    answer(path, headers, body, key, alias) -> (status, json, lines)
        POST /v1/chat/completions (and /chat/completions): 401 without `Authorization: Bearer <key>` when a key is
        set; else llama-server's answer shape with `timings` {prompt_n, prompt_ms, predicted_n, predicted_ms, ...}
        and `usage`, and the slot's print_timing lines for the log. The prompt is a token per 4 characters; the
        reply max_tokens when that is 128 or less (finish_reason length), else 200 tokens (stop). The rates come
        from FAKE_LLAMA_TOK_S (decode, default 11.2) and FAKE_LLAMA_PP_S (prompt, default 400).
"""
from __future__ import annotations

import os

REPLY_N = 200


def key_of(argv: list, arg) -> "tuple[object, str]":
    path = arg(argv, "--api-key-file")
    if path is not None:
        if os.environ.get("FAKE_LLAMA_NO_KEY_FILE") == "1":
            return False, "error: invalid argument: --api-key-file"
        try:
            with open(path, encoding="utf-8") as f:
                key = f.readline().strip()
        except OSError as e:
            return False, f"error: failed to read --api-key-file ({type(e).__name__})"
        return key, f"main: api key read from a file ({len(key)} characters, 1 key)"
    key = arg(argv, "--api-key")
    return key, ("main: api key from the command line" if key else "main: no api key: every endpoint is open")


def _text(body: dict) -> str:
    out = []
    for m in body.get("messages") or []:
        c = m.get("content") if isinstance(m, dict) else ""
        if isinstance(c, list):
            out += [str(p.get("text") or "") for p in c if isinstance(p, dict)]
        else:
            out.append(str(c or ""))
    return "".join(out)


def answer(path: str, headers, body: dict, key, alias: str) -> "tuple[int, dict, list]":
    if not path.rstrip("/").endswith("chat/completions"):
        return 404, {"error": {"code": 404, "message": "File Not Found"}}, []
    if key and str(headers.get("Authorization") or "") != f"Bearer {key}":
        return 401, {"error": {"code": 401, "message": "Invalid API Key", "type": "authentication_error"}}, \
            ["srv  log_server_r: request: POST /v1/chat/completions 127.0.0.1 401"]
    tok_s = float(os.environ.get("FAKE_LLAMA_TOK_S") or 11.2)
    pp_s = float(os.environ.get("FAKE_LLAMA_PP_S") or 400.0)
    prompt_n = max(1, len(_text(body)) // 4)
    asked = int(body.get("max_tokens") or REPLY_N)
    n, finish = (asked, "length") if asked <= 128 else (min(asked, REPLY_N), "stop")
    prompt_ms, eval_ms = prompt_n / pp_s * 1000.0, n / tok_s * 1000.0
    timings = {"prompt_n": prompt_n, "prompt_ms": round(prompt_ms, 3), "prompt_per_token_ms": round(prompt_ms / prompt_n, 3),
               "prompt_per_second": round(pp_s, 2), "predicted_n": n, "predicted_ms": round(eval_ms, 3),
               "predicted_per_token_ms": round(eval_ms / n, 3), "predicted_per_second": round(tok_s, 2)}
    lines = ["slot print_timing: id  0 | task 1 | ",
             f"prompt eval time = {prompt_ms:10.2f} ms / {prompt_n:5d} tokens ({prompt_ms / prompt_n:8.2f} ms per token, "
             f"{pp_s:8.2f} tokens per second)",
             f"       eval time = {eval_ms:10.2f} ms / {n:5d} tokens ({eval_ms / n:8.2f} ms per token, {tok_s:8.2f} tokens "
             "per second)",
             f"      total time = {prompt_ms + eval_ms:10.2f} ms / {prompt_n + n:5d} tokens",
             "srv  log_server_r: request: POST /v1/chat/completions 127.0.0.1 200"]
    out = {"id": "chatcmpl-fake", "object": "chat.completion", "model": alias,
           "choices": [{"index": 0, "finish_reason": finish, "message": {"role": "assistant", "content": "ready " * n}}],
           "usage": {"prompt_tokens": prompt_n, "completion_tokens": n, "total_tokens": prompt_n + n}, "timings": timings}
    return 200, out, lines
