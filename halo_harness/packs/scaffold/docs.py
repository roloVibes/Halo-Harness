"""halo_harness.packs.scaffold.docs -- the files of a new pack that are written from its manifest (Halo 3.3.12.0 R4):
the entry command `commands/<id>.md` (`/<id>` once the pack is enabled), the README and HALO-PACK.md's "what it
brings" list.

    parts(manifest, files)          [(what, name, line)] -- every command, workflow, lineup, bio, skill, server ...
    entry_command(manifest, files)  commands/<id>.md
    readme(manifest, files, github) README.md: what it is, Install (from `requires:`), Install from GitHub, Use it,
                                    Permissions, Files (every file in one line), Develop it
"""

from __future__ import annotations

import re

FILE_WHAT = {
    "pack.yaml": "the manifest: id, version, the extension API range, what it contributes, what it requests",
    "README.md": "this page, written from pack.yaml by halo pack new",
    "HALO-PACK.md": "what a Halo session (or you) follows when working on the pack: the contract, the loop, the rules",
    "CHANGELOG.md": "each release of the pack, newest first",
    "LICENSE": "the pack's license",
    ".gitignore": "caches and run-time data kept out of the repo",
    ".github/workflows/pack-test.yml": "GitHub Actions: halo pack test . on Linux and Windows at a pinned Halo tag",
    ".claude-plugin/plugin.json": "the Claude-plugin half's name (the pack's id)",
    ".mcp.json": "the MCP servers, started with Halo's own Python once their mcp:<server> grant is given",
    "hooks/hooks.json": "the hooks, loaded once the hooks grant is given",
    "tests/__init__.py": "makes tests/ a package, so python -m tests.pack_test finds the pack's own",
    "tests/pack_test.py": "the pack's own test: halo_harness.ext.testing's checks, then its own",
}
FOLDER_WHAT = {"agents": "a bio", "teams": "a lineup", "skills": "a skill", "commands": "a slash command",
               "workflows": "a workflow", "events": "an event kind's schema", "artifacts": "an artifact schema",
               "studio": "a Studio panel's source", "fleet": "a fleet inspector line", "policy": "a policy hook",
               "setup": "a Setup block's file", "mcp": "an MCP server", "hooks": "a hook script",
               "tests": "a sample a schema is checked against"}


def _front(text: str) -> dict:
    from halo_harness.config.frontmatter import parse
    fm, _body = parse(text or "")
    return fm if isinstance(fm, dict) else {}


def _yaml_desc(text: str) -> str:
    m = re.search(r"^description:\s*(.+)$", text or "", re.M)
    return m.group(1).strip().strip('"') if m else ""


def parts(manifest: dict, files: dict) -> "list[tuple[str, str, str]]":
    pid = str(manifest.get("id"))
    out = []
    for rel in sorted(files):
        p = rel.split("/")
        if p[0] == "commands" and rel.endswith(".md") and rel != f"commands/{pid}.md":
            out.append(("command", f"/{pid}:{p[-1][:-3]}", _front(files[rel]).get("description", "")))
        elif p[0] == "workflows" and rel.endswith(".yaml"):
            out.append(("workflow", f"{pid}/{p[-1][:-5]}", _yaml_desc(files[rel])))
        elif p[0] == "teams" and rel.endswith(".yaml"):
            out.append(("lineup", f"{pid}--{p[-1][:-5]}", _yaml_desc(files[rel])))
        elif p[0] == "agents" and rel.endswith(".yaml"):
            out.append(("bio", f"{pid}--{p[-1][:-5]}", _yaml_desc(files[rel])))
        elif p[0] == "skills" and p[-1] == "SKILL.md":
            out.append(("skill", f"{pid}:{p[1]}", _front(files[rel]).get("description", "")))
    c = manifest.get("contributes") or {}
    out += [("MCP server", str(e.get("name")), str(e.get("description") or "")) for e in c.get("mcp") or []]
    out += [("policy", str(e.get("id")), f"asked about {', '.join((e.get('when') or {}).get('tools') or ['every tool'])}")
            for e in c.get("policy") or []]
    out += [("mode", str(e.get("id")), str(e.get("label") or "")) for e in c.get("modes") or []]
    out += [("Setup block", str(e.get("id")), str(e.get("title") or "")) for e in c.get("setup") or []]
    out += [("theme", f"{pid}/{e.get('id')}", str(e.get("label") or "")) for e in c.get("themes") or []]
    out += [("Studio section", str(s.get("id")), str(s.get("title") or "")) for s in (c.get("studio") or {}).get("sections") or []]
    out += [("fleet capability", str(f.get("name")), str(f.get("description") or ""))
            for f in (c.get("fleet") or {}).get("capabilities") or []]
    out += [("event", str(e), "") for e in c.get("events") or []]
    out += [("artifact", str(a), "") for a in c.get("artifacts") or []]
    if manifest.get("bundle"):
        out.append(("bundle", "bundle:", "the local model the pack keeps ready while it is on"))
    out += [("requirement", str(r.get("name")), str(r.get("why") or "")) for r in manifest.get("requires") or []
            if isinstance(r, dict) and r.get("kind")]
    return out


def brings(manifest: dict, files: dict) -> str:
    rows = parts(manifest, files)
    return "\n".join(f"- {what} `{name}`" + (f" -- {line}" if line else "") for what, name, line in rows) or "- nothing yet"


def entry_command(manifest: dict, files: dict) -> str:
    pid, name = manifest.get("id"), manifest.get("name")
    rows = [r for r in parts(manifest, files) if r[0] in ("command", "workflow", "lineup")]
    listing = "\n".join(f"- {what} {ref}" + (f" -- {line}" if line else "") for what, ref, line in rows) or "- (only this command)"
    flows = [ref for what, ref, _ in rows if what == "workflow"]
    cmds = [ref for what, ref, _ in rows if what == "command"]
    if flows:
        action = (f"Run the pack's default action, the workflow {flows[0]}, with the request below as its input: tell "
                  f"the user the command (`halo workflow run {flows[0]} --input request=\"<the request>\"`), what it "
                  "costs (its budget_usd) and run it once they agree.")
    elif cmds:
        action = f"Do what {cmds[0]} does, with the request below."
    else:
        action = "Answer the request below as this pack's guide: say which of its parts fits, and how to use it."
    return (f"---\ndescription: \"{name}: what the pack is, its commands, workflows and lineups -- and its default "
            f"action\"\nargument-hint: \"[what to do]\"\n---\n"
            f"This is the {name} pack ({pid} {manifest.get('version')}): {manifest.get('description')}\n\n"
            f"What it brings:\n{listing}\n\nIf the request below is empty, show the user the list above, one line each, "
            f"and stop. Otherwise: {action}\n\nRequest: $ARGUMENTS\n")


def _what(rel: str, manifest: dict) -> str:
    if rel in FILE_WHAT:
        return FILE_WHAT[rel]
    if rel == f"commands/{manifest.get('id')}.md":
        return f"the entry command /{manifest.get('id')}: what the pack is, its parts, its default action"
    if rel.startswith("tests/samples/"):
        return "a sample its schema is checked against by halo pack test"
    return FOLDER_WHAT.get(rel.split("/")[0], "a file of the pack")


def readme(manifest: dict, files: dict, *, github: bool) -> str:
    from halo_harness.packs.manifest_requires import tools_of
    pid, name = manifest.get("id"), manifest.get("name")
    out = [f"# {name} ({pid})", "", str(manifest.get("description") or ""), "",
           "A Halo pack. `HALO-PACK.md` is how to work on it; this page is how to use it.", ""]
    tools = tools_of(manifest)
    if tools:
        out += ["## Install", "", "It uses these open-source tools; Halo never installs them, so install each once:", ""]
        for t in tools:
            out += [f"- **{t.get('name')}** ({t.get('license')}, {t.get('url')}): {t.get('why')}",
                    *[f"  - {os}: `{line}`" for os, line in (t.get("install") or {}).items()]]
        out.append("")
    if github:
        out += ["## Install from GitHub", "", "```", "halo pack sources add https://github.com/<you>/" + str(pid),
                f"halo pack install {pid}", f"halo pack enable {pid} --grant-all", "```", "",
                "`halo pack update` reads the repo again and says each `migrations` note first; tag each release.", ""]
    out += ["## Use it", "", "```", f"halo pack install ./{pid}", f"halo pack enable {pid} --grant-all",
            "```", "", f"Then `/{pid}` in a session lists what it brings:", "", brings(manifest, files), ""]
    perms = manifest.get("permissions") or []
    grant = {"hooks": "its hooks and its policy hooks run", "studio-script": "its Studio bundle panel's script runs in "
             "the page", "bash": "its code may run commands", "network": "its code may reach the network",
             "home-write": "its code may write outside its data folder",
             "services": "runs a program of this pack in the background while the supervisor runs"}  # 3.3.13.0 R3
    out += ["## Permissions", "", "Each one runs nothing until you grant it (`halo pack enable "
            f"{pid} --grant <name>`):", ""]
    out += [f"- `{p}`: " + (f"its MCP server {p[4:]} starts" if p.startswith("mcp:") else grant.get(p, "")) for p in perms]
    out += ([] if perms else ["- none"]) + [""]
    out += ["## Files", ""] + [f"- `{rel}`: {_what(rel, manifest)}" for rel in sorted(set(files) | {"README.md", "pack.yaml"})]
    out += ["", "## Develop it", "", "`halo pack test .` checks every part in a scratch home; `halo pack install . --link "
            "--project` makes the installed pack this folder, so an edit shows at once; `halo pack doctor` says what is "
            "left. HALO-PACK.md has the loop and the rules.", ""]
    return "\n".join(out)
