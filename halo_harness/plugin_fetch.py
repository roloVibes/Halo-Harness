"""halo_harness.plugin_fetch -- W4a `--plugin-dir`/`--plugin-url`: "load a
plugin's skills, commands, agents, hooks and MCP servers from a directory or
a git URL" (plans/2.0.1-w4-plan.md W4a item 2). `--plugin-dir` needs no
fetching at all -- its path IS the plugin root, handed straight to
`config.agents_md.discover_agents`'s own `plugin_roots=` kwarg (the one
precedence tier that already exists for "a plugin" generally). `--plugin-url`
(a git URL, per the gap list's own gloss -- Claude Code's real flag fetches
a .zip; this harness takes the simpler, already-everywhere-available git
clone instead) is cloned ONCE per URL into a cache keyed by its own hash, so
a repeat launch with the same URL reuses the existing checkout rather than
re-cloning every single time.

W5 (carried from W4a): `resolve_plugin_roots`'s own output is now threaded
through ALL FIVE of Claude Code's plugin precedence tiers for a CLI-
supplied plugin directory/URL, not just agents -- `headless.build_session`
resolves it ONCE, near the top, and hands the same list to `discover_agents`
(`plugin_roots=`), `mcp_setup.build_manager` (`extra_plugin_roots=`, via
`config.plugins.discover_plugin_mcp_servers`'s own `extra_roots=`),
`build_hook_runner` (`extra_plugin_roots=`, via `hooks.load_plugin_hooks`),
and `commands.registry.Registry.discover` (`plugin_roots=`, which reaches
both `commands/custom.py`'s own `commands/` scan and `commands/skills.py`'s
own `skills/` scan) -- plus `Session.plugin_roots`/`ToolContext.
plugin_roots` so a model-invoked `Skill` tool call sees a CLI plugin's
skills too, not only the `/` slash-command surface. A CLI-supplied root has
no `installed_plugins.json` record to read a NAME from (unlike an installed
plugin, whose name is the manifest key) -- `plugin_name_for_root` below
reads `.claude-plugin/plugin.json`'s own `name` field, falling back to the
root directory's own basename, and that name is what every tier below uses:
MCP servers as `plugin_<name>_<server>` (`config.plugins.plugin_server_
name`, same as an installed plugin), skills/commands namespaced `<name>:
<skill-or-command>` (binary-facts sec.11: "plugin skills are
`<plugin>:<skill>`" -- commands follow the same convention)."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

log = logging.getLogger("bridge")


def plugin_name_for_root(root) -> str:
    """The plugin's own name, for a root that has no `installed_plugins.
    json` manifest entry to read one from: `.claude-plugin/plugin.json`'s
    `name` field when that file exists and sets one, else the root
    directory's own basename (e.g. `--plugin-dir ../my-plugin` names it
    `my-plugin`, same as a `git clone`d `--plugin-url`'s checkout directory
    name would without a declared name either). Never raises -- a missing
    or malformed `plugin.json` just falls back to the basename."""
    root = Path(root)
    plugin_json = root / ".claude-plugin" / "plugin.json"
    try:
        data = json.loads(plugin_json.read_text(encoding="utf-8-sig"))
        name = data.get("name") if isinstance(data, dict) else None
        if isinstance(name, str) and name.strip():
            return name.strip()
    except (OSError, ValueError):
        pass
    return root.name


def _clone_cache_dir(state_dir: Path) -> Path:
    d = Path(state_dir) / "plugins-cache"
    d.mkdir(parents=True, exist_ok=True)
    return d


def clone_plugin_url(url: str, state_dir: Path, *, timeout: float = 60.0) -> Optional[Path]:
    """Shallow-clones `url` into `<state_dir>/plugins-cache/<sha1(url)[:16]>`
    the FIRST time it's seen; a later call with the SAME url reuses the
    existing checkout unchanged (never re-clones, never `git pull`s -- a
    plugin's own version is pinned to whatever was there on first use,
    same spirit as this harness's other caches). Returns `None` (never
    raises) when `git` is missing or the clone fails -- the caller's own
    notice is what the user actually sees; this stays silent about why.

    finding 47: cloned into a fresh temp directory FIRST, `os.replace`d
    into `dest` only once `git clone` actually finished and `dest/.git`
    is confirmed -- a clone that TIMED OUT (or was killed/crashed)
    partway used to leave a half-written `dest` behind, and the cache-hit
    check above (`.git` is a directory the instant `git` creates it,
    long before the clone finishes) then treated that half-clone as a
    permanently valid cache hit on every later call, with no way to ever
    retry. The `--` separator also means a url shaped like an option
    (e.g. `--upload-pack=...`) is read as a positional argument, never as
    a flag `git clone` would otherwise honour."""
    digest = hashlib.sha1(url.encode("utf-8", "replace")).hexdigest()[:16]
    cache_dir = _clone_cache_dir(state_dir)
    dest = cache_dir / digest
    if (dest / ".git").is_dir():
        return dest
    # Halo 2.0.3 fix pass C-1 (review finding 3): checked AFTER the
    # cache-hit short-circuit above (an already-cloned checkout needs no
    # network at all) but before the real `git clone` -- a `--plugin-url`
    # under offline mode used to clone anyway. Same "background check:
    # skip quietly" shape as this function's own existing silent-failure
    # contract (git missing/clone failed both already return None with
    # no exception).
    from halo_harness.providers.http import offline_mode_enabled
    if offline_mode_enabled():
        log.debug("plugin_fetch: offline mode is on -- skipping git clone of a --plugin-url")
        return None
    tmp_dest = Path(tempfile.mkdtemp(prefix=f"{digest}.", dir=str(cache_dir)))
    try:
        result = subprocess.run(
            ["git", "clone", "--depth", "1", "--", url, str(tmp_dest)],
            capture_output=True, text=True, timeout=timeout,
        )
    except (OSError, subprocess.SubprocessError):
        result = None
    if result is None or result.returncode != 0 or not (tmp_dest / ".git").is_dir():
        shutil.rmtree(tmp_dest, ignore_errors=True)
        return None
    try:
        if dest.exists():
            shutil.rmtree(dest, ignore_errors=True)
        os.replace(tmp_dest, dest)
    except OSError:
        shutil.rmtree(tmp_dest, ignore_errors=True)
        return None
    return dest


def resolve_plugin_roots(plugin_dirs: list, plugin_urls: list, *, state_dir: Path) -> "list[str]":
    """`cli_flags["plugin_dir"] + cli_flags["plugin_url"]` -> a flat list of
    real, existing directory paths (string form, `discover_agents`'s own
    `plugin_roots` shape) -- an unresolvable `--plugin-dir` (doesn't exist)
    or a failed `--plugin-url` clone is dropped silently (best-effort,
    matching every other plugin-loading path in this harness)."""
    roots: "list[str]" = []
    for d in plugin_dirs or []:
        p = Path(d)
        if p.is_dir():
            roots.append(str(p))
    for url in plugin_urls or []:
        cloned = clone_plugin_url(url, state_dir)
        if cloned is not None:
            roots.append(str(cloned))
    return roots
