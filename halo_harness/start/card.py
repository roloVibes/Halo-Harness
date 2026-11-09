"""halo_harness.start.card -- the card `halo start` opens on (Halo 3.2.2.0 R2):
what the guided first run does, the models it will call, what it should
cost, how long it takes and what it writes, before anything runs.

`card_lines(...)` is the card as plain text lines: `halo start` prints it as
its first screen (`--explain` prints only it), Studio's Start here shows it
above its Run button (`GET /api/start` -> `card`), the wizard's Summary and
`halo check` use its estimate for the `start` row (start/checks.py).

3.3.15.0 R7: the card names the lineup the run rehearses (the active one, or
`--lineup`'s; start/lineup.py `pick`) and who plays what from its own cards
(`lineup.parts`, through `teams_yaml.resolve_role_table`): the lead (its
plan, and the judge when two workers' edits conflict) is the lead card, each
lane a lane card. A card that pins no model plays on the role table's
`main` / `subagent`, else the default model (`orchestra.adapters.role_model`,
the same fallback the run takes); `--model REF` plays every part. The models
it lists are the distinct ones, each with its catalog price.

The estimate, a stated rule (`BUDGET`): one lead plan (15k tokens in, 3k
out), one worker lane per lane card (a `halo -p` session of about eight
turns: 120k in, 6k out per lane, the context sent again every turn), one
judge pass (8k in, 1k out), priced with the catalog's `price_in_per_m` /
`price_out_per_m`. A local model (`ol:`, `hf:local/`, `hf:mlx/`) costs
nothing; a model the catalog has no price for is named ("unknown for
<model>"), never counted as free.
"""

from __future__ import annotations

import datetime as _dt
from pathlib import Path
from typing import Optional

from halo_harness.start import steps as S

#: (part, tokens in per call, tokens out per call, the role whose model plays it)
BUDGET = (("one lead plan", 15_000, 3_000, "main"), ("worker lane", 120_000, 6_000, "subagent"),
          ("one judge pass", 8_000, 1_000, "main"))
TIME = "5-20 minutes on cloud models; longer on local ones (the run stops itself after 2 hours)."
NOT_A_TEST = "It is one real Orchestra run on your models, not a test of them (halo gym measures models)."
FAKE = "the fake lead, workers and judge (HALO_START_FAKE=1): no model is called"
UNTOUCHED = "Your lineup is not touched: the run reads it as it is; edit it in Roles (halo studio --mode roles)."


def _default_model() -> str:
    from halo_harness.start.provider import default_model
    return default_model()


def part_models(model: Optional[str] = None, default: str = "") -> "dict[str, str]":
    """`{"main": ref, "subagent": ref}` from the role table (no lineup): '' when nothing names a model."""
    from halo_harness.orchestra.adapters import role_model
    default = default or _default_model()
    return {role: str(role_model(role, model) or default or "") for role in ("main", "subagent")}


def lineup_parts(lineup: Optional[str] = None, *, state_dir=None, cwd=None) -> Optional[dict]:
    """`lineup.parts` of the lineup the run rehearses; None when there is none (Auto, a missing name)."""
    from halo_harness.start.lineup import LineupError, parts, pick
    try:
        return parts(pick(lineup, state_dir=state_dir, cwd=cwd), state_dir=state_dir, cwd=cwd)
    except LineupError:
        return None


def part_refs(p: Optional[dict], model: Optional[str] = None, default: str = "") -> dict:
    """`{"main": ref, "lanes": [ref per lane]}`: each card's own model, else the role table's, else the default."""
    roles = part_models(model, default)
    if not p:
        from halo_harness.start.lineup import SAMPLE_LANES
        return {"main": roles["main"], "lanes": [roles["subagent"]] * SAMPLE_LANES}
    lead = (p.get("lead") or {}).get("model")
    return {"main": model or lead or roles["main"],
            "lanes": [model or c.get("model") or roles["subagent"] for c in p.get("lanes") or []]}


def _shown(ref: str) -> str:
    if not ref:
        return "your default model (none is set yet: halo init sets one)"
    if ref == "auto":
        return "the models picked at spawn (auto)"
    return ref


def _is_local(ref: str) -> bool:
    from halo_harness.model import is_local_ref_string
    return is_local_ref_string(ref)


def _calls(parts: dict) -> "list[tuple[str, int, int, str]]":
    """`(what, tokens in, tokens out, ref)` per call, from `{"main", "lanes"}` or the older `{"main", "subagent"}`."""
    lanes = parts.get("lanes")
    if lanes is None:
        from halo_harness.start.lineup import SAMPLE_LANES
        lanes = [parts.get("subagent", "")] * SAMPLE_LANES
    out = []
    for what, tin, tout, role in BUDGET:
        refs = lanes if role == "subagent" else [parts.get("main", "")]
        out += [(what, tin, tout, ref) for ref in refs]
    return out


def estimate(model: Optional[str] = None, *, fake: bool = False, models_by_ref: "Optional[dict]" = None,
             parts: "Optional[dict]" = None, default: str = "", rule: bool = True, lineup: Optional[str] = None,
             state_dir=None, cwd=None) -> str:
    """The card's one cost line: "free ...", "about $X.XX ..." or "unknown for <model> ..."; `rule=False`
    leaves out the token budget it was computed with (the check rows). No `parts`: the lineup's."""
    if fake:
        return "free: " + FAKE
    from halo_harness.tui.dialogs.team_preview import _price, catalog_by_ref
    if parts is None:
        parts = part_refs(lineup_parts(lineup, state_dir=state_dir, cwd=cwd), model, default)
    rows = catalog_by_ref() if models_by_ref is None else models_by_ref
    calls = _calls(parts)
    total, unknown, priced = 0.0, [], False
    for _what, tin, tout, ref in calls:
        if ref and _is_local(ref):
            continue
        row = rows.get(ref) if ref else None
        pin, pout = _price(row, "price_in_per_m"), _price(row, "price_out_per_m")
        if pin is None or pout is None:
            name = _shown(ref) if ref else "your default model (none is set yet)"
            if name not in unknown:
                unknown.append(name)
            continue
        total += (tin * pin + tout * pout) / 1_000_000
        priced = True
    n = sum(1 for c in calls if c[0] == "worker lane")
    budget = "; ".join((f"{n} worker lane(s) {tin // 1000}k in / {tout // 1000}k out each" if what == "worker lane"
                        else f"{what} {tin // 1000}k in / {tout // 1000}k out") for what, tin, tout, _r in BUDGET)
    if unknown:
        line = f"unknown for {', '.join(unknown)} (the catalog has no price for it: halo models --refresh)"
        return line + (f"; the rule: {budget}" if rule else "")
    if not priced:
        return "free: every model it calls is local"
    return f"about ${total:.2f} at the catalog's prices" + (f" (the rule: {budget})" if rule else "")


def price_lines(parts: dict, models_by_ref: "Optional[dict]" = None) -> "list[str]":
    """One line per distinct model the run calls, with its catalog price."""
    from halo_harness.tui.dialogs.team_preview import _price, catalog_by_ref
    rows = catalog_by_ref() if models_by_ref is None else models_by_ref
    out = []
    for ref in dict.fromkeys(r for _w, _i, _o, r in _calls(parts)):
        if ref and _is_local(ref):
            out.append(f"{ref}: local, free")
            continue
        row = rows.get(ref) if ref else None
        pin, pout = _price(row, "price_in_per_m"), _price(row, "price_out_per_m")
        price = f"${pin:.2f} in / ${pout:.2f} out per M tokens" if pin is not None and pout is not None else \
            "no price in the catalog (halo models --refresh)"
        out.append(f"{_shown(ref)}: {price}")
    return out


def _lineup_lines(p: dict, state_dir, cwd, explicit: bool) -> "list[str]":
    from halo_harness import teams_yaml as T
    from halo_harness.start.lineup import who_lines
    from halo_harness.tui.dialogs import team_preview as P
    source = "named with --lineup" if explicit else "your active lineup"
    lines = [f"The lineup it rehearses: {p['name']} ({source})"] + ["  " + w for w in who_lines(p)]
    lines += ["  " + p["short"]] if p["short"] else []
    template = T.resolve_team_template(p["name"], cwd=cwd, state_dir=state_dir) or {}
    table, _notes = T.resolve_role_table(template, cwd=cwd, state_dir=state_dir)
    lines += ["  its cards, alias -> bio -> model:"]
    return lines + ["    " + line for line in P._tree_lines(template, table, P.catalog_by_ref(), cwd, state_dir)]


def writes(*, state_dir=None, repo: Optional[str] = None, today: Optional[str] = None) -> "list[str]":
    """What the start writes, one line each (paths, not yet written)."""
    from halo_harness.start.sample_repo import _free_folder, start_root
    state = Path(state_dir) if state_dir is not None else _home()
    out = ["nothing for the lineup: the run reads it as it is"]
    if repo:
        out.append(f"in your repo {repo}: the run's folder (.halo/orchestra/<run>) and one git worktree per lane")
    else:
        day = start_root(state) / (today or _dt.date.today().isoformat())
        out.append(f"{_free_folder(day)} (the sample repo: a git repo with one commit)")
        out.append("inside it: the run's folder (.halo/orchestra/<run>) and one git worktree per lane")
    return out


def _home() -> Path:
    from halo_harness.config.paths import bridge_home
    return Path(bridge_home())


def card_lines(*, lineup: Optional[str] = None, state_dir=None, cwd=None, model: Optional[str] = None,
               fake: bool = False, repo: Optional[str] = None, today: Optional[str] = None,
               models_by_ref: "Optional[dict]" = None) -> "list[str]":
    """The whole card, plain text lines (no markup). Never raises: a part that cannot be read says so."""
    lines = ["The guided first run (halo start)", NOT_A_TEST, "", f"What it does, in {S.TOTAL} steps:"]
    lines += [f"  {n}. {title}: {why}" for n, (_k, title, why) in enumerate(S.STEPS, 1)]
    lines.append("")
    p = None
    try:
        from halo_harness.start.lineup import LineupError, no_coder_line, parts, pick
        try:
            p = parts(pick(lineup, state_dir=state_dir, cwd=cwd), state_dir=state_dir, cwd=cwd)
            lines += _lineup_lines(p, state_dir, cwd, bool(lineup and lineup.strip()))
            lines += [] if p["lanes"] else ["  " + no_coder_line(p["name"])]
        except LineupError as e:
            lines.append(f"The lineup it rehearses: {e}")
    except Exception as e:
        lines.append(f"The lineup it rehearses: could not be read: {type(e).__name__}: {e}")
    lines += ["", "Models it will call:"]
    try:
        if fake:
            lines.append("  " + FAKE)
        else:
            refs = part_refs(p, model)
            lines.append(f"  the lead (the plan, and the judge of a conflict): {_shown(refs['main'])}")
            lines.append(f"  {len(refs['lanes'])} worker lane(s) (a halo -p session each): "
                         + ", ".join(_shown(r) for r in refs["lanes"]))
            lines += ["  prices: " + line for line in price_lines(refs, models_by_ref)]
    except Exception as e:
        lines.append(f"  could not resolve the models: {type(e).__name__}: {e}")
    try:
        cost = estimate(model, fake=fake, models_by_ref=models_by_ref, parts=None if fake else part_refs(p, model))
    except Exception as e:
        cost = f"unknown ({type(e).__name__}: {e})"
    lines += ["", f"Estimated cost: {cost}", f"Time: {TIME}", "", "Writes:"]
    try:
        lines += ["  " + w for w in writes(state_dir=state_dir, repo=repo, today=today)]
    except Exception as e:
        lines.append(f"  could not name the paths: {type(e).__name__}: {e}")
    return lines + ["", UNTOUCHED]
