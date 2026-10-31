"""halo_harness.local_hf_serve_cli -- Halo 3.3.5.0 R5: `halo local serve <path> [--runtime llama-server|mlx]
[--window N] [--port P] [--keep] [--yes] [--backend B] [--json]` (local_hf_cli.py dispatches it). It prints each flag
with where it comes from (providers/local_server_cmd.plan_flags: the fit planner on this machine's card, the file's
trained context, the card's kv_cache_type, a steward profile), the command line, then the URL and the
`hf:local/<model>` ref the catalog lists it under. The model is a path `halo local ls` lists, any exact .gguf file or
model folder, a name `halo local --terminal` shows, or with `--runtime mlx` a Hugging Face repo id (the round 5f
`hf:mlx/<repo>` path). When no llama-server is found, `--yes` lets Halo fetch the pinned release (round 5c).
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
    p.add_argument("model", help="a path halo local ls lists, an exact .gguf file or model folder, a name halo local "
                   "--terminal shows, or with --runtime mlx a Hugging Face repo id")
    p.add_argument("--runtime", choices=("llama-server", "mlx", "mlx_lm"), default=None, help="mlx: Apple Silicon only")
    p.add_argument("--window", type=int, default=None, help="the window (-c); default: the planner's for this card")
    p.add_argument("--port", type=int, default=None, help="default: a free loopback port")
    p.add_argument("--keep", action="store_true", help="keep it running after the last Halo process on this home exits")
    p.add_argument("--yes", action="store_true", help="fetch the llama-server runtime without asking when none is found")
    p.add_argument("--backend", choices=("cuda", "vulkan", "cpu", "metal"), default=None,
                   help="which llama-server build to fetch (default: CUDA when the driver reports one, else Vulkan; Metal on macOS)")
    p.add_argument("--json", action="store_true")
    a = p.parse_args(argv)
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
