"""halo_harness.design.session -- one design turn (Halo 3.0.1.0 round D2):
a real headless Halo turn (`halo -p`, stream-json out) in the project
folder, on the project's model, with the file tools and every present
craft app's tools allowed and the Design skill appended to the system
prompt. Events are handed to `on_event` as they stream; when the turn ends
the store snapshots every changed artboard and logs the turn with its cost.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Callable, Optional

from halo_harness.design import crafts
from halo_harness.design.store import Project

ARTBOARD_CONTRACT = """You are working inside a Halo Design project folder (the current directory).
An ARTBOARD is a folder under artboards/<id>/ (lower-case id, hyphens). Each holds the artboard's CURRENT files:
- a web prototype, page or deck: index.html (self-contained: inline CSS and JS, no CDN; use the design tokens as CSS variables on :root);
- a craft render: render.png / render.svg / render.pdf (saved by the app's own export tool) plus source.json
  {"app": "<craft app>", "document": "<saved document path>", "kind": "<page|deck|vector|photo|motion|video|pdf|image>", "title": "..."};
- optional controls.json: knobs the person can move without you. A knob is
  {"name": "Spacing", "kind": "range|color|select", "target": "css:--space" | "craft:<tool>:<param>", "min": 0, "max": 64, "step": 1, "value": 16, "options": [...]}.
  For css: targets, index.html must read the value from a CSS variable of that name on :root.
Create a new artboard by creating its folder and files; edit an existing one in place (versions are kept for you).
Never write outside the project folder. Put uploads and captures you need under assets/.
When you finish, reply in a few short lines: which artboards you made or changed and what to look at.
"""


def _system_lines(project: Project) -> list:
    sysd = project.system()
    if not sysd:
        return ["No design system is set yet: pick tasteful defaults and write them as CSS variables so they can be swapped later."]
    out = ["The design system (system.json) -- use these tokens and components, never invent competing ones:"]
    tokens = sysd.get("tokens") or {}
    for group, vals in tokens.items():
        if isinstance(vals, dict):
            out.append(f"- {group}: " + ", ".join(f"{k}={v}" for k, v in list(vals.items())[:24]))
    comps = sysd.get("components") or []
    if comps:
        out.append("- components: " + ", ".join(str(c.get("name") if isinstance(c, dict) else c) for c in comps[:40]))
    if sysd.get("sources"):
        out.append("- sources: " + ", ".join(str(s) for s in sysd["sources"][:6]))
    return out


def _comment_lines(project: Project) -> list:
    pins = [c for c in project.comments() if not c.get("resolved")]
    if not pins:
        return []
    out = ["Open comments to address (artboard, where, what):"]
    for c in pins[:40]:
        where = c.get("path") or f"at {c.get('x', 0):.0f}%,{c.get('y', 0):.0f}%"
        out.append(f"- [{c['id']}] {c.get('artboard')} {where}: {c.get('text')}")
    return out


def skill_text(project: Project, registered=None) -> str:
    meta = project.meta()
    parts = [f"# Halo Design: project '{meta.get('name', project.slug)}'", "", ARTBOARD_CONTRACT, "",
             *crafts.guide_lines(registered), "", *_system_lines(project)]
    pins = _comment_lines(project)
    if pins:
        parts += ["", *pins]
    boards = project.artboards()
    if boards:
        parts += ["", "Artboards already in the project: " + ", ".join(f"{a['id']} ({a['kind']}, v{a['latest']})" for a in boards)]
    return "\n".join(parts) + "\n"


def _cost_of(line: dict) -> Optional[float]:
    for key in ("total_cost_usd", "cost_usd"):
        v = line.get(key)
        if isinstance(v, (int, float)):
            return float(v)
    return None


def _temp(prefix: str, suffix: str, text: str) -> Path:
    fd, name = tempfile.mkstemp(prefix=prefix, suffix=suffix)
    os.close(fd)  # Windows keeps an open handle from unlinking the file afterwards
    Path(name).write_text(text, encoding="utf-8")
    return Path(name)


def run_turn(project: Project, prompt: str, *, model: str = "", on_event: Optional[Callable[[dict], None]] = None,
             max_budget_usd: Optional[float] = None, max_turns: int = 40, registered=None, entries: Optional[dict] = None,
             env: Optional[dict] = None, runner: Optional[Callable] = None, timeout: int = 1800) -> dict:
    """Run one design turn. `runner(cmd, cwd, env, on_line)` can replace the
    subprocess (tests). The craft apps are the turn's ONLY MCP servers (a
    strict --mcp-config written for the run); `--tools` keeps the core
    built-ins. Returns {code, cost, text, versions, events}."""
    from halo_harness.design.crafts_probe import craft_server_entries
    if entries is None:
        entries = craft_server_entries(cwd=project.path)
        if registered is not None:
            entries = {k: v for k, v in entries.items() if k in {str(r).lower() for r in registered}}
    registered = set(entries) if registered is None else registered
    skill_path = _temp("halo-design-skill-", ".md", skill_text(project, registered))
    mcp_path = _temp("halo-design-mcp-", ".json", json.dumps({"mcpServers": entries}, indent=1))
    model = model or str(project.meta().get("model") or "")
    cmd = [sys.executable, "-m", "halo_harness", "-p", prompt, "--cwd", str(project.path), "--output-format", "stream-json",
           "--permission-mode", "auto", "--append-system-prompt-file", str(skill_path),
           "--mcp-config", str(mcp_path), "--strict-mcp-config",
           "--tools", crafts.allowed_tools(registered), "--max-turns", str(max_turns), "--no-intro"]
    if model:
        cmd += ["--model", model]
    if max_budget_usd:
        cmd += ["--max-budget-usd", str(max_budget_usd)]
    child_env = dict(os.environ if env is None else env)
    child_env["PYTHONIOENCODING"] = "utf-8"
    events, texts, cost = [], [], None

    def handle(line: str) -> None:
        nonlocal cost
        line = line.strip()
        if not line:
            return
        try:
            obj = json.loads(line)
        except ValueError:
            obj = {"type": "stdout", "text": line}
        events.append(obj)
        c = _cost_of(obj)
        if c is not None:
            cost = c
        if obj.get("type") == "result" and isinstance(obj.get("result"), str):
            texts.append(obj["result"])
        if on_event:
            on_event(obj)

    try:
        if runner is not None:
            code = runner(cmd, str(project.path), child_env, handle)
        else:
            proc = subprocess.Popen(cmd, cwd=str(project.path), env=child_env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                    encoding="utf-8", errors="replace")
            try:
                for line in proc.stdout:  # type: ignore[union-attr]
                    handle(line)
                code = proc.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                proc.kill()
                code = 124
    finally:
        for p in (skill_path, mcp_path):
            try:
                p.unlink()
            except OSError:
                pass
    versions = project.snapshot(note=prompt[:80])
    project.log_turn({"prompt": prompt, "model": model, "cost": cost, "code": code, "versions": versions})
    done = {"type": "halo_design", "code": code, "cost": cost, "versions": versions}
    if on_event:
        on_event(done)
    return {"code": code, "cost": cost, "text": "\n".join(texts), "versions": versions, "events": events}
