"""halo_harness.local_cli -- `halo local [--terminal] [--refresh]` and its round 5c
subcommands (`add`/`forget`/`serve`/`stop`/`import`/`runtime remove`), the
CLI twin of `/local`'s TUI dialog and `commands/builtins.py`'s `/local`
print-mode fallback. The default (no subcommand) view renders `providers.
local_models.build_local_view`/`format_local_view`, so none of the three
surfaces can quietly disagree about what's running/cached locally; every
subcommand below is a thin argument-parsing wrapper over `providers.
local_model_dirs`/`local_use`, which hold the actual logic (and its own
tests) independent of argparse/stdin. 3.3.5.0 R1: on a real terminal `halo
local` opens Studio's Local section (local_tab_cli.py); `--terminal` prints
the merged view here, and `halo local hosts | models | resources` print the
Local pages' lines. 3.3.5.0 R5: `halo local download | ls | rm | serve | stop |
servers | log` (local_hf_cli.py), and bare `halo local` opens the Hugging Face page. 3.3.6.0 R5: `halo local
bench | tune | changes | revert` (local_bench_cli.py).
"""

from __future__ import annotations

import argparse
import sys


def _confirm(question: str, *, yes: bool) -> bool:
    """`--yes`, else a plain stdin yes/no -- the SAME idiom `halo work-
    matrix apply` already uses (`input(... "[y/N] ")`, EOFError -> no)."""
    if yes:
        return True
    try:
        answer = input(f"{question} [y/N] ").strip().lower()
    except EOFError:
        answer = ""
    return answer in ("y", "yes")


def _cmd_default(argv: list) -> int:
    from halo_harness.providers.local_models import build_local_view, format_local_view
    parser = argparse.ArgumentParser(
        prog="halo local", add_help=True,
        description="Merged local-model view: Ollama hosts, running Hugging Face local servers "
                     "(auto-detected and manual), the Hugging Face Hub cache, and huggingface.model_dirs.")
    parser.add_argument("--terminal", action="store_true", help="print the merged view here (on a real terminal "
                         "`halo local` opens Studio's Local section instead)")
    parser.add_argument("--refresh", action="store_true",
                         help="bypass the Ollama catalog's short-TTL cache and probe every configured "
                              "huggingface.local_servers entry (skipped otherwise -- see docs/MODELS.md)")
    args = parser.parse_args(argv)
    print(format_local_view(build_local_view(refresh=args.refresh)))
    # Halo 3.2.3.0 R2: an Ollama on this machine that is not an ollama.hosts entry yet
    from halo_harness.providers.ollama_discover_hosts import found_not_added_lines
    found = found_not_added_lines(force=args.refresh)
    if found:
        print()
        print("Ollama (found, not added):")
        for line in found:
            print(f"  {line}")
    return 0


def _cmd_add(argv: list) -> int:
    from halo_harness.providers.local_model_dirs import add_model_dir
    parser = argparse.ArgumentParser(prog="halo local add", description="Add a folder to huggingface.model_dirs.")
    parser.add_argument("path")
    args = parser.parse_args(argv)
    ok, message = add_model_dir(args.path)
    print(message)
    return 0 if ok else 1


def _cmd_forget(argv: list) -> int:
    from halo_harness.providers.local_model_dirs import forget_model_dir
    parser = argparse.ArgumentParser(prog="halo local forget",
                                      description="Remove a folder from huggingface.model_dirs.")
    parser.add_argument("path")
    args = parser.parse_args(argv)
    ok, message = forget_model_dir(args.path)
    print(message)
    return 0 if ok else 1


def _cmd_serve(argv: list) -> int:
    from halo_harness.providers.local_use import serve_local_model
    parser = argparse.ArgumentParser(prog="halo local serve", description="Serve a file-backed model on a "
                                      "free loopback port with a managed llama-server/mlx_lm runtime.")
    parser.add_argument("model", help="an exact .gguf/model-folder path, a name shown by `halo local`, or "
                         "(round 5f, with --runtime mlx_lm) a bare Hugging Face Hub repo id, e.g. "
                         "mlx-community/Qwen2.5-7B-Instruct-4bit -- the explicit form of hf:mlx/<org>/<repo>")
    parser.add_argument("--runtime", choices=("llama-server", "mlx_lm"), default=None,
                         help="mlx_lm is Apple Silicon only; round 5f: also accepts a bare repo id (above)")
    parser.add_argument("--backend", choices=("cuda", "vulkan", "cpu", "metal"), default=None,
                         help="override which llama-server build to fetch (default: CUDA if your driver "
                              "reports a version, else Vulkan; Metal on macOS)")
    parser.add_argument("--port", type=int, default=None)
    parser.add_argument("--keep", action="store_true", help="keep running after this halo process exits")
    parser.add_argument("--yes", action="store_true", help="consent to fetching the llama-server runtime "
                         "if none is found, without asking")
    args = parser.parse_args(argv)
    ok, lines = serve_local_model(args.model, runtime=args.runtime, port=args.port, keep=args.keep,
                                   backend=args.backend, confirm=lambda q: _confirm(q, yes=args.yes))
    for line in lines:
        print(line)
    return 0 if ok else 1


def _cmd_stop(argv: list) -> int:
    from halo_harness.providers.local_use import stop_local_model
    parser = argparse.ArgumentParser(prog="halo local stop", description="Stop a model started by `halo local serve`.")
    parser.add_argument("model")
    args = parser.parse_args(argv)
    ok, lines = stop_local_model(args.model)
    for line in lines:
        print(line)
    return 0 if ok else 1


def _cmd_import(argv: list) -> int:
    from halo_harness.providers.local_use import import_local_model
    parser = argparse.ArgumentParser(prog="halo local import", description="Copy a .gguf file into Ollama's "
                                      "own model store (ollama create via /api/create).")
    parser.add_argument("model", help="an exact .gguf path, or a name shown by `halo local`")
    parser.add_argument("--name", default=None, help="the new ol:<name> (default: the file's own stem)")
    parser.add_argument("--host", default=None, help="an ollama.hosts entry name (default: the default host)")
    parser.add_argument("--yes", action="store_true")
    args = parser.parse_args(argv)
    ok, lines = import_local_model(args.model, name=args.name, host_name=args.host,
                                    confirm=lambda q: _confirm(q, yes=args.yes),
                                    on_status=lambda s: print(f"  {s.get('status', s)}"))
    for line in lines:
        print(line)
    return 0 if ok else 1


def _cmd_runtime(argv: list) -> int:
    parser = argparse.ArgumentParser(prog="halo local runtime", description="Manage fetched llama.cpp runtimes.")
    sub = parser.add_subparsers(dest="action", required=True)
    remove_p = sub.add_parser("remove", help="delete a fetched llama-server runtime from ~/.halo/runtimes/")
    remove_p.add_argument("version", nargs="?", default=None, help="a release tag (default: every version)")
    args = parser.parse_args(argv)
    if args.action == "remove":
        from halo_harness.config.paths import bridge_home
        from halo_harness.providers.local_runtime_fetch import remove_runtime
        ok, message = remove_runtime(bridge_home(), args.version)
        print(message)
        return 0 if ok else 1
    return 2


def _cmd_warm(argv: list) -> int:
    """2.0.7 ollama polish: `halo local warm [MODELS...] [--host NAME]
    [--keep-alive DURATION]` -- pre-load the session's local-role models
    (or the named ones) so the FIRST real call doesn't pay the cold-load.
    One 1-token /api/chat per model at its fit-num_ctx, `keep_alive` set
    so the weights actually STAY (default: 30m, matching a work session;
    `--keep-alive 0` drops them right after, `--keep-alive -1` forever).
    With no model args, warms every `ol:` ref in the roles table plus the
    default `model` when it is one."""
    from halo_harness.providers.ollama import _get_json, ollama_names_match, resolve_ollama_host
    parser = argparse.ArgumentParser(
        prog="halo local warm",
        description="Pre-load local models so the first real call skips the cold-load.")
    parser.add_argument("models", nargs="*", help="Model names (default: every ol: role in the table)")
    parser.add_argument("--host", default=None, help="A named Ollama host (default: the default host)")
    parser.add_argument("--keep-alive", default="30m",
                        help="How long weights stay resident after warming (default 30m; -1 = forever)")
    args = parser.parse_args(argv)
    # Ollama reads a bare JSON number as seconds (negative = forever) but a
    # string only with a unit ("30m"), so "-1" / "0" / "3600" go out as numbers.
    keep_alive = args.keep_alive
    try:
        keep_alive = int(keep_alive)
    except ValueError:
        pass
    host = resolve_ollama_host(args.host)
    if host is None:
        print("halo local warm: no Ollama host configured -- set ollama.hosts in ~/.halo/config.json")
        return 2
    models = list(args.models)
    if not models:
        from halo_harness.roles import configured_role_table
        from halo_harness.theme import get_config_value
        for value in list(configured_role_table().values()) + [get_config_value("model", default=None)]:
            if isinstance(value, str) and value.startswith("ol:"):
                name = value[3:].split("@")[0]
                if name and name not in models:
                    models.append(name)
    if not models:
        print("halo local warm: no models named and no ol: roles configured -- nothing to warm.")
        return 0
    # Check what is actually resident first (/api/ps): already-loaded
    # models are reported, not re-paid.
    ps = _get_json(host, "/api/ps") or {}
    resident = [m.get(k) for m in ps.get("models", []) if isinstance(m, dict) for k in ("name", "model")]
    failed = []
    for name in models:
        if any(ollama_names_match(name, r) for r in resident):
            print(f"  {name}: already resident -- nothing to do")
            continue
        # A tiny 1-token chat forces the load; the fit ctx is not needed
        # for warming (the first real call re-seats it if larger).
        body = {"model": name, "stream": False,
                "messages": [{"role": "user", "content": "hi"}],
                "options": {"num_predict": 1},
                "keep_alive": keep_alive}
        out = _get_json(host, "/api/chat", method="POST", body=body, timeout=180.0)
        if out is None:
            failed.append(name)
            print(f"  {name}: FAILED to load (host reachable? model pulled? keep-alive syntax is 30m, 24h or -1)")
        else:
            print(f"  {name}: warmed (keep_alive={keep_alive})")
    if failed:
        print(f"halo local warm: {len(failed)} model(s) failed: {', '.join(failed)}")
        return 1
    print(f"halo local warm: {len(models)} model(s) ready.")
    return 0


_SUBCOMMANDS = {"add": _cmd_add, "forget": _cmd_forget, "serve": _cmd_serve, "stop": _cmd_stop,
                "import": _cmd_import, "runtime": _cmd_runtime, "warm": _cmd_warm}


def _hf_commands() -> dict:
    """3.3.5.0 R5: download | ls | rm | serve | stop | servers | log (local_hf_cli.py; serve and stop replace round
    5c's, which stay as `_cmd_serve` / `_cmd_stop` for the code that calls them)."""
    from halo_harness.local_hf_cli import COMMANDS
    return COMMANDS


def cmd_local(argv: list) -> int:
    from halo_harness.local_bench_cli import COMMANDS as BENCH  # 3.3.6.0 R5: bench | tune | changes | revert
    if argv and argv[0] in BENCH:
        return BENCH[argv[0]](argv[1:])
    if argv and argv[0] in _hf_commands():
        return _hf_commands()[argv[0]](argv[1:])
    if argv and argv[0] in _SUBCOMMANDS:
        return _SUBCOMMANDS[argv[0]](argv[1:])
    from halo_harness.local_tab_cli import cmd_tab  # 3.3.5.0 R1: the door into Studio's Local tab, and its printers
    rc = cmd_tab(argv)
    if rc >= 0:
        return rc
    return _cmd_default([a for a in argv if a in ("--terminal", "--refresh", "-h", "--help")])
