"""halo_harness.ext.compat -- the compatibility policy of the extension API
(Halo 3.2.0.0 R7; docs/EXTENSION_API.md "Compatibility and migration").

The policy, as this module applies it:

- The API version is MAJOR.MINOR (`API_VERSION`, "1.4" since Halo 3.5.0.0; "1.3" since 3.4.0.0; "1.2" since 3.3.13.0; "1.1" since 3.3.10.0). A minor version only
  adds names: every name keeps its meaning for every later minor of the same
  major. A major version may remove a name, and only one `deprecations()` has
  listed for at least one minor version before it.
- A pack states `halo_api: {min, max}`. `min` is required; `max` is inclusive
  at its own precision (`max: "1.9"` takes 1.9.4). Without `max` a pack runs on
  its `min`'s major only: `{min: "1.0"}` runs on every 1.x and not on 2.0.
- A Halo whose API is outside the range does not run the pack, and says so in
  one line (`halo_harness.packs.resolve.compat_lines`):
  "pack doc-review needs extension API 1.3 to 1.9; this Halo has 1.2".
- 1.1 (3.3.10.0 R1) adds `set_mode` / `current_mode` and the manifest's `contributes.policy` and
  `contributes.modes`; R2 enforces a verdict and adds the post-call verdict (`after: true`: pass | redact | drop),
  and Policy hooks is stable: a 1.0 pack keeps everything -- `{min: "1.0"}` and `{min: "1.0", max: "1.9"}`
  take 1.1, and a pack with no `policy` or `modes` reads and runs as before (`CHANGES`).

    api_version()                           "1.4"
    compatible({"min": "1.0", "max": "1.9"})   True on this Halo
    compatible({"min": "1.0"}, "2.0")       False: a new major
    range_words({"min": "1.2"})             "1.2 or a later 1.x"
    deprecations()                          [{name, since, removed_in, use}]; empty in 1.0
"""

from __future__ import annotations

from typing import Optional

#: The names announced for removal: `{name: {"since": "1.x", "removed_in": "2.0", "use": "<the name to use>"}}`.
#: A name is listed here for at least one minor version before the major that removes it. Empty in 1.0 and 1.1.
DEPRECATED: "dict[str, dict]" = {}
#: What each minor version added, and what a pack written for the one before keeps (docs/EXTENSION_API.md
#: "Changes in 1.x" lists the same).
CHANGES: "dict[str, dict]" = {
    "1.1": {"halo": "3.3.10.0", "adds": ["set_mode", "current_mode", "contributes.policy", "contributes.modes",
                                         "the post-call verdict (contributes.policy[].after: pass | redact | drop)",
                                         "the bundle panel's api: publish, on, getData, mode, attention, route (R3)",
                                         "contributes.setup: a pack's own Setup blocks, stable (Halo 3.3.11.0 R3)",
                                         "contributes.themes: a pack's own palettes, <pack-id>/<id>, stable (Halo 3.3.12.0 R2)",
                                         "testing: a pack's tests, what halo pack test runs, stable (Halo 3.3.12.0 R4)",
                                         "requires: a tool entry {kind, name, install, url, license, why}, stable "
                                         "(Halo 3.3.12.0 R4)"],
            "deprecates": [], "keeps": "everything: a 1.0 pack runs unchanged; one without policy, modes, setup or themes is untouched",
            "status": "Policy hooks: draft in 3.3.10.0 R1, stable from R2 (a session enforces each verdict)"},
    "1.2": {"halo": "3.3.13.0", "adds": ["host: what Halo does for a pack's code (state folder, models for a task, MCP "
                                         "servers and a probe, the tool env, a URL fetch, ComfyUI)",
                                         "contributes.studio.sections[].view: a section drawn whole by one bundle",
                                         "the bundle api's lib: the shell's React, ReactDOM, lib/ui and helpers",
                                         "contributes.studio.routes and the studio-routes grant: a pack's own Studio "
                                         "API routes", "a command's `studio:` frontmatter: it opens the pack's section",
                                         "testing.scratch_home, testing.studio, testing.pack_module",
                                         "remote: the transport seam -- sessions, connect, start_session, cards, notify / listen / "
                                         "notes, transcribe, qr_text, words, service, capture_studio (ext/remote.py), stable",
                                         "contributes.services: programs the supervisor keeps running while the pack is enabled "
                                         "and granted services, stable",
                                         "a pack command with `run:` in its frontmatter runs that program of the pack (no model call)",
                                         "halo pack test runs the pack's own tests/test_*.py, one check per module"],
            "deprecates": [], "keeps": "everything: a 1.0 or 1.1 pack runs unchanged; one without services is untouched",
            "status": "stable (Halo 3.3.13.0: the signal and design packs are built on it)"},
    "1.3": {"halo": "3.4.0.0", "adds": ["contributes.cli: a pack's own `halo <verb>` (main(argv)), grant cli:<verb>",
                                         "contributes.slash: a pack's own `/<name>` run by its Python (run(args_text, facade)), "
                                         "the grant of its verb of that name",
                                         "contributes.doctor: a pack's own `halo doctor` rows (rows(ctx)), grant doctor",
                                         "contributes.settings: a pack's own Settings rows, packs.settings.<id>.<key>, no grant",
                                         "core: the core modules the shipped first-run and coach packs drive (core.REACHABLE)"],
            "deprecates": [], "keeps": "everything: a 1.0, 1.1 or 1.2 pack runs unchanged; one without the four keys is untouched",
            "status": "draft (Halo 3.4.0.0: the first-run and coach packs are built on it; may change in a minor with a "
                      "migration note)"},
    "1.4": {"halo": "3.5.0.0", "adds": ["contributes.capabilities: what the pack can do here (capabilities, inspector "
                                         "lines), the new name of contributes.fleet, which is still read (its mission key "
                                         "ignored)"],
            "deprecates": [], "keeps": "everything: a pack with contributes.fleet reads as before, its capabilities checked",
            "status": "stable (Halo 3.5.0.0: the doc-review pack uses it)"},
    "1.5": {"halo": "3.6.0.0", "adds": ["contributes.studio panels: role (main | drawer | tab), side (left | right), content_w "
                                         "(a drawer's width from its content, 360-560 px): how the panel opens on the stage"],
            "deprecates": [], "keeps": "everything: a panel's w / h still work (w columns -> a right drawer w x 60 px wide)",
            "status": "stable (Halo 3.6.0.0 R0a: the stage, one main thing per view)"},
}


def api_version() -> str:
    """This Halo's extension API version (`API_VERSION`)."""
    from halo_harness.ext import API_VERSION
    return API_VERSION


def _major(version) -> Optional[int]:
    from halo_harness.packs.semver import release
    parts = release(version)
    return parts[0] if parts else None


def compatible(rng, version=None) -> bool:
    """True when the API `version` (default this Halo's) is inside a pack's `halo_api` range under the policy:
    `min <= version <= max`, and with no `max`, the same major as `min`."""
    from halo_harness.packs import semver as V
    version = str(version if version is not None else api_version())
    if not isinstance(rng, dict) or V.range_problem(rng) or V.release(version) is None:
        return False
    if not V.in_range(version, rng):
        return False
    if rng.get("max") is None and rng.get("min") is not None:
        return _major(version) == _major(rng["min"])
    return True


def range_words(rng) -> str:
    """A `halo_api` range in the policy's words: "1.0 to 1.9", "1.2 or a later 1.x", "<= 1.9"."""
    from halo_harness.packs import semver as V
    if isinstance(rng, dict) and rng.get("max") is None and rng.get("min") is not None:
        return f"{rng['min']} or a later {_major(rng['min'])}.x"
    return V.describe(rng)


def deprecations() -> "list[dict]":
    """Every name announced for removal, by name: `[{name, since, removed_in, use}]` (`use` may be '')."""
    return [{"name": name, "since": str(info.get("since") or ""), "removed_in": str(info.get("removed_in") or ""),
             "use": str(info.get("use") or "")} for name, info in sorted(DEPRECATED.items())]


__all__ = ["DEPRECATED", "CHANGES", "api_version", "compatible", "range_words", "deprecations"]
