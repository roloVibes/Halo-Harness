"""halo_harness.orchestra.coach_ask -- "Ask the model" on a coach card (Halo
3.1.3.0 R1): one paragraph per card, written by the run's own lead.

The lead is the run's lineup lead: an Orchestra run's `lead` role (goal.json,
default `main`) with the model its lineup gives that role (the entry's
`models.preference`, else its bio's), else the role table's model for it,
else the configured default; a flow, mission or team run asks the `main`
role. The call is one turn of a brand-new bare session with no tools
(orchestra/adapters.one_shot, the normal provider layer), given the card,
its why lines and the run's evidence.

The paragraphs are kept beside the cache, in `<run>/coach.ask.json`:

    {"<suggestion id>": {"paragraph": "...", "error": "", "model": "<ref>", "role": "main",
                         "cost_usd": 0.0012, "ts": 1760800000.0}}

A second ask reads the paragraph back without a call; `refresh=True` asks
again. A model error is kept as that card's one `error` line (and asked
again next time), never raised. `HALO_COACH_FAKE=1` answers with a fixed
paragraph and no model (`HALO_COACH_FAKE=error`: a failed call), for tests
and a dry look; tests may also set `ASK` (prompt, model, cwd) -> {text, ok, error}.
"""

from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Callable, Optional

from halo_harness.orchestra import jsonl

STORE = "coach.ask.json"
FAKE_ENV = "HALO_COACH_FAKE"
MAX_CHARS = 1200
ASK: Optional[Callable] = None


def read_store(run_dir) -> dict:
    data = jsonl.read_json(Path(run_dir) / STORE, {})
    return data if isinstance(data, dict) else {}


def _lineup_model(lineup: str, role: str, cwd, state_dir) -> str:
    try:
        from halo_harness import teams_yaml as T
        from halo_harness.orchestra.coach_lane_facts import _bio_model
        raw = T.load_team_template_raw(lineup, cwd=cwd, state_dir=state_dir) or {}
        e = next((e for e in raw.get("agents") or [] if isinstance(e, dict) and role in (e.get("as"), e.get("role"))), {})
        return str((e.get("models") or {}).get("preference") or _bio_model(str(e.get("agent") or ""), cwd, state_dir))
    except Exception:
        return ""


def lead_of(run_dir, kind: str, *, cwd=None, state_dir=None) -> tuple:
    """(role, model ref or '') of the run's lead."""
    from halo_harness.orchestra.adapters import role_model
    goal = (jsonl.read_json(Path(run_dir) / "goal.json", {}) or {}) if kind == "orchestra" else {}
    role = str(goal.get("lead") or "main")
    model = _lineup_model(str(goal["lineup"]), role, cwd, state_dir) if goal.get("lineup") else ""
    return role, model or str(role_model(role) or "")


def prompt_for(s: dict, result: dict) -> str:
    evidence = json.dumps(result.get("evidence") or {}, ensure_ascii=False, default=str)[:4000]
    return (f"You led this {result.get('kind')} run ({result.get('run')}). The post-run coach read the run's files "
            "and wrote the card below. In ONE paragraph of plain prose (no list, no heading, at most 120 words), "
            "explain to the person who owns the run what the evidence shows, why the change the card names would "
            "help the next run, and what to watch after making it.\n\n"
            f"Card: [{s.get('severity')}] {s.get('kind')}: {s.get('text')}\n"
            + "Why:\n" + "".join(f"- {w}\n" for w in s.get("why") or [])
            + (f"Apply: {s['apply'].get('target')} {s['apply'].get('name')}: {s['apply'].get('field')} = "
               f"{s['apply'].get('value')}\n" if s.get("apply") else "Apply: nothing to fill in\n")
            + f"\nThe run's evidence (JSON): {evidence}\n")


def _fake(prompt: str, model: str, cwd) -> dict:
    if os.environ.get(FAKE_ENV, "").strip().lower() == "error":
        return {"text": "", "ok": False, "error": "the fake lead failed (HALO_COACH_FAKE=error)"}
    card = next((ln[6:] for ln in prompt.splitlines() if ln.startswith("Card: ")), "the card")
    return {"text": f"The fake lead on {model or 'the default model'} reads {card} as the run's clearest lesson.",
            "ok": True, "cost_usd": 0.0}


def _caller() -> Callable:
    if ASK is not None:
        return ASK
    if os.environ.get(FAKE_ENV, "").strip().lower() not in ("", "0", "false", "no", "off"):
        return _fake
    from halo_harness.orchestra.adapters import one_shot
    return lambda prompt, model, cwd: one_shot(prompt, model=model or None, cwd=cwd)


def paragraph_of(text: str) -> str:
    first = next((p for p in re.split(r"\n\s*\n", str(text or "").strip()) if p.strip()), "")
    flat = re.sub(r"\s+", " ", first).strip()
    return flat if len(flat) <= MAX_CHARS else flat[:MAX_CHARS - 3].rstrip() + "..."


def ask(run_dir, result: dict, sid: str, *, refresh: bool = False, cwd=None, state_dir=None) -> dict:
    """{id, paragraph, error, model, role, cached} for one card; kept in coach.ask.json."""
    run_dir = Path(run_dir)
    store = read_store(run_dir)
    kept = store.get(sid) or {}
    if kept.get("paragraph") and not refresh:
        return dict(kept, id=sid, cached=True)
    s = next((x for x in result.get("suggestions") or [] if x.get("id") == sid), None)
    if s is None:
        return {"id": sid, "paragraph": "", "error": f"no suggestion {sid!r} on this run's card", "cached": False}
    role, model = lead_of(run_dir, str(result.get("kind")), cwd=cwd, state_dir=state_dir)
    try:
        got = _caller()(prompt_for(s, result), model, cwd or run_dir)
        text, ok = paragraph_of(got.get("text")), bool(got.get("ok", True))
        error = "" if ok and text else str(got.get("error") or "the lead answered with no text").splitlines()[0][:200]
    except Exception as e:  # a provider error is the card's one line
        text, error, got = "", (f"{type(e).__name__}: {e}".splitlines() or ["the call failed"])[0][:200], {}
    row = {"paragraph": text if not error else "", "error": error, "model": model, "role": role,
           "cost_usd": float(got.get("cost_usd") or 0.0), "ts": round(time.time(), 3)}
    store = read_store(run_dir)
    store[sid] = row
    try:
        jsonl.write_json(run_dir / STORE, store)
    except OSError:
        pass
    return dict(row, id=sid, cached=False)


def ask_all(run_dir, result: dict, *, refresh: bool = False, cwd=None, state_dir=None) -> list:
    return [ask(run_dir, result, s["id"], refresh=refresh, cwd=cwd, state_dir=state_dir)
            for s in result.get("suggestions") or []]
