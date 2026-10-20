"""halo_harness.orchestra.coach_probe_schema -- the strict shape of a probe
candidate and the run facts it is checked against (Halo 3.1.6.0 R2; the
candidates are drafted by orchestra/coach_probe.py).

A candidate is an overlay of the run's harness, one of two kinds:

    invariant  how the agents work whatever the goal (planning, tool use,
               context budget, delegation):
        {"lead":    {"model": "<ref>", "effort": "low|medium|high|xhigh|max", "prompt_notes": "..."},
         "workers": {"model": "<ref>", "prompt_notes": "...", "max_iterations": 40,
                     "tools": {"allow": ["Read", "Edit"], "deny": ["WebFetch"]}},
         "bios":    {"<bio>": {the four keys of workers}},
         "why":     "one line"}
    domain     what this goal needs (procedure, knowledge, constraints):
        {"workers": {"prompt_notes": "..."},
         "bios":    {"<bio>": {"prompt_notes": "...", "use_for": ["word", ...]}},
         "plan":    [{"job": "job-2", "after": ["job-1"]}],
         "why":     "one line"}

`workers` is every lane's worker; `bios.<bio>` the lanes that ran as that bio
(it wins over `workers` key by key; two notes are both kept). `clean(kind,
raw, facts)` keeps what fits and names each thing it drops: an unknown key,
a model ref that does not resolve (not `<route>:<id>`, a removed cc:/cx:
route, an id its provider's catalog does not list), a bio that is not one of
the run's (`facts["bios"]`: the lanes' bios and the lineup's), a job that is
not in the run's plan, a note over NOTE_MAX characters, an effort or a
number out of range. `facts(run_dir)` reads those facts once.
"""

from __future__ import annotations

import re
from pathlib import Path

from halo_harness.orchestra import jsonl

KINDS = ("invariant", "domain")
NOTE_MAX, WHY_MAX, WORDS_MAX = 600, 300, 12
EFFORTS = ("low", "medium", "high", "xhigh", "max")
TOP = {"invariant": ("lead", "workers", "bios", "why"), "domain": ("workers", "bios", "plan", "why")}
PARTS = {"invariant": {"lead": ("model", "effort", "prompt_notes"),
                       "workers": ("model", "prompt_notes", "max_iterations", "tools"),
                       "bio": ("model", "prompt_notes", "max_iterations", "tools")},
         "domain": {"lead": (), "workers": ("prompt_notes",), "bio": ("prompt_notes", "use_for")}}
_REF = re.compile(r"^[a-z]{2,4}:\S+$")
_TOOL = re.compile(r"^[A-Za-z0-9_.*()-]{1,80}$")


def facts(run_dir, *, cwd=None, state_dir=None) -> dict:
    """The reference run's goal, jobs, lanes and lineup: what a candidate may name."""
    from halo_harness.orchestra.goal import load_goal, repo_root_of
    from halo_harness.orchestra.lanes import list_lanes
    run_dir = Path(run_dir)
    goal, repo = load_goal(run_dir / "goal.json"), repo_root_of(run_dir)
    cwd = cwd or repo
    split = jsonl.read_json(run_dir / "split.json", {}) or {}
    jobs = [j for j in split.get("jobs") or [] if isinstance(j, dict)]
    lanes = [{"n": l.n, "bio": str(l.data().get("bio") or l.job.bio or ""), "model": str(l.data().get("model") or ""),
              "cost_usd": float(l.cost_usd or 0.0), "job": l.job.id} for l in list_lanes(run_dir)]
    raw, entries = {}, []
    if goal.lineup:
        try:
            from halo_harness import teams_yaml as T
            raw = T.load_team_template_raw(goal.lineup, cwd=cwd, state_dir=state_dir) or {}
        except Exception:
            raw = {}
        entries = [e for e in raw.get("agents") or [] if isinstance(e, dict)]

    def entry(role: str) -> dict:
        return next((e for e in entries if role in (e.get("as"), e.get("role"))), {})
    lead_bio, worker_bio = str(entry(goal.lead).get("agent") or ""), str(entry(goal.worker).get("agent") or "")
    bios = {b for b in [lead_bio, worker_bio] + [str(e.get("agent") or "") for e in entries]
            + [l["bio"] for l in lanes] + [str(j.get("bio") or "") for j in jobs] if b}
    return {"run_dir": run_dir, "repo": repo, "cwd": cwd, "state_dir": state_dir, "goal": goal, "jobs": jobs,
            "lanes": lanes, "lineup": goal.lineup if raw else "", "lineup_raw": raw, "lead_role": goal.lead,
            "worker_role": goal.worker, "lead_bio": lead_bio, "worker_bio": worker_bio,
            "bios": sorted(b for b in bios if _bio_exists(b, cwd, state_dir)),
            "job_ids": [str(j.get("id")) for j in jobs], "cost_usd": _ref_cost(run_dir)}


def _ref_cost(run_dir: Path) -> float:
    report = jsonl.read_json(run_dir / "report.json", {}) or {}
    return float(report.get("cost_usd") or 0.0) if isinstance(report, dict) else 0.0


def _bio_exists(name: str, cwd, state_dir) -> bool:
    try:
        from halo_harness.agents_yaml import resolve_agent_bio
        return resolve_agent_bio(name, cwd=cwd, state_dir=state_dir) is not None
    except Exception:
        return False


def ref_problem(ref, state_dir=None) -> str:
    """'' when `ref` resolves, else the reason."""
    if not isinstance(ref, str) or not _REF.match(ref.strip()):
        return f"{ref!r} is not a model ref (<route>:<id>)"
    if ref.startswith(("cc:", "cx:")):
        return f"{ref} is on a route removed in 3.1.5.0"
    try:
        from halo_harness.agents_doctor import missing_model_provider
        provider = missing_model_provider(ref.strip(), catalogs={}, state_dir=state_dir)
    except Exception:
        provider = None
    return f"{ref} is not in the {provider} catalog" if provider else ""


def _note(value):
    text = value.strip() if isinstance(value, str) else ""
    return text if 0 < len(text) <= NOTE_MAX else None


def _names(value, pattern=_TOOL, cap: int = 40):
    if not isinstance(value, list) or not all(isinstance(v, str) and pattern.match(v.strip()) for v in value):
        return None
    return [v.strip() for v in value][:cap]


def _value(key: str, value, where: str, f: dict, dropped: list):
    """The cleaned value of one field, None (with a dropped line) when it does not fit."""
    got, why = None, "does not fit"
    if key == "model":
        why = ref_problem(value, f.get("state_dir"))
        got = None if why else value.strip()
    elif key == "effort":
        got, why = (value if value in EFFORTS else None), f"is one of {', '.join(EFFORTS)}"
    elif key == "prompt_notes":
        got, why = _note(value), f"is a note of 1 to {NOTE_MAX} characters"
    elif key == "max_iterations":
        ok = isinstance(value, int) and not isinstance(value, bool) and 1 <= value <= 500
        got, why = (value if ok else None), "is a whole number from 1 to 500"
    elif key == "tools":
        why = "is {allow: [tool names], deny: [tool names]}"
        if isinstance(value, dict):
            parts = {k: _names(value.get(k)) for k in ("allow", "deny") if k in value}
            got = {k: v for k, v in parts.items() if v is not None} or None
            bad = [k for k in value if k not in ("allow", "deny") or parts.get(k) is None]
            if bad and got is not None:
                dropped.append(f"{where}.{', '.join(map(str, bad))}: tools takes allow and deny, each a list of tool names")
    elif key == "use_for":
        words = _names(value, re.compile(r"^[\w .:/+-]{1,40}$"), WORDS_MAX)
        got, why = (words or None), f"is a list of up to {WORDS_MAX} short words"
    if got is None:
        dropped.append(f"{where}: {why}")
    return got


def _part(raw, keys: tuple, where: str, f: dict, dropped: list) -> dict:
    if not isinstance(raw, dict):
        dropped.append(f"{where}: not an object")
        return {}
    out = {}
    for k, v in raw.items():
        if k not in keys:
            dropped.append(f"{where}.{k}: not a key of this candidate ({', '.join(keys) or 'none here'})")
            continue
        got = _value(k, v, f"{where}.{k}", f, dropped)
        if got is not None:
            out[k] = got
    return out


def _plan(raw, where: str, f: dict, dropped: list) -> list:
    jobs, out = set(f.get("job_ids") or []), []
    for i, row in enumerate(raw if isinstance(raw, list) else [raw]):
        job = str((row or {}).get("job") or "") if isinstance(row, dict) else ""
        after = (row or {}).get("after") if isinstance(row, dict) else None
        if job not in jobs:
            dropped.append(f"{where}[{i}]: {job or '(no job)'} is not a job of the run's plan")
        elif not isinstance(after, list) or not all(isinstance(a, str) and a in jobs and a != job for a in after):
            dropped.append(f"{where}[{i}]: after is a list of the plan's other jobs")
        else:
            out.append({"job": job, "after": list(dict.fromkeys(after))})
    return out


def clean(kind: str, raw, f: dict) -> "tuple[dict, list]":
    """(the candidate's overlay as it may run, [one line per dropped thing])."""
    dropped: list = []
    if kind not in KINDS or not isinstance(raw, dict):
        return {}, [f"{kind}: not an object"]
    out: dict = {}
    for k, v in raw.items():
        where = f"{kind}.{k}"
        if k not in TOP[kind]:
            dropped.append(f"{where}: not a key of a {kind} candidate ({', '.join(TOP[kind])})")
        elif k == "why":
            out["why"] = re.sub(r"\s+", " ", str(v or "")).strip()[:WHY_MAX]
        elif k in ("lead", "workers"):
            part = _part(v, PARTS[kind][k], where, f, dropped)
            if part:
                out[k] = part
        elif k == "bios":
            bios = {}
            for name, b in (v.items() if isinstance(v, dict) else []):
                if name not in f.get("bios", []):
                    dropped.append(f"{where}.{name}: not one of the run's bios ({', '.join(f.get('bios') or []) or 'none'})")
                    continue
                part = _part(b, PARTS[kind]["bio"], f"{where}.{name}", f, dropped)
                if part:
                    bios[name] = part
            if bios:
                out["bios"] = bios
        elif k == "plan":
            rows = _plan(v, where, f, dropped)
            if rows:
                out["plan"] = rows
    return out, dropped


def is_empty(overlay: dict) -> bool:
    return not any(k != "why" and v for k, v in (overlay or {}).items())


def joined(a, b):
    """Two notes both kept (b once); else b wins."""
    if isinstance(a, str) and isinstance(b, str):
        return a if b in a else f"{a}\n{b}"
    return b if b not in (None, "", [], {}) else a


def for_bio(overlay: dict, bio: str) -> dict:
    """What the overlay gives a lane that runs as `bio` ('' = no bio): `workers`, then `bios.<bio>` key by key."""
    out = dict((overlay or {}).get("workers") or {})
    for k, v in (((overlay or {}).get("bios") or {}).get(bio) or {}).items() if bio else ():
        out[k] = joined(out.get(k), v) if k == "prompt_notes" else v
    return out


def merge(a: dict, b: dict) -> dict:
    """Two overlays as one (compose's merge): every part of both, notes joined, b's other fields winning."""
    out: dict = {}
    for k in ("lead", "workers"):
        part = dict((a or {}).get(k) or {})
        for f, v in ((b or {}).get(k) or {}).items():
            part[f] = joined(part.get(f), v) if f == "prompt_notes" else v
        if part:
            out[k] = part
    bios = {name: dict(v) for name, v in ((a or {}).get("bios") or {}).items()}
    for name, v in ((b or {}).get("bios") or {}).items():
        cur = bios.setdefault(name, {})
        for f, x in v.items():
            cur[f] = joined(cur.get(f), x) if f == "prompt_notes" else x
    if bios:
        out["bios"] = bios
    plan = {r["job"]: r for r in ((a or {}).get("plan") or []) + ((b or {}).get("plan") or [])}
    if plan:
        out["plan"] = list(plan.values())
    out["why"] = "; ".join(x for x in ((a or {}).get("why"), (b or {}).get("why")) if x)[:WHY_MAX]
    return out
