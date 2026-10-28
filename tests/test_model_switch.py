"""tests.test_model_switch -- Halo 3.3.5.0 R0: the switch step through the loop
rig (a real Session over a fake Ollama on 127.0.0.1:0; tests/helpers/
model_switch_rig.py). No real server, no model call:

1. `/model` from a 65,536 model to one with a learned cap of 32,768, through
   the worker pump: the line first ("switching to ol:small:9b@lan: window
   32,768 (learned cap); this conversation is N tokens -> compacting to
   fit"), the compaction (`trigger: "switch"`) on the model being left,
   before any call to the new one; the report after; the window and the tool
   cap set; a `model_switch` node in the log; the first call's ledger line
   `fitted` and `switched_from`;
2. a vision + thinking + tools model -> one with none of them: images become
   captions, thinking blocks go, tool turns are flattened to text, no tools
   are sent, and the request still holds a user turn;
3. Ollama -> a Hugging Face local server answering `/props`: the window is
   the server's `n_ctx`, named "loaded window".
Run: python -m tests.test_model_switch
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ.setdefault("BRIDGE_TEST_HOME", tempfile.mkdtemp(prefix="m0-switch-"))
os.environ.setdefault("BRIDGE_TEST_NO_BACKGROUND_NET", "1")

from tests.helpers.model_switch_rig import Rig, fill, ledger_lines, markers, png_file  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


@test
def test_model_to_a_smaller_ollama_model(ctx: Ctx):
    from halo_harness import events
    from halo_harness.providers.ollama_fit import resolve_ollama_tools_max
    with Rig() as rig:
        s = rig.session("ol:big:30b@lan")
        fill(s, 45)
        ref, profile, creds = rig.resolve("ol:small:9b@lan")
        evs = rig.run(s, [events.Command("set_model", {"model_ref": ref, "model_profile": profile, "creds": creds}),
                          events.Command("user_input", {"text": "and now?"})])
        lines = markers(evs)
        ctx.check(f"two switch lines (the plan, then the report), got {lines}", len(lines) == 2)
        ctx.check(f"the line before anything moves, got {lines[:1]}", lines and lines[0].startswith(
            "switching to ol:small:9b@lan: window 32,768 (learned cap); this conversation is ")
                  and lines[0].split(" · ")[0].endswith("tokens -> compacting to fit"))
        kinds = [(e.kind, e.data.get("state") or e.data.get("phase"), e.data.get("trigger")) for e in evs
                 if e.kind in ("turn_marker", "compaction")]
        first_line = kinds.index(("turn_marker", "switch", None))
        done = next(i for i, k in enumerate(kinds) if k == ("compaction", "done", "switch"))
        ctx.check(f"the compaction (trigger switch) runs after the line, got {kinds[:6]}", done > first_line)
        bodies = rig.chats()
        models = [b.get("model") for b in bodies]
        ctx.check(f"the summary is written by the model being left, before any call to the new one, got {models}",
                  models[0] == "big:30b" and "small:9b" in models and models.index("small:9b") > 0
                  and "small:9b" not in models[:models.index("small:9b")])
        first = rig.chats("small:9b")[0]
        num_ctx = (first.get("options") or {}).get("num_ctx")
        ctx.check(f"the first call fits the new window, got num_ctx {num_ctx}", isinstance(num_ctx, int) and num_ctx <= 32768)
        ctx.check(f"the session is on the new model with its window, got {s.model_ref.raw} {s.model_profile.context_tokens}",
                  s.model_ref.raw == "ol:small:9b@lan" and s.model_profile.context_tokens == 32768)
        node = next((n for n in s.log._nodes if n.get("type") == "model_switch"), None)
        rep = (node or {}).get("report") or {}
        ctx.check(f"a model_switch node with the report, got {sorted(rep)}", rep.get("to") == "ol:small:9b@lan"
                  and rep.get("from") == "ol:big:30b@lan" and rep.get("compacted") is True and rep.get("source") == "learned cap"
                  and rep.get("window") == 32768 and rep.get("prompt_after", 10 ** 9) <= rep.get("target_tokens", 0))
        ctx.check(f"the tool catalog's cap for the window's class, got {rep.get('tools_max')}",
                  rep.get("tools_max") == resolve_ollama_tools_max(32768))
        ctx.check(f"the report line names the tools and the reserve, got {lines[1:]}",
                  len(lines) > 1 and "compacted to" in lines[1] and f"tools {rep.get('tools_max')}" in lines[1] and "reply reserve" in lines[1])
        trig = [n.get("trigger") for n in s.log._nodes if n.get("type") == "compacted"]
        ctx.check(f"the log's compaction marker says switch, got {trig}", trig == ["switch"])
        led = [x for x in ledger_lines(rig.state_dir) if x.get("model") == "small:9b"]
        ctx.check(f"the first call to the new model: fitted, switched from the old one, got {led[:1]}",
                  led and led[0].get("fitted") is True and led[0].get("switched_from") == "big:30b")


@test
def test_a_model_without_vision_thinking_or_tools(ctx: Ctx):
    with Rig() as rig:
        s = rig.session("ol:big:30b@lan")
        s.log.append_user([{"type": "text", "text": "look at this"}, {"type": "image", "image_path": png_file(),
                                                                        "media_type": "image/png", "width": 1, "height": 1}])
        s.log.append_assistant(content=[{"type": "thinking", "thinking": "hm, an image", "signature": "sig"},
                                        {"type": "text", "text": "reading the file"},
                                        {"type": "tool_use", "id": "functions.Read:0", "name": "Read", "input": {"file_path": "a.txt"}}],
                               stop_reason="tool_use")
        s.log.append_tool_result(tool_use_id="functions.Read:0", content="hello from a.txt")
        s.log.append_assistant(content=[{"type": "text", "text": "it says hello"}], stop_reason="end_turn")
        from halo_harness.agent.model_switch import run_switch
        ref, profile, creds = rig.resolve("ol:notools:7b@lan")
        evs = list(run_switch(s, ref, profile, creds))
        rep = next(n for n in s.log._nodes if n.get("type") == "model_switch")["report"]
        ctx.check(f"what was converted, got {rep['converted']}", rep["converted"] == {"images": 1, "thinking": 1, "tools": 2})
        ctx.check(f"it fits, so nothing compacts, got {markers(evs)[:1]}", "fits (" in markers(evs)[0] and not rep["compacted"])
        ctx.check("no tools for a model that has none", rep["tools_max"] == 0 and "no tools (answers only)" in markers(evs)[1])
        from halo_harness import events
        rig.run(s, [events.Command("user_input", {"text": "what did it say?"})])
        body = rig.chats("notools:7b")[0]
        wire = json.dumps(body["messages"])
        ctx.check("no image goes to a model without vision; its caption does",
                  not any(m.get("images") for m in body["messages"]) and "[Image: " in wire and "this model takes no images" in wire)
        ctx.check("the thinking block is gone", "hm, an image" not in wire)
        ctx.check("the tool turns are text, no tool calls, no tools field", "[tool call: Read" in wire and "[result of Read: hello from a.txt]" in wire
                  and not any(m.get("tool_calls") for m in body["messages"]) and not body.get("tools"))
        ctx.check("the request ends on a user turn with text", body["messages"][-1]["role"] == "user"
                  and "what did it say?" in body["messages"][-1]["content"])


class _Props(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        path = self.path.rstrip("/")
        data = {"data": [{"id": "m"}]} if path.endswith("/v1/models") else ({"n_ctx": 8192} if path == "/props" else None)
        raw = json.dumps(data or {"error": "no"}).encode()
        self.send_response(200 if data else 404)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


@test
def test_ollama_to_a_local_server_answering_props(ctx: Ctx):
    srv = HTTPServer(("127.0.0.1", 0), _Props)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        with Rig() as rig:
            from halo_harness.theme import set_config_value
            set_config_value("huggingface.local_servers", [{"name": "box", "url": f"http://127.0.0.1:{srv.server_port}/v1"}])
            from halo_harness.providers.huggingface_local_resolve import reset_local_probe_cache
            reset_local_probe_cache()
            s = rig.session("ol:big:30b@lan")
            fill(s, 4)
            from halo_harness.agent.model_switch import plan
            from halo_harness.model import parse_model_ref
            rep = plan(s, parse_model_ref("hf:local/m@box"))
            ctx.check(f"the server's /props n_ctx is the window, named, got {rep['window']} {rep['source']}",
                      rep["window"] == 8192 and rep["source"] == "loaded window")
            ctx.check(f"a conversation past 80 % of it compacts first, got {rep['line']}",
                      rep["needs_compaction"] and rep["line"].startswith("switching to hf:local/m@box: window 8,192 (loaded window)")
                      and "effort: effort n/a" in rep["line"])
    finally:
        srv.shutdown()


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
