"""halo_harness.voice.server -- Halo's own speech server (Halo 3.3.9.0 R1; docs/VOICE.md "The server"):

    python -m halo_harness.voice.server --model <catalog name> [--kind stt|tts] [--device auto|cpu|cuda]
        [--path <model folder>] [--port 0] [--host 127.0.0.1] [--log <file>] [--voice af_heart] [--gpu-free-mib N]

It binds the port (0: a free one), prints `listening on 127.0.0.1:<port>`, loads the model through the engine seam
(voice/engines.py; `/health` answers 503 while it loads) and serves the OpenAI audio routes (voice/server_routes.py)
with stdlib http.server and a thread per request. Its log (`--log`, else stdout) holds one line per load and per
request (voice/log_lines.py), the lines the steward reads. `halo local serve --stt | --tts` runs it as a managed
subprocess (voice/launch.py); `halo voice serve` runs it in the foreground. Exit 2: nothing to serve (a declared
model with no engine, the extra not installed -- the one install line --, the model not on disk); exit 1: the load
failed (its error is the log's `voice load failed:` line).
"""

from __future__ import annotations

import argparse
import sys
import threading
import time
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Optional

from halo_harness.voice import log_lines as L


class _Http(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = False


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="halo voice serve", description="Serve one speech model (OpenAI's audio routes) on "
                                "a loopback port.")
    p.add_argument("--model", required=True, help="a speech catalog name (halo voice models)")
    p.add_argument("--kind", choices=("stt", "tts"), default=None, help="default: the catalog row's")
    p.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto", help="auto: CUDA when the engines see it")
    p.add_argument("--path", default=None, help="the model's folder (default: where halo voice download put it)")
    p.add_argument("--port", type=int, default=0, help="0: a free port")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--log", default=None, help="the log file (default: stdout)")
    p.add_argument("--voice", default=None, help="the TTS voice a request names none of (default: voice.tts_voice)")
    p.add_argument("--gpu-free-mib", type=int, default=None, help="the GPU's free MiB the launcher read (its log line)")
    return p


def _voice(asked: Optional[str]) -> str:
    if asked:
        return asked
    try:
        from halo_harness.theme import get_config_value
        return str(get_config_value("voice.tts_voice", default=None) or "af_heart")
    except Exception:
        return "af_heart"


def main(argv: Optional[list] = None) -> int:
    from halo_harness.voice import catalog, engines
    from halo_harness.voice.install import present
    from halo_harness.voice.server_routes import State, make_handler
    a = _parser().parse_args(argv)
    row = catalog.get(a.model)
    if row is None:
        print(f"{a.model} is not in the speech catalog: halo voice models lists them", flush=True)
        return 2
    kind = a.kind or row.kind
    if kind != row.kind or kind not in ("stt", "tts"):
        print(f"{row.name} is a {row.kind.upper()} model, not {kind.upper()}", flush=True)
        return 2
    if not row.built:  # a declared model is never served, not even by the fake engine
        print(catalog.no_engine_line(row), flush=True)
        return 2
    gone = engines.missing(row.engine)
    if gone:
        print(str(engines.ExtraMissing(gone)), flush=True)
        return 2
    path = Path(a.path) if a.path else present(row)
    if path is None and not engines.fake_on():
        print(f"{row.name} is not present -- halo voice download {row.name} ({row.download_gb:g} GB)", flush=True)
        return 2
    device = a.device if a.device != "auto" else ("cuda" if "cuda" in engines.devices() else "cpu")
    out = open(a.log, "a", encoding="utf-8", buffering=1) if a.log else sys.stdout

    def say(line: str) -> None:
        try:
            out.write(f"{line}\n")
            out.flush()
        except (OSError, ValueError):
            pass

    st = State(kind, row.name, device, say, _voice(a.voice))
    httpd = _Http((a.host, int(a.port or 0)), make_handler(st))
    port = httpd.server_address[1]
    print(f"listening on {a.host}:{port}", flush=True)
    say(L.listening(f"http://{a.host}:{port}", kind, row.name))
    threading.Thread(target=httpd.serve_forever, name="voice-http", daemon=True).start()
    t0 = time.monotonic()
    try:
        st.engine = engines.load(row, device, path or Path("."))
    except engines.ExtraMissing as e:
        st.status, st.error = "failed", str(e)
        say(L.load_failed(kind, row.name, device, str(e)))
        print(str(e), flush=True)
        httpd.shutdown()
        return 2
    except Exception as e:
        st.status, st.error = "failed", f"{type(e).__name__}: {e}"
        say(L.load_failed(kind, row.name, device, st.error))
        httpd.shutdown()
        return 1
    st.status = "ok"
    say(L.loaded(kind, row.name, device, st.engine.compute, time.monotonic() - t0, a.gpu_free_mib))
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        httpd.shutdown()
        return 0


if __name__ == "__main__":
    sys.exit(main())
