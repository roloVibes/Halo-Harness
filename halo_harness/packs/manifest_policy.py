"""halo_harness.packs.manifest_policy -- a pack's `contributes.policy` and `contributes.modes` (Halo 3.3.10.0 R1;
docs/EXTENSION_API.md "Policy hooks", status draft).

    contributes:
      policy:
        - id: fence
          run: ["${halo_python}", "${CLAUDE_PLUGIN_ROOT}/policy/fence.py"]   # or one string, split like a shell line
          when: {tools: [Write, Edit], modes: [fenced]}
          impact: high            # low | medium (default) | high: what the pack says its verdicts weigh; shown
          on_error: deny          # allow (default) | deny: a late, malformed or missing answer
          redact: [MY_TOKEN]      # env names whose values are taken out of the input before it leaves Halo
          after: false            # declared now, read by 3.3.10.0 R2 (the post-call verdict)
      modes:
        - {id: fenced, label: Fenced, theme: midnight}   # theme: accepted, read from 3.3.12.0

    policies_of(manifest) / modes_of(manifest)    the entries (mappings only)
    entry(manifest, policy_id) / mode_entry(manifest, mode_id)
    run_argv(entry, root)       the command with ${halo_python} and ${CLAUDE_PLUGIN_ROOT} put in (exec form, no shell)
    policy_lines(data, root)    one line per problem, each naming the manifest entry
    needs(data)                 [("hooks", "policy <id>")]: a policy rides on the hooks permission
"""

from __future__ import annotations

import difflib
import re
import shlex
from pathlib import Path

from halo_harness.packs import names as N

POLICY_KEYS = ("id", "run", "when", "impact", "on_error", "redact", "after")
WHEN_KEYS = ("tools", "modes")
MODE_KEYS = ("id", "label", "theme")
ON_ERROR = ("allow", "deny")
IMPACT = ("low", "medium", "high")
#: The core tools (halo_harness/tools/ and agent/planmode.py): the names checked without importing the registry. A
#: name outside them is checked against `tool_names()`, every tool class Halo has loaded at validation time; an MCP
#: tool is `mcp__<server>__<tool>`, a connector's `connector__<slug>`; `*` is every tool.
KNOWN_TOOLS = ("Agent", "AskUserQuestion", "Bash", "BashOutput", "Edit", "EnterPlanMode", "ExitPlanMode", "Glob", "Grep",
               "ListMcpResourcesTool", "Media", "NotebookEdit", "OrchestraClaim", "OrchestraClaims", "OrchestraNote",
               "OrchestraRelease", "PowerShell", "Read", "ReadMcpResourceTool", "Screenshot", "SendUserMessage", "Skill",
               "Task", "TaskCreate", "TaskList", "TaskStop", "TaskUpdate", "TodoWrite", "ToolSearch", "WebFetch",
               "WebSearch", "Write", "knowledge_add", "knowledge_search")
TOOL_PREFIXES = ("mcp__", "connector__")
ENV_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
PYTHON = "${halo_python}"
ROOT = "${CLAUDE_PLUGIN_ROOT}"


def _contributes(manifest) -> dict:
    c = manifest.get("contributes") if isinstance(manifest, dict) else None
    return c if isinstance(c, dict) else {}


def policies_of(manifest) -> "list[dict]":
    raw = _contributes(manifest).get("policy")
    return [e for e in raw if isinstance(e, dict)] if isinstance(raw, list) else []


def modes_of(manifest) -> "list[dict]":
    raw = _contributes(manifest).get("modes")
    return [e for e in raw if isinstance(e, dict)] if isinstance(raw, list) else []


def entry(manifest, policy_id: str):
    return next((e for e in policies_of(manifest) if e.get("id") == policy_id), None)


def mode_entry(manifest, mode_id: str):
    return next((e for e in modes_of(manifest) if e.get("id") == mode_id), None)


def ids(entries) -> "list[str]":
    return [str(e.get("id")) for e in entries if isinstance(e.get("id"), str)]


def when_of(e: dict) -> "tuple[list, list]":
    """`(tools, modes)`: the `when` filter; no `tools` is every tool, no `modes` is every mode (none included)."""
    w = e.get("when") if isinstance(e.get("when"), dict) else {}
    tools = [t for t in w.get("tools") or [] if isinstance(t, str)] if isinstance(w.get("tools"), list) else []
    modes = [m for m in w.get("modes") or [] if isinstance(m, str)] if isinstance(w.get("modes"), list) else []
    return tools, modes


def _argv(run) -> "list[str] | None":
    if isinstance(run, list) and run and all(isinstance(a, str) and a for a in run):
        return list(run)
    if isinstance(run, str) and run.strip():
        try:
            return shlex.split(run, posix=True)
        except ValueError:
            return None
    return None


def script_rel(run) -> "tuple[str, str]":
    """`(the pack file the command runs, '')`, or `('', the line saying why not)`: the program is `${halo_python}`
    with a pack file after it, or a pack file itself; a pack file is `${CLAUDE_PLUGIN_ROOT}/<path>` or `<path>`."""
    argv = _argv(run)
    if not argv:
        return "", "a command is required: [\"${halo_python}\", \"${CLAUDE_PLUGIN_ROOT}/policy/<name>.py\"]"
    target = argv[1] if argv[0] == PYTHON and len(argv) > 1 else argv[0]
    if target == PYTHON:
        return "", "${halo_python} needs the pack file it runs after it"
    rel = target[len(ROOT):].lstrip("/\\") if target.startswith(ROOT) else target
    p = Path(rel.replace("\\", "/"))
    if not rel or p.is_absolute() or rel.startswith(("/", "\\")) or re.match(r"^[A-Za-z]:", rel) or ".." in p.parts \
            or "$" in rel:
        return "", f"{target!r} is outside the pack folder (a command in the pack: ${{CLAUDE_PLUGIN_ROOT}}/<path>)"
    return p.as_posix(), ""


def run_argv(e: dict, root) -> "list[str]":
    """The policy's command, ready to start: `${halo_python}` is Halo's Python, `${CLAUDE_PLUGIN_ROOT}` the pack's
    folder, a bare pack path (`policy/x.py`) the file in the pack's folder. Each argument goes in as it is."""
    from halo_harness.packs.interpreter import python_path
    argv = _argv(e.get("run")) or []
    rel, _why = script_rel(e.get("run"))
    out = []
    for i, a in enumerate(argv):
        a = a.replace(PYTHON, python_path()).replace(ROOT, str(root))
        if rel and i == (1 if argv[0] == PYTHON else 0) and not argv[i].startswith(ROOT):
            a = str(Path(root) / rel)
        out.append(a)
    return out


def tool_names() -> "set[str]":
    """Every tool name Halo knows now: the core list plus the `name` of each `halo_harness` Tool subclass loaded in
    this process (the registry imports the core ones; a module such as preflight.py adds its own)."""
    out = set(KNOWN_TOOLS)
    try:
        import halo_harness.tools.registry  # noqa: F401  (imports every core tool class)
        from halo_harness.tools.base import Tool
    except Exception:  # the registry does not import here: the core list stands
        return out
    seen, todo = set(), [Tool]
    while todo:
        for sub in todo.pop().__subclasses__():
            if sub not in seen:
                seen.add(sub)
                todo.append(sub)
                name = getattr(sub, "name", None)
                if isinstance(name, str) and name and str(sub.__module__).startswith("halo_harness."):
                    out.add(name)
    return out


def tool_known(name: str, names=None) -> bool:
    """`*`, an MCP or connector tool, a core tool, or (looked up only then) a tool class Halo has loaded."""
    if name == "*" or name in KNOWN_TOOLS or name.startswith(TOOL_PREFIXES):
        return True
    return name in (names if names is not None else tool_names())


def needs(data) -> "list[tuple[str, str]]":
    return [("hooks", f"policy {pid}") for pid in ids(policies_of(data))]


def _closest(name: str, choices) -> str:
    hit = difflib.get_close_matches(name, list(choices), n=1)
    return f" (closest: {hit[0]})" if hit else ""


def _id_lines(entries, where: str) -> "list[str]":
    out, seen = [], set()
    for i, e in enumerate(entries):
        pid = e.get("id")
        if not isinstance(pid, str) or not pid:
            out.append(f"{where}[{i}].id: required (a name: letters, digits, - and _)")
        elif not N.is_valid_name(pid) or "--" in pid:
            out.append(f"{where}[{i}].id {pid!r} is not a name (letters, digits, - and _, no --)")
        elif pid in seen:
            out.append(f"{where}[{i}].id {pid!r} is used twice")
        else:
            seen.add(pid)
    return out


def _policy_lines(i: int, e: dict, modes: "set[str]", root) -> "list[str]":
    where = f"contributes.policy[{i}]"
    out = []
    rel, why = script_rel(e.get("run"))
    if why:
        out.append(f"{where}.run: {why}")
    elif root is not None and not (Path(root) / rel).is_file():
        out.append(f"{where}.run: {rel} is not in the pack")
    tools, wanted = when_of(e)
    live = None  # the loaded tool classes, read once and only for a name outside the core list
    for t in tools:
        if t == "*" or t in KNOWN_TOOLS or t.startswith(TOOL_PREFIXES):
            continue
        live = tool_names() if live is None else live
        if t not in live:
            out.append(f"{where}.when.tools: {t!r} is not a tool Halo has{_closest(t, sorted(live))}; "
                       "a tool name, mcp__<server>__<tool> or *")
    for m in wanted:
        if m not in modes:
            out.append(f"{where}.when.modes: {m!r} is not one of contributes.modes ({', '.join(sorted(modes)) or 'none'})")
    for key, choices, default in (("on_error", ON_ERROR, "allow"), ("impact", IMPACT, "medium")):
        v = e.get(key)
        if v is not None and v not in choices:
            out.append(f"{where}.{key} {v!r} is not one of {', '.join(choices)} ({default} when left out)")
    redact = e.get("redact")
    if redact is not None and not isinstance(redact, list):
        out.append(f"{where}.redact: a list of environment variable names")
    for name in redact if isinstance(redact, list) else []:
        if not isinstance(name, str) or not ENV_NAME.match(name):
            out.append(f"{where}.redact: {name!r} is not an environment variable name (the name, never its value)")
    if e.get("after") is not None and not isinstance(e.get("after"), bool):
        out.append(f"{where}.after: true or false")
    return out


def policy_lines(data, root=None) -> "list[str]":
    """One line per problem in `contributes.policy` and `contributes.modes`; [] for a pack without them."""
    c = _contributes(data)
    out = []
    for key in ("policy", "modes"):
        if key in c and not isinstance(c[key], list):
            out.append(f"contributes.{key}: a list of entries")
    modes, pols = modes_of(data), policies_of(data)
    out += _id_lines(modes, "contributes.modes") + _id_lines(pols, "contributes.policy")
    for i, m in enumerate(modes):
        if m.get("label") is not None and not (isinstance(m.get("label"), str) and m["label"].strip()):
            out.append(f"contributes.modes[{i}].label: a line a person reads")
        if m.get("theme") is not None and not isinstance(m.get("theme"), str):
            out.append(f"contributes.modes[{i}].theme: a theme name")
    declared = set(ids(modes))
    for i, e in enumerate(pols):
        out += _policy_lines(i, e, declared, root)
    return out
