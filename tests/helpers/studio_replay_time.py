"""tests.helpers.studio_replay_time -- the page helpers of Studio's browser checks (Halo 3.4.1.0 R1 "Time"), kept when
the scrubber, Save, Export a clip and History left Studio (3.6.0.3 B, L-B6): its own History and replay steps went with
them; tests/helpers/studio_report_card.py imports Q, QA and open_page from here.
"""
from __future__ import annotations

Q = "document.querySelector"
QA = "document.querySelectorAll"


def open_page(c, page, query: str) -> None:
    c.go("about:blank")  # a navigation to the same address with a #t= fragment is a fragment hop
    c.go(page(query))
    c.wait(f"{QA}('[data-testid=\"section-tab\"]').length > 0 && !!{Q}('.section-view')", 40)
