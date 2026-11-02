"""halo_harness.voice_cli -- `halo voice` (Halo 3.3.9.0 R1; docs/COMMANDS-voice.md, docs/VOICE.md):

    halo voice [models] [--json]              the speech catalog: each model's kind, engine, repo, download size,
                                              footprint on a GPU and on the CPU, built or declared, present or not
    halo voice download <model> [--dir D] [--yes]   the size and the folder first, then the hub download `halo local
                                              download` makes (Ctrl+C keeps the part file; the same line resumes)
    halo voice rm <model> [--force]           its files go (not while a speech server serves it)
    halo voice serve <model> [--device auto|cpu|cuda] [--port P] [--log F]   the speech server in the foreground
                                              (`halo local serve --stt | --tts <model>` runs it in the background)

The engines are the optional extra: without it `serve` prints the one install line and exits 2; the catalog,
download and rm need nothing extra.
"""

from __future__ import annotations

import argparse
import json
import sys
import threading


def _models(argv: list) -> int:
    from halo_harness.voice import catalog, engines, install
    p = argparse.ArgumentParser(prog="halo voice models", description="The speech catalog and what is on disk.")
    p.add_argument("--json", action="store_true")
    a = p.parse_args(argv)
    rows = []
    for r in catalog.ROWS:
        where = install.present(r)
        rows.append({**r.to_json(), "present": where is not None, "path": str(where) if where else None})
    gone = engines.missing()
    if a.json:
        print(json.dumps({"models": rows, "extra_missing": gone}, indent=2))
        return 0
    for r in rows:
        row = catalog.get(r["name"])
        state = "present" if r["present"] else f"not present (halo voice download {r['name']}, {r['download_gb']:g} GB)"
        built = "built" if r["built"] else "declared, no engine in this build"
        print(f"{r['kind']:<4} {r['name']:<30} {r['engine']:<15} {catalog.footprint(row)}; {built}; {state}")
        print(f"     {r['repo']}{catalog.unverified(row)} -- {r['note']}")
    print(f"the engines: {'installed' if not gone else 'not installed -- ' + engines.INSTALL_LINE}")
    return 0


def _ask(question: str, yes: bool, line: str) -> bool:
    from halo_harness.local_hf_cli import _ask as ask
    return ask(question, yes, line)


def _download(argv: list) -> int:
    from halo_harness.models_library.hf_hub import token
    from halo_harness.providers.hf_download import HubError
    from halo_harness.studio.local_hf_api import pick_dir
    from halo_harness.voice import catalog, install
    p = argparse.ArgumentParser(prog="halo voice download", description="Download a speech model into a "
                                "huggingface.model_dirs folder (the files its engine loads).")
    p.add_argument("model", help="a catalog name (halo voice models)")
    p.add_argument("--dir", default="", help="a huggingface.model_dirs folder (default: the first)")
    p.add_argument("--yes", action="store_true", help="download without asking")
    a = p.parse_args(argv)
    row = catalog.get(a.model)
    if row is None:
        print(f"{a.model} is not in the speech catalog: {', '.join(r.name for r in catalog.ROWS)}")
        return 1
    where = install.present(row)
    if where is not None:
        print(f"{row.name} is present: {where}")
        return 0
    d, why = pick_dir(a.dir)
    if d is None:
        print(why)
        return 1
    print(f"{row.name}: {row.download_gb:g} GB from {row.repo}{catalog.unverified(row)} into {d}")
    tok = token()
    try:
        plan = install.plan(row.name, token=tok)
    except HubError as e:
        print(e.message)
        return 1
    print(plan["licence"]["line"])
    for f in plan["files"]:
        print(f"  {f['name']}  {install.gb(f['size'])}")
    print(f"  {len(plan['files'])} file(s), {install.gb(plan['total'])}")
    if plan["needs_token"] and not tok:
        print("the repo is gated: set HF_TOKEN first (Setup -> Providers -> Hugging Face)")
        return 1
    if not _ask("Download it?", a.yes, f"halo voice download {row.name} --yes"):
        return 1
    got: dict = {}
    stop = threading.Event()
    t = threading.Thread(target=lambda: got.update(install.download(row.name, dest_dir=d, token=tok, cancel=stop,
                                                                    plan_=plan)), daemon=True)
    t.start()
    try:
        while t.is_alive():
            t.join(0.2)
    except KeyboardInterrupt:
        stop.set()
        t.join(30)
        print(got.get("say") or "stopped: the part file stays; the same line resumes it")
        return 130
    print(got.get("say") or "")
    if got.get("ok"):
        kind = row.kind if row.kind in ("stt", "tts") else ""
        print(f"serve it: halo local serve --{kind} {row.name}" if kind and row.built else
              f"{catalog.no_engine_line(row)}" if kind else "R2's loop reads it")
    return 0 if got.get("ok") else 1


def _rm(argv: list) -> int:
    from halo_harness.config.paths import bridge_home
    from halo_harness.voice import catalog, install
    p = argparse.ArgumentParser(prog="halo voice rm", description="Delete a speech model's files.")
    p.add_argument("model")
    p.add_argument("--force", action="store_true", help="delete without asking")
    a = p.parse_args(argv)
    row = catalog.get(a.model)
    where = install.present(row) if row else None
    if where is None:
        print(f"{a.model} is not on disk (halo voice models)")
        return 1
    on = install.serving(row.name, bridge_home())
    if on:
        print(f"{on['id']} serves it on port {on['port']}: halo local stop {on['id']} first")
        return 1
    print(f"  {where}")
    if not a.force and not _ask("Delete it?", False, f"halo voice rm {row.name} --force"):
        return 1
    freed, target = install.remove(row.name)
    print(f"deleted {target} ({install.gb(freed)} freed)")
    return 0


def _serve(argv: list) -> int:
    from halo_harness.voice import catalog, server
    if argv and not argv[0].startswith("-"):
        row = catalog.get(argv[0])
        argv = ["--model", argv[0]] + (["--kind", row.kind] if row and row.kind in ("stt", "tts") else []) + argv[1:]
    return server.main(argv)


COMMANDS = {"models": _models, "download": _download, "rm": _rm, "serve": _serve}


def cmd_voice(argv: list) -> int:
    if not argv or argv[0] in ("--json",):
        return _models(argv)
    if argv[0] in ("-h", "--help"):
        print(__doc__.split("\n\n", 1)[1].split("\n\nThe engines")[0])
        return 0
    fn = COMMANDS.get(argv[0])
    if fn is None:
        print(f"halo voice: no subcommand {argv[0]!r} (models, download, rm, serve)", file=sys.stderr)
        return 2
    return fn(argv[1:])

