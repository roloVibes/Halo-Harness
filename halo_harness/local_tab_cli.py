"""halo_harness.local_tab_cli -- Halo 3.3.5.0 R1: `halo local` is the door into
Studio's Local section (the machines that serve models, and the models they
serve), and `halo local hosts | models | resources` print what its pages show.

    halo local [page]            opens Studio on Local (`?mode=local&page=huggingface` bare, 3.3.5.0 R5;
                                 studio/local_door.py) on a real terminal; the
                                 page word picks the page (resources, hosts,
                                 models, library, huggingface, logs, benchmarks,
                                 steward; 3.3.6.0 R3: logs)
    halo local --terminal        the merged local-model view here instead (the
                                 pre-3.3.5.0 `halo local`; `--refresh` as before)
    halo local hosts             one block per host: kind, url, who serves it,
                                 version, what is loaded, who calls it
    halo local models [--host H] one line per installed model: the card's chips,
                                 the fit meter, the window and its source
    halo local resources         one sample of this machine now: GPU, VRAM and
                                 who holds it, RAM, CPU, temperature, each with
                                 its source

The printers read what the pages read (studio/local_hosts_view.py,
local_models_view.py, ollama_steward/resources.py); nothing here writes.
"""

from __future__ import annotations

import sys
import time

PRINTERS = ("hosts", "models", "resources")


def _gib(n) -> str:
    return f"{n / 2 ** 30:.1f} GiB" if isinstance(n, (int, float)) else "?"


def hosts_lines(state_dir) -> "list[str]":
    from halo_harness.studio.local_hosts_view import hosts
    out = []
    for h in hosts(state_dir)["hosts"]:
        who = "served here" if h["served_here"] else (f"served by {h['served_by']}" if h["served_by"] else h["source"])
        out.append(f"{h['name']}  {h['kind']}  {h['url']}  ({who}; {h['source']})" + (f"  v{h['version']}" if h["version"] else ""))
        if h["loaded"]:
            out.append("  loaded: " + "; ".join(f"{m['model']} {_gib(m['size_vram'])} on the GPU"
                                                 + (f" ({m['vram_pct']}%)" if m.get("vram_pct") is not None else "")
                                                 for m in h["loaded"]))
        if h["users"]:
            out.append("  calls in 24 h: " + ", ".join(f"{u['from'] or 'this machine'} {u['calls']}" for u in h["users"]))
        if h["finding"]:
            out.append(f"  steward: {h['finding']}")
        c = h["controls"]
        out.append(f"  load / unload: {'from here, via ' + c['via'] if c['ok'] else c['why']}")
    return out or ["no host: add one in Setup -> Providers -> Ollama, or halo ollama discover --add"]


def models_lines(state_dir, host: str = "") -> "list[str]":
    from halo_harness.studio.local_models_view import models
    out = []
    for h in models(state_dir, host)["hosts"]:
        out.append(f"{h['name']} ({h['kind']}): {len(h['models'])} model{'s' if len(h['models']) != 1 else ''}")
        for m in h["models"]:
            chips = " ".join(v for k, v in (m["card"].get("chips") or {}).items() if v and k != "window")
            w = (m["card"].get("window") or {})
            win = f"window {w['tokens']:,} ({w.get('source')})" if w.get("tokens") else "window ?"
            out.append(f"  {m['model']:<40} fit {m['fit'].get('level', '?'):<7} {win}  {chips}".rstrip())
    return out or [f"no host named {host!r}" if host else "no host configured"]


def resources_lines(state_dir) -> "list[str]":
    from halo_harness.ollama_steward.resources import Sampler
    s = Sampler(state_dir)  # its CPU reader is primed: the figure is the share over the half second below
    time.sleep(0.5)
    out = []
    for x in s.sample_once():
        src = x["sources"]
        out.append(f"{x['host']} at {time.strftime('%H:%M:%S', time.localtime(x['t']))}:")
        gpu = f"{x['gpu']}%" if x["gpu"] is not None else "n/a"
        out.append(f"  GPU use {gpu}  ({src['gpu']})")
        out.append(f"  VRAM {_gib(x['vram_used'])} of {_gib(x['vram_total'])}" + (f", most held by {x['holder']}" if x["holder"] else "")
                   + f"  ({src['vram']}; holder: {src['holder']})")
        out.append(f"  RAM {_gib(x['ram_used'])} of {_gib(x['ram_total'])}  ({src['ram']})")
        out.append(f"  CPU {x['cpu']}%  ({src['cpu']})" if x["cpu"] is not None else f"  CPU ?  ({src['cpu']})")
        out.append(f"  temperature {x['temp']} C  ({src['temp']})" if x["temp"] is not None else f"  temperature: {src['temp']}")
    return out


def _open(page: str) -> bool:
    from halo_harness.studio.local_door import LocalTarget
    from halo_harness.studio.setup_door import cli_door
    cli = "halo local --terminal"
    return cli_door(LocalTarget(page=page), terminal_cli=cli, fallback="view")


def cmd_tab(argv: list) -> int:
    """`halo local` with no subcommand of the round 5c set: the door, `--terminal`, or a printer."""
    from halo_harness.config.paths import bridge_home
    if argv and argv[0] in PRINTERS:
        import argparse
        p = argparse.ArgumentParser(prog=f"halo local {argv[0]}", description=f"Print Local -> {argv[0].title()}.")
        if argv[0] == "models":
            p.add_argument("--host", default="", help="one host's models only")
        args = p.parse_args(argv[1:])
        lines = {"hosts": lambda: hosts_lines(bridge_home()), "resources": lambda: resources_lines(bridge_home()),
                 "models": lambda: models_lines(bridge_home(), getattr(args, "host", ""))}[argv[0]]()
        print("\n".join(lines))
        return 0
    from halo_harness.studio.local_door import page_word
    words = [a for a in argv if not a.startswith("-")]
    page, why = page_word(words[0] if words else "huggingface")  # 3.3.5.0 R5: bare `halo local` opens Hugging Face
    if page is None:
        print(f"halo local: {why}", file=sys.stderr)
        return 2
    if "--terminal" not in argv and "--refresh" not in argv and sys.stdin.isatty() and sys.stdout.isatty() and _open(page):
        return 0
    return -1  # the caller prints the merged local view
