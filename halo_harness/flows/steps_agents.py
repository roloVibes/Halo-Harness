"""halo_harness.flows.steps_agents -- the intake, roles and org steps.

* intake: checks the run's intake values against the step's `form` (text is
  required, a number is a number, files exist, a list field takes values
  from its choices and defaults to all of them), copies dropped files into
  `<project>/assets/`; output = the form values (+ `project`).
* roles: one `adapters.one_shot(role, prompt, model)` per role, in order,
  each role seeing the earlier roles' answers; the model is `--model` when
  given, else the lineup's role table entry, else the session default.
  Output `{text, per_role, models, cost_usd}`.
* org: `adapters.run_org(org, goal, budget_usd, on_event, approval_sink)`;
  an approval-gated position's result becomes a flow gate (accept, redo
  with an instruction = the position runs again, stop = the run stops).
  Output `{text, cost_usd, positions: {title: {text, prompt?}}}`; a position
  with ComfyUI tools (the Art Director) gets its final text as `prompt`.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

from halo_harness.flows import gates
from halo_harness.flows.refs import resolve_value
from halo_harness.flows.state import StopFlow


def _choices(value, choices: list, field: str) -> list:
    if value in (None, "", []):
        return list(choices)
    items = value if isinstance(value, list) else [v for v in re.split(r"[,\s]+", str(value)) if v]
    lower = {str(c).lower(): c for c in choices}
    bad = [v for v in items if str(v).lower() not in lower]
    if bad:
        raise StopFlow(f"intake: {field} takes {', '.join(map(str, choices))}; got {', '.join(map(str, bad))}")
    return [lower[str(v).lower()] for v in items]


def _copy_asset(src: Path, assets: Path) -> str:
    assets.mkdir(parents=True, exist_ok=True)
    target, n = assets / src.name, 2
    while target.exists() and target.read_bytes() != src.read_bytes():
        target = assets / f"{src.stem}-{n}{src.suffix}"
        n += 1
    if not target.exists():
        shutil.copy2(src, target)
    return str(target)


def intake(ctx) -> dict:
    form = ctx.step.get("form") or {}
    given = dict(ctx.intake)
    out = {}
    for field, kind in form.items():
        value = given.get(field)
        if kind == "text":
            if not str(value or "").strip():
                raise StopFlow(f"intake: {field} is required (halo flow run {ctx.spec.get('name')} --input {field}=...)")
            out[field] = str(value).strip()
        elif kind == "number":
            if value in (None, ""):
                continue
            try:
                out[field] = float(value)
            except (TypeError, ValueError):
                raise StopFlow(f"intake: {field} is a number, got {value!r}") from None
        elif kind == "files":
            files = value if isinstance(value, list) else ([value] if value else [])
            missing = [f for f in files if not Path(str(f)).expanduser().is_file()]
            if missing:
                raise StopFlow(f"intake: {field}: no such file {', '.join(map(str, missing))}")
            assets = ctx.project().path / "assets"
            out[field] = [_copy_asset(Path(str(f)).expanduser(), assets) for f in files]
        elif isinstance(kind, list):
            out[field] = _choices(value, kind, field)
    out["project"] = ctx.project().slug
    for name in out.get("assets") or []:
        ctx.flow.log("note", f"intake: copied {Path(name).name} into the project", step=ctx.sid)
    return out


def _role_model(table: dict, role: str):
    from halo_harness.roles import role_value_parts
    model, _effort = role_value_parts(table.get(role))
    return None if not model or str(model).lower() == "default" else model


def _inputs_text(inputs: dict) -> str:
    rows = []
    for k, v in (inputs or {}).items():
        v = ", ".join(map(str, v)) if isinstance(v, list) else v
        rows.append(f"{k}: {v}")
    return "\n".join(rows)


def roles(ctx) -> dict:
    from halo_harness.teams_yaml import resolve_role_table, resolve_team_template
    lineup = str(ctx.step.get("uses") or "")[len("lineup:"):]
    template = resolve_team_template(lineup)
    if template is None:
        raise StopFlow(f"{ctx.sid}: lineup {lineup!r} does not resolve")
    table, _notes = resolve_role_table(template)
    inputs = resolve_value(ctx.step.get("inputs") or {}, ctx.outputs)
    budget = ctx.step_budget()
    texts, models = {}, {}
    for role in ctx.step.get("roles") or []:
        if budget is not None and ctx.cost >= budget:
            ctx.flow.log("note", f"{ctx.sid}: the step budget ${budget:.2f} is spent; {role} is skipped", step=ctx.sid)
            continue
        model = ctx.adapters.model or _role_model(table, role)
        earlier = "".join(f"\n\nThe {r} answered:\n{t}" for r, t in texts.items())
        prompt = (f"You are the {role} in the flow {ctx.spec.get('name')!r}, step {ctx.sid!r}.\n\n"
                  f"{_inputs_text(inputs)}{earlier}\n\nGive your answer as plain text, short and concrete.")
        res = ctx.adapters.one_shot(role, prompt, model) or {}
        ctx.cost += float(res.get("cost_usd") or 0.0)
        text = str(res.get("text") or "").strip()
        if not text and res.get("error"):
            raise StopFlow(f"{ctx.sid}: the {role} call failed: {res.get('error')}")
        texts[role], models[role] = text, model
        ctx.flow.log("note", f"{ctx.sid}: {role} answered (${float(res.get('cost_usd') or 0):.4f}"
                             f"{', ' + model if model else ''})", step=ctx.sid, role=role)
    joined = "\n\n".join(f"## {r}\n{t}" for r, t in texts.items())
    return {"text": joined, "per_role": texts, "models": models, "cost_usd": round(ctx.cost, 6)}


def clean_prompt(text: str) -> str:
    """An image prompt out of a position's final text: no fences, labels or quotes."""
    lines = [l for l in str(text or "").strip().splitlines()
             if not l.strip().startswith(("```", "[approval gate]", "[budget]", "[sub-agent"))]
    s = "\n".join(lines).strip()
    s = re.sub(r"^(?:\*\*)?(?:image\s+)?prompt(?:\*\*)?\s*:\s*(?:\*\*)?", "", s, flags=re.I).strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in "\"'":
        s = s[1:-1].strip()
    return re.sub(r"\s+", " ", s)


def _prompt_positions(org: dict) -> set:
    out = set()
    for p in (org or {}).get("positions") or []:
        tools = p.get("tools") if isinstance(p, dict) else None
        if isinstance(tools, list) and any(str(t).startswith("mcp__comfyui__") for t in tools):
            out.add(p.get("title"))
    return out


def org(ctx) -> dict:
    from halo_harness.orgs import load_org
    name = str(ctx.step.get("uses") or "")[len("org:"):]
    org_def = load_org(name)
    if org_def is None:
        raise StopFlow(f"{ctx.sid}: org {name!r} is not found")
    inputs = resolve_value(ctx.step.get("inputs") or {}, ctx.outputs)
    goal = str(inputs.get("goal") or "")
    rest = {k: v for k, v in inputs.items() if k != "goal"}
    if rest:
        goal = f"{goal}\n\n{_inputs_text(rest)}"
    budget = ctx.step_budget()
    rounds, stopped = {}, {}

    def on_event(text: str, data: "dict | None" = None) -> None:
        ctx.flow.log("note", f"{ctx.sid}: {text}", step=ctx.sid, **dict(data or {}))

    def approval_sink(req: dict) -> dict:
        pos = str(req.get("position") or "?")
        if ctx.adapters.auto_accept:
            ctx.flow.log("gate", f"{ctx.sid}: {pos}'s result accepted automatically (--yes)", step=ctx.sid,
                         position=pos, action="accept", auto=True, result=str(req.get("text") or "")[:2000])
            return {"action": "accept"}
        rounds[pos] = rounds.get(pos, 0) + 1
        gate = gates.post_gate(ctx.flow, ctx.n, {"id": f"{ctx.run}:{ctx.sid}:{pos}", "step": ctx.sid, "position": pos,
                                                 "text": str(req.get("text") or ""), "round": rounds[pos],
                                                 "request": req.get("id")})
        ctx.flow.set(ctx.sid, "waiting", f"{pos} needs approval")
        ans = gates.wait_answer(ctx.flow, ctx.n, gate, poll_s=ctx.adapters.poll_s, answer_gate=ctx.adapters.answer_gate)
        ctx.flow.set(ctx.sid, "running")
        if ans["action"] == "stop":
            stopped["reason"] = f"{pos}'s result was stopped at the gate" + (f": {ans['instruction']}" if ans["instruction"] else "")
            return {"action": "stop"}
        if ans["action"] == "redo":
            return {"action": "edit", "instruction": ans["instruction"]}
        return {"action": "accept"}

    res = ctx.adapters.run_org(name, goal, budget, on_event, approval_sink) or {}
    ctx.cost += float(res.get("cost_usd") or 0.0)
    ctx.record["rounds"] = sum(rounds.values())
    if stopped:
        raise StopFlow(stopped["reason"])
    positions = {}
    for title, value in (res.get("positions") or {}).items():
        positions[title] = dict(value) if isinstance(value, dict) else {"text": str(value)}
    for title in _prompt_positions(org_def):
        if title in positions and not positions[title].get("prompt"):
            positions[title]["prompt"] = clean_prompt(positions[title].get("text"))
    if res.get("is_error") and not positions:
        raise StopFlow(f"{ctx.sid}: org {name} failed: {str(res.get('text') or '')[:300]}")
    return {"text": str(res.get("text") or ""), "cost_usd": round(ctx.cost, 6), "positions": positions,
            "org": name, "budget_usd": budget}
