"""halo_harness.checks.steward -- the first-run checklist's "steward candidates" row (Halo 3.3.7.0 R5; ROADMAP
"Candidates at init": Setup's Check scans the installed local models for a steward candidate and names the best,
offers to pull a known-good small one when none is installed and the card has room, and sets ollama.steward.model).

    pick(ctx) -> {best | None, download | None, line}     ollama_steward/candidates.py over this home
    on_by_default(ctx) -> bool     on when an installed candidate fits and ollama.steward.model is not set yet; off when
                                   nothing fits without a download (the row then says the download)
    cost(ctx) -> "free" | "a download: qwen3.5:9b (6.6 GB, ~3 min)"
    run_steward(ctx) -> lines      the best installed one -> ollama.steward.model; with none installed, the row was
                                   ticked knowing its download: the pull (providers/ollama_control.pull), then that model
A cloud model is never picked here: "ask a bigger model" is the chat's.
"""

from __future__ import annotations

from pathlib import Path


def _state(ctx) -> Path:
    from halo_harness.checks.run import _state_dir
    return _state_dir(ctx)


def pick(ctx, *, cached: bool = True) -> dict:
    """cached (the row's default and its cost): only what is read already -- Setup's state read opens no connection."""
    from halo_harness.ollama_steward.candidates import best, candidates, line
    try:
        cands = candidates(_state(ctx), cached=cached)
    except Exception as e:
        return {"best": None, "download": None, "line": f"candidates not read ({type(e).__name__})"}
    top = best(cands)
    dl = next((c for c in cands if not c["installed"] and c["fits_beside_main"] is not False), None) if top is None else None
    return {"best": top, "download": dl, "line": line(cands)}


def _configured() -> bool:
    try:
        from halo_harness.theme import get_config_value
        v = get_config_value("ollama.steward.model", default=None)
    except Exception:
        v = None
    return isinstance(v, str) and bool(v.strip())


def on_by_default(ctx) -> bool:
    return not _configured() and pick(ctx)["best"] is not None


def _dl_words(c: dict) -> str:
    name = c["model"][3:].rsplit("@", 1)[0]
    return f"{name} ({c['download_gb']:g} GB, ~{c['minutes']} min)" if c.get("download_gb") else name


def cost(ctx) -> str:
    p = pick(ctx)
    if p["best"] is not None or p["download"] is None:
        return "free"
    return f"a download: {_dl_words(p['download'])} onto {p['download']['host']}"


def run_steward(ctx) -> list:
    from halo_harness.checks.run import CheckFailed
    from halo_harness.theme import set_config_value
    p = pick(ctx, cached=False)
    c = p["best"]
    out = [p["line"]]
    if c is None and p["download"] is not None:
        from halo_harness.local_sched.facts import host_named
        from halo_harness.providers.ollama_control import pull
        d = p["download"]
        name = d["model"][3:].rsplit("@", 1)[0]
        got = pull(host_named(d["host"]), name)
        out.append(got.get("say") or f"pulled {name}")
        if not got.get("ok"):
            raise CheckFailed(out)
        c = d
    if c is None:
        raise CheckFailed(out + ["no local model here could run the steward (halo ollama steward candidates)"])
    set_config_value("ollama.steward.model", c["ref"])
    return out + [f"ollama.steward.model = {c['ref']} ({c['why']})"]
