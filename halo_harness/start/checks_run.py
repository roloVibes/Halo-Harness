"""halo_harness.start.checks_run -- what each of the five first-run checks
runs, and the cost line it states (Halo 3.2.2.0 R2; the list itself is
start/checks.py).

Every `run_<key>(ctx)` calls the function Halo already has for the job and
returns its result lines; it raises `CheckFailed(lines)` when the check
failed:

    doctor   doctor.run_checks                      fails on a MISSING line
    catalog  studio.models_refresh.refresh          fails when no provider's list came back
    hello    init_cli._run_live_pong (the pong)     fails without a valid reply
    gym      gym_run.run_gym(quick=True)            fails when every model came back with only errors
    start    start_cli.cmd_start                    fails on a non-zero exit
"""

from __future__ import annotations

from pathlib import Path

#: The hello call, roughly: a bare one-turn session's prompt in, one word out.
HELLO_TOKENS = (2_000, 10)
GYM_LOCAL_ONLY = "not run: the gym's battery runs local models only (ol:, hf:local/, hf:mlx/)"


class CheckFailed(Exception):
    """The check ran and failed; `lines` are its result lines."""

    def __init__(self, lines):
        super().__init__("; ".join(lines) if lines else "failed")
        self.lines = list(lines)


def _state_dir(ctx) -> Path:
    if ctx.state_dir is not None:
        return Path(ctx.state_dir)
    from halo_harness.config.paths import bridge_home
    return Path(bridge_home())


def is_local(ref: str) -> bool:
    from halo_harness.model import is_local_ref_string
    return is_local_ref_string(ref)


def call_price(ref: str, tokens_in: int, tokens_out: int, rows=None) -> str:
    """"free (local)", "about $X at <ref>'s catalog price" or "price unknown for <ref>"."""
    if is_local(ref):
        return "free (a local model)"
    from halo_harness.tui.dialogs.team_preview import _price, catalog_by_ref
    row = (catalog_by_ref() if rows is None else rows).get(ref)
    pin, pout = _price(row, "price_in_per_m"), _price(row, "price_out_per_m")
    if pin is None or pout is None:
        return f"price unknown for {ref} (the catalog has no price for it)"
    return f"about ${(tokens_in * pin + tokens_out * pout) / 1_000_000:.4f} at {ref}'s catalog price"


# -- doctor -------------------------------------------------------------------
def run_doctor(ctx) -> "list[str]":
    from halo_harness.doctor import run_checks
    lines, ok = run_checks(cwd=ctx.cwd)
    if not ok:
        raise CheckFailed(lines)
    return list(lines)


# -- catalog ------------------------------------------------------------------
def run_catalog(ctx) -> "list[str]":
    if ctx.no_live:
        return ["skipped: --no-live"]
    from halo_harness.studio.catalog_env import catalog_env
    from halo_harness.studio.models_refresh import refresh
    record = refresh(_state_dir(ctx), catalog_env(ctx.cwd))
    outcomes = record.get("outcomes") or []
    if not outcomes:
        return ["no provider is set up yet, so there is no list to fetch: halo init sets one up"]
    lines = [f"[{'ok' if o.get('ok') else '!!'}] {o.get('name')}: {o.get('line')}" for o in outcomes]
    if not any(o.get("ok") for o in outcomes):
        raise CheckFailed(lines)
    return lines


# -- hello --------------------------------------------------------------------
def hello_cost(ctx) -> str:
    if not ctx.model:
        return "nothing: no default model is set yet"
    return "one tiny call, " + call_price(ctx.model, *HELLO_TOKENS)


def run_hello(ctx) -> "list[str]":
    if ctx.no_live:
        return ["skipped: --no-live"]
    if not ctx.model:
        return ["skipped: no default model is set yet (halo init sets one)"]
    from halo_harness import init_cli
    ok, line = init_cli._run_live_pong(ctx.model, Path(ctx.cwd))
    if not ok:
        raise CheckFailed([line, "Next: `halo doctor` explains what's missing."])
    return [line]


# -- gym ----------------------------------------------------------------------
def gym_candidates(ctx) -> "list[str]":
    """The models the gym row offers: the default model, who plays the start's lead and workers, and the
    start lineup's pinned models, in that order, each once."""
    out: "list[str]" = []

    def add(ref) -> None:
        if isinstance(ref, str) and ref and ref not in ("default", "auto") and ref not in out:
            out.append(ref)
    add(ctx.model)
    try:
        from halo_harness.start.card import _target, part_models
        for ref in part_models(default=ctx.model).values():
            add(ref)
        from halo_harness import teams_yaml as T
        for name in (_target(ctx.lineup), ctx.lineup):
            template = T.resolve_team_template(name, cwd=ctx.cwd, state_dir=ctx.state_dir)
            if template is not None:
                table, _notes = T.resolve_role_table(template, cwd=ctx.cwd, state_dir=ctx.state_dir)
                for value in table.values():
                    add(value.get("model") if isinstance(value, dict) else value)
                break
    except Exception:
        pass
    return out


def gym_models(ctx) -> "list[str]":
    return list(ctx.gym_models) if ctx.gym_models is not None else gym_candidates(ctx)


def gym_model_cost(ref: str) -> str:
    return "free, a few minutes" if is_local(ref) else GYM_LOCAL_ONLY


def gym_cost(ctx) -> str:
    models = gym_models(ctx)
    if not models:
        return "nothing to run: no model is picked"
    return "; ".join(f"{ref}: {gym_model_cost(ref)}" for ref in models)


def run_gym(ctx) -> "list[str]":
    from halo_harness.gym import overall_score
    from halo_harness.gym_run import run_gym as gym_entry
    models = gym_models(ctx)
    if not models:
        return ["nothing to run: no model is picked (halo check --gym --models REF,REF)"]
    local = [m for m in models if is_local(m)]
    lines = [f"{m}: {GYM_LOCAL_ONLY}" for m in models if m not in local]
    if not local:
        return lines
    results = gym_entry(local, quick=True, state_dir=_state_dir(ctx))
    scored = 0
    for ref, result in zip(local, results):
        score = overall_score(result)
        errors = list(result.get("errors") or [])
        if score is not None:
            scored += 1
            lines.append(f"{ref}: overall {score:.2f}" + (f" ({len(errors)} error(s))" if errors else ""))
        else:
            lines.append(f"{ref}: no score: " + ("; ".join(errors) or "nothing was measured"))
    lines.append("each model's card: halo gym show <model>")
    if not scored:
        raise CheckFailed(lines)
    return lines


# -- start --------------------------------------------------------------------
def start_cost(ctx) -> str:
    from halo_harness.start.card import estimate
    return estimate(fake=ctx.fake, default=ctx.model, rule=False) + " (halo start --explain shows the rule)"


def run_start(ctx) -> "list[str]":
    from halo_harness.start_cli import cmd_start
    rc = cmd_start(list(ctx.start_argv))
    line = f"halo start {' '.join(ctx.start_argv)}".rstrip() + f" ended with exit {rc}"
    if rc != 0:
        raise CheckFailed([line])
    return [line]
