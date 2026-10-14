"""halo_harness.flows.cli_run -- `halo flow run` and `halo flow resume`.

`run` validates the flow, makes a run folder (`new_run`) from the intake
flags and walks it with the real adapters, printing one line per finished
step (every event with --watch), the gate prompt when a human gate opens,
and the report at the end. Exit 0 when the run finished, 1 when it stopped.
With --watch and live posts, it then keeps sampling their metrics on the
metrics step's `every` (flows/watch.py).
"""

from __future__ import annotations

import argparse
import os
import re
import sys

from halo_harness.flows import spec as fspec, state

# A test seam: called with the Adapters keyword arguments; None = the real Adapters.
ADAPTER_FACTORY = None


def _value(text: str):
    t = text.strip()
    if re.fullmatch(r"-?\d+", t):
        return int(t)
    if re.fullmatch(r"-?\d+\.\d*", t):
        return float(t)
    return t


def parse_inputs(args) -> "tuple[dict, dict]":
    intake: dict = {}
    for item in args.input or []:
        key, sep, val = item.partition("=")
        if not sep or not key.strip():
            raise ValueError(f"--input takes KEY=VALUE, got {item!r}")
        intake[key.strip()] = val.strip()
    if args.brief is not None:
        intake["brief"] = args.brief
    if args.asset:
        intake["assets"] = [os.path.abspath(os.path.expanduser(a)) for a in args.asset]
    if args.project:
        intake["project"] = args.project
    overrides: dict = {}
    for item in args.set or []:
        key, sep, val = item.partition("=")
        step, dot, field = key.partition(".")
        if not sep or not dot or not step or not field:
            raise ValueError(f"--set takes STEP.KEY=VALUE, got {item!r}")
        overrides.setdefault(step, {})[field] = _value(val)
    return intake, overrides


def _printer(watch: bool):
    def on_event(entry: dict) -> None:
        kind, data = entry.get("kind"), entry.get("data") or {}
        if watch:
            print(state.format_line(entry), flush=True)
            return
        if kind == "state" and data.get("state") in ("done", "failed", "waiting"):
            print(state.format_line(entry), flush=True)
        elif kind in ("gate", "post", "metric") or (kind == "state" and str(entry.get("text", "")).startswith("resume")):
            print(state.format_line(entry), flush=True)
            gate = data.get("gate") if isinstance(data.get("gate"), dict) else None
            if gate:
                for line in str(gate.get("text") or "").splitlines()[:20]:
                    print(f"      {line}", flush=True)
    return on_event


def drive(run_dir, args) -> int:
    from halo_harness.flows.adapters import Adapters
    from halo_harness.flows.report import format_report
    from halo_harness.flows.run import run
    adapters = (ADAPTER_FACTORY or Adapters)(model=getattr(args, "model", None), auto_accept=bool(args.yes),
                                             cwd=os.getcwd())
    try:
        report = run(run_dir, adapters=adapters, on_event=_printer(bool(args.watch)))
    except KeyboardInterrupt:
        print(f"\ninterrupted; continue with: halo flow resume {run_dir.name}", file=sys.stderr)
        return 130
    print(format_report(report))
    if args.watch and report.get("status") == "finished":
        from halo_harness.flows.watch import watch_metrics
        try:
            watch_metrics(run_dir, say=lambda t: print(t, flush=True))
        except KeyboardInterrupt:
            print("metrics polling ended", file=sys.stderr)
    return 0 if report.get("status") == "finished" else 1


def _add_common(p: argparse.ArgumentParser) -> None:
    p.add_argument("--model", default=None, help="the model for every role and org position (default: the lineup's)")
    p.add_argument("--yes", action="store_true", help="accept every human gate automatically")
    p.add_argument("--watch", action="store_true", help="print every event as it lands")


def cmd_run(rest: list) -> int:
    p = argparse.ArgumentParser(prog="halo flow run")
    p.add_argument("name")
    p.add_argument("--brief", default=None)
    p.add_argument("--input", action="append", metavar="KEY=VALUE")
    p.add_argument("--asset", action="append", metavar="PATH")
    p.add_argument("--project", default=None)
    p.add_argument("--set", action="append", metavar="STEP.KEY=VALUE", help="override a step's set value")
    p.add_argument("--resume", action="store_true", help="continue this flow's last unfinished run instead")
    _add_common(p)
    a = p.parse_args(rest)
    if a.resume:
        runs = [r for r in state.list_runs() if r["name"] == a.name and r["status"] != "finished"]
        if not runs:
            print(f"halo flow run --resume: no unfinished run of {a.name!r}", file=sys.stderr)
            return 1
        run_dir = state.find_run(runs[-1]["run"])
        print(f"resuming run {run_dir.name}")
        return drive(run_dir, a)
    path = fspec.find_flow(a.name)
    if path is None:
        print(f"halo flow run: no flow {a.name!r} (halo flow new {a.name} makes one from a template; "
              f"templates: {', '.join(fspec.template_names())})", file=sys.stderr)
        return 2
    try:
        spec = fspec.load_flow(path)
        intake, overrides = parse_inputs(a)
    except ValueError as e:
        print(f"halo flow run: {e}", file=sys.stderr)
        return 2
    lines = fspec.validate_flow(spec)
    for line in lines:
        print(f"  {line}", file=sys.stderr)
    if fspec.errors(lines):
        print(f"halo flow run: {path} has problems; nothing ran", file=sys.stderr)
        return 2
    run_dir = state.new_run(spec, intake, source=str(path), overrides=overrides)
    print(f"run {run_dir.name}: flow {spec.get('name')} from {path}")
    return drive(run_dir, a)


def cmd_resume(rest: list) -> int:
    p = argparse.ArgumentParser(prog="halo flow resume")
    p.add_argument("run")
    _add_common(p)
    a = p.parse_args(rest)
    run_dir = state.find_run(a.run)
    if run_dir is None:
        print(f"halo flow resume: no run {a.run!r}", file=sys.stderr)
        return 2
    print(f"resuming run {run_dir.name}")
    return drive(run_dir, a)
