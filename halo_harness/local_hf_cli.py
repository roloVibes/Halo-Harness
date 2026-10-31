"""halo_harness.local_hf_cli -- Halo 3.3.5.0 R5: the CLI of Local -> Hugging Face (the same calls the page makes:
providers/hf_download.py, studio/local_hf_view.py, providers/local_server.py; dispatched by local_cli.cmd_local).

    halo local download <repo> [<file>] [--dir D] [--yes]   the licence line, then the progress; Ctrl+C keeps the
                                                             part file and the same line resumes it
    halo local ls [--dir D] [--host H] [--window N] [--json] what is on disk per folder, sizes, the fit word
    halo local rm <path> [--force]                           the uses card, then the files go
    halo local serve <path> [--runtime llama-server|mlx] [--window N] [--port P] [--keep] [--yes] [--backend B]
                                                             the flags and their sources, the URL, the hf:local ref
    halo local stop <id|port>   halo local servers [--json]   halo local log <id> [-n N]
"""

from __future__ import annotations

import argparse
import json
import sys
import threading
import time


def _gib(n) -> str:
    return f"{n / 2 ** 30:.2f} GiB" if isinstance(n, (int, float)) else "?"


def _ask(question: str, yes: bool, line: str) -> bool:
    if yes:
        return True
    if not sys.stdin.isatty():
        print(f"no terminal to ask on: run {line}")
        return False
    from halo_harness.local_cli import _confirm
    return _confirm(question, yes=False)


def cmd_download(argv: list) -> int:
    from halo_harness.models_library.hf_hub import token
    from halo_harness.providers.hf_download import HubError, download, prepare
    from halo_harness.studio.local_hf_api import dl_cli, pick_dir
    p = argparse.ArgumentParser(prog="halo local download", description="Download a Hugging Face repo (or one file) into a huggingface.model_dirs folder.")
    p.add_argument("repo", help="<org>/<name>")
    p.add_argument("file", nargs="?", default="", help="one file, or a quant word such as Q4_K_M (default: an MLX repo's every file, a GGUF repo's one quant)")
    p.add_argument("--dir", default="", help="a huggingface.model_dirs folder (default: the first)")
    p.add_argument("--yes", action="store_true", help="accept the licence line without asking")
    a = p.parse_args(argv)
    d, why = pick_dir(a.dir)
    if d is None:
        print(why)
        return 1
    tok = token()
    try:
        plan = prepare(a.repo, a.file or None, token=tok)
    except HubError as e:
        print(e.message)
        return 1
    print(plan["licence"]["line"])
    if plan["licence"]["prompt"]:
        print(f"  the repo says: {plan['licence']['prompt']}")
    for f in plan["files"]:
        print(f"  {f['name']}  {_gib(f['size'])}")
    print(f"  {len(plan['files'])} file(s), {_gib(plan['total'])} into {d}")
    if plan["needs_token"] and not tok:
        print("the repo is gated: set HF_TOKEN first (Setup -> Providers -> Hugging Face)")
        return 1
    if not _ask("Download it?", a.yes, dl_cli(plan["repo"], a.file, str(d))):
        return 1
    stop, got, last = threading.Event(), {}, [0.0]
    tty = sys.stdout.isatty()

    def on(obj):
        now = time.monotonic()
        if obj.get("total") and now - last[0] >= (0.25 if tty else 5.0):
            last[0] = now
            pct = 100.0 * (obj.get("completed") or 0) / obj["total"]
            text = f"  {obj.get('digest')}: {pct:5.1f}% of {_gib(obj['total'])}"
            print(text.ljust(70), end="\r" if tty else "\n", flush=True)

    t = threading.Thread(target=lambda: got.update(download(plan["repo"], a.file or None, dest_dir=d, token=tok, on_status=on,
                                                            cancel=stop, plan=plan)), daemon=True)
    t.start()
    try:
        while t.is_alive():
            t.join(0.2)
    except KeyboardInterrupt:
        stop.set()
        t.join(30)
        print()
        print(got.get("say") or "stopped: the part file stays; the same line resumes it")
        return 130
    if tty:
        print()
    print(got.get("say") or "")
    if got.get("ok"):
        print(f"serve it: halo local serve {got['path']}")
    return 0 if got.get("ok") else 1


def cmd_ls(argv: list) -> int:
    from halo_harness.studio.local_hf_view import dirs
    p = argparse.ArgumentParser(prog="halo local ls", description="What is on disk in each huggingface.model_dirs folder.")
    p.add_argument("--dir", default="", help="one folder only")
    p.add_argument("--host", default="", help="the host whose card rates the fit (default: this machine's)")
    p.add_argument("--window", type=int, default=None, help="the window the fit is rated at")
    p.add_argument("--json", action="store_true")
    a = p.parse_args(argv)
    from halo_harness.config.paths import bridge_home
    got = dirs(bridge_home(), host=a.host, window=a.window)
    rows = [x for x in got["dirs"] if not a.dir or x["path"] == a.dir or x["path"].endswith(a.dir)]
    if a.json:
        print(json.dumps({**got, "dirs": rows}, indent=2, default=str))
        return 0
    if not rows:
        print("no huggingface.model_dirs folder: halo local add <path>")
        return 0
    print(f"fit at {got['window']:,} on {got['host'] or 'no host with a card'}")
    for x in rows:
        print(f"{x['path']}  ({_gib(x['size'])}{'' if x['exists'] else ', not there'})")
        for m in x["models"]:
            on = "; ".join(f"served by {s['id']} on :{s['port']}" for s in m["served"] if s.get("alive"))
            name = f"{m['repo']} {m['file']}".strip() if m["repo"] else m["path"]
            print(f"  {m['kind']:<11} {_gib(m['size']):>10}  {m['fit']['level']:<7} {name}" + (f"  [{on}; {m['ref']}]" if on else ""))
        for part in x["partial"]:
            print(f"  part        {_gib(part['bytes']):>10}  {part['repo']}: stopped part-way (halo local download {part['repo']} resumes)")
        if not x["models"] and not x["partial"]:
            print("  (nothing yet: halo local download <repo>)")
    return 0


def cmd_rm(argv: list) -> int:
    from halo_harness.config.paths import bridge_home
    from halo_harness.studio.local_hf_api import _serving, _uses, find, remove
    from types import SimpleNamespace
    p = argparse.ArgumentParser(prog="halo local rm", description="Delete a model halo local ls lists (its files).")
    p.add_argument("path")
    p.add_argument("--force", action="store_true", help="delete it even when something names it, without asking")
    a = p.parse_args(argv)
    raw = find(a.path)
    if raw is None:
        print(f"halo local ls lists no model at {a.path}")
        return 1
    on = _serving(raw, bridge_home())
    if on:
        print(f"{on[0]['id']} serves it on port {on[0]['port']}: halo local stop {on[0]['id']} first")
        return 1
    import os
    uses = _uses(raw, SimpleNamespace(cwd=os.getcwd(), state_dir=bridge_home()))
    print(uses["line"])
    print(f"  {raw['path']}  {_gib(raw['size'])}")
    if not a.force and not _ask("Delete it?", False, f"halo local rm {raw['path']} --force"):
        return 1
    print(f"deleted {raw['path']} ({_gib(remove(raw))} freed)")
    return 0


def cmd_servers(argv: list) -> int:
    from halo_harness.config.paths import bridge_home
    from halo_harness.providers.local_server import servers
    p = argparse.ArgumentParser(prog="halo local servers", description="The local servers Halo started.")
    p.add_argument("--json", action="store_true")
    a = p.parse_args(argv)
    rows = servers(bridge_home())
    if a.json:
        print(json.dumps(rows, indent=2, default=str))
        return 0
    for e in rows:
        f = e.get("flags") or {}
        state = ("ready" if e.get("ready") else "loading") if e.get("alive") else "gone"
        print(f"{e['id']}  {e.get('kind')}  http://127.0.0.1:{e.get('port')}  {state}  hf:local/{e.get('model')}"
              f"  -c {f.get('window')} -ngl {f.get('ngl')} -np {f.get('parallel')}{'  (keep)' if e.get('keep') else ''}")
        print(f"  {e.get('model_path')}  log: {e.get('log')}")
    if not rows:
        print("no server Halo started: halo local serve <path> (halo local ls lists the models)")
    return 0


def cmd_stop(argv: list) -> int:
    from halo_harness.config.paths import bridge_home
    from halo_harness.providers.local_server import stop
    p = argparse.ArgumentParser(prog="halo local stop", description="Stop a server Halo started (its id, its port, or the model).")
    p.add_argument("server")
    a = p.parse_args(argv)
    got = stop(a.server, state_dir=bridge_home())
    if not got["ok"] and not got.get("ours"):
        from halo_harness.providers.local_use import stop_local_model  # a round 5c `halo local serve` row, by model
        ok, lines = stop_local_model(a.server)
        if ok:
            print("\n".join(lines))
            return 0
    print(got["say"])
    return 0 if got["ok"] else 1


def cmd_log(argv: list) -> int:
    from halo_harness.config.paths import bridge_home
    from halo_harness.providers.local_server import tail
    p = argparse.ArgumentParser(prog="halo local log", description="The tail of a server's log.")
    p.add_argument("server")
    p.add_argument("-n", type=int, default=40, help="lines (40)")
    a = p.parse_args(argv)
    got = tail(a.server, a.n, state_dir=bridge_home())
    print(f"{got['path']}:")
    print("\n".join(got["lines"]) or got["say"] or "(empty)")
    return 0 if got["ok"] else 1


from halo_harness.local_hf_serve_cli import cmd_serve  # noqa: E402  (the serve subcommand, its own module)

COMMANDS = {"download": cmd_download, "ls": cmd_ls, "rm": cmd_rm, "serve": cmd_serve, "stop": cmd_stop,
            "servers": cmd_servers, "log": cmd_log}
