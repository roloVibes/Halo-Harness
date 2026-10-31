"""halo_harness.models_probe_hf -- `halo models probe hf:local/<model>[@server]` (Halo 3.3.7.0 R4): the battery's vision
probe on a Hugging Face local server (providers/battery_vision_hf.py). llama-server with a projector, LM Studio's vlm
models and MLX-VLM are asked with one 1 px image; any other server is "not asked" and says why. The profile is kept
where the model card reads its vision (providers/vision_fact.hf_profile).
"""

from __future__ import annotations

import json
import sys

COST = "one tiny call to {model} on {server} (one 1 px image, for the eyes), no cost"


def probe_hf(ref: str, *, as_json: bool, state_dir) -> int:
    from halo_harness.providers.battery_vision_hf import probe
    from halo_harness.providers.huggingface_local_resolve import resolve_local_server
    from halo_harness.providers.model_card_purpose import parse_ref
    from halo_harness.providers.vision_fact import line, vision_of
    r = parse_ref(ref)
    if getattr(r, "provider", "") != "huggingface" or not r.model:
        print(f"halo models probe: {ref!r} is not an hf:local/<model> or hf:mlx/<model> reference", file=sys.stderr)
        return 2
    srv = resolve_local_server(r.host, model=r.model, state_dir=state_dir)
    if srv is None:
        print(f"halo models probe: no Hugging Face local server answers for {ref} (halo local servers lists them)",
              file=sys.stderr)
        return 1
    kind = ("mlx-vlm" if "vl" in r.model.lower() else "mlx") if getattr(r, "mlx", False) else None
    if not as_json:
        print(COST.format(model=r.model, server=srv.name or srv.base_url))
    p = probe(srv.base_url, r.model, kind=kind, state_dir=state_dir, server=srv.name)
    if as_json:
        print(json.dumps(p, indent=2, default=str))
        return 0
    f = vision_of(profile=p)
    print(f"{r.model} on {srv.name or srv.base_url}: vision {p['vision']} -- {p['vision_why']}")
    print(f"  the card says: {line(f, ref)}")
    return 0
