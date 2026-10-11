"""halo_harness.tui.widgets.review_cards -- the `/review` result in the
transcript: one `ReviewCard` per finding (file:line, severity, verdict badge,
the short summary, the failure scenario folded) under a one-line header.

`file:line` is a link: clicking it (or pressing `c`) copies the location.
Enter or a click on the summary toggles the folded details; `y` copies the
whole finding.
"""

from __future__ import annotations

from textual.binding import Binding
from textual.markup import escape
from textual.widgets import Static

_VERDICT_MARK = {"CONFIRMED": "confirmed", "PLAUSIBLE": "plausible", "DISMISSED": "dismissed"}


def location_text(finding: dict) -> str:
    file = finding.get("file") or ""
    if not file:
        return "(no file)"
    line = finding.get("line")
    return f"{file}:{line}" if line else file


class ReviewCard(Static, can_focus=True):
    BINDINGS = [
        Binding("enter", "toggle_details", "Details", show=False),
        Binding("c", "copy_location", "Copy location", show=False),
        Binding("y", "copy_card", "Copy", show=False),
    ]

    def __init__(self, finding: dict, index: int) -> None:
        verdict = str(finding.get("verdict") or "PLAUSIBLE")
        severity = str(finding.get("severity") or "medium")
        super().__init__("", markup=True,
                         classes=f"review-card review-sev-{severity} review-verdict-{_VERDICT_MARK.get(verdict, 'plausible')}")
        self.finding = finding
        self.index = index
        self.expanded = False
        self._render_card()

    # ---- rendering ---------------------------------------------------------

    def header_markup(self) -> str:
        f = self.finding
        sev = escape(str(f.get("severity") or "medium").upper())
        badge = escape(str(f.get("verdict") or "PLAUSIBLE"))
        loc = escape(location_text(f))
        cat = escape(str(f.get("category") or ""))
        return f"{self.index}. \\[{sev}] [@click=copy_location]{loc}[/]  {badge}  ({cat})"

    def plain_lines(self) -> "list[str]":
        f = self.finding
        lines = [f"{self.index}. [{str(f.get('severity') or 'medium').upper()}] {location_text(f)}  "
                 f"{f.get('verdict') or 'PLAUSIBLE'}  ({f.get('category') or ''})", f"   {f.get('short_summary') or ''}"]
        summary = (f.get("summary") or "").strip()
        if summary and summary != f.get("short_summary"):
            lines += [f"   {ln}" for ln in summary.splitlines()]
        if f.get("failure_scenario"):
            lines.append(f"   Failure scenario: {f['failure_scenario']}")
        if f.get("reason"):
            lines.append(f"   Judge: {f['reason']}")
        if f.get("outcome"):
            note = f.get("fix_note")
            lines.append(f"   Fix: {f['outcome']}" + (f" -- {note}" if note else ""))
        return lines

    def _render_card(self) -> None:
        f = self.finding
        out = [self.header_markup(), "   " + escape(str(f.get("short_summary") or ""))]
        if f.get("outcome"):
            out.append("   Fix: " + escape(str(f["outcome"])))
        if self.expanded:
            for ln in self.plain_lines()[2:]:
                out.append(escape(ln))
        elif f.get("failure_scenario") or f.get("summary"):
            out.append("   > details folded (enter to unfold)")
        self.update("\n".join(out))

    # ---- actions -----------------------------------------------------------

    def action_toggle_details(self) -> None:
        self.expanded = not self.expanded
        self._render_card()

    def on_click(self, event) -> None:
        # A click on the location link runs its own action; a click elsewhere folds/unfolds.
        if "@click" not in getattr(getattr(event, "style", None), "meta", {}):
            self.action_toggle_details()

    def action_copy_location(self) -> None:
        self.app.perform_copy(location_text(self.finding), label="location")

    def copy_text(self) -> str:
        return "\n".join(self.plain_lines())

    def action_copy_card(self) -> None:
        self.app.perform_copy(self.copy_text(), label="finding")


class ReviewHeader(Static):
    """The one-line summary above the cards."""

    def __init__(self, text: str) -> None:
        super().__init__(text, markup=False, classes="system-note system-note-command review-header")
        self.raw_text = text

    def copy_text(self) -> str:
        return self.raw_text
