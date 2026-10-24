"""halo_harness.isolation.cli -- `halo isolation` (Halo 3.1.8.0 R5, docs/ISOLATION.md).

    halo isolation image            the default image name and the Dockerfile Halo ships
    halo isolation build [--image NAME] [--dry-run]
                                    build that image with docker (or podman) at this harness's version
    halo isolation check            which modes this host can run, and what your lineups and bios declare

Exit codes: 0 done, 1 could not (the reason on stderr), 2 usage.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="halo isolation", description="Opt-in isolation for Orchestra workers.")
    sub = p.add_subparsers(dest="cmd")
    sub.add_parser("image", help="print the default image name and the Dockerfile Halo ships")
    b = sub.add_parser("build", help="build the default image with docker (or podman)")
    b.add_argument("--image", default=None, help="the tag to build (default: halo-harness-worker:<version>)")
    b.add_argument("--dry-run", action="store_true", help="print the build command, run nothing")
    sub.add_parser("check", help="which modes this host can run, and what your lineups and bios declare")
    return p


def cmd_isolation(argv: list, *, runner=subprocess.run, which=shutil.which) -> int:
    p = _parser()
    args = p.parse_args(argv)
    from halo_harness.isolation import Stop
    from halo_harness.isolation import container as C
    if args.cmd == "image":
        print(f"image: {C.default_image()}")
        print(f"Dockerfile: {C.dockerfile_path()}")
        print()
        print(C.dockerfile_text().rstrip())
        return 0
    if args.cmd == "build":
        try:
            argv_build = C.build_argv(args.image, which=which)
        except Stop as e:
            print(f"halo isolation build: {e}", file=sys.stderr)
            return 1
        print(" ".join(argv_build))
        if args.dry_run:
            return 0
        proc = runner(argv_build, stdin=subprocess.DEVNULL)
        return 0 if proc.returncode == 0 else 1
    if args.cmd == "check":
        from pathlib import Path
        from halo_harness.isolation.declared import declared
        from halo_harness.isolation.doctor_rows import isolation_row, secrets_row
        from halo_harness.isolation.lines import isolation_line
        from halo_harness.isolation.secrets import line as secrets_line
        found = declared(cwd=Path.cwd())
        print(isolation_row(found, which=which, runner=runner))
        print(secrets_row(found, which=which))
        for label, iso, sec in found:
            print(f"  {label}: " + "; ".join(x for x in (isolation_line(iso), secrets_line(sec)) if x))
        return 0
    p.print_help()
    return 2


if __name__ == "__main__":  # pragma: no cover
    sys.exit(cmd_isolation(sys.argv[1:]))
