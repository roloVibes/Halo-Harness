"""halo_harness.packs.doctor -- every pack problem, one line each (Halo
3.2.0.0 R1): what `halo pack doctor` prints and `halo doctor --config` lists
under the packs group.

    problems(cwd=..., state_dir=...) -> [{"pack", "severity": "blocks" | "warns", "check", "text", "fix", "path"}]

Checked: a pack.yaml that does not validate (blocks for an enabled pack, a
warning for one that is not); the extension API or Halo version outside a
pack's range, a missing, disabled or out-of-range required pack, a requires
cycle; a contribution whose permission is not granted (it does not run);
settings that do not fit the pack's schema; a bio's capability set no
catalog model has and a bio's need not granted (3.2.0.0 R2, packs/roles.py);
a fleet capability not available here, with why (3.2.0.0 R4, packs/contrib_views.py);
a permission the installed version requests that its version before the last update did not and that is not
granted, and a use of an extension API name announced for removal (3.2.0.0 R7, packs/deprecations.py);
two packs, or a pack and you,
offering one name; a pack shadowed by a same-id project pack; a state.json
record whose folder is gone; a bio or lineup file the manifest does not
list; and what `privacy_scan` finds in the pack's text files.
"""

from __future__ import annotations

from pathlib import Path


def _p(pack_id, severity, check, text, fix="", path="") -> dict:
    return {"pack": pack_id, "severity": severity, "check": check, "text": text, "fix": fix, "path": str(path)}


def undeclared_lines(pack) -> "list[str]":
    """Bio and lineup files in the pack the manifest's `contributes` does not list."""
    contributes = pack.manifest.get("contributes") if isinstance(pack.manifest.get("contributes"), dict) else {}
    out = []
    for kind in ("agents", "teams"):
        listed = {str(x) for x in contributes.get(kind) or [] if isinstance(x, str)}
        folder = Path(pack.root) / kind
        for p in sorted(folder.glob("*.yaml")) if folder.is_dir() else []:
            rel = f"{kind}/{p.name}"
            if rel not in listed:
                out.append(f"{pack.id}: {rel} is in the pack but not under contributes.{kind} in pack.yaml")
    return out


def privacy_lines(pack) -> "list[str]":
    from halo_harness.packs.fetch import files_of
    from halo_harness.privacy_scan import BINARY_SKIP_SUFFIXES, scan_text_content
    out = []
    for rel in files_of(Path(pack.root)):
        if rel.suffix.lower() in BINARY_SKIP_SUFFIXES:
            continue
        try:
            text = (Path(pack.root) / rel).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for f in scan_text_content(text, rel_path=rel.as_posix(), allowlist=set()):
            out.append(f"{pack.id}: {rel.as_posix()} line {f['line']}: {f['kind']} ({f['excerpt']})")
    return out


def _sources_problems() -> "list[dict]":
    """`packs.sources`: a list of folders and git urls; a folder that is not there is one line."""
    from halo_harness.packs.names import is_url
    from halo_harness.theme import get_config_value
    raw = get_config_value("packs.sources", default=None)
    if raw is None:
        return []
    if not isinstance(raw, list):
        return [_p("", "blocks", "sources", "packs.sources is a list of folders and git urls",
                   "halo config set packs.sources '[\"~/packs\"]'")]
    return [_p("", "warns", "sources", f"packs.sources: {src} is not a folder", "fix or drop the entry")
            for src in raw if isinstance(src, str) and not is_url(src) and not Path(src).expanduser().is_dir()]


def problems(*, cwd=None, state_dir=None) -> "list[dict]":
    from halo_harness.packs import grants as G
    from halo_harness.packs import settings as ST
    from halo_harness.packs import state as S
    from halo_harness.packs.conflicts import conflict_lines
    from halo_harness.packs.registry import snapshot
    snap = snapshot(cwd=cwd, state_dir=state_dir)
    out: "list[dict]" = []
    for pack in snap.packs:
        on = pack.id in snap.enabled
        yaml_path = Path(pack.root) / "pack.yaml"
        if not on:
            out += [_p(pack.id, "warns", "manifest", f"{pack.id}: pack.yaml: {line}", "fix pack.yaml", yaml_path)
                    for line in pack.problems]
        for line in snap.problems.get(pack.id, []):
            out.append(_p(pack.id, "blocks", "resolve", line, "until this is fixed the pack contributes nothing",
                          yaml_path))
        for shadow in pack.shadowed:
            out.append(_p(pack.id, "warns", "shadowed", f"{pack.id} in {shadow} is not used: the one in "
                          f"{pack.root} has the same id", "remove one of the two", shadow))
        if pack.id in snap.order:
            for perm, why in G.missing(pack, S.granted(pack.id, snap.state)):
                out.append(_p(pack.id, "warns", "not-granted", f"{pack.id}: {why} does not run: {perm} is not granted",
                              f"halo pack enable {pack.id} --grant {perm}", yaml_path))
            out += [_p(pack.id, "blocks", "settings", line, "halo config set packs.settings."
                       f"{pack.id}.<key> <value>") for line in ST.problems(pack)]
            from halo_harness.packs.roles import doctor_rows  # 3.2.0.0 R2: a bio's capabilities and needs
            out += [_p(pack.id, r["severity"], r["check"], r["text"], r["fix"], r["path"])
                    for r in doctor_rows(pack, S.granted(pack.id, snap.state), cwd=cwd, state_dir=state_dir)]
            from halo_harness.packs import contrib_views as CW  # 3.2.0.0 R4: a fleet capability not available here
            out += [_p(pack.id, r["severity"], r["check"], r["text"], r["fix"], r["path"])
                    for r in CW.doctor_rows(pack, S.granted(pack.id, snap.state), cwd=cwd, state_dir=state_dir)]
            from halo_harness.packs.deprecations import update_request_rows  # 3.2.0.0 R7: a grant the update asked for
            out += update_request_rows(pack, S.entry(pack.id, data=snap.state) or {}, S.granted(pack.id, snap.state))
        from halo_harness.packs.deprecations import deprecated_rows  # 3.2.0.0 R7: an ext name announced for removal
        out += deprecated_rows(pack)
        out += [_p(pack.id, "warns", "undeclared", line, "list it in pack.yaml", yaml_path)
                for line in undeclared_lines(pack)]
        out += [_p(pack.id, "warns", "privacy", line, "take it out of the pack's file", yaml_path)
                for line in privacy_lines(pack)]
    for line in conflict_lines(snap.active, cwd=cwd, state_dir=state_dir):
        out.append(_p("", "warns", "conflict", line, "rename one of the two"))
    out += _sources_problems()
    for pack_id, rec in sorted((S.load(state_dir).get("installed") or {}).items()):
        root = rec.get("root") if isinstance(rec, dict) else None
        if not isinstance(rec, dict) or rec.get("removed"):
            continue
        if root and not Path(root).is_dir():  # a project pack of another repo is still there: not listed
            out.append(_p(pack_id, "warns", "missing", f"state.json lists {pack_id} at {root}, and that folder "
                          "is gone", f"halo pack remove {pack_id}", S.state_path(state_dir)))
    return out


def config_findings(*, cwd=None, state_dir=None) -> "list[dict]":
    """`problems` as `halo doctor --config` findings (doctor_config.finding), kind "packs"."""
    from halo_harness.doctor_config import finding
    from halo_harness.packs.state import state_path
    from halo_harness.where.rows import display
    out = []
    for p in problems(cwd=cwd, state_dir=state_dir):
        path = p["path"] or str(state_path(state_dir))
        row = {"file": display(path, cwd=cwd), "path": path, "kind": "packs"}
        out.append(finding(f"pack-{p['check']}", p["severity"], row, p["text"], key=p["pack"], fix=p["fix"]))
    return out
