"""halo_harness.ollama_steward.rules_tensorfold -- the steward watches a TensorFold server (Halo 3.3.9.3; docs/MODELS-
steward-servers.md "TensorFold"; knowledge/local-servers.md "## TensorFold"). The events are TensorFold's own log lines
(server_log_tensorfold.py) and its queue from `/health` / `/metrics` (server_stats_tensorfold.py), from the source,
unverified against a live run; one finding per rule and group, keyed `<server>|<model>`, each with `server`, `runtime`
(tensorfold) and a stated fix line -- never applied by itself.

    tf-waiting           requests queue past the streams TensorFold accepted at startup ("N streams at once"): the
                         queue read waiting > 0, or replies that waited QUEUE_S or more before their first round --
                         `--parallel` (when memory holds more streams: TensorFold refuses a count that does not fit) or
                         a smaller model, and at most that many of Halo's lanes on this server at once
    tf-backend-fallback  an NVFP4 checkpoint on a CUDA card without thread-block clusters (sm_80 to sm_89: RTX 30 / 40,
                         A100, L40) runs TensorFold's fallback path: slower -- the MLX 4-bit checkpoint of the model, or
                         a card of sm_90 and later
    tf-load              the load of a large checkpoint takes minutes (TensorFold opens its port only once it is in
                         memory): a load still going LOAD_SAY_S after Halo started it, or a load that took over three
                         minutes -- said, never a timeout; a restart costs it again

    tensorfold_rules(ctx) -> [finding]
"""

from __future__ import annotations

from halo_harness.ollama_steward.rules import finding, hint

QUEUE_S = 1.0
RECENT = 8
LOAD_SAY_S = 60.0


def _tag(f: dict, g: dict) -> dict:
    from halo_harness.ollama_steward.server_rules_hf import not_asked
    f.update(server=g.get("server") or g["host"], runtime="tensorfold", not_asked=not_asked("tensorfold"), applied=False)
    return f


def _of(g: dict, kind: str) -> list:
    return [e for e in g["events"] if e.get("kind") == kind]


def _d(e: dict) -> dict:
    return e.get("data") or {}


def _streams(g: dict):
    for e in reversed(_of(g, "load-result") + _of(g, "capacity")):
        if isinstance(_d(e).get("streams"), int):
            return _d(e)["streams"]
    lanes = [_d(e).get("lanes") for e in _of(g, "queue") if isinstance(_d(e).get("lanes"), int)]
    return lanes[-1] if lanes else None


def waiting(g: dict, ctx: dict) -> list:
    queues = [e for e in _of(g, "queue") if int(_d(e).get("waiting") or 0) > 0]
    timed = [e for e in _of(g, "timing") if isinstance(_d(e).get("queued_s"), (int, float))][-RECENT:]
    slow = [e for e in timed if _d(e)["queued_s"] >= QUEUE_S]
    if not queues and len(slow) < 2:
        return []
    who, n = g.get("server") or g["host"], _streams(g)
    most = max((int(_d(e)["waiting"]) for e in queues), default=0)
    longest = max((float(_d(e)["queued_s"]) for e in slow), default=0.0)
    text = (f"{g['model']} on {who}: requests queue past the {n if n else 'accepted'} stream{'s' if n != 1 else ''} "
            "TensorFold runs at once" + (f" (up to {most} waiting)" if most else "")
            + (f"; {len(slow)} of the newest {len(timed)} replies waited up to {longest:g} s" if slow else "")
            + " -- `--parallel` with more streams if memory holds them (TensorFold refuses a count that does not fit), "
            "or a smaller model; at most " + (f"{n}" if n else "that many") + " of Halo's lanes on this server at once")
    nums = {"streams": n, "most_waiting": most or None, "queued_replies": len(slow), "longest_queue_s": longest or None,
            "source": _d(queues[-1]).get("source") if queues else "the done lines"}
    more = (n or 1) * 2
    line = f"halo local stop {who}, then halo local serve --runtime tensorfold --model {g['model']} --parallel {more}"
    return [_tag(finding("tf-waiting", g, "warn", text, events=(queues + slow)[-8:], numbers=nums,
                         server_hint=hint(None, line, "each stream takes memory from the window; a count that does "
                                                      "not fit is refused at startup")), g)]


def fallback(g: dict, ctx: dict) -> list:
    loads = _of(g, "load-result") + _of(g, "capacity")
    last = next((e for e in reversed(loads) if _d(e).get("backend") == "cuda"), None)
    sm = _d(last).get("sm") if last else None
    if not (isinstance(sm, int) and 80 <= sm <= 89):
        return []
    from halo_harness.tensorfold.catalog import match
    row = match(g["model"])
    if not ("nvfp4" in str(g["model"]).lower() or (row and row.get("nvfp4"))):
        return []
    who, dev = g.get("server") or g["host"], _d(last).get("device") or f"an sm_{sm} card"
    text = (f"{g['model']} on {who}: an NVFP4 checkpoint on {dev} (sm_{sm}, no thread-block clusters) runs "
            "TensorFold's fallback path, slower -- the model's MLX 4-bit checkpoint, or a card of sm_90 and later")
    return [_tag(finding("tf-backend-fallback", g, "warn", text, events=[last], numbers={"sm": sm, "device": dev},
                         server_hint=hint(None, f"halo models browse --source hf tensorfold (an MLX 4-bit row of {g['model']})",
                                          "another download (its GB said), or a newer card")), g)]


def load(g: dict, ctx: dict) -> list:
    from halo_harness.ollama_steward.ledger import parse_at
    who = g.get("server") or g["host"]
    starts, loads = _of(g, "load-start"), _of(g, "load-result")
    last_start = parse_at(starts[-1].get("at")) if starts else None
    last_load = parse_at(loads[-1].get("at")) if loads else None
    now = ctx.get("now") or 0
    if last_start and (last_load is None or last_load < last_start) and now - last_start >= LOAD_SAY_S:
        took = now - last_start
        text = (f"{g['model']} on {who}: TensorFold has been loading for {took:.0f} s -- it opens its port once the "
                "whole checkpoint is in memory (a 70 GiB one takes minutes); not a timeout: halo local log "
                f"{who} shows its startup lines")
        return [_tag(finding("tf-load", g, "info", text, events=starts[-1:], numbers={"loading_s": round(took),
                                                                                      "done": False}), g)]
    slow = [e for e in loads if isinstance(_d(e).get("load_s"), (int, float)) and _d(e)["load_s"] > 180]
    if not slow:
        return []
    s = float(_d(slow[-1])["load_s"])
    gib = _d(slow[-1]).get("model_gib")
    text = (f"{g['model']} on {who}: the load took {s:.0f} s" + (f" for {gib:g} GiB" if gib else "")
            + " -- TensorFold reads the whole checkpoint into memory before it serves; a restart (another model, a new "
            "--parallel) costs that again, so placement counts it as the loading tax")
    return [_tag(finding("tf-load", g, "info", text, events=slow[-1:], numbers={"load_s": round(s), "model_gib": gib,
                                                                                "done": True}), g)]


def tensorfold_rules(ctx: dict) -> list:
    out: list = []
    for g in ctx.get("groups") or []:
        if g.get("runtime") == "tensorfold":
            out += waiting(g, ctx) + fallback(g, ctx) + load(g, ctx)
    return out
