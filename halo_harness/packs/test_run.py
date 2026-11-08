"""halo_harness.packs.test_run -- `halo pack test`'s checks, run in a process of their own (Halo 3.3.12.0 R4).

    python -m halo_harness.packs.test_run <folder> [--kinds a,b] [--timeout S]   -> one JSON object on stdout

`halo_harness.ext.testing.run` starts this with a scratch home (BRIDGE_TEST_HOME a fresh folder, offline mode on,
OLLAMA_HOST at a closed port, Halo's provider keys left out) and reads the JSON when it has exited, so nothing here
touches the owner's home, and every process a check starts ends with it. The steps:

1. the manifest and every `manifest_*` check (a problem stops here: nothing installs with one);
2. install the folder into the scratch home, enable it with every grant it requests, and `halo pack doctor` on the
   installed copy (a row about this machine -- no catalog model with a bio's tags, a fleet capability not available,
   a program not on PATH, a requirement not installed -- is a skip line, not a failure);
3. each kind's checks (packs/test_run_parts.py, packs/test_run_proc.py).

Each check is `{kind, file, what, ok, fix}`; `ok` is true, false, or null for a check skipped with its reason.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

#: A doctor row about this machine, not the pack: a skip line in `halo pack test`.
HERE_CHECKS = ("bio-model", "fleet-capability", "not-on-path", "missing-requirement", "fleet-hidden", "setup-waiting")


class Run:
    def __init__(self, folder: Path, kinds, timeout: float):
        from halo_harness.config.paths import bridge_home
        self.folder, self.kinds, self.timeout = folder, set(kinds or []), timeout
        self.home = bridge_home().parent
        self.project = self.home / "project"
        self.project.mkdir(parents=True, exist_ok=True)
        self.checks: "list[dict]" = []
        self.pack = None

    def wants(self, kind: str) -> bool:
        return not self.kinds or kind in self.kinds

    def add(self, kind: str, file: str, what: str, ok, fix: str = "") -> None:
        self.checks.append({"kind": kind, "file": str(file), "what": str(what), "ok": ok, "fix": str(fix or "")})

    @property
    def root(self) -> Path:
        return Path(self.pack.root)

    @property
    def manifest(self) -> dict:
        return self.pack.manifest


def _manifest(r: Run) -> bool:
    from halo_harness.packs.discover import read_pack
    from halo_harness.packs.resolve import compat_lines
    pack = read_pack(r.folder, "source", folder_is_id=False)
    for line in pack.problems:
        named = re.match(r"^([A-Za-z0-9_./-]+[.](yaml|json|md))( line [0-9]+)?:", line)
        file = named.group(1) if named else "pack.yaml"
        r.add("manifest", file, line, False, "change what the line names (docs/EXTENSION_API.md has every key)")
    if pack.problems:
        return False
    for line in compat_lines(pack):
        r.add("manifest", "pack.yaml", line, False, "widen halo_api / halo in pack.yaml, or use a Halo in the range")
    r.add("manifest", "pack.yaml", f"the manifest and every file it names read clean ({pack.id} {pack.version})", True)
    return not compat_lines(pack)


def _install(r: Run) -> bool:
    from halo_harness.packs.discover import find
    from halo_harness.packs.grants import enable
    from halo_harness.packs.install import install
    ok, lines = install(str(r.folder), cwd=r.project)
    if not ok:
        for line in lines:
            r.add("manifest", "pack.yaml", f"install: {line}", False, "the line says what to change")
        return False
    from halo_harness.packs.manifest import load_manifest
    data, _ = load_manifest(r.folder)
    r.pack = find(str(data.get("id")), cwd=r.project)
    ok, lines = enable(r.pack, grant_all=True)
    r.add("manifest", "pack.yaml", "installs into a scratch home and enables with every grant it requests", ok,
          "; ".join(lines))
    return ok


def _doctor(r: Run) -> None:
    from halo_harness.packs.doctor import problems
    rows = [p for p in problems(cwd=r.project) if p.get("pack") in (r.pack.id, "")]
    for p in rows:
        if p["severity"] == "info":
            continue
        file = Path(p["path"]).name if p.get("path") else "pack.yaml"
        if p["check"] in HERE_CHECKS:
            r.add("doctor", file, f"doctor ({p['check']}): {p['text']}", None, p.get("fix") or "")
        else:
            r.add("doctor", file, f"doctor ({p['check']}): {p['text']}", False, p.get("fix") or "fix what it names")
    if not [p for p in rows if p["severity"] != "info" and p["check"] not in HERE_CHECKS]:
        r.add("doctor", "pack.yaml", "halo pack doctor finds nothing wrong with the installed copy", True)


def run(folder: Path, kinds=(), timeout: float = 10.0) -> dict:
    from halo_harness.packs import test_run_parts as P
    from halo_harness.packs import test_run_proc as X
    r = Run(Path(folder).resolve(), kinds, timeout)
    if _manifest(r) and _install(r):
        _doctor(r)
        for step in (P.agents, P.teams, P.skills, P.commands, X.entry, X.hooks, X.mcp, P.events, P.artifacts,
                     P.workflows, P.studio, P.bundle, P.fleet, X.policy, P.modes, X.setup, P.themes, P.requirements):
            try:
                step(r)
            except Exception as e:  # a check that breaks says so as a failure of its own, the rest still run
                r.add(step.__name__, "pack.yaml", f"the {step.__name__} check stopped: {type(e).__name__}: {e}", False,
                      "this is a fault of halo pack test itself if the pack's files read clean; say so with the line")
    from halo_harness.packs import policy
    policy.stop_all()
    pid = r.pack.id if r.pack is not None else r.folder.name
    return {"pack": pid, "folder": str(r.folder), "checks": r.checks}


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="python -m halo_harness.packs.test_run")
    p.add_argument("folder")
    p.add_argument("--kinds", default="")
    p.add_argument("--timeout", type=float, default=10.0)
    args = p.parse_args(argv)
    kinds = [k for k in args.kinds.replace(",", " ").split() if k]
    out = run(Path(args.folder), kinds, args.timeout)
    sys.stdout.write(json.dumps(out) + "\n")
    sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
