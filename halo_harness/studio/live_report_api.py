"""halo_harness.studio.live_report_api -- the run report card's route (3.4.1.0 R3; 3.6.0.3 B, R-B12: `live/report`).

    GET  live/report?ref=<ref>    the card (live/report_card.py) -> {card, markdown, story_all}; ref: session:<id> |
                                  run:<id> | a bare id; 422 without one, 404 when it names nothing (an old saved file:
                                  404 with the one retired line, 3.6.0.3 B Z13); no model call, nothing written.
                                  story_all: every step of the story (the card keeps about ten), for the card's page
                                  (3.6.0.3 B, Z10)

Studio's report card (crew/live/cardData.ts) reads it here. Registered with the other `live/*` routes (studio/live_api.py).
"""

from __future__ import annotations


def get_report(req):
    from halo_harness.live import report_card
    from halo_harness.live.card_data import CompareError
    from halo_harness.live.report_card_text import markdown
    ref = str(req.query.get("ref") or "").strip()
    if not ref:
        return 422, {"error": "name the run: ?ref=session:<id> | run:<id>", "problems": []}
    try:
        p = report_card.resolve(req.state_dir, ref, cwd=req.cwd)
    except CompareError as e:  # report_card.OldFile too: its message is the one retired line (Z13)
        return 404, {"error": str(e)}
    c = report_card.card(p, ref)
    return 200, {"card": c, "markdown": markdown(c), "story_all": report_card.story_all(p)}


ROUTES = [("GET", r"^live/report$", get_report)]
