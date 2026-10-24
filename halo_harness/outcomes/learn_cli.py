"""halo_harness.outcomes.learn_cli -- see and reset what Auto learned (Halo
3.1.9.0 R3, docs/OUTCOMES.md "What was learned", docs/COMMANDS-supervise.md).

    halo outcomes learned [--kind K] [--model REF] [--json]
        per model and task kind, over the window (models.learn.window_days): the checked tasks, the
        first-time passes and the rate, the auto pick's weight, how many were the model's own pick,
        and whether it is dropped for the kind (outcomes/learn.py)
    halo outcomes forget [--model REF] [--kind K] [--before DATE] [--yes]
        remove the matching rows from outcomes.jsonl (every row when nothing narrows it), the file
        before kept beside it as outcomes.jsonl.bak-<time>; the best-at cache rebuilds on its next read
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
from typing import Optional

KINDS_HELP = "code, research, check, writing, plan, review, media, other"


def _home():
    from halo_harness.config.paths import bridge_home
    return bridge_home()


def table(rows: list, cfg: dict) -> list:
    from halo_harness.outcomes.learn import window_words
    state = "on" if cfg["enabled"] else "off (models.learn: false -- the pick and the roster ignore these numbers)"
    head = (f"Learning {state}; {window_words(cfg)}; weighed from {cfg['min_tasks']} checked tasks "
            f"(weight 0.5 + 0.5 x rate); dropped below {cfg['drop_below'] * 100:.0f}%.")
    if not rows:
        return [head, "Nothing learned yet: every checked agent task (an Orchestra lane, a sub-agent with an "
                      "acceptance) adds a row to outcomes.jsonl; `halo outcomes` lists them."]
    out = [head, f"{'model':<44} {'kind':<9} {'n':>3}  {'passed':>6}  {'rate':>5}  {'weight':>6}  {'picks':>5}  dropped"]
    for r in rows:
        mark = (f"dropped for {r['kind']}" if r["dropped"] else
                "" if r["counted"] else f"(fewer than {cfg['min_tasks']}: not weighed)")
        out.append(f"{r['model']:<44} {r['kind']:<9} {r['n']:>3}  {r['passed']:>3}/{r['n']:<2}  {r['rate'] * 100:>4.0f}%  "
                   f"{r['weight']:>6.3f}  {r['picked']:>2}/{r['n']:<2}  {mark}".rstrip())
    out.append("picks = tasks whose model was picked at spawn (auto / measured); `halo outcomes forget --model REF` "
               "starts a model over, `halo config set models.learn false` turns learning off")
    return out


def cmd_learned(argv) -> int:
    parser = argparse.ArgumentParser(prog="halo outcomes learned",
                                     description="What the auto pick learned per model and task kind (outcomes.jsonl)")
    parser.add_argument("--kind", default="", help=f"Only this kind: {KINDS_HELP}")
    parser.add_argument("--model", default="", help="Only this model ref")
    parser.add_argument("--json", action="store_true", help="The settings and the rows as JSON")
    args = parser.parse_args(argv)
    from halo_harness.outcomes.learn import learned_rows, numbers, settings, since
    cfg = settings()
    rows = [r for r in learned_rows(numbers(_home(), cfg), cfg)
            if (not args.kind or r["kind"] == args.kind) and (not args.model or r["model"] == args.model)]
    if args.json:
        print(json.dumps({"learn": cfg, "since": since(cfg), "rows": rows}, indent=1, ensure_ascii=False))
        return 0
    print("\n".join(table(rows, cfg)))
    return 0


def _matches(row: dict, model: str, kind: str, before: Optional[float]) -> bool:
    return ((not model or row.get("model") == model) and (not kind or row.get("kind") == kind)
            and (before is None or float(row.get("ts") or 0) < before))


def _backup_path(target):
    stamp = time.strftime("%Y%m%d-%H%M%S")
    path, n = target.with_name(f"{target.name}.bak-{stamp}"), 1
    while path.exists():
        n += 1
        path = target.with_name(f"{target.name}.bak-{stamp}-{n}")
    return path


def forget(state_dir, *, model: str = "", kind: str = "", before: Optional[float] = None,
           dry_run: bool = False) -> dict:
    """Remove the outcome rows matching every filter given (all rows with none); the lines that are not
    rows, and the rows that do not match, stay as they were. `{matched, kept, backup}` (`backup`: the
    file before, beside it; None when nothing was removed)."""
    from halo_harness.models_best_at import invalidate
    from halo_harness.orchestra import jsonl
    from halo_harness.outcomes.records import WORDS, path
    target = path(state_dir)
    if not target.exists():
        return {"matched": 0, "kept": 0, "backup": None}
    with jsonl.locked(target):
        keep, matched = [], 0
        for raw in target.read_text(encoding="utf-8").splitlines():
            try:
                row = json.loads(raw) if raw.strip() else None
            except ValueError:
                row = None
            if isinstance(row, dict) and row.get("outcome") in WORDS and _matches(row, model, kind, before):
                matched += 1
            elif raw.strip():
                keep.append(raw + "\n")
        if not matched or dry_run:
            return {"matched": matched, "kept": len(keep), "backup": None}
        backup = _backup_path(target)
        shutil.copy2(target, backup)
        tmp = target.with_name(f".{target.name}.{os.getpid()}.tmp")
        with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
            fh.write("".join(keep))
        os.replace(tmp, target)
    invalidate(state_dir)
    return {"matched": matched, "kept": len(keep), "backup": backup}


def _what(model: str, kind: str, before_text: str) -> str:
    parts = [f"model {model}" if model else "", f"kind {kind}" if kind else "",
             f"before {before_text}" if before_text else ""]
    return ", ".join(p for p in parts if p) or "every row"


def cmd_forget(argv) -> int:
    parser = argparse.ArgumentParser(prog="halo outcomes forget",
                                     description="Remove outcome rows so the auto pick starts over for them")
    parser.add_argument("--model", default="", help="Only this model ref's rows")
    parser.add_argument("--kind", default="", help=f"Only this kind's rows: {KINDS_HELP}")
    parser.add_argument("--before", default="", help="Only rows older than: 7d, 24h, 30m, 2026-10-20 or an epoch")
    parser.add_argument("--yes", action="store_true", help="Remove them without asking (a backup is kept beside the file)")
    args = parser.parse_args(argv)
    from halo_harness.outcomes.records import since_ts
    before = None
    if args.before:
        before = since_ts(args.before)
        if before is None:
            print(f"halo outcomes forget: --before {args.before!r} does not read: give 7d, 24h, 30m, 2026-10-20 or an epoch")
            return 2
    what = _what(args.model, args.kind, args.before)
    home = _home()
    found = forget(home, model=args.model, kind=args.kind, before=before, dry_run=True)
    if not found["matched"]:
        print(f"No outcome row matches ({what}); nothing removed.")
        return 0
    if not args.yes:
        if not sys.stdin.isatty():
            print(f"{found['matched']} outcome row(s) match ({what}); nothing removed yet: add --yes to remove them "
                  "(a backup is kept beside the file).")
            return 1
        answer = input(f"Remove {found['matched']} outcome row(s) ({what})? A backup is kept beside the file. [y/N] ")
        if answer.strip().lower() not in ("y", "yes"):
            print("Nothing removed.")
            return 1
    done = forget(home, model=args.model, kind=args.kind, before=before)
    print(f"Removed {done['matched']} outcome row(s) ({what}), {done['kept']} kept; the file before is "
          f"{done['backup']} (the best-at cache rebuilds on its next read).")
    return 0
