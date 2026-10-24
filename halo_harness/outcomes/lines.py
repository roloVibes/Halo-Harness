"""halo_harness.outcomes.lines -- an Evidence as the short lines a person (and the
judge) reads (Halo 3.1.8.0 R3). Never the agent's own summary. A kind's own
item always has its line (code: tests, research: sources, check:
reproduction, writing: written), "none" included; any other item only when
the transcript has one.

    tests: `python -m pytest -q` exit 0, 12 passed
    tests: `npm test` exit 1, 3 passed, failing: test_total (test_basket.TestBasket)
    tests: none run
    sources: 3 -- fetch https://docs.python.org/3/library/decimal.html; read docs/ORCHESTRA.md; search decimal rounding
    sources: none fetched or read
    reproduction: `curl -sI localhost:8080` exit 0 -- HTTP/1.1 200 OK
    written: basket.py (+5 -1)
    acceptance: 'non-empty' met
    no transcript was found: nothing to read
"""

from __future__ import annotations

from halo_harness.outcomes.evidence import Evidence

CMD_CAP, TARGET_CAP, SHOWN = 90, 80, 3


def _cut(text, cap: int) -> str:
    text = " ".join(str(text or "").split())
    return text if len(text) <= cap else text[:cap - 3] + "..."


def test_line(t: dict) -> str:
    bits = [f"`{_cut(t.get('command'), CMD_CAP)}` exit {'?' if t.get('exit') is None else t.get('exit')}"]
    if isinstance(t.get("passed"), int):
        bits.append(f"{t['passed']} passed")
    failed = t.get("failed") or []
    if failed:
        bits.append("failing: " + ", ".join(str(f) for f in failed[:SHOWN]) + (f" (+{len(failed) - SHOWN})" if len(failed) > SHOWN else ""))
    return ", ".join(bits)


def lines(ev, *, kinds=("tests", "sources", "reproduction", "written", "acceptance")) -> list:
    """The evidence lines of `ev` (an Evidence or its dict), in the order of `kinds`."""
    ev = ev if isinstance(ev, Evidence) else Evidence.from_dict(ev)
    if not ev.transcript:
        return ["no transcript was found: nothing to read"]
    out = []
    for what in kinds:  # a kind's own item always shows (its "none" too); another kind's only when found
        if what == "tests" and (ev.tests or ev.kind == "code"):
            out.append("tests: " + ("; ".join(test_line(t) for t in ev.tests[-SHOWN:]) if ev.tests else "none run"))
        elif what == "sources" and (ev.sources or ev.kind == "research"):
            shown = "; ".join(f"{s.get('kind')} {_cut(s.get('target'), TARGET_CAP)}" for s in ev.sources[:SHOWN])
            more = f" (+{len(ev.sources) - SHOWN})" if len(ev.sources) > SHOWN else ""
            out.append(f"sources: {len(ev.sources)} -- {shown}{more}" if ev.sources else "sources: none fetched or read")
        elif what == "reproduction" and (ev.reproduction or ev.kind == "check"):
            if not ev.reproduction:
                out.append("reproduction: no command run")
                continue
            r = ev.reproduction[-1]
            last = (str(r.get("tail") or "").strip().splitlines() or [""])[-1]
            out.append(f"reproduction: `{_cut(r.get('command'), CMD_CAP)}` exit {'?' if r.get('exit') is None else r['exit']}"
                       + (f" -- {_cut(last, TARGET_CAP)}" if last else "")
                       + (f" (+{len(ev.reproduction) - 1} more)" if len(ev.reproduction) > 1 else ""))
        elif what == "written" and (ev.written or ev.kind == "writing"):
            if not ev.written:
                out.append("written: no file")
                continue
            d = ev.diff or {}
            stat = f" (+{d.get('added', 0)} -{d.get('removed', 0)})" if d.get("added") or d.get("removed") else ""
            names = ", ".join(_cut(p, TARGET_CAP) for p in ev.written[:SHOWN])
            out.append(f"written: {names}{stat}" + (f" (+{len(ev.written) - SHOWN} files)" if len(ev.written) > SHOWN else ""))
        elif what == "acceptance" and ev.acceptance:
            a = ev.acceptance
            out.append(f"acceptance: {a.get('expect')!r} {'met' if a.get('met') else 'not met'}"
                       + (f" -- {_cut(a.get('why'), TARGET_CAP)}" if a.get("why") and not a.get("met") else ""))
    return out


def judge_lines(ev) -> list:
    """What the judge reads of a lane: its tests, sources and reproductions."""
    return lines(ev, kinds=("tests", "sources", "reproduction"))
