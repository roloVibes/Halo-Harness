"""scripts/realcheck/steps_c.py -- steps 7 to 9: a pack from the tree, another machine's models, the update check."""
from __future__ import annotations

import json
import re
import time

from realcheck import fakes, screen
from realcheck.core import Fail, Skip, excerpt
from realcheck.steps_a import _no_leftovers


def packs(ctx):
    h = ctx.home("packs")
    src = ctx.repo / "halo_harness" / "templates" / "packs" / "doc-review"
    ev: dict = {}
    bad: list = []
    for args in (("pack", "install", str(src)), ("pack", "enable", "doc-review"), ("pack", "list")):
        r = ctx.run(h, *args, timeout=60)
        ev[" ".join(args[:2])] = {"exit": r.code, "seconds": round(r.seconds, 2), "out": excerpt(r.out, 300)}
        if r.code != 0 or screen.TRACEBACK in r.err:
            bad.append(f"`halo {' '.join(args[:2])}` exit {r.code}: {excerpt(r.out + r.err, 200)}")
    listed = ev["pack list"]["out"]
    if "doc-review" not in listed or "enabled" not in listed or not re.search(r"offers .*agent", listed):
        bad.append(f"`halo pack list` does not name doc-review, enabled, with what it offers: {listed[:160]!r}")
    r = ctx.run(h, "-p", "RC-PACK agent=doc-review--reviewer", timeout=120)
    subs = ctx.provider.requests_with("RC-SUB: review README.md")
    system = " ".join(fakes._text(m.get("content")) for q in subs for m in (q.get("body") or {}).get("messages") or []
                      if isinstance(m, dict) and m.get("role") == "system")
    tool = [fakes._text(m.get("content")) for q in ctx.provider.requests_with("RC-PACK agent=")
            for m in (q.get("body") or {}).get("messages") or [] if isinstance(m, dict) and m.get("role") == "tool"]
    ev.update(turn_exit=r.code, turn_s=round(r.seconds, 2), sub_calls=len(subs), tool_result=excerpt(" ".join(tool), 300),
              reviewer_instructions_seen="unclear, wrong or missing" in system)
    if r.code != 0 or fakes.PACK_DONE not in r.out:
        bad.append(f"a session handing work to doc-review--reviewer: exit {r.code}, printed {excerpt(r.out, 80)!r}")
    if not subs:
        bad.append("the pack's agent never reached the model: " + excerpt(" ".join(tool), 200))
    elif not ev["reviewer_instructions_seen"]:
        bad.append("the agent that ran did not carry the pack reviewer's instructions")
    _no_leftovers(ctx, h, "the pack commands and the session")
    if bad:
        raise Fail("; ".join(bad), ev)
    return f"installed, enabled, listed with what it offers; doc-review--reviewer took a task ({r.seconds:.1f}s)", ev


MODEL = "rc-tiny:1b"


def local(ctx):
    h = ctx.home("local")
    fake = fakes.ollama({MODEL: {"size_gb": 1.0, "trained": 32768}})
    ev: dict = {}
    bad: list = []
    try:
        hosts = json.dumps([{"name": "lab", "url": fake.base_url}])
        r = ctx.run(h, "config", "set", "ollama.hosts", hosts, timeout=30)
        ev["add_host"] = {"exit": r.code, "out": excerpt(r.out + r.err, 160)}
        if r.code != 0:
            raise Fail(f"`halo config set ollama.hosts <one host>` exit {r.code}: {excerpt(r.out + r.err, 200)}", ev)
        for verb in (("ps",), ("warm", MODEL), ("ps",), ("unload", MODEL)):
            loads0, unloads0 = len(fake.loads), len(fake.unloads)
            r = ctx.run(h, "local", *verb, "--host", "lab", timeout=60)
            key = " ".join(verb[:1]) + ("" if verb != ("ps",) or "ps" not in ev else " (2)")
            ev[key] = {"exit": r.code, "seconds": round(r.seconds, 2), "out": excerpt(r.out + r.err, 240),
                       "loads": len(fake.loads) - loads0, "unloads": len(fake.unloads) - unloads0}
            if r.code != 0 or screen.TRACEBACK in r.err:
                bad.append(f"`halo local {' '.join(verb)} --host lab` exit {r.code}: {excerpt(r.out + r.err, 160)}")
        if ev["warm"]["loads"] != 1:
            bad.append(f"`halo local warm` loaded the model {ev['warm']['loads']} time(s), not once")
        if ev["unload"]["unloads"] != 1:
            bad.append(f"`halo local unload` unloaded {ev['unload']['unloads']} time(s), not once")
        if MODEL not in ev["ps (2)"]["out"]:
            bad.append(f"`halo local ps` after warm does not name {MODEL}: {ev['ps (2)']['out'][:120]!r}")
        for n in (1, 2):
            loads0 = len(fake.loads)
            r = ctx.run(h, "-p", "RC-ASK one word", "--model", f"ol:{MODEL}@lab", timeout=120)
            ev[f"one-shot {n}"] = {"exit": r.code, "seconds": round(r.seconds, 2), "loads": len(fake.loads) - loads0,
                                   "out": excerpt(r.out, 80), "err": excerpt(r.err, 200)}
            want = 1 if n == 1 else 0
            if r.code != 0:
                bad.append(f"one-shot {n} through the other machine's model: exit {r.code}: {excerpt(r.err, 160)}")
            elif ev[f"one-shot {n}"]["loads"] != want:
                bad.append(f"one-shot {n} loaded the model {ev[f'one-shot {n}']['loads']} time(s), not {want}")
        ev["fake"] = {"loads": len(fake.loads), "unloads": len(fake.unloads)}
    finally:
        fake.stop()
    if ctx.real_local:
        _real_local(ctx, ev, bad)
    _no_leftovers(ctx, h, "the local commands")
    if bad:
        raise Fail("; ".join(bad), ev)
    real = f"; real {ev['real']['first_s']}s then {ev['real']['second_s']}s" if "real" in ev else ""
    return f"ps / warm / unload on the other machine; one load for the first one-shot, none for the second{real}", ev


def _real_local(ctx, ev: dict, bad: list) -> None:
    """--real-local ol:<model>@<http://host:port>: a one-word answer twice; the second under 3 s."""
    m = re.match(r"ol:(.+)@(https?://\S+)$", ctx.real_local)
    if not m:
        bad.append(f"--real-local wants ol:<model>@<http://host:port>, got {ctx.real_local!r}")
        return
    h = ctx.home("real-local")
    ctx.run(h, "config", "set", "ollama.hosts", json.dumps([{"name": "real", "url": m.group(2)}]), timeout=30)
    times = []
    for _ in range(2):
        t = time.monotonic()
        r = ctx.run(h, "-p", "Answer with one word: yes", "--model", f"ol:{m.group(1)}@real", timeout=600)
        times.append(round(time.monotonic() - t, 2))
        if r.code != 0:
            bad.append(f"--real-local: exit {r.code}: {excerpt(r.err, 160)}")
            break
    ev["real"] = {"first_s": times[0] if times else None, "second_s": times[1] if len(times) > 1 else None}
    if len(times) > 1 and times[1] > 3.0:
        bad.append(f"--real-local: the second call took {times[1]}s (budget 3 s)")
    ctx.run(h, "local", "unload", m.group(1), "--host", "real", timeout=60)  # leave the card as it was found


def update(ctx):
    h = ctx.home("update")
    ev: dict = {}
    bad: list = []
    runs = (("online", (), ctx.env(h)), ("offline", (), ctx.env(h, HALO_OFFLINE="1", BRIDGE_TEST_NO_BACKGROUND_NET="1")),
            ("stable", ("--channel", "stable"), ctx.env(h)))
    for tag, extra, env in runs:
        r = ctx.run(h, "update", "--check", *extra, timeout=60, env=env)
        ev[tag] = {"exit": r.code, "seconds": round(r.seconds, 2), "out": excerpt(r.out, 500), "err": excerpt(r.err, 300)}
        if screen.TRACEBACK in r.out + r.err:
            bad.append(f"`halo update --check` {tag} printed a traceback: {excerpt(r.err, 200)}")
        elif not (r.out + r.err).strip():
            bad.append(f"`halo update --check` {tag} printed nothing")
    channel = ctx.run(h, "config", "get", "update.channel", timeout=30).out.strip()
    ev["channel_after_check"] = channel
    if "stable" in channel:
        bad.append("`halo update --check --channel stable` (report only) saved update.channel=stable: every later "
                   "`halo update` follows the stable channel")
    for tag in ("online", "stable"):
        older = _offer_is_older(ctx, ev[tag]["out"])
        ev[tag]["offer_is_older"] = older
        # "differs from (<channel>)" is Halo's own label when git confirmed this build is NOT behind the offer
        # (update_cli._print_report): a release candidate ahead of its channel is told so; "available" is the lie
        if older and not re.search(r"\b(older|behind|back to|earlier|downgrade|ahead of)\b|\bdiffers from \(\w+\):",
                                   ev[tag]["out"], re.I):
            bad.append(f"`halo update --check` ({tag}) offers {older}, older than this build, and does not say so: "
                       f"{ev[tag]['out'][:220]!r}")
    _no_leftovers(ctx, h, "`halo update --check`")
    if bad:
        raise Fail("; ".join(bad), ev)
    text = ev["online"]["out"]
    if not re.search(r"available|differs|up to date|newest", text, re.I):
        raise Skip(f"the check answered without naming a release (no network here?): {text[:160]!r}")
    return f"online: {excerpt(text, 100)}; offline: {excerpt(ev['offline']['out'] or ev['offline']['err'], 90)}", ev


def _offer_is_older(ctx, text: str) -> str:
    """'<ref> (<date>)' when the release the check offers was made before the build it says is installed (by the
    commits' dates in this checkout's git, or the offer is an ancestor of the build), else ''."""
    import subprocess
    have = re.search(r"installed: halo \S+ \(([0-9a-f]{7,40})", text)
    offer = re.search(r"(?:available|differs from) \((\w+)\): ([0-9a-f]{7,40}), (\S+)", text)
    if not have or not offer:
        return ""

    def when(sha: str) -> int:
        try:
            out = subprocess.run(["git", "-C", str(ctx.repo), "log", "-1", "--format=%ct", sha], capture_output=True,
                                 text=True, timeout=20).stdout.strip()
            return int(out) if out.isdigit() else 0
        except (OSError, subprocess.SubprocessError):
            return 0
    def ancestor(old: str, new: str) -> bool:
        try:
            return subprocess.run(["git", "-C", str(ctx.repo), "merge-base", "--is-ancestor", old, new],
                                  capture_output=True, timeout=20).returncode == 0
        except (OSError, subprocess.SubprocessError):
            return False
    a, b = when(have.group(1)), when(offer.group(2))
    if a and b and (b < a or (have.group(1) != offer.group(2) and ancestor(offer.group(2), have.group(1)))):
        return f"{offer.group(3)} ({time.strftime('%Y-%m-%d %H:%M', time.gmtime(b))} UTC)"
    return ""
