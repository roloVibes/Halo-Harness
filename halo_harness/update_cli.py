"""halo_harness.update_cli -- `halo update` (Halo 2.0.2 round 6). `cmd_update`
is the argv-parsing entry point `cli.py` dispatches `argv[0] == "update"` to;
`apply_update()` is the reusable half (no argv) that `cli.py`'s own `/update`
restart handoff calls directly once the TUI has already quit. Every real
action goes through `update.run`/`update.other_halo_pids`/`update.
latest_available`, all three seams a test fakes -- this module never shells
out or opens a socket on its own.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import Optional

from halo_harness import update as upd


def _retarget_spec(spec: Optional[str], to: str) -> Optional[str]:
    """`--to <ref>`: only meaningful for a `git+URL[@rev]` spec (a real
    uv-tool/pipx/pip install) -- a checkout kind's own reinstall is always
    `git pull`, which has no "spec" to retarget at all, so this is a no-op
    there (the caller's own `cmd.replace(...)` then has nothing to
    replace, which is fine: `--to` simply does not apply to that kind)."""
    if not spec or not spec.startswith("git+"):
        return spec
    return f"{spec.split('@', 1)[0]}@{to}"


def _print_report(build: dict, avail: dict, lines: list, count, cmd: Optional[str], *,
                   ordering: Optional[bool] = None) -> None:
    print(f"installed: {upd.format_version_line(build)}")
    if avail.get("commit"):
        ref = f", {avail['ref']}" if avail.get("ref") else ""
        # Halo 2.0.2 round C: `ordering` is `upd.commit_is_ancestor`'s own
        # three-way answer -- False means a real local checkout CHECKED
        # this and confirmed the installed commit is NOT behind it (a
        # diverged/rebased-backward history, or a deliberately different
        # ref); True or None (no checkout to ask, or confirmed a clean
        # ancestor) both keep the plain "available" wording that already
        # implies "ahead of you", unchanged.
        label = "differs from" if ordering is False else "available"
        print(f"{label} ({avail.get('channel', '?')}): {avail['commit']}{ref}")
    else:
        print(f"available ({avail.get('channel', '?')}): unknown ({avail.get('reason') or 'no reason given'})")
    if lines:
        print(f"{count if isinstance(count, int) and count > len(lines) else len(lines)} commit(s):")
        for line in lines:
            print(f"  {line}")
    elif count:
        print(f"{count} commit(s) ahead (no local checkout here to list them one by one)")
    print(f"update command: {cmd or '(unknown -- could not determine how halo was installed)'}")


def _exit_code(build: dict, avail: dict) -> int:
    if not avail.get("commit") or not build.get("commit"):
        return 1
    return 0 if build["commit"] == avail["commit"] else 10


def apply_update(*, cmd: Optional[str] = None, force: bool = False) -> int:
    """Runs the reinstall command LIVE (inherited stdio -- "output
    visible"), then re-queries `halo --version` as a FRESH subprocess --
    this process's own already-imported `halo_harness` module would
    otherwise just keep reporting the OLD version forever, update or not.
    Refuses (returns 1, no reinstall attempted) while another halo
    process is on this machine unless `force=True`; `cli.py`'s own
    `/update` restart handoff always calls this AFTER the TUI's process
    has already quit (Textual torn down), so that check still correctly
    counts only genuinely OTHER processes, never a stale earlier one."""
    # Halo 2.0.3 fix pass C-1 (review finding 3): checked before anything
    # else -- an explicit `halo update`/`/update` apply is a real
    # reinstall (`git pull`/`uv tool install`/`pip install --upgrade`,
    # every one of them network-reaching), never a background check, so
    # this returns an error result instead of silently skipping.
    from halo_harness.providers.http import format_offline_refusal, offline_mode_enabled
    if offline_mode_enabled():
        print(f"halo update: {format_offline_refusal('the update server')}", file=sys.stderr)
        return 1
    others = upd.other_halo_pids()
    if others and not force:
        pids = ", ".join(str(p) for p in others)
        print(f"halo update: refusing -- another halo process looks like it's running "
              f"(pid {pids}); close it first, or pass --force", file=sys.stderr)
        return 1
    before = upd.installed_build()
    kind = upd.install_kind()
    if cmd is None:
        cmd = kind.get("reinstall_cmd")
    if not cmd:
        if kind.get("kind") == "source_dir":
            # Halo 2.0.2 round 6/C: a plain source directory (no .git, no
            # dist metadata) has no `git pull` to run and no package
            # manager that installed it to reinstall through -- say so
            # plainly instead of the generic "could not determine" below.
            print(f"halo update: running from a plain source directory ({kind.get('spec')}) with no git "
                  f"metadata -- replace the directory to update", file=sys.stderr)
        else:
            print("halo update: could not determine how halo was installed -- nothing to run", file=sys.stderr)
        return 1
    # Finding 3: a checkout kind's `spec` is the real checkout directory
    # (never a bare "."  -- see update.install_kind) -- running there,
    # not in whatever directory `halo update`/`/update` happened to be
    # invoked from, is what makes the git pull (and the reinstall's own
    # path argument) land on the right repo. An installed-package kind's
    # `spec` is a URL/git+spec, not a real local directory, so `cwd` stays
    # None there and the command runs from wherever, same as before.
    spec = kind.get("spec")
    cwd = spec if spec and Path(spec).is_dir() else None
    print(f"halo update: installed {upd.format_version_line(before)}")
    print(f"halo update: running: {cmd}")
    try:
        result = upd.run(cmd, shell=True, cwd=cwd, capture_output=False, text=True, timeout=600)
        returncode = result.returncode
    except (OSError, subprocess.SubprocessError) as e:
        print(f"halo update: the reinstall command failed to run: {e}", file=sys.stderr)
        returncode = 1
    after = upd.run(["halo", "--version"], capture_output=True, text=True, timeout=15)
    after_line = (after.stdout or "").strip() or "(unknown -- could not run `halo --version` after the update)"
    print(f"halo update: before {upd.format_version_line(before)}")
    print(f"halo update: after  {after_line}")
    return 0 if returncode == 0 else 1


def cmd_update(argv: "list[str]") -> int:
    parser = argparse.ArgumentParser(prog="halo update", add_help=True,
                                      description="Check for, or apply, a halo update.")
    parser.add_argument("--check", action="store_true", help="Report only -- never reinstalls")
    parser.add_argument("--to", default=None, metavar="TAG_OR_BRANCH_OR_COMMIT",
                         help="Pick an exact revision instead of the channel's latest")
    parser.add_argument("--channel", choices=["stable", "main"], default=None,
                         help="stable tracks the newest v* tag, main tracks the branch halo came from")
    parser.add_argument("--force", action="store_true",
                         help="Reinstall even if another halo process looks like it's running")
    parser.add_argument("--refresh", action="store_true",
                        help="(always on now -- kept for compatibility) ignore the cache, always check live")
    # 2.0.6 round 8 (the v2.0.4 review's item 7, the verification half):
    # refuse to install a target tag whose GitHub release has no
    # checksums.txt asset -- every release.py-built tag carries one
    # (the tag's own git archive + its sha256); a missing one means a
    # broken or foreign release, not something to install unverified.
    parser.add_argument("--no-verify", dest="verify", action="store_false",
                        help="Skip the target tag's release-checksums check before installing")
    args = parser.parse_args(argv)
    if args.channel:
        from halo_harness.theme import set_config_value
        set_config_value("update.channel", args.channel)
    build = upd.installed_build()
    channel = args.channel or upd.default_channel(build)
    # Halo 2.0.2 round C: "an explicit --check or /update always queries
    # (5 s cap) with the cache only as the fallback" -- ANY invocation of
    # `halo update` (--check or not) is explicit by definition, so this
    # no longer waits for --check specifically before always-refreshing
    # (that flag is now a no-op, kept only so an existing script that
    # passes it still runs); the cache-first path is `update.cache_ttl_s`
    # alone now, for the passive startup note only (see latest_
    # available's own docstring).
    avail = upd.latest_available(channel, refresh=True)
    kind = upd.install_kind()
    cmd = kind.get("reinstall_cmd")
    if args.to and cmd and kind.get("spec"):
        retargeted = _retarget_spec(kind["spec"], args.to)
        if retargeted and retargeted != kind["spec"]:
            cmd = cmd.replace(kind["spec"], retargeted)
    checkout = Path(build["checkout"]) if build.get("checkout") else None
    lines, count = upd.commits_between(build.get("commit"), avail.get("commit"), checkout=checkout)
    ordering = upd.commit_is_ancestor(build.get("commit"), avail.get("commit"), checkout=checkout)
    _print_report(build, avail, lines, count, cmd, ordering=ordering)
    code = _exit_code(build, avail)
    if args.check:
        return code
    if code == 0:
        print("halo update: already up to date")
        return 0
    # 2.0.6 round 8: the target tag must carry a checksums.txt release
    # asset before we install it. Only a TAG-shaped target can be checked
    # (a branch/commit target has no release); an unreadable release
    # (offline, rate-limited) fails OPEN with a printed warning -- a
    # network blip must not block the update the user explicitly asked
    # for, only a tag that verifiably lacks the asset refuses.
    if getattr(args, "verify", True):
        target = args.to or avail.get("commit")
        if isinstance(target, str) and target.startswith("v") and target[1:].replace(".", "").isdigit():
            assets = upd.tag_checksums(target)
            if assets is not None and not any(a.get("name") == "checksums.txt" for a in assets):
                print(f"halo update: refusing -- release {target} has no checksums.txt asset "
                      f"(broken or foreign release; --no-verify skips this check)", file=sys.stderr)
                return 1
            elif assets is None:
                print(f"halo update: could not read release {target}'s assets "
                      f"(offline or rate-limited) -- installing without the checksums check",
                      file=sys.stderr)
    return apply_update(cmd=cmd, force=args.force)
