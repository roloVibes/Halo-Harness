"""halo_harness.remote.signal_calls -- the signal-cli methods the bridge
calls (Halo 2.0.9 round 3), as a mixin over `SignalTransport.request`:
`send` (text, styles, `data:` attachment, Note to Self), `send_typing`,
`send_receipt`, `list_identities`/`safety_number`, `trust`,
`submit_captcha`, and `take_attachments` (inbound `text/x-signal-plain`
becomes the prompt; every downloaded file is deleted)."""

from __future__ import annotations

import re
from typing import Optional

from halo_harness.remote import signal_errors as E

TEXT_ATTACHMENT = "text/x-signal-plain"
MAX_TEXT_ATTACHMENT = 512 * 1024
_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


class SignalCalls:
    """Needs `request`, `rate_limited`, `linked`, `own_aci`, `paused_until`,
    `captcha_token` and `data_dir` from the class it is mixed into."""

    # ---- the calls the bridge makes -------------------------------------------
    def send(self, recipient: str, text: str = "", *, attachment: Optional[str] = None,
             styles: Optional[list] = None, note_to_self: Optional[bool] = None):
        if self.rate_limited() > 0:
            raise E.RateLimited("sending is paused after a rate limit", retry_after=self.rate_limited(),
                                token=self.captcha_token)
        params: dict = {"message": text}
        if note_to_self if note_to_self is not None else (self.linked and recipient == self.own_aci):
            params["noteToSelf"] = True
        else:
            params["recipient"] = [recipient]
        if attachment:
            params["attachment"] = [attachment]
        if styles:
            params["textStyle"] = list(styles)
        return self.request("send", params)

    def send_typing(self, recipient: str, stop: bool = False):
        if self.linked and recipient == self.own_aci:
            return None
        params: dict = {"recipient": [recipient]}
        if stop:
            params["stop"] = True
        return self.request("sendTyping", params)

    def send_receipt(self, recipient: str, timestamp: int, kind: str = "read"):
        if self.linked and recipient == self.own_aci:
            return None
        return self.request("sendReceipt", {"recipient": recipient, "targetTimestamp": [int(timestamp)], "type": kind})

    def list_identities(self, recipient: Optional[str] = None) -> list:
        res = self.request("listIdentities", {"number": recipient} if recipient else {})
        return [r for r in res if isinstance(r, dict)] if isinstance(res, list) else []

    def safety_number(self, aci: str) -> Optional[str]:
        """The 60-digit safety number signal-cli holds for `aci` (the newest key)."""
        rows = [r for r in self.list_identities(aci) if r.get("uuid") == aci or r.get("number") == aci]
        rows.sort(key=lambda r: r.get("addedTimestamp") or 0)
        return rows[-1].get("safetyNumber") if rows else None

    def trust(self, recipient: str, safety_number: str):
        return self.request("trust", {"recipient": recipient, "verifiedSafetyNumber": safety_number})

    def submit_captcha(self, token: str, captcha: str):
        res = self.request("submitRateLimitChallenge", {"challenge": token, "captcha": captcha})
        self.paused_until, self.captcha_token = 0.0, ""
        return res

    # ---- attachments ---------------------------------------------------------------
    def take_attachments(self, attachments, want_text: bool) -> Optional[str]:
        """Read the first `text/x-signal-plain` attachment's text (when `want_text`;
        every other type is ignored) and delete every downloaded file from
        signal-cli's data directory. Returns the text or None."""
        text = None
        for att in attachments if isinstance(attachments, list) else []:
            if not isinstance(att, dict) or not _SAFE_ID.match(str(att.get("id") or "")):
                continue
            path = self.data_dir / "attachments" / str(att["id"])
            try:
                if want_text and text is None and att.get("contentType") == TEXT_ATTACHMENT:
                    with open(path, "rb") as f:
                        text = f.read(MAX_TEXT_ATTACHMENT).decode("utf-8", "replace")
            except OSError:
                pass
            try:
                path.unlink()
            except OSError:
                pass
        return text
