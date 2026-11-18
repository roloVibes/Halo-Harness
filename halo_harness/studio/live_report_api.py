"""halo_harness.studio.live_report_api -- the run report card's route (3.4.1.0 R3; 3.6.0.3 B, R-B12: `live/report`).

    GET  live/report?ref=<ref>    the card (live/report_card.py) -> {card, markdown}; ref: session:<id> | run:<id> |
                                  file:<id>; 422 without one, 404 when it names nothing; no model call, nothing written

Studio's report card (crew/live/cardData.ts) reads it here. Registered with the other `live/*` routes (studio/live_api.py);
`replays/report` points at this same handler until the replay routes leave.
"""

from __future__ import annotations


def get_report(req):
    from halo_harness.live import report_card
    from halo_harness.live.card_data import CompareError
    from halo_harness.live.report_card_text import markdown
    ref = str(req.query.get("ref") or "").strip()
    if not ref:
        return 422, {"error": "name the run: ?ref=session:<id> | run:<id> | file:<id>", "problems": []}
    try:
        p, from_file = report_card.resolve(req.state_dir, ref, cwd=req.cwd)
    except CompareError as e:
        return 404, {"error": str(e)}
    c = report_card.card(p, ref, from_file)
    return 200, {"card": c, "markdown": markdown(c)}


ROUTES = [("GET", r"^live/report$", get_report)]
