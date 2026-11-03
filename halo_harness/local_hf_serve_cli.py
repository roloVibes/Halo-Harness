"""halo_harness.local_hf_serve_cli -- Halo 3.3.5.0 R5: `halo local serve <path> [--runtime llama-server|mlx]
[--window N] [--port P] [--keep] [--yes] [--backend B] [--json]` (local_hf_cli.py dispatches it). It prints each flag
with where it comes from (providers/local_server_cmd.plan_flags: the fit planner on this machine's card, the file's
trained context, the card's kv_cache_type, a steward profile), the command line, then the URL and the
`hf:local/<model>` ref the catalog lists it under. The model is a path `halo local ls` lists, any exact .gguf file or
model folder, a name `halo local --terminal` shows, or with `--runtime mlx` a Hugging Face repo id (the round 5f
`hf:mlx/<repo>` path). When no llama-server is found, `--yes` lets Halo fetch the pinned release (round 5c).
3.3.8.0 R3: `--pool <model>` runs a pool catalog model across the pool's members instead (pool_run_cli.serve_pool:
the preflight, the claims, each worker's rpc-server, llama-server --rpc ..., the `pool` entry).
3.3.9.0 R1: `--stt <model>` / `--tts <model>` [--device auto|cpu|cuda] runs Halo's speech server for a speech catalog
model instead (voice/launch.serve: the `stt` / `tts` server and its huggingface.local_servers entry).
3.3.9.1: `--runtime freetoken --model <checkpoint dir> [--lan]` runs FreeToken's `ft serve` (freetoken/launch.serve).
3.3.9.2: `--runtime strata --model <family>/<set>` (or `--model-path DIR`) `[--lan] [--plan]` runs Strata's `strata
launch` once its plan says nothing to download (strata/launch.serve); `--plan` prints Strata's own plan and the fit.
"""

from __future__ import annotations

import argparse
import json


def _resolve(model: str):
    from halo_harness.studio.local_hf_api import find
    raw = find(model)
    if raw is not None:
        return raw
    from halo_harness.providers.local_use import model_id_for_path, resolve_local_file
    e = resolve_local_file(model)
    if e is None:
        return None
    return {"path": e.path, "kind": e.format, "model": model_id_for_path(e.path, e.format), "size": e.size_bytes}


def cmd_serve(argv: list) -> int:
    from halo_harness.config.paths import background_net_disabled, bridge_home
    from halo_harness.local_cli import _confirm
    from halo_harness.providers import local_server as S
    from halo_harness.providers.local_server_cmd import binary, plan_flags, runtime_of
    p = argparse.ArgumentParser(prog="halo local serve", description="Start a local server (llama-server, or mlx_lm.server "
                                "on a Mac) for a model on disk, with the fit planner's window and layers.")
    p.add_argument("model", nargs="?", default=None, help="a path halo local ls lists, an exact .gguf file or model folder, a name halo local "
                   "--terminal shows, or with --runtime mlx a Hugging Face repo id")
    p.add_argument("--runtime", choices=("llama-server", "mlx", "mlx_lm", "freetoken", "strata"), default=None,
                   help="mlx: Apple Silicon only; freetoken: a Mixture-of-Experts checkpoint folder on Linux (FreeToken); "
                   "strata: a Strata set, <family>/<set> (Windows, Linux, the Mac)")
    p.add_argument("--model-path", default=None, help="with --runtime strata: the folder of a set's files you already have")
    p.add_argument("--plan", action="store_true", help="with --runtime strata: Strata's own plan and the fit; nothing starts")
    p.add_argument("--model", dest="model_opt", default=None, help="the model (the same as the positional one)")
    p.add_argument("--lan", action="store_true", help="with --runtime freetoken or strata: every address, behind a key")
    p.add_argument("--window", type=int, default=None, help="the window (-c); default: the planner's for this card")
    p.add_argument("--port", type=int, default=None, help="default: a free loopback port")
    p.add_argument("--keep", action="store_true", help="keep it running after the last Halo process on this home exits")
    p.add_argument("--yes", action="store_true", help="fetch the llama-server runtime without asking when none is found")
    p.add_argument("--backend", choices=("cuda", "vulkan", "cpu", "metal"), default=None,
                   help="which llama-server build to fetch (default: CUDA when the driver reports one, else Vulkan; Metal on macOS)")
    p.add_argument("--json", action="store_true")
    p.add_argument("--pool", action="store_true", help="the model is a pool catalog model: serve it across the pool")
    p.add_argument("--allow-wifi", action="store_true", help="with --pool: keep a Wi-Fi member (a slower decode)")
    p.add_argument("--stt", action="store_true", help="the model is a speech-to-text model of the speech catalog (halo "
                   "voice models): Halo's speech server serves it as `stt`")
    p.add_argument("--tts", action="store_true", help="the model is a text-to-speech model: Halo's speech server, `tts`")
    p.add_argument("--device", choices=("auto", "cpu", "cuda"), default=None,
                   help="with --stt / --tts: where it runs (default: voice.device, auto: CUDA when it fits)")
    a = p.parse_args(argv)
    a.model = a.model or a.model_opt
    if a.runtime == "strata":  # 3.3.9.2: strata/launch.py (docs/MODELS-strata.md "Serve")
        from halo_harness.strata.launch import serve as serve_st
        if not (a.model or a.model_path):
            p.error("name the set: halo local serve --runtime strata --model <family>/<set> (or --model-path DIR)")
        code, lines, row = serve_st(a.model, model_path=a.model_path, port=a.port, lan=a.lan, plan=a.plan)
        print(json.dumps({"code": code, "lines": lines, "server": row}, indent=2, default=str) if a.json else "\n".join(lines))
        return code
    if not a.model:
        p.error("name the model: halo local serve <model> (or --model <model>)")
    if a.runtime == "freetoken":  # 3.3.9.1: freetoken/launch.py (docs/MODELS-freetoken.md "Serve")
        from halo_harness.freetoken.launch import serve as serve_ft
        code, lines, row = serve_ft(a.model, port=a.port, keep=a.keep, lan=a.lan)
        print(json.dumps({"code": code, "lines": lines, "server": row}, indent=2, default=str) if a.json else "\n".join(lines))
        return code
    if a.stt or a.tts:  # 3.3.9.0 R1: voice/launch.py (docs/VOICE.md "Serve")
        from halo_harness.voice.launch import serve as serve_speech
        code, lines, row = serve_speech("stt" if a.stt else "tts", a.model, device=a.device, port=a.port, keep=a.keep)
        print(json.dumps({"code": code, "lines": lines, "server": row}, indent=2, default=str) if a.json else "\n".join(lines))
        return code
    if a.pool:
        from halo_harness.pool_run_cli import serve_pool
        return serve_pool(a.model, window=a.window, keep=a.keep, allow_wifi=a.allow_wifi or None, as_json=a.json)
    raw = _resolve(a.model)
    if raw is None:
        if a.runtime in ("mlx", "mlx_lm") and "/" in a.model:
            from halo_harness.providers.local_use import serve_local_model
            ok, lines = serve_local_model(a.model, runtime="mlx_lm", port=a.port, keep=a.keep,
                                          confirm=lambda q: _confirm(q, yes=a.yes))
            print("\n".join(lines))
            return 0 if ok else 1
        print(f"no model on disk at or named {a.model!r}: halo local ls lists them (halo local add a folder first)")
        return 1
    runtime = runtime_of(raw["kind"], a.runtime)
    flags = plan_flags(raw["path"], raw["kind"], model=raw["model"], window=a.window)
    if not a.json:
        print(f"{raw['path']} ({raw['kind']}, served as hf:local/{raw['model']}):")
        for k, flag in (("window", "-c"), ("ngl", "-ngl"), ("parallel", "-np"), ("kv_type", "--cache-type-k/v"),
                        ("flash_attn", "--flash-attn"), ("num_predict", "-n")):
            v = flags[k]
            shown = "on" if v is True else "-" if v in (None, False) else f"{v:,}" if isinstance(v, int) else v
            print(f"  {flag:<17} {shown:<8} {flags['sources'].get(k, '')}")
        for n in flags["notes"]:
            print(f"  note: {n}")
    prefix, why = binary(runtime, state_dir=bridge_home())
    if prefix is None and runtime == "llama-server" and not background_net_disabled():
        from halo_harness.providers.local_use import ensure_llama_server_binary
        prefix, lines = ensure_llama_server_binary(state_dir=bridge_home(), confirm=lambda q: _confirm(q, yes=a.yes),
                                                   backend_override=a.backend)
        print("\n".join(lines))
        why = "the runtime Halo fetched" if prefix else why
    if prefix is None:
        print(why)
        return 1
    info = S.start(raw["path"], runtime=runtime, port=a.port or 0, window=flags["window"], ngl=flags["ngl"],
                   parallel=flags["parallel"], kv_type=flags["kv_type"], flash_attn=flags["flash_attn"],
                   num_predict=flags["num_predict"], model=raw["model"], keep=a.keep, state_dir=bridge_home(),
                   sources={**flags["sources"], "binary": why}, prefix=prefix)
    if a.json:
        print(json.dumps({**S.view(info), "notes": flags["notes"]}, indent=2, default=str))
        return 0 if info.ok else 1
    print("  " + " ".join(info.argv))
    print(info.say)
    if info.ok:
        print(f"  {info.url}  (OpenAI dialect at {info.url}/v1)  use it as hf:local/{info.model}")
        print(f"  halo local log {info.id}   halo local stop {info.id}")
        if not a.keep:
            print("  it stops when the last Halo process on this home exits (--keep keeps it running)")
    return 0 if info.ok else 1
