"""halo_harness.start.checks -- the checks Halo offers after setup, each one
saying what it does, what it costs, how long it takes and what it writes
(Halo 3.2.2.0 R2). The wizard's Summary, `halo check`, the TUI's `/check`
and `halo start`'s card read this one list.

    CHECKS   five entries, in this order (the first three on by default):
             doctor   your config, files and PATH                 free, seconds
             catalog  every provider's model list                 free (network), seconds
             hello    one one-turn call to your default model     one tiny call
             gym      `halo gym --quick` on the models you pick   free for local models, minutes each
             start    the guided first run (`halo start`)         the card's estimate, 5-20 minutes

Each entry is `{key, title, what, cost, time, writes, default_on, run}`;
`run(ctx) -> list[str]` (start/checks_run.py) calls the function Halo
already has and raises `CheckFailed` when the check failed. `cost_line`
fills in the price a check's models carry (the hello call, the gym's models,
the start's estimate). `explain(keys)` is a row per check as the wizard
shows it; `run_one` / `run_many` run them and never raise.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from halo_harness.start import checks_run as R
from halo_harness.start.checks_run import CheckFailed  # noqa: F401 (the one a check raises)
from halo_harness.start.steps import DEFAULT_LINEUP


@dataclass
class CheckCtx:
    cwd: Path = field(default_factory=Path.cwd)
    state_dir: Optional[Path] = None          # None: bridge_home()
    model: str = ""                           # the default model (hello; the first gym candidate)
    gym_models: Optional[list] = None         # the models ticked for the gym (None: R.gym_candidates)
    fake: bool = False                        # the start on fake model calls (HALO_START_FAKE=1)
    no_live: bool = False                     # halo init --no-live: catalog and hello say skipped
    start_argv: list = field(default_factory=list)
    lineup: str = DEFAULT_LINEUP


CHECKS = (
    {"key": "doctor", "title": "Doctor", "default_on": True, "run": R.run_doctor,
     "what": "checks your config, your files and that halo is on PATH (halo doctor)",
     "cost": "free", "time": "seconds", "writes": "nothing"},
    {"key": "catalog", "title": "Model catalog", "default_on": True, "run": R.run_catalog,
     "what": "fetches the model list of every provider you set up (halo models --refresh)",
     "cost": "free (network)", "time": "seconds (6 s per provider at most)",
     "writes": "the catalog caches under ~/.halo and ~/.halo/studio/models-refresh.json"},
    {"key": "hello", "title": "Hello", "default_on": True, "run": R.run_hello,
     "what": "one one-turn call to your default model, which answers pong",
     "cost": "one tiny call", "time": "seconds", "writes": "one session log, as every halo -p run does"},
    {"key": "gym", "title": "Model gym, quick", "default_on": False, "run": R.run_gym,
     "what": "halo gym --quick on the models you pick: tool calls, edits, recall and instructions, scored",
     "cost": "free for local models; the gym does not run cloud models", "time": "a few minutes per model",
     "writes": "one card per model under ~/.halo/gym/<host>/"},
    {"key": "start", "title": "The guided first run", "default_on": False, "run": R.run_start,
     "what": "halo start: one real Orchestra run on your models -- a lineup copy, a sample repo, the plan, the "
             "run, the report and the coach",
     "cost": "the card's estimate", "time": "5-20 minutes on cloud models; longer on local ones",
     "writes": "a lineup copy (my-halo-dev-cycle) and a sample repo under ~/.halo/start/<date>/"},
)
KEYS = tuple(c["key"] for c in CHECKS)
DEFAULT_KEYS = tuple(c["key"] for c in CHECKS if c["default_on"])
_COST: "dict[str, Callable]" = {"hello": R.hello_cost, "gym": R.gym_cost, "start": R.start_cost}


def check(key: str) -> dict:
    for c in CHECKS:
        if c["key"] == key:
            return c
    raise KeyError(key)


def cost_line(c: dict, ctx: Optional[CheckCtx] = None) -> str:
    """The check's cost with its models' prices when there is a ctx; its static cost otherwise."""
    fn = _COST.get(c["key"])
    if ctx is None or fn is None:
        return c["cost"]
    try:
        return fn(ctx)
    except Exception as e:
        return f"{c['cost']} (the price could not be read: {type(e).__name__})"


def detail_line(c: dict, ctx: Optional[CheckCtx] = None) -> str:
    """The muted line under a row's title: what / cost / time / writes."""
    return f"{c['what']}. Cost: {cost_line(c, ctx)}. Time: {c['time']}. Writes: {c['writes']}."


def explain(keys=None, ctx: Optional[CheckCtx] = None) -> "list[str]":
    """A row per check, `[x]` for the ones in `keys` (None: the defaults), then its detail line."""
    on = set(DEFAULT_KEYS if keys is None else keys)
    out = []
    for c in CHECKS:
        out.append(f"[{'x' if c['key'] in on else ' '}] {c['title']} ({c['key']})")
        out.append(f"    {detail_line(c, ctx)}")
    return out


def ordered(keys) -> "list[str]":
    """`keys` in CHECKS order, unknown ones dropped."""
    wanted = set(keys)
    return [k for k in KEYS if k in wanted]


def run_one(key: str, ctx: CheckCtx) -> "tuple[bool, list[str]]":
    """`(ok, result lines)`; any error the check did not expect is one `<Type>: <message>` line."""
    try:
        return True, list(check(key)["run"](ctx) or [])
    except CheckFailed as e:
        return False, e.lines or ["failed"]
    except Exception as e:
        return False, [f"{type(e).__name__}: {e}"]


def run_many(keys, ctx: CheckCtx, on_each: Optional[Callable] = None,
             stop: Optional[Callable[[], bool]] = None) -> "list[tuple[str, bool, list]]":
    """Run `keys` in CHECKS order; `on_each(key, ok, lines)` after each one (and `on_each(key, None, [])`
    before it starts); `stop()` true ends the list before the next one. Returns `[(key, ok, lines)]`."""
    out = []
    for key in ordered(keys):
        if stop is not None and stop():
            break
        if on_each is not None:
            on_each(key, None, [])
        ok, lines = run_one(key, ctx)
        out.append((key, ok, lines))
        if on_each is not None:
            on_each(key, ok, lines)
    return out


def default_ctx(cwd=None, **kw) -> CheckCtx:
    """A ctx for this home: the configured default model and the start's fake switch."""
    from halo_harness.start import fake
    from halo_harness.start.provider import default_model
    kw.setdefault("model", default_model())
    kw.setdefault("fake", fake.enabled())
    return CheckCtx(cwd=Path(cwd) if cwd else Path.cwd(), **kw)
