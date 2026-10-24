"""halo_harness.studio.session_open -- Studio on a section, the Session
dashboard first (Halo 3.1.4.0 R2, "The session dashboard").

A section target names the Studio section to open, and for Session the
session to watch:

    SectionTarget("session", "<sid>")   Session, that session chosen (the map
                                        and the agent panel follow it)
    SectionTarget("fleet")              Fleet (or any section of STUDIO_MODES)

It goes through the same opener as an edit target (studio/edit_open.py
`open_edit`: the Studio already running for this home is focused, else one
starts) and rides the page URL as `?mode=session&session=<sid>` (the token
stays in the fragment); a page already open gets it as a `focus` frame
`{edit: "", mode, session}` (studio/focus_api.py, ui/src/shell/edit.ts).

`live_sessions()` is this harness's registry (`~/.halo/run/sessions.json`,
never a private session), oldest first. `boot_html(page)` marks the served
page with the newest one's id, `<html data-live-session="<sid>">` ('' when
none), so the page can land on Session before its stores load
(ui/src/lib/store.ts `initialSection`); 3.2.1.0 R1: and, when a pack with
Studio sections runs, `data-pack-sections` (`[{id, pack, title}]`, JSON) so
a saved pack section is the first paint (its frame says "loading the
pack's section" until `GET pack/registry` answers). `cli_target` is `halo studio
--session [<id>]`, `section_target` the TUI's `/studio [<section>]`.
"""

from __future__ import annotations

import html
import json
import re
from dataclasses import dataclass
from typing import Optional
from urllib.parse import quote

BOOT_ATTR = "data-live-session"
PACK_ATTR = "data-pack-sections"  # 3.2.1.0 R1: the running packs' own sections, read by ui/src/lib/store.ts
_SID_RE = re.compile(r"[A-Za-z0-9_.:-]{1,128}")


@dataclass(frozen=True)
class SectionTarget:
    mode: str
    session: str = ""
    name: str = ""  # how the one-line outcome names it ("this session"); default below

    @property
    def text(self) -> str:
        """What `url_for` / `existing_url` / `launch_detached` carry as `edit`: the session id, '' for a section."""
        return self.session if self.mode == "session" else ""

    @property
    def display(self) -> str:
        if self.name:
            return self.name
        if self.mode != "session":
            return self.mode.capitalize()
        return f"session {self.session[:8]}" if self.session else "Session"

    @property
    def verb(self) -> str:
        return "watch" if self.mode == "session" else "open"

    @property
    def cli(self) -> str:
        if self.mode == "session":
            return "halo studio --session" + (f" {self.session}" if self.session else "")
        return f"halo studio --mode {self.mode}"

    def query(self) -> str:
        if self.mode == "session" and self.session:
            return f"?mode=session&session={quote(self.session, safe='')}"
        return f"?mode={self.mode}"

    def focus(self) -> dict:
        """The `focus` frame's data, and POST /api/focus's body."""
        return {"edit": "", "mode": self.mode, "session": self.text}


def valid_session_id(sid: str) -> bool:
    return bool(_SID_RE.fullmatch(sid or ""))


def live_sessions() -> list:
    """This harness's live sessions (the registry, no private one), oldest first."""
    try:
        from halo_harness.remote import registry
        rows = [r for r in registry.list_live() if isinstance(r, dict) and r.get("session_id") and not r.get("private")]
    except Exception:
        return []
    return sorted(rows, key=lambda r: (float(r.get("started") or 0), str(r.get("session_id"))))


def newest_live() -> str:
    rows = live_sessions()
    return str(rows[-1]["session_id"]) if rows else ""


def pack_sections_attr(cwd=None, state_dir=None) -> str:
    """3.2.1.0 R1: ` data-pack-sections="[{id, pack, title}, ...]"` (JSON) for the running packs' own sections,
    '' when none runs (or the packs cannot be read): the page keeps a saved pack section as its first paint."""
    try:
        from halo_harness.packs.studio_registry import section_heads
        heads = section_heads(cwd=cwd, state_dir=state_dir)
    except Exception:  # a pack that cannot be read never stops the page
        heads = []
    if not heads:
        return ""
    return f' {PACK_ATTR}="{html.escape(json.dumps(heads, separators=(",", ":")), quote=True)}"'


def boot_html(page: bytes, sid: Optional[str] = None, *, cwd=None, state_dir=None) -> bytes:
    """The shell's index.html with `data-live-session` on its <html> tag (and, given `state_dir`,
    `data-pack-sections`: 3.2.1.0 R1)."""
    sid = newest_live() if sid is None else sid
    text = f' {BOOT_ATTR}="{html.escape(sid or "", quote=True)}"'
    if state_dir is not None:
        text += pack_sections_attr(cwd, state_dir)
    attr = text.encode("utf-8")
    return page.replace(b"<html", b"<html" + attr, 1) if b"<html" in page else page


def cli_target(asked: str) -> "tuple[SectionTarget, str]":
    """`halo studio --session [<id>]`: the target and a note ('' or what Studio shows instead).
    `<id>` may be a prefix of a live session's id; omitted, the newest live one."""
    asked = (asked or "").strip()
    live = [str(r["session_id"]) for r in live_sessions()]
    if asked:
        hits = [s for s in live if s == asked] or [s for s in live if s.startswith(asked)]
        if len(hits) == 1:
            return SectionTarget("session", hits[0]), ""
        why = "matches several live sessions" if hits else "is not live on this harness"
        return (SectionTarget("session", asked),
                f"session {asked} {why}: Studio opens Session with it chosen; it shows the moment it registers.")
    if not live:
        return (SectionTarget("session"),
                "no session is live on this harness: Studio opens Session on its Start view (start one with `halo`).")
    return SectionTarget("session", live[-1]), ""


def section_target(word: str, session_id: str = "") -> "tuple[Optional[SectionTarget], str]":
    """The TUI's `/studio [<section>]`: bare (or `session`) is this session, else that section."""
    from halo_harness.studio.server import STUDIO_MODES
    w = (word or "").strip().lower()
    if not w or w == "session":
        sid = session_id if valid_session_id(session_id) else ""
        return SectionTarget("session", sid, "this session" if sid else ""), ""
    if w in STUDIO_MODES:
        return SectionTarget(w), ""
    return None, f"/studio opens this session, or a section: {', '.join(STUDIO_MODES)} (got {word!r})"
