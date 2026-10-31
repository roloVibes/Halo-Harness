"""halo_harness.models_control_cli -- Halo 3.3.5.0 R3: `halo models pull | rm | load | unload | copy | rename |
twin | loaded` (and `--host` on `halo models show`, model_card_cli.py): an Ollama host's models from the terminal,
the same calls as Studio's Local tab (providers/ollama_control.py, providers/ollama_load.py, providers/
ollama_tune.py; every Studio button's title is one of these lines). `--host` names an `ollama.hosts` entry (the
default host without it); the call goes to that host's URL. Never a model call.

    halo models pull <name> [--host H]          progress on one line; Ctrl+C stops it (Ollama keeps the layers)
    halo models rm <name> [--host H] [--force]  the uses card first; asks unless --force; waits for live sessions
    halo models load <name> [--host H] [--num-ctx N] [--keep-alive K]   halo models unload <name> [--host H]
    halo models copy <src> <dst> [--host H]     halo models rename <src> <dst> [--host H]
    halo models twin <name> --window N [--host H]                       halo models loaded [--host H]
"""

from __future__ import annotations

import argparse
import json
import sys
import threading

VERBS = ("pull", "rm", "load", "unload", "copy", "rename", "twin", "loaded")
HELP = {"pull": "Pull a model onto an Ollama host (a library name, or hf.co/<repo>:<quant>)",
        "rm": "Delete a model from an Ollama host (prints what uses it first)",
        "load": "Load a model into the host's memory now (a warm generate at the profile's window)",
        "unload": "Unload a model now (keep_alive 0)", "copy": "Copy a model to a new name (the same layers)",
        "rename": "Rename a model (a copy, then the delete of the old name)",
        "twin": "Make a tuned twin (FROM the model, num_ctx = --window, every layer on the GPU)",
        "loaded": "What is loaded on the host now (/api/ps)"}


def _parser(verb: str) -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog=f"halo models {verb}", description=HELP[verb])
    if verb in ("copy", "rename"):
        p.add_argument("src", help="the model")
        p.add_argument("dst", help="the new name")
    elif verb != "loaded":
        p.add_argument("name", help="the model, e.g. qwen3.5:9b")
    p.add_argument("--host", default="", help="the ollama.hosts entry (the default host without it)")
    p.add_argument("--json", action="store_true", help="the answer as JSON")
    if verb == "rm":
        p.add_argument("--force", action="store_true", help="delete it although a lineup, role or profile names it")
    if verb == "twin":
        p.add_argument("--window", type=int, required=True, help="the twin's num_ctx")
    if verb == "load":
        p.add_argument("--num-ctx", type=int, default=None, help="the window to load at (default: the profile's)")
        p.add_argument("--keep-alive", default=None, help="how long it stays loaded (5m, 1h, -1)")
    return p


def _host(name: str):
    from halo_harness.providers.ollama import resolve_ollama_host
    host = resolve_ollama_host(name or None)
    if host is None:
        print(f"halo models: no Ollama host named {name!r} (halo ollama lists them)", file=sys.stderr)
    return host


def _say(got: dict, as_json: bool) -> int:
    print(json.dumps(got, indent=2, default=str) if as_json else got.get("say") or ("done" if got.get("ok") else "failed"),
          file=sys.stdout if got.get("ok") or as_json else sys.stderr)
    return 0 if got.get("ok") else 1


def progress_line(job: dict) -> str:
    """'pulling 1a2b3c 45.0 %  1.2 GB of 2.7 GB  120 MB/s  eta 13 s' from a pull job's view."""
    gb = lambda n: f"{n / 1e9:.1f} GB" if isinstance(n, (int, float)) else "?"  # noqa: E731
    parts = [str(job.get("status") or "")]
    if job.get("percent") is not None:
        parts.append(f"{job['percent']:.1f} %  {gb(job.get('completed'))} of {gb(job.get('total'))}")
    if job.get("speed"):
        parts.append(f"{job['speed'] / 1e6:.0f} MB/s")
    if job.get("eta") is not None:
        parts.append(f"eta {job['eta']} s")
    return "  ".join(p for p in parts if p)


def _pull(host, name: str, as_json: bool) -> int:
    from halo_harness.studio.local_pull_job import _measure
    from halo_harness.providers.ollama_control import pull
    import time
    cancel, box, job = threading.Event(), {}, {"layers": {}, "samples": [], "status": "", "speed": None, "eta": None}
    tty = sys.stdout.isatty() and not as_json

    def on(obj: dict) -> None:
        _measure(job, obj, time.monotonic())
        if tty:
            print("\r" + progress_line(job)[:110].ljust(110), end="", flush=True)

    t = threading.Thread(target=lambda: box.update(pull(host, name, on_status=on, cancel=cancel)), daemon=True)
    t.start()
    while t.is_alive():
        try:
            t.join(0.2)
        except KeyboardInterrupt:
            cancel.set()
    if tty:
        print()
    if box.get("cancelled"):
        _say(box, as_json)
        return 130
    return _say({**box, "total": job.get("total"), "completed": job.get("completed")}, as_json)


def _rm(host, name: str, args) -> int:
    from halo_harness.providers.ollama_control import delete
    from halo_harness.providers.ollama_tune_store import forget_twin
    from halo_harness.studio.local_uses import uses_of
    from halo_harness.config.paths import bridge_home
    u = uses_of(f"ol:{name}@{host.name}")
    if u["any"] and not args.json:
        print(u["line"])
    if u["live"]:
        print(f"{u['live']} live session(s) on {name}: the delete runs once they end or move to another model", file=sys.stderr)
        return 1
    if u["any"] and not args.force:
        if not sys.stdin.isatty():
            print("delete it anyway: halo models rm " + name + (f" --host {host.name}" if args.host else "") + " --force",
                  file=sys.stderr)
            return 1
        if input("delete it anyway? [y/N] ").strip().lower() not in ("y", "yes"):
            print("kept")
            return 1
    got = delete(host, name)
    if got["ok"]:
        forget_twin(bridge_home(), host_url=host.url, twin=name)
    return _say({**got, "uses": u}, args.json)


def _twin(host, name: str, args) -> int:
    from halo_harness.config.paths import bridge_home
    from halo_harness.providers.ollama_tune import TuneError, create_twin, plan_twin
    try:
        plan = plan_twin(host, name, args.window, state_dir=bridge_home())
    except TuneError as e:
        print(f"halo models twin: {e.message}", file=sys.stderr)
        return 1
    if not args.json:
        print(plan.line)
    got = create_twin(host, plan, on_progress=None if args.json else (lambda s: print(f"  {s}")), state_dir=bridge_home())
    verified = None
    if got.ok:  # 3.3.6.0 R1: load it at its window, read /api/ps and the log, time one warm call
        from halo_harness.providers.ollama_twin_verify import verify
        if not args.json:
            print(f"  verifying: loads {plan.twin} at {plan.window:,} and times one warm call (the first is never timed)")
        verified = verify(host, plan.twin, plan.window, state_dir=bridge_home())
        if not args.json:
            print(f"  {verified['line']}")
    return _say({"ok": got.ok, "say": f"{got.message} [{plan.ref}]" if got.ok else got.message, "twin": plan.twin,
                 "ref": plan.ref, "verify": verified}, args.json)


def _loaded(host, as_json: bool) -> int:
    from halo_harness.providers.ollama_control import loaded
    got = loaded(host)
    if as_json or not got["ok"]:
        return _say(got, as_json)
    for m in got["models"]:
        print(f"{m['model']}  {m['vram_pct'] if m['vram_pct'] is not None else '?'}% on the GPU  "
              f"window {m['context_length'] or '?'}  until {m['expires'] or '?'}")
    print(got["say"])
    return 0


def cmd_models_control(verb: str, argv: list) -> int:
    from halo_harness.providers import ollama_control as C
    from halo_harness.providers.ollama_load import load, unload
    args = _parser(verb).parse_args(argv)
    host = _host(args.host)
    if host is None:
        return 1
    if verb == "pull":
        return _pull(host, args.name, args.json)
    if verb == "rm":
        return _rm(host, args.name, args)
    if verb == "twin":
        return _twin(host, args.name, args)
    if verb == "loaded":
        return _loaded(host, args.json)
    if verb in ("copy", "rename"):
        return _say((C.rename if verb == "rename" else C.copy)(host, args.src, args.dst), args.json)
    if verb == "load":
        keep = args.keep_alive
        keep = int(keep) if isinstance(keep, str) and keep.lstrip("-").isdigit() else keep  # -1 / 3600 go out as numbers
        return _say(load(host, args.name, num_ctx=args.num_ctx, keep_alive=keep), args.json)
    return _say(unload(host, args.name), args.json)
