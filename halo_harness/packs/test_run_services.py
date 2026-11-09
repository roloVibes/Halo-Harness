"""halo_harness.packs.test_run_services -- `halo pack test`'s check of `contributes.services` (Halo 3.3.13.0 R3;
docs/EXTENSION_API.md "Services", docs/COMMANDS-packs-kit.md). For each service: its command resolves (the program
is Halo's Python or a file of the pack, and the file it runs is there), its health probe has a shape the supervisor
reads (a file in the data folder with a max age, or a url on this machine), its log lands in the data folder, and the
`services` grant is requested. The service is not started: it may need a tool or an account this machine does not
have; the supervisor starts it once the pack is enabled and granted (`halo supervise services` shows it).
"""

from __future__ import annotations

from pathlib import Path


def services(r) -> None:
    from halo_harness.packs import manifest_services as MS
    from halo_harness.packs.manifest import requested
    from halo_harness.packs.manifest_policy import run_argv, script_rel
    entries = MS.services_of(r.manifest)
    if not r.wants("services") or not entries:
        return
    if MS.GRANT not in requested(r.manifest):
        r.add("services", "pack.yaml", "a service needs the services grant requested", False,
              f"add {MS.GRANT} to permissions:")
    for e in entries:
        name = str(e.get("name"))
        rel, why = script_rel(e.get("run"))
        argv = run_argv(e, r.root) if not why else []
        ok = bool(argv) and (Path(argv[0]).is_file() or Path(argv[0]).name.lower().startswith("python")) \
            and (r.root / rel).is_file()
        r.add("services", rel or "pack.yaml", f"service {name}: its command resolves ({' '.join(Path(a).name for a in argv)})",
              ok, why or "the command names a file of the pack: [\"${halo_python}\", \"${CLAUDE_PLUGIN_ROOT}/<path>.py\"]")
        h = MS.health_of(e)
        what = (f"a file it rewrites, {h['file']}, younger than {int(h['max_age_s'])} s" if "file" in h else
                f"a url on this machine, {h['url']}" if "url" in h else "none: the row says running or stopped only")
        r.add("services", "pack.yaml", f"service {name}: its health probe is {what}", True)
        r.add("services", "pack.yaml", f"service {name}: restart {MS.restart_of(e)}, autostart "
              f"{'yes' if e.get('autostart') is True else 'no'}, log {MS.log_of(e)} in the data folder", True)
