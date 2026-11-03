"""tests.helpers.fake_strata -- Halo 3.3.9.2: a stand-in for Strata's `strata` that loads no model, needs no GPU and
downloads nothing. The tests set `huggingface.strata_bin` to [python, this file] (tests/helpers/st_home.StHome); Halo
runs it exactly as it runs the real one. Its state (the launches it serves) lives in FAKE_STRATA_STATE, a scratch
folder, as Strata's own lives in its state folder:

    strata --version                     "strata 0.2.10 (build fake; python ... at ...)" (strata_cli/cli.py's wording)
    strata launch ... --plan [--output json]   the plan, human or {"plan": {model, download: {gb, engine_missing,
        text}}}; FAKE_STRATA_DOWNLOAD_GB (default 0) and FAKE_STRATA_ENGINE_MISSING=1 say what would download
    strata launch --family F --model S | --model-path D --yes --no-tui --access A --port P --api-key-env NAME
        prints the launch's lines (FAKE_STRATA_ENGINE_PCT: an engine download's progress first), starts the server in
        a process of its own (as Strata's supervisor does: it outlives the launch), waits for its /health, prints
        "Strata is serving.", the addresses and "Engine log ...", and returns 0; FAKE_STRATA_LAUNCH_S delays the
        serving (a launch still loading); FAKE_STRATA_NO_ENGINE=1: "Strata couldn't find an engine ...", nothing served
    strata launch --status --output json   {"schema_version": 1, "ok": true, "running": [{name, profile, state, port, url}]}
    strata launch --stop --preset NAME   ends that server: "Stopped NAME."
    serve (internal)                     127.0.0.1:P only: GET /health {"status": "ok", ..., "loaded": true, "service":
        "strata"}; GET /v1/models (the key) one row {id, object, status, meta: {n_ctx}, architecture}; POST
        /v1/chat/completions an OpenAI reply with `usage`; the narrator's lines, `ready:`, and one `done:` line per
        request go to <state>/runtime/launch-<name>.server.log, the engine's request line to <state>/launch/<name>.
        engine.log. FAKE_STRATA_MODE (ram | mapped), FAKE_STRATA_TOK_S (42.0), FAKE_STRATA_HIT (81.2),
        FAKE_STRATA_PARALLEL ("4:2": asked, runs) shape them.
Its lines are tests/helpers/st_lines.py's (Strata's own wording, from the source, unverified).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import st_lines as L  # noqa: E402

MODEL_ID = "qwen3.8-flash-next"  # serve/server.py's default model name (from the source, unverified)


def _arg(argv: list, name: str, default=None):
    return argv[argv.index(name) + 1] if name in argv and argv.index(name) + 1 < len(argv) else default


def _state() -> Path:
    p = Path(os.environ.get("FAKE_STRATA_STATE") or Path.cwd() / "fake-strata-state")
    p.mkdir(parents=True, exist_ok=True)
    return p


def _runs() -> dict:
    try:
        return json.loads((_state() / "runs.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _save(runs: dict) -> None:
    (_state() / "runs.json").write_text(json.dumps(runs), encoding="utf-8")


def _alive(pid) -> bool:
    try:
        if os.name == "nt":
            out = subprocess.run(["tasklist", "/FI", f"PID eq {int(pid)}", "/NH"], capture_output=True, text=True).stdout
            return str(int(pid)) in out
        os.kill(int(pid), 0)
        return True
    except (OSError, ValueError, TypeError):
        return False


def kill(pid) -> None:
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/F", "/PID", str(int(pid))], capture_output=True)
        else:
            os.kill(int(pid), 9)
    except (OSError, ValueError, TypeError):
        pass


def _name(argv: list) -> str:
    what = _arg(argv, "--model") or Path(str(_arg(argv, "--model-path", "model"))).name
    return f"{what.lower().replace('_', '-')}-32k"


def plan(argv: list) -> int:
    gb = float(os.environ.get("FAKE_STRATA_DOWNLOAD_GB") or 0)
    engine = os.environ.get("FAKE_STRATA_ENGINE_MISSING") == "1"
    text = "Nothing to download: the model is already on this computer." if gb < 0.05 else (
        f"About {gb:.1f} GB to download: the model files ({gb:.1f} GB).")
    if "--output" in argv:
        print(json.dumps({"schema_version": 1, "ok": True, "plan": {
            "model": {"family": _arg(argv, "--family"), "model": _arg(argv, "--model"), "model_gb": 76.0},
            "download": {"gb": gb, "parts": [], "engine_missing": engine, "text": text}}}))
        return 0
    print(f"Plan for '{_name(argv)}':\n  model     {_arg(argv, '--family')} {_arg(argv, '--model')}, 76 GB\n"
          f"  context   32K    pictures off    parallel fit to your card\n  download  {text}\nNothing was changed.")
    return 0


def launch(argv: list) -> int:
    if "--plan" in argv:
        return plan(argv)
    if "--status" in argv:
        runs = {k: v for k, v in _runs().items() if _alive(v["pid"])}
        print(json.dumps({"schema_version": 1, "ok": True, "running": [
            {"name": k, "profile": f"launch-{k}", "state": "ready", "port": v["port"], "url": f"http://127.0.0.1:{v['port']}",
             "host": "127.0.0.1", "config": None} for k, v in runs.items()]}))
        return 0
    if "--stop" in argv:
        name, runs = _arg(argv, "--preset"), _runs()
        hit = runs.pop(name, None)
        if hit:
            kill(hit["pid"])
        _save(runs)
        print(f"Stopped {name}." if hit else "Nothing from `strata launch` is running.")
        return 0
    say = lambda s: print(s, flush=True)  # noqa: E731
    if os.environ.get("FAKE_STRATA_ENGINE_PCT"):
        say(L.engine_download(int(os.environ["FAKE_STRATA_ENGINE_PCT"])))
    if os.environ.get("FAKE_STRATA_NO_ENGINE") == "1":
        say(L.no_engine())
        return 0
    port, name, st = int(_arg(argv, "--port", "8080")), _name(argv), _state()
    for d in ("runtime", "launch"):
        (st / d).mkdir(exist_ok=True)
    log = st / "runtime" / f"launch-{name}.server.log"
    env = {**os.environ, "FAKE_STRATA_KEY": os.environ.get(_arg(argv, "--api-key-env", "") or "_none_", "")}
    flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    with open(log, "ab") as out:
        proc = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "serve", "--port", str(port), "--name", name],
                                stdout=out, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, env=env,
                                creationflags=flags, start_new_session=os.name != "nt")
    runs = _runs()
    runs[name] = {"pid": proc.pid, "port": port}
    _save(runs)
    say("    Loading the model… 0 s")
    end = time.monotonic() + 30
    while time.monotonic() < end:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=1) as r:
                if json.loads(r.read()).get("loaded"):
                    break
        except OSError:
            time.sleep(0.1)
    say("")
    say("Strata is serving.")
    say(f"  {'This computer':<14} http://127.0.0.1:{port}/v1")
    say(f"  {'Anthropic apps':<14} http://127.0.0.1:{port}   (Claude Code: ANTHROPIC_BASE_URL, no /v1 at the end)")
    say(f"  {'Engine log':<14} {st / 'launch' / (name + '.engine.log')}   (follow it: strata logs --follow)")
    return 0


def serve(argv: list) -> int:
    port, name, st = int(_arg(argv, "--port")), _arg(argv, "--name"), _state()
    key, ctx = os.environ.get("FAKE_STRATA_KEY") or "", 32768
    engine_log = st / "launch" / f"{name}.engine.log"
    tok_s, hit = float(os.environ.get("FAKE_STRATA_TOK_S") or 42.0), float(os.environ.get("FAKE_STRATA_HIT") or 81.2)
    say = lambda s: print(s, flush=True)  # noqa: E731
    say(L.starting())
    say(L.experts(os.environ.get("FAKE_STRATA_MODE") or "ram"))
    loaded = threading.Event()

    class H(BaseHTTPRequestHandler):
        def log_message(self, *_a):
            pass

        def _json(self, code, obj):
            body = json.dumps(obj).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _keyed(self) -> bool:
            return not key or self.headers.get("Authorization") == f"Bearer {key}" or self.headers.get("x-api-key") == key

        def do_GET(self):  # noqa: N802
            if self.path in ("/health", "/api/health"):
                return self._json(200, {"status": "ok", "max_context": ctx, "model": MODEL_ID, "images": False,
                                        "api_key": bool(key), "image_generation": False, "loaded": loaded.is_set(),
                                        "service": "strata"})
            if not self._keyed():
                return self._json(401, {"error": {"message": "invalid API key"}})
            if self.path.rstrip("/") in ("/v1/models", "/models"):
                return self._json(200, {"object": "list", "data": [
                    {"id": MODEL_ID, "object": "model", "status": {"value": "loaded"}, "meta": {"n_ctx": ctx},
                     "architecture": {"input_modalities": ["text"], "output_modalities": ["text"]}}]})
            return self._json(404, {"error": {"message": "not found"}})

        def do_POST(self):  # noqa: N802
            n = int(self.headers.get("Content-Length") or 0)
            try:
                body = json.loads(self.rfile.read(n) or b"{}")
            except ValueError:
                body = {}
            if not self._keyed():
                return self._json(401, {"error": {"message": "invalid API key"}})
            if self.path.rstrip("/") != "/v1/chat/completions":
                return self._json(404, {"error": {"message": "not found"}})
            text = " ".join(str(m.get("content") or "") for m in body.get("messages") or [] if isinstance(m, dict))
            p_tok, want = max(1, len(text) // 4), int(body.get("max_tokens") or 16)
            out = min(want, 120)
            time.sleep(0.05)  # a reply takes time: the bench's rate needs a clock that moved (Windows ticks ~15 ms)
            with open(engine_log, "a", encoding="utf-8") as f:
                f.write(L.engine_request(p_tok, 0, 900.0, out, tok_s) + "\n")
            say(L.done(out, 1, tok_s, hit))
            return self._json(200, {"id": "chatcmpl-fake", "object": "chat.completion", "model": MODEL_ID, "choices": [
                {"index": 0, "message": {"role": "assistant", "content": "ready " * out},
                 "finish_reason": "length" if out >= want else "stop"}],
                "usage": {"prompt_tokens": p_tok, "completion_tokens": out, "total_tokens": p_tok + out}})

    srv = ThreadingHTTPServer(("127.0.0.1", port), H)
    srv.daemon_threads = True
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    time.sleep(float(os.environ.get("FAKE_STRATA_LAUNCH_S") or 0.1))
    say(L.loaded(31))
    par = os.environ.get("FAKE_STRATA_PARALLEL")
    if par:
        asked, runs = (int(x) for x in par.split(":"))
        say(L.parallel(asked, runs))
    say(L.ready(port, ctx, key=bool(key)))
    loaded.set()
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        return 0


def main(argv: list) -> int:
    if argv[:1] in (["--version"], ["-V"]):
        print(f"strata 0.2.10 (build fake; python {sys.version.split()[0]} at {sys.executable})")
        return 0
    if argv[:1] == ["launch"]:
        return launch(argv[1:])
    if argv[:1] == ["serve"]:
        return serve(argv[1:])
    print(f"unknown strata command: {' '.join(argv[:1])}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
