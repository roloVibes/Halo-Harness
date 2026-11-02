"""halo_harness.doctor_voice -- `halo doctor --voice` (Halo 3.3.9.0 R1; docs/VOICE.md "Doctor"): what the speech side
of this machine has, one line each, files and imports only (no model loads, no request but each running speech
server's /health on loopback):

    the extra        the engines' packages importable, or the one install line
    each model       present (its folder) or the download line with its GB; a declared model says it has no engine
    the devices      CUDA visible to the engines (engines.devices()), or "CPU only (N cores)"
    the servers      `stt` / `tts` when Halo runs them: the model, the device, the url and its /health

    steps(state_dir) -> [{step, level (OK | WARN | INFO), line}]       lines(steps) -> the printed lines
"""

from __future__ import annotations

import os


def _s(step: str, level: str, line: str) -> dict:
    return {"step": step, "level": level, "line": line}


def steps(state_dir) -> list:
    from halo_harness.voice import INSTALL_LINE, catalog, engines, install
    out = []
    if engines.fake_on():
        out.append(_s("extra", "INFO", "the fake engine (HALO_VOICE_ENGINE=fake): the extra is not asked"))
    else:
        gone = engines.missing()
        out.append(_s("extra", "OK", "the speech engines are installed (faster-whisper, kokoro-onnx, onnxruntime)")
                   if not gone else _s("extra", "WARN", f"the speech engines are not installed ({', '.join(gone)} "
                                                         f"missing): {INSTALL_LINE}"))
    for r in catalog.ROWS:
        where = install.present(r)
        tail = "" if r.built else f"; {catalog.no_engine_line(r)}"
        if where is not None:
            out.append(_s(f"model {r.name}", "OK", f"{r.name} ({r.kind}) present: {where}{tail}"))
        else:
            out.append(_s(f"model {r.name}", "INFO", f"{r.name} ({r.kind}) not present -- halo voice download {r.name} "
                                                    f"({r.download_gb:g} GB){tail}"))
    seen = engines.devices()
    out.append(_s("devices", "OK", "CUDA visible to the engines" if "cuda" in seen else
                  f"CPU only ({os.cpu_count() or '?'} cores): the engines see no CUDA device"))
    out += _servers(state_dir)
    return out


def _servers(state_dir) -> list:
    from halo_harness.providers.local_server import servers
    from halo_harness.providers.local_server_cmd import get
    from halo_harness.voice import is_voice_runtime
    out = []
    for e in servers(state_dir):
        if not is_voice_runtime(e.get("kind")):
            continue
        url = f"http://127.0.0.1:{e.get('port')}"
        if not e.get("alive"):
            out.append(_s(f"server {e['id']}", "WARN", f"{e['id']}: {e.get('model')} -- its process is gone "
                                                     f"(halo local stop {e['id']} clears it)"))
            continue
        code, body = get(f"{url}/health", timeout=1.0)
        state = (body or {}).get("status") if isinstance(body, dict) else None
        out.append(_s(f"server {e['id']}", "OK" if code == 200 else "WARN",
                      f"{e['id']}: {e.get('model')} on {e.get('device')} at {url} -- /health {code or 'no answer'}"
                      + (f" ({state})" if state else "")))
    if not out:
        out.append(_s("servers", "INFO", "no speech server running (halo local serve --stt | --tts <model>)"))
    return out


def lines(rows: list) -> list:
    return [f"{r['level']:<4}  {r['line']}" for r in rows]


def cmd(as_json: bool = False) -> int:
    import json
    from halo_harness.config.paths import bridge_home
    rows = steps(bridge_home())
    if as_json:
        print(json.dumps(rows, indent=2))
        return 0
    print("halo doctor --voice")
    print("  The speech side of this machine: the engines, the speech models on disk, CUDA, the speech servers.")
    for line in lines(rows):
        print(f"  {line}")
    return 0
