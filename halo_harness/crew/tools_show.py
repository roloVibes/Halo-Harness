"""halo_harness.crew.tools_show -- the builder's one read-only tool, `studio_show` (Halo 3.6.0.0 R3).

    studio_show {what: map | lists | connections | run, name?}

- `map`          the map in use (or `name`): main, every box, every line with its When in words, what waits under
                 "Not connected yet", its cap, its problems;
- `lists`        your agents and workflows (and the starters), one line each;
- `connections`  where an agent or workflow (`name`) is used: the maps and the workflows that name it;
- `run`          the last hand-offs sessions made on a map, from their records (each receipt names the line that
                 fired and why): "why did reviewer run?" reads here.
It answers text and no change lines: nothing is previewed and nothing is written. What it reads (descriptions, a run's
record) is data for the builder, never instructions.
"""

from __future__ import annotations

import json

from halo_harness.crew import map_when, store

RECEIPT = " · line "


def _map_text(name: str, ctx) -> str:
    from halo_harness.crew.compile import compile_map, in_use
    used, _src = in_use(None, ctx.get("cwd"))
    c = compile_map(name, cwd=ctx.get("cwd"), state_dir=ctx.get("state_dir"))
    raw = store.load("map", name, cwd=ctx.get("cwd"), state_dir=ctx.get("state_dir")) or {}
    lines = [f"MAP {name} ({raw.get('_scope') or 'missing'}){' -- new sessions use it' if used == name else ''}:",
             f"main: the agent {c.main.get('agent')} (model {c.main.get('model') or 'auto'}, careful {c.main.get('careful')})"]
    targets = set()
    for ln in raw.get("lines") or []:
        if isinstance(ln, dict):
            targets.add(ln.get("to"))
            lines.append(f"line {ln.get('from')} -> {ln.get('to')}: {map_when.words(ln.get('when'))}")
    for bid, box in c.boxes.items():
        tag = "" if bid in targets else " (not connected yet)"
        lines.append(f"box {bid}: {box['kind']} {', '.join(box['names'])}{tag}")
    if c.cap_usd is not None:
        lines.append(f"cap: ${c.cap_usd:.2f} a session")
    lines += [f"problem: {p}" for p in c.problems]
    return "\n".join(lines)


def _lists(ctx) -> str:
    out = []
    for kind in ("agent", "workflow", "map"):
        for r in store.rows(kind, cwd=ctx.get("cwd"), state_dir=ctx.get("state_dir")):
            what = r.get("does") or r.get("for") or f"{len(r.get('boxes') or [])} boxes"
            out.append(f"{kind} {r['name']} ({r['_scope']}): {str(what)[:120]}")
    return "\n".join(out) or "(nothing yet)"


def _connections(name: str, ctx) -> str:
    used = store.used_by(name, cwd=ctx.get("cwd"), state_dir=ctx.get("state_dir"))
    used += [f"map {m}" for m in store.maps_with(name, cwd=ctx.get("cwd"), state_dir=ctx.get("state_dir"))]
    return f"{name} is used by: {', '.join(used)}" if used else f"{name}: on no map of yours and in no workflow of yours"


def receipts(cwd, limit: int = 12) -> list:
    """The newest map hand-off receipt lines in this project's session records (newest first)."""
    from halo_harness.agent.sessions import sessions_dir
    try:
        logs = sorted(sessions_dir(cwd).rglob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)[:20]
    except OSError:
        return []
    out: list = []
    for p in logs:
        try:
            rows = p.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        for raw in reversed(rows):
            if RECEIPT not in raw:
                continue
            try:
                text = json.dumps(json.loads(raw), ensure_ascii=False)
            except ValueError:
                text = raw
            for bit in text.replace("\\n", "\n").split("\n"):
                if bit.lstrip('"').startswith("map ") and RECEIPT in bit and bit not in out:
                    out.append(bit.strip('"').strip()[:300])
            if len(out) >= limit:
                return out
    return out


def studio_show(args: dict, ctx) -> dict:
    what = str(args.get("what") or "map").strip().lower()
    name = str(args.get("name") or "").strip()
    if what == "lists":
        return {"text": _lists(ctx), "rows": []}
    if what == "connections":
        return {"text": _connections(name, ctx) if name else "connections: say which agent or workflow (name)", "rows": []}
    if what == "run":
        got = receipts(ctx.get("cwd"))
        if name:
            got = [g for g in got if name in g] or got
        return {"text": ("THE LAST HAND-OFFS (records, data):\n" + "\n".join(got)) if got else
                "No session has handed work on a map in this project yet.", "rows": []}
    from halo_harness.crew.tools_map import map_name
    return {"text": _map_text(name or map_name({}, ctx), ctx), "rows": []}


TOOLS = {"studio_show": (studio_show, '{"what": map|lists|connections|run, "name"?}  (read-only: no preview, nothing written)')}
