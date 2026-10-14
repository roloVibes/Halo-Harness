"""halo_harness.flows.steps_postiz -- the post and metrics steps, as dry-run
stubs until Postiz is wired in (round R4).

* post, `live: false`: one entry per platform appended to the design
  project's `posts.json`: `{platform, text, media, dry_run: true, argv,
  run, step, ts}` where `argv` is the postiz command that would publish it;
  each one is logged as a `post` line. `live: true` stops the step: posting
  arrives in R4.
* metrics: logs one `metric` line (the schedule it will follow) and returns {}.
"""

from __future__ import annotations

import json
import re
import time

from halo_harness.flows.refs import resolve_value
from halo_harness.flows.state import StopFlow

_PLATFORM_NAMES = {"x": ("x", "twitter", "x (twitter)", "x/twitter"), "youtube": ("youtube", "youtube shorts"),
                   "instagram": ("instagram", "ig"), "tiktok": ("tiktok", "tik tok")}


def _header_of(line: str, platforms: list) -> "str | None":
    s = re.sub(r"^[#>*\-\s]+|[*:\s]+$", "", line.strip()).strip().lower()
    s = re.sub(r"\*+", "", s).strip()
    if not s or len(s) > 40:
        return None
    for p in platforms:
        names = _PLATFORM_NAMES.get(str(p).lower(), (str(p).lower(),))
        if s in names or any(s.startswith(n + " ") or s.startswith(n + "(") for n in names if len(n) > 1):
            return p
    return None


def platform_text(text: str, platform: str, platforms: list) -> str:
    """The block of `text` headed by `platform` (the Copywriter writes one
    block per platform); the whole text when there are no such headings."""
    lines = str(text or "").splitlines()
    heads = [(i, _header_of(l, platforms)) for i, l in enumerate(lines)]
    heads = [(i, p) for i, p in heads if p is not None]
    for k, (i, p) in enumerate(heads):
        if p == platform:
            end = heads[k + 1][0] if k + 1 < len(heads) else len(lines)
            block = "\n".join(lines[i + 1:end]).strip().strip("-").strip()
            if block:
                return block
    return str(text or "").strip()


def postiz_argv(text: str, media: list, platform: str) -> list:
    argv = ["postiz", "posts:create", "-c", text]
    if media:
        argv += ["-m", ",".join(media)]
    return argv + ["-i", f"<{platform} integration id>"]


def post(ctx) -> dict:
    if ctx.step.get("live") is True:
        raise StopFlow(f"{ctx.sid}: live posting arrives in R4 (Postiz); set live: false for a dry run")
    inputs = resolve_value(ctx.step.get("inputs") or {}, ctx.outputs)
    text = inputs.get("text") or ""
    media = [str(m) for m in (inputs.get("media") or [])]
    platforms = inputs.get("platforms") or []
    platforms = platforms if isinstance(platforms, list) else [platforms]
    project = ctx.project()
    path = project.path / "posts.json"
    try:
        rows = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else []
    except ValueError:
        rows = []
    rows = rows if isinstance(rows, list) else []
    entries = []
    for platform in platforms or ["(no platform)"]:
        body = text.get(platform, "") if isinstance(text, dict) else platform_text(str(text), platform, platforms)
        entry = {"platform": platform, "text": body, "media": media, "dry_run": True,
                 "argv": postiz_argv(body, media, platform), "run": ctx.run, "step": ctx.sid,
                 "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime())}
        entries.append(entry)
        ctx.flow.log("post", f"dry run: {platform}, {len(body)} chars, {len(media)} media", step=ctx.sid,
                     platform=platform, dry_run=True)
    path.write_text(json.dumps(rows + entries, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return {"posts": entries, "dry_run": True, "path": str(path)}


def metrics(ctx) -> dict:
    every, days = ctx.step.get("every") or "6h", ctx.step.get("days") or 7
    ctx.flow.log("metric", f"{ctx.sid}: metrics arrive with Postiz (R4): every {every} for {days} days into "
                           f"{ctx.project().path / 'metrics.jsonl'}", step=ctx.sid, every=every, days=days,
                 stub=True)
    return {}
