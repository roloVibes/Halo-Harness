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
import queue
import subprocess
import sys
import tempfile
import threading
import time
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


MAX_PROMPT_BYTES = 1_000_000  # UTF-8 bytes; the prompt travels on stdin (halo -p caps stdin at 10 MB), never in argv


def _stdin_prompt(prompt: str) -> str:
    """The prompt as the child's stdin, capped in UTF-8 bytes on a whole
    character. One argv string is capped by the OS (131072 bytes on Linux,
    E2BIG), so the prompt never goes in argv."""
    raw = str(prompt).encode("utf-8")
    if len(raw) <= MAX_PROMPT_BYTES:
        return str(prompt)
    return raw[:MAX_PROMPT_BYTES].decode("utf-8", "ignore")


def _call_runner(runner: Callable, cmd: list, cwd: str, env: dict, handle: Callable, stdin_text: str, cancel=None) -> int:
    """A test runner gets the stdin text as `stdin=` (and the cancel event as `cancel=`) when it takes them."""
    import inspect
    try:
        params = list(inspect.signature(runner).parameters.values())
    except (TypeError, ValueError):
        params = []
    takes = lambda name: any(p.name == name or p.kind is inspect.Parameter.VAR_KEYWORD for p in params)  # noqa: E731
    kw = {**({"stdin": stdin_text} if takes("stdin") else {}), **({"cancel": cancel} if cancel is not None and takes("cancel") else {})}
    return runner(cmd, cwd, env, handle, **kw)


def _feed_stdin(proc, text: str) -> None:
    """Write the prompt on a helper thread so a large prompt never blocks
    the stdout pump, then close stdin so the child sees EOF."""
    def write() -> None:
        try:
            proc.stdin.write(text)
        except (OSError, ValueError):
            pass
        finally:
            try:
                proc.stdin.close()
            except (OSError, ValueError):
                pass
    threading.Thread(target=write, daemon=True).start()


def _temp(prefix: str, suffix: str, text: str) -> Path:
    fd, name = tempfile.mkstemp(prefix=prefix, suffix=suffix)
    os.close(fd)  # Windows keeps an open handle from unlinking the file afterwards
    Path(name).write_text(text, encoding="utf-8")
    return Path(name)


def _killed(proc, code: int) -> int:
    proc.kill()
    proc.wait()
    return code


def _pump(proc, handle: Callable[[str], None], timeout: float, cancel=None) -> int:
    """Feed the child's stdout lines to `handle` on THIS thread while a
    helper thread does the blocking reads, so the deadline holds even when
    the child hangs with its stdout open. Past the deadline the child is
    killed and the code is 124; a set `cancel` event kills it with 130."""
    lines: "queue.Queue" = queue.Queue()

    def read() -> None:
        try:
            for line in proc.stdout:  # type: ignore[union-attr]
                lines.put(line)
        except (OSError, ValueError):
            pass
        lines.put(None)

    threading.Thread(target=read, daemon=True).start()
    deadline = time.monotonic() + timeout
    while True:
        if cancel is not None and cancel.is_set():
            return _killed(proc, 130)
        try:
            line = lines.get(timeout=max(0.0, min(0.25, deadline - time.monotonic())))
        except queue.Empty:
            if time.monotonic() >= deadline:
                return _killed(proc, 124)
            continue
        if line is None:
            break
        handle(line)
    try:
        return proc.wait(timeout=max(1.0, deadline - time.monotonic()))
    except subprocess.TimeoutExpired:
        return _killed(proc, 124)


def run_turn(project: Project, prompt: str, *, model: str = "", on_event: Optional[Callable[[dict], None]] = None,
             max_budget_usd: Optional[float] = None, max_turns: int = 40, registered=None, entries: Optional[dict] = None,
             env: Optional[dict] = None, runner: Optional[Callable] = None, timeout: int = 1800,
             tools_override: Optional[str] = None, cancel=None) -> dict:
    """Run one design turn. `runner(cmd, cwd, env, on_line)` can replace the
    subprocess (tests). The craft apps are the turn's ONLY MCP servers (a
    strict --mcp-config written for the run); `--tools` keeps the core
    built-ins; `tools_override` (a critique's "Read,Glob") replaces the tool list;
    a set `cancel` event (threading.Event) stops the turn with code 130. Returns {code, cost, text, versions, events}."""
    from halo_harness.design.crafts_probe import craft_server_entries
    if entries is None:
        entries = craft_server_entries(cwd=project.path)
        if registered is not None:
            entries = {k: v for k, v in entries.items() if k in {str(r).lower() for r in registered}}
    registered = set(entries) if registered is None else registered
    skill_path = _temp("halo-design-skill-", ".md", skill_text(project, registered))
    mcp_path = _temp("halo-design-mcp-", ".json", json.dumps({"mcpServers": entries}, indent=1))
    model = model or str(project.meta().get("model") or "")
    stdin_text = _stdin_prompt(prompt)
    cmd = [sys.executable, "-m", "halo_harness", "-p", "--cwd", str(project.path), "--output-format", "stream-json",
           "--permission-mode", "auto", "--append-system-prompt-file", str(skill_path),
           "--mcp-config", str(mcp_path), "--strict-mcp-config",
           "--tools", tools_override or crafts.allowed_tools(registered), "--max-turns", str(max_turns), "--no-intro"]
    if model:
        cmd += ["--model", model]
    if max_budget_usd:
        cmd += ["--max-budget-usd", str(max_budget_usd)]
    child_env = dict(os.environ if env is None else env)
    child_env["PYTHONIOENCODING"] = "utf-8"
    events, texts, cost, tool_calls, started = [], [], None, 0, time.monotonic()

    def handle(line: str) -> None:
        nonlocal cost, tool_calls
        line = line.strip()
        if not line:
            return
        try:
            obj = json.loads(line)
        except ValueError:
            obj = {"type": "stdout", "text": line}
        events.append(obj)
        if obj.get("type") == "assistant":
            tool_calls += sum(1 for b in (obj.get("message") or {}).get("content") or [] if isinstance(b, dict) and b.get("type") == "tool_use")
        c = _cost_of(obj)
        if c is not None:
            cost = c
        if obj.get("type") == "result" and isinstance(obj.get("result"), str):
            texts.append(obj["result"])
        if on_event:
            on_event(obj)

    try:
        if runner is not None:
            code = _call_runner(runner, cmd, str(project.path), child_env, handle, stdin_text, cancel)
        else:
            proc = subprocess.Popen(cmd, cwd=str(project.path), env=child_env, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT, encoding="utf-8", errors="replace")
            _feed_stdin(proc, stdin_text)
            code = _pump(proc, handle, timeout, cancel)
    finally:
        for p in (skill_path, mcp_path):
            try:
                p.unlink()
            except OSError:
                pass
    versions, text = project.snapshot(note=prompt[:80]), "\n".join(texts)
    project.log_turn({"prompt": prompt, "model": model, "cost": cost, "code": code, "versions": versions, "text": text[:8000],
                      "elapsed": round(time.monotonic() - started, 1), "tool_calls": tool_calls,
                      **({"cancelled": True} if cancel is not None and cancel.is_set() else {})})
    done = {"type": "halo_design", "code": code, "cost": cost, "versions": versions}
    if on_event:
        on_event(done)
    return {"code": code, "cost": cost, "text": text, "versions": versions, "events": events}
