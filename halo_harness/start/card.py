"""halo_harness.start.card -- the card `halo start` opens on (Halo 3.2.2.0 R2):
what the guided first run does, the models it will call, what it should
cost, how long it takes and what it writes, before anything runs.

`card_lines(...)` is the card as plain text lines: `halo start` prints it as
its first screen (`--explain` prints only it), Studio's Start here shows it
above its Run button (`GET /api/start` -> `card`), the wizard's Summary and
`halo check` use its estimate for the `start` row (start/checks.py).

Who plays which part comes from the same function the run uses
(`orchestra.adapters.role_model`): the lead (its plan, and the judge when two
workers' edits conflict) is the role table's `main`, each of the five
workers its `subagent`, `--model REF` both, and the default model when the
role table names none. The copied lineup's own cards (alias -> bio -> model)
are listed under it, from `team_preview`'s tree.

The estimate, a stated rule (`BUDGET`): one lead plan (15k tokens in, 3k
out), five worker lanes, each a `halo -p` session of about eight turns
(120k in, 6k out per lane: the context is sent again every turn), one judge
pass (8k in, 1k out), priced with the catalog's `price_in_per_m` /
`price_out_per_m`. A local model (`ol:`, `hf:local/`, `hf:mlx/`) costs
nothing; a model the catalog has no price for is named ("unknown for
<model>"), never counted as free.
"""

from __future__ import annotations

import datetime as _dt
from pathlib import Path
from typing import Optional

from halo_harness.start import steps as S

#: (part, calls, tokens in per call, tokens out per call, the role whose model plays it)
BUDGET = (("one lead plan", 1, 15_000, 3_000, "main"),
          ("five worker lanes", 5, 120_000, 6_000, "subagent"),
          ("one judge pass", 1, 8_000, 1_000, "main"))
TIME = "5-20 minutes on cloud models; longer on local ones (the run stops itself after 2 hours)."
NOT_A_TEST = "It is one real Orchestra run on your models, not a test of them (halo gym measures models)."
FAKE = "the fake lead, workers and judge (HALO_START_FAKE=1): no model is called"


def _default_model() -> str:
    from halo_harness.start.provider import default_model
    return default_model()


def part_models(model: Optional[str] = None, default: str = "") -> "dict[str, str]":
    """`{"main": ref, "subagent": ref}`: who plays the lead and the workers ('' when nothing names a model);
    `default` stands in for the configured default model (the wizard's pick before anything reads config)."""
    from halo_harness.orchestra.adapters import role_model
    default = default or _default_model()
    return {role: str(role_model(role, model) or default or "") for role in ("main", "subagent")}


def _shown(ref: str) -> str:
    if not ref:
        return "your default model (none is set yet: halo init sets one)"
    if ref == "auto":
        return "the models picked at spawn (auto)"
    return ref


def _is_local(ref: str) -> bool:
    from halo_harness.model import is_local_ref_string
    return is_local_ref_string(ref)


def estimate(model: Optional[str] = None, *, fake: bool = False, models_by_ref: "Optional[dict]" = None,
             parts: "Optional[dict]" = None, default: str = "", rule: bool = True) -> str:
    """The card's one cost line: "free ...", "about $X.XX ..." or "unknown for <model> ..."; `rule=False`
    leaves out the token budget it was computed with (the check rows)."""
    if fake:
        return "free: " + FAKE
    from halo_harness.tui.dialogs.team_preview import _price, catalog_by_ref
    parts = parts if parts is not None else part_models(model, default)
    rows = catalog_by_ref() if models_by_ref is None else models_by_ref
    total, unknown, priced = 0.0, [], False
    for _what, calls, tin, tout, role in BUDGET:
        ref = parts.get(role, "")
        if ref and _is_local(ref):
            continue
        row = rows.get(ref) if ref else None
        pin, pout = _price(row, "price_in_per_m"), _price(row, "price_out_per_m")
        if pin is None or pout is None:
            name = _shown(ref) if ref else "your default model (none is set yet)"
            if name not in unknown:
                unknown.append(name)
            continue
        total += calls * (tin * pin + tout * pout) / 1_000_000
        priced = True
    budget = "; ".join(f"{what} {tin // 1000}k in / {tout // 1000}k out" + (" each" if calls > 1 else "")
                       for what, calls, tin, tout, _r in BUDGET)
    if unknown:
        line = f"unknown for {', '.join(unknown)} (the catalog has no price for it: halo models --refresh)"
        return line + (f"; the rule: {budget}" if rule else "")
    if not priced:
        return "free: every model it calls is local"
    return f"about ${total:.2f} at the catalog's prices" + (f" (the rule: {budget})" if rule else "")


def _target(lineup: str) -> str:
    """The lineup the start runs: `my-<name>` for a shipped one, else the name itself."""
    from halo_harness import teams_yaml as T
    from halo_harness.start.lineup import own_name
    return own_name(lineup) if lineup in T.list_bundled_team_templates() else lineup


def _lineup_lines(lineup: str, state_dir, cwd) -> "list[str]":
    from halo_harness import teams_yaml as T
    from halo_harness.tui.dialogs import team_preview as P
    copy = _target(lineup)
    name = copy if T.find_team_template_path(copy, cwd=cwd, state_dir=state_dir) else lineup
    template = T.resolve_team_template(name, cwd=cwd, state_dir=state_dir)
    if template is None:
        return [f"  {lineup}: no such lineup (halo teams list shows them)"]
    table, _notes = T.resolve_role_table(template, cwd=cwd, state_dir=state_dir)
    return ["  " + line for line in P._tree_lines(template, table, P.catalog_by_ref(), cwd, state_dir)]


def writes(*, lineup: str = S.DEFAULT_LINEUP, state_dir=None, repo: Optional[str] = None,
           today: Optional[str] = None) -> "list[str]":
    """What the start writes, one line each (paths, not yet written)."""
    from halo_harness import teams_yaml as T
    from halo_harness.start.lineup import own_name
    from halo_harness.start.sample_repo import _free_folder, start_root
    state = Path(state_dir) if state_dir is not None else _home()
    out = []
    if lineup in T.list_bundled_team_templates():
        path = T.user_teams_dir(state) / f"{own_name(lineup)}.yaml"
        out.append(f"{path} (a copy of the shipped {lineup}; one already there is kept as it is)")
    else:
        out.append(f"nothing for the lineup: {lineup} is already yours and is used as it is")
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


def card_lines(*, lineup: str = S.DEFAULT_LINEUP, state_dir=None, cwd=None, model: Optional[str] = None,
               fake: bool = False, repo: Optional[str] = None, today: Optional[str] = None,
               models_by_ref: "Optional[dict]" = None) -> "list[str]":
    """The whole card, plain text lines (no markup). Never raises: a part that cannot be read says so."""
    target = _target(lineup)
    lines = ["The guided first run (halo start)", NOT_A_TEST, "", f"What it does, in {S.TOTAL} steps:"]
    lines += [f"  {n}. {title}: {why}" for n, (_k, title, why) in enumerate(S.STEPS, 1)]
    lines += ["", "Models it will call:"]
    try:
        if fake:
            lines.append("  " + FAKE)
        else:
            parts = part_models(model)
            lines.append(f"  the lead (the plan, and the judge of a conflict): {_shown(parts['main'])}")
            lines.append(f"  five workers (one lane each, a halo -p session): {_shown(parts['subagent'])}")
    except Exception as e:
        lines.append(f"  could not resolve the models: {type(e).__name__}: {e}")
    head = f"The lineup it copies ({lineup} -> {target})" if target != lineup else f"The lineup it uses ({lineup})"
    lines += ["", head + ", alias -> bio -> model:"]
    try:
        lines += _lineup_lines(lineup, state_dir, cwd)
    except Exception as e:
        lines.append(f"  could not read the lineup: {type(e).__name__}: {e}")
    try:
        cost = estimate(model, fake=fake, models_by_ref=models_by_ref)
    except Exception as e:
        cost = f"unknown ({type(e).__name__}: {e})"
    lines += ["", f"Estimated cost: {cost}", f"Time: {TIME}", "", "Writes:"]
    try:
        lines += ["  " + w for w in writes(lineup=lineup, state_dir=state_dir, repo=repo, today=today)]
    except Exception as e:
        lines.append(f"  could not name the paths: {type(e).__name__}: {e}")
    lines += ["", f"Your active lineup is not touched: halo teams use {target} makes "
                  + ("the copy" if target != lineup else "it") + " the one sessions use."]
    return lines
