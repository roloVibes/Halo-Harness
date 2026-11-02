"""halo_harness.packs.policy_views -- the policy hooks and modes as `halo pack inspect`, `halo pack policy status`
and `halo pack doctor` show them (Halo 3.3.10.0 R1; docs/EXTENSION_API.md "Policy hooks", draft).

    block(pack, state_dir=None, *, running=None, granted=()) -> {"mode": mode.json, "modes": [...], "policies": [...]}
    block_lines(d)        the lines under "policy hooks:" (each policy's command, when, impact, on_error, redact, state)
    status(cwd=None, state_dir=None) -> [block + {id, version, state}] for every pack that declares a policy or a mode
    status_lines(rows)
    doctor_rows(pack, state_dir=None) -> a row for a mode or an armed policy mode.json names and the manifest does not
"""

from __future__ import annotations

def _state_of(p: dict, rec: dict, running: bool, hooks: bool, pack_id: str) -> str:
    if p["id"] not in rec["armed"]:
        return f"not armed (halo pack policy arm {pack_id} {p['id']})"
    if not running:
        return f"armed, not asked: the pack does not run here (halo pack enable {pack_id} --grant hooks)"
    if not hooks:
        return f"armed, not asked: hooks is not granted (halo pack grant {pack_id} hooks)"
    if p["modes"] and rec["mode"] not in p["modes"]:
        return f"armed, not asked: mode {' or '.join(p['modes'])} is not on (the mode now: {rec['mode'] or 'none'})"
    return "armed, asked now"


def block(pack, state_dir=None, *, running=None, granted=()) -> "dict | None":
    from halo_harness.packs import manifest_policy as MP
    from halo_harness.packs import mode_state as M
    pols, modes = MP.policies_of(pack.manifest), MP.modes_of(pack.manifest)
    if not pols and not modes:
        return None
    rec = M.read(pack.id, state_dir)
    out = {"mode": rec, "modes": [], "policies": []}
    for m in modes:
        out["modes"].append({"id": m.get("id"), "label": m.get("label") or m.get("id"), "theme": m.get("theme"),
                             "on": rec["mode"] == m.get("id")})
    for e in pols:
        tools, wanted = MP.when_of(e)
        run = e.get("run")
        p = {"id": e.get("id"), "run": run if isinstance(run, str) else " ".join(str(a) for a in run or []),
             "tools": tools, "modes": wanted, "impact": e.get("impact") or "medium", "on_error": e.get("on_error") or "allow",
             "redact": list(e.get("redact") or []), "after": e.get("after") is True}
        p["state"] = _state_of(p, rec, bool(running), "hooks" in set(granted or ()), pack.id) if running is not None else ""
        out["policies"].append(p)
    return out


def block_lines(d) -> "list[str]":
    if not d:
        return []
    rec = d["mode"]
    out = ["policy hooks and modes (draft: nothing enforces a verdict before 3.3.10.0 R2):"]
    for m in d["modes"]:
        theme = f", theme {m['theme']} (read from 3.3.12.0)" if m.get("theme") else ""
        out.append(f"  mode {m['id']} ({m['label']}{theme}): " + ("on" if m["on"] else "off"))
    if rec["mode"] or rec["armed"]:
        out.append(f"  mode.json: mode {rec['mode'] or 'none'}, armed {', '.join(rec['armed']) or 'none'}"
                   + (f", since {rec['since']} by {rec['by']}" if rec.get("since") else ""))
    for p in d["policies"]:
        when = f"tools {', '.join(p['tools']) or 'every tool'}" + (f"; modes {', '.join(p['modes'])}" if p["modes"] else "")
        extra = f"; redact {', '.join(p['redact'])}" if p["redact"] else ""
        out.append(f"  policy {p['id']}: {when}; impact {p['impact']}; on_error {p['on_error']}{extra}"
                   + ("; after (read from R2)" if p["after"] else ""))
        out.append(f"    run: {p['run']}")
        if p.get("state"):
            out.append(f"    {p['state']}")
    return out


def status(*, cwd=None, state_dir=None) -> "list[dict]":
    from halo_harness.packs import state as S
    from halo_harness.packs.registry import snapshot
    snap = snapshot(cwd=cwd, state_dir=state_dir)
    rows = []
    for pack in snap.packs:
        running = pack.id in snap.order
        granted = S.granted(pack.id, snap.state) if pack.id in snap.enabled else []
        b = block(pack, state_dir, running=running, granted=granted)
        if b is not None:
            word = "runs here" if running else ("enabled, not running" if pack.id in snap.enabled else "disabled")
            rows.append({"id": pack.id, "version": pack.version, "state": word, **b})
    return rows


def status_lines(rows) -> "list[str]":
    if not rows:
        return ["No pack here declares a policy hook or a mode."]
    out = []
    for r in rows:
        out.append(f"{r['id']} {r['version']} ({r['state']}): mode {r['mode']['mode'] or 'none'}")
        for p in r["policies"]:
            out.append(f"  {p['id']}: {p['state']}")
    return out


def doctor_rows(pack, state_dir=None) -> "list[dict]":
    from halo_harness.packs import manifest_policy as MP
    from halo_harness.packs import mode_state as M
    rec = M.read(pack.id, state_dir)
    path = str(M.mode_path(pack.id, state_dir))
    out = []
    modes, pols = MP.ids(MP.modes_of(pack.manifest)), MP.ids(MP.policies_of(pack.manifest))
    if rec["mode"] and rec["mode"] not in modes:
        out.append({"severity": "warns", "check": "policy-mode", "path": path,
                    "fix": f"halo pack mode {pack.id} <mode> on (contributes.modes: {', '.join(modes) or 'none'})",
                    "text": f"{pack.id}: mode.json names mode {rec['mode']!r}, which contributes.modes does not declare"})
    for a in rec["armed"]:
        if a not in pols:
            out.append({"severity": "warns", "check": "policy-armed", "path": path,
                        "fix": f"halo pack policy disarm {pack.id} {a}",
                        "text": f"{pack.id}: mode.json arms policy {a!r}, which contributes.policy does not declare"})
    return out
