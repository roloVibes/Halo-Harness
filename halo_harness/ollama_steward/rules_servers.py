"""halo_harness.ollama_steward.rules_servers -- Halo 3.3.8.0 R2: the steward's rules for a local server (llama-server,
LM Studio, mlx_lm.server), the same findings as an Ollama host's, keyed `<server>|<model>`, each with `server` and
`runtime` on it:

    prepare(ctx, servers=None)   rules.gather's last step: the groups whose host is a server get `server`,
                                 `server_obj`, `runtime`, the OpenAI-dialect stats and, as the cap, the server's
                                 window per slot (its log's `n_ctx_slot`, LM Studio's loaded context length)
    RULES                        run on those groups instead of the Ollama window rules

- `window-small`: prompts the server cut, shifted or refused (its log), 400s for the context, or a p95 prompt within
  10 % of its window -> Halo's window for that model set to the server's window per slot (compaction keeps the prompt
  under it), and the server's own line said: `--ctx-size N` / LM Studio's Context Length (tune_lines_hf.py);
- `reply-cut`, `cut-resent`: rules_reply's, with the server's `--n-predict` said when its own limit cut the reply;
- `cpu-spill`: layers the server left on the CPU -> `--n-gpu-layers N` / LM Studio's GPU Offload, said;
- `tools-heavy`: the tool catalog is over a third of prompts that outgrow the window -> a tool budget (`tools_max`).

A kind the runtime's log never prints (server_rules_hf.not_asked) is listed on each finding as `not_asked`: the rule
did not see it, it was not asked. Nothing here changes a server; every server line carries `applied: false`.
"""

from __future__ import annotations

from statistics import median
from typing import Optional

from halo_harness.ollama_steward.rules import finding, proposal

NEAR = 0.9
HEAVY = 0.35
TOOLS_FLOOR = 6


def _pow2_ceil(n: int) -> int:
    p = 1
    while p < n:
        p *= 2
    return p


def _load(g: dict) -> dict:
    rows = [e for e in g["events"] if e.get("kind") == "load-result" and (e.get("data") or {}).get("window")]
    if rows:
        return dict(rows[-1].get("data") or {})
    rows = [e for e in g["events"] if (e.get("data") or {}).get("window")]
    return {"window": (rows[-1].get("data") or {}).get("window")} if rows else {}


def stats(g: dict) -> dict:
    from halo_harness.ollama_steward.traffic import percentile
    lines = [x for x in g["lines"] if x.get("kind") != "calibrate"]
    ok = [x for x in lines if x.get("status") == 200 and isinstance(x.get("prompt_eval_count"), int)]
    refused = [x for x in lines if x.get("status") == 400 and "context" in str(x.get("error") or "").lower()]
    prompts = [x["prompt_eval_count"] for x in ok]
    window = g["profile"].get("num_ctx") or _load(g).get("window")
    return {"calls": len(lines), "native": lines, "ok": ok, "window": window, "windows": {},
            "p50": percentile(prompts, 50), "p95": percentile(prompts, 95), "max_prompt": max(prompts, default=None),
            "trims": [x for x in lines if x.get("trimmed") and x.get("preflight") != "sent"] + refused,
            "cuts": [x for x in lines if x.get("done_reason") == "length"], "reloads": [],
            "eval_p50": percentile([x.get("eval_tok_s") for x in lines if not x.get("warming")], 50)}


def prepare(ctx: dict, servers: Optional[list] = None) -> None:
    from halo_harness.ollama_steward.servers_hf import roster
    if servers is None:
        try:
            servers = roster(ctx.get("state_dir"))
        except Exception:
            servers = []
    ctx["servers"] = list(servers)
    by = {s.name.lower(): s for s in servers}
    for g in ctx["groups"]:
        s = by.get(str(g["host"]).lower())
        if s is None:
            continue
        g.update(server=s.name, server_obj=s, runtime=s.runtime or "llama-server")
        g["stats"] = stats(g)
        win = _load(g).get("window")
        g["cap"], g["cap_source"] = (win, "the server's window per slot") if win else (None, "unknown")


def _tag(f: dict, g: dict) -> dict:
    from halo_harness.ollama_steward.server_rules_hf import not_asked
    f.update(server=g["server"], runtime=g["runtime"], not_asked=not_asked(g["runtime"]))
    return f


def window_small(g: dict, ctx: dict) -> list:
    from halo_harness.ollama_steward.rules_window import chosen_cut
    from halo_harness.ollama_steward.tune_lines_hf import hint, line
    s, ld = g["stats"], _load(g)
    win = ld.get("window")
    evs = [e for e in g["events"] if e.get("kind") == "prompt-trimmed" and not chosen_cut(g, e)]
    near = bool(win and s["p95"] is not None and s["p95"] >= NEAR * win)
    if not (evs or s["trims"] or near):
        return []
    slots = ld.get("n_slots") or 1
    want = _pow2_ceil(max(2 * win, int((s["p95"] or 0) * 1.25) + 4096)) if win else None
    stated = line(g["server_obj"], "ctx-size", want * slots, was=ld.get("n_ctx") or win * slots) if want else None
    prof = g["profile"].get("num_ctx")
    prop = (proposal("num_ctx", prof, win, f"the server holds {win:,} per slot: compaction keeps the prompt under it")
            if win and (not prof or prof > win) else None)
    why = (f"{len(evs)} prompts cut, shifted or refused by the server" + (f", {len(s['trims'])} refused calls" if s["trims"] else "")
           + (f", p95 prompt {s['p95']:.0f} of {win}" if near else ""))
    text = (f"{g['model']} on {g['server']} ({g['runtime']}): the server's window "
            + (f"{win:,} per slot" if win else "(not in its log)") + f" is too small: {why}")
    return [_tag(finding("window-small", g, "warn", text, calls=s["trims"][:8], events=evs,
                         numbers={"window": win, "slots": slots, "p95_prompt": s["p95"], "trims": len(evs) + len(s["trims"])},
                         proposal=prop, server_hint=hint(stated), stated=[stated] if stated else []), g)]


def replies(g: dict, ctx: dict) -> list:
    from halo_harness.ollama_steward.rules_reply import cut_resent, replies_cut
    from halo_harness.ollama_steward.tune_lines_hf import hint, line
    out = replies_cut(g, ctx) + cut_resent(g, ctx)
    limited = [e for e in g["events"] if e.get("kind") == "reply-cut" and isinstance((e.get("data") or {}).get("n_predict"), int)
               and e["data"]["n_predict"] > 0]
    for f in out:
        if limited and f["rule"] == "reply-cut" and not f.get("server_hint"):
            stated = line(g["server_obj"], "n-predict", -1, was=limited[-1]["data"]["n_predict"])
            f.update(server_hint=hint(stated), stated=[stated] if stated else [])
            f["finding"] += f" (the server's own --n-predict {limited[-1]['data']['n_predict']} cut it)"
        _tag(f, g)
    return out


def spilled(g: dict, ctx: dict) -> list:
    from halo_harness.ollama_steward.tune_lines_hf import hint, line
    spills = [e for e in g["events"] if e.get("kind") == "cpu-spill"]
    if not spills:
        return []
    d = spills[-1].get("data") or {}
    layers = d.get("layers")
    stated = line(g["server_obj"], "n-gpu-layers", layers if g["runtime"] != "lmstudio" else "max", was=d.get("offloaded"))
    text = (f"{len(spills)} CPU spills of {g['model']} on {g['server']} ({g['runtime']}): " +
            (f"{d.get('offloaded')} of {layers} layers on the GPU" if layers else "part of it on the CPU"))
    return [_tag(finding("cpu-spill", g, "warn", text, events=spills, numbers={"spills": len(spills),
                         "offloaded": d.get("offloaded"), "layers": layers}, server_hint=hint(stated),
                         stated=[stated] if stated else []), g)]


def tools_heavy(g: dict, ctx: dict) -> list:
    s = g["stats"]
    shares = [(x.get("composition") or {}).get("tools_schema", 0) / (x.get("composition") or {}).get("total")
              for x in s["ok"] if isinstance((x.get("composition") or {}).get("total"), int) and x["composition"]["total"] > 0]
    tools = [x.get("tools_count") for x in s["ok"] if isinstance(x.get("tools_count"), int)]
    win = g["cap"]
    pressed = s["trims"] or [e for e in g["events"] if e.get("kind") == "prompt-trimmed"] or (
        win and s["p95"] is not None and s["p95"] >= NEAR * win)
    if not shares or not tools or median(shares) < HEAVY or not pressed:
        return []
    to = max(TOOLS_FLOOR, min(12, int(median(tools)) // 2))
    cur = g["profile"].get("tools_max")
    if (cur and cur <= to) or median(tools) <= to:
        return []
    return [_tag(finding("tools-heavy", g, "warn", f"the tool catalog is {median(shares):.0%} of the prompts to "
                         f"{g['model']} on {g['server']} and they outgrow its window: offer the {to} most relevant tools",
                         calls=s["ok"][-4:], numbers={"tools_share": round(median(shares), 2), "tools": int(median(tools))},
                         proposal=proposal("tools_max", cur, to, "a tool budget: the prompt fits the server's window")), g)]


RULES = [window_small, replies, spilled, tools_heavy]
