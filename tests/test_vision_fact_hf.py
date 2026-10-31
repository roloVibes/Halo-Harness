"""tests.test_vision_fact_hf -- Halo 3.3.7.0 R4: the battery's vision probe on Hugging Face local servers
(providers/battery_vision_hf.py, models_probe_hf.py) over an in-process fake server on 127.0.0.1:0 that answers like
llama-server (`/props` with or without `modalities.vision`) or LM Studio (`/api/v0/models` with `type: vlm | llm`) and
`/v1/chat/completions` (the image as an `image_url` data URL):

1. llama-server with a projector is asked and a "red" answer is verified yes; one with no projector is "not asked";
2. LM Studio's vlm is asked, its llm not; mlx-lm is not asked, mlx-vlm is; an unknown server is "not asked";
3. a server that refuses the image is a verified no; the profile is kept and the model card's vision says
   "verified: the battery's image probe" for that hf:local model; `halo models probe hf:local/<m>@<server>` prints it.
Nothing leaves 127.0.0.1; no model is called.
Run: python -m tests.test_vision_fact_hf
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402
from tests.helpers.steward_seed import Home  # noqa: E402

test, TESTS = new_registry()


class Fake:
    """GET /props, /api/v0/models; POST /v1/chat/completions; each answer from `self.answers` (None: 404)."""

    def __init__(self, props=None, lms=None, reply="Red.", refuse: str = ""):
        self.answers = {"/props": props, "/api/v0/models": lms}
        self.reply, self.refuse, self.chats = reply, refuse, []

    def __enter__(self):
        fake = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *_a):
                pass

            def _send(self, code, obj):
                data = json.dumps(obj).encode("utf-8")
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def do_GET(self):  # noqa: N802
                got = fake.answers.get(self.path)
                self._send(200, got) if got is not None else self._send(404, {"error": "not found"})

            def do_POST(self):  # noqa: N802
                body = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
                fake.chats.append(body)
                if fake.refuse:
                    return self._send(400, {"error": fake.refuse})
                self._send(200, {"choices": [{"message": {"role": "assistant", "content": fake.reply}}]})
        self.srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.srv.server_address[1]}/v1"
        return self

    def __exit__(self, *exc):
        self.srv.shutdown()
        self.srv.server_close()


@test
def test_who_is_asked(ctx: Ctx):
    from halo_harness.providers.battery_vision_hf import probe
    with Home() as h:
        with Fake(props={"modalities": {"vision": True}, "n_ctx": 8192}) as f:
            yes = probe(f.url, "gemma-3-4b", state_dir=h.state)
            sent = f.chats[0]["messages"][0]["content"]
        with Fake(props={"n_ctx": 8192}) as f:
            text = probe(f.url, "qwen3-8b")
            asked_text = len(f.chats)
        with Fake(lms={"data": [{"id": "qwen2.5-vl-7b", "type": "vlm"}, {"id": "qwen3-8b", "type": "llm"}]}) as f:
            lms_v, lms_t = probe(f.url, "qwen2.5-vl-7b"), probe(f.url, "qwen3-8b")
        with Fake() as f:
            unknown = probe(f.url, "some-model")
            mlx, vlm = probe(f.url, "llama-3.2-3b", kind="mlx"), probe(f.url, "qwen2-vl-2b", kind="mlx-vlm")
    ctx.check(f"llama-server with a projector: asked, red is yes, got {yes['vision']} {yes['vision_why']}",
              yes["vision"] == "yes" and sent[1]["type"] == "image_url" and sent[1]["image_url"]["url"].startswith(
                  "data:image/png;base64,"))
    ctx.check(f"no projector: not asked, got {text['vision']} {text['vision_why']}", text["vision"] == "not asked"
              and asked_text == 0 and "no projector" in text["vision_why"])
    ctx.check(f"LM Studio: the vlm is asked, the llm not, got {lms_v['vision']} {lms_t['vision']}",
              lms_v["vision"] == "yes" and lms_t["vision"] == "not asked")
    ctx.check(f"an unknown server is not asked, got {unknown['vision_why']}", unknown["vision"] == "not asked"
              and "says nothing about images" in unknown["vision_why"])
    ctx.check(f"mlx-lm not asked, mlx-vlm asked, got {mlx['vision']} {vlm['vision']}", mlx["vision"] == "not asked"
              and vlm["vision"] == "yes")


@test
def test_a_refusal_the_card_and_the_command(ctx: Ctx):
    from halo_harness.models_probe_cli import cmd_models_probe
    from halo_harness.providers.battery_vision_hf import probe
    from halo_harness.providers.vision_fact import vision_of
    with Home() as h:
        with Fake(props={"modalities": {"vision": True}}, refuse="image input is not supported") as f:
            no = probe(f.url, "text-only", state_dir=h.state)
        with Fake(props={"modalities": {"vision": True}}) as f:
            cfg = json.loads((h.state / "config.json").read_text(encoding="utf-8"))
            cfg["huggingface"] = {"local_servers": [{"name": "box", "url": f.url}]}
            (h.state / "config.json").write_text(json.dumps(cfg), encoding="utf-8")
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                rc = cmd_models_probe(["hf:local/gemma-3-4b@box"])
        from halo_harness.providers.model_card import card_of
        card = card_of("hf:local/gemma-3-4b@box", state_dir=h.state)
    ctx.check(f"a refused image is a verified no, got {no['vision']} {no['vision_why']}", no["vision"] == "no"
              and vision_of(profile=no)["truth"] == "verified")
    ctx.check(f"halo models probe hf:local/... prints the answer, got {rc} {out.getvalue()!r}", rc == 0
              and "vision yes" in out.getvalue() and "reads images (verified: the battery's image probe" in out.getvalue())
    ctx.check(f"the card reads it, got {card.get('vision')} {card.get('vision_truth')} {card.get('sources', {}).get('vision')}",
              card.get("vision") is True and card.get("vision_truth") == "verified")


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
