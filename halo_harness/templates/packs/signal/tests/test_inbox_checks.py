"""tests.test_inbox_checks -- a phone's files land only after the checks (Halo 3.3.14.0 R2, plans/REVIEW-2026-11.md #20,
REMOTE-3): a signed phone's unsigned message with a PDF is refused and inbox/ stays empty (the file is deleted, as
signal-cli's copy), a slash command's file is not kept and the phone is told once, a good message's file lands, and a
running bridge clears inbox/ files past a day on its tick. Run: python -m tests.test_inbox_checks"""

from __future__ import annotations

import os
import time
from pathlib import Path

from tests.rig import Phone
from tests.support import ACI_A, main, registry, wait_for

test, TESTS = registry()


def _att(p, att_id: str, ctype: str, data: bytes, filename: str) -> dict:
    p.tr.files[att_id] = (data, ctype)
    return {"id": att_id, "contentType": ctype, "filename": filename, "size": len(data)}


def _inbox(p) -> list:
    d = Path(p.b.inbox_dir)
    return sorted(x.name for x in d.iterdir()) if d.is_dir() else []


@test
def test_a_refused_message_keeps_no_file(ctx):
    with Phone() as p:
        p.pair()
        p.b.pairing.set_signed(ACI_A, True)
        p.text("read this", attachments=[_att(p, "d1", "application/pdf", b"%PDF-1.4", "spec.pdf")])
        ctx.check("the unsigned message is refused", p.wait("set to signed messages"))
        ctx.check(f"inbox/ stays empty, got {_inbox(p)}", _inbox(p) == [])


@test
def test_a_commands_file_is_not_kept(ctx):
    with Phone() as p:
        p.pair()
        p.text("/help", attachments=[_att(p, "d2", "application/pdf", b"%PDF-1.4", "spec.pdf")])
        ctx.check("the phone is told once", p.wait("A file sent with a /command is not kept"))
        ctx.check(f"and the file is gone, got {_inbox(p)}", wait_for(lambda: _inbox(p) == [], 3.0))
        ctx.check("said once", p.joined().count("is not kept") == 1)


@test
def test_a_good_message_lands_and_the_tick_sweeps(ctx):
    with Phone() as p:
        p.pair()
        p.text("what is this?", attachments=[_att(p, "d3", "application/pdf", b"%PDF-1.4", "spec.pdf")])
        ctx.check("the file lands in inbox/", wait_for(lambda: any("spec.pdf" in n for n in _inbox(p)), 4.0))
        old = Path(p.b.inbox_dir) / "old-note.pdf"
        old.write_bytes(b"%PDF-1.4")
        os.utime(old, (time.time() - 2 * 86400, time.time() - 2 * 86400))
        p.b._sweep_at = 0.0  # the hour is up
        ctx.check("the running bridge clears a file past a day", wait_for(lambda: not old.exists(), 3.0))
        ctx.check("and keeps today's", any("spec.pdf" in n for n in _inbox(p)))


if __name__ == "__main__":
    raise SystemExit(main(TESTS))
