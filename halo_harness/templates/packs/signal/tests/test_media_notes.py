"""tests.test_media_notes -- both directions carry more than text, and the phone sees the harness on request
(3.3.13.0 R3): a voice note through a stub transcriber, a picture as the turn's image, a PDF named by its path,
`/file`, `/shot`, `/notify`, a supervisor note reaching the phones that asked for it (and not the others), an `asks`
note about the attached session skipped, `/live`, `/cost`. Run: python -m tests.test_media_notes"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from tests.support import ACI_A, main, registry, wait_for
from tests.rig import Phone

test, TESTS = registry()


def _att(p, att_id: str, ctype: str, data: bytes, filename: str = None) -> dict:
    p.tr.files[att_id] = (data, ctype)
    return {"id": att_id, "contentType": ctype, "filename": filename, "size": len(data)}


@test
def test_a_voice_note(ctx):
    with Phone() as p:
        p.pair()
        p.text(None, attachments=[_att(p, "v1", "audio/aac", b"\x00\x01", "note.m4a")])
        ctx.check("the transcriber heard it", wait_for(lambda: p.heard, 3.0))
        ctx.check("the session got it with (voice note) in front",
                  wait_for(lambda: p.session() and p.session().submitted
                           and p.session().submitted[0]["text"] == "(voice note) make it blue", 4.0))
        ctx.check("the audio file is gone after", not Path(p.heard[0]).exists())


@test
def test_a_voice_note_with_no_speech_server(ctx):
    with Phone(transcribe=lambda path: (None, "no local speech server runs here: `halo local serve --stt`")) as p:
        p.pair()
        p.text(None, attachments=[_att(p, "v2", "audio/aac", b"\x00\x01")])
        ctx.check("one line says how to turn transcription on", p.wait("halo local serve --stt"))
        ctx.check("no session was started for nothing", not p.sessions.started)


@test
def test_a_picture_and_a_pdf(ctx):
    with Phone() as p:
        p.pair()
        png = b"\x89PNG\r\n\x1a\n" + b"0" * 20
        p.text("what is this?", attachments=[_att(p, "i1", "image/png", png, "shot.png"),
                                              _att(p, "d1", "application/pdf", b"%PDF-1.4", "spec.pdf")])
        ok = wait_for(lambda: p.session() and p.session().submitted, 4.0)
        sub = p.session().submitted[0] if ok else {}
        ctx.check("the picture rides with the prompt", sub.get("image", {}).get("media_type") == "image/png")
        ctx.check("the PDF is named by its path in the inbox", "spec.pdf" in sub.get("text", "")
                  and "inbox" in sub.get("text", ""))


@test
def test_file_and_shot(ctx):
    folder = tempfile.mkdtemp(prefix="signal-files-")
    Path(folder, "out.txt").write_text("result", encoding="utf-8")
    with Phone(capture=lambda sid: (os.path.join(folder, "out.txt"), "")) as p:
        p.pair()
        p.text(f"/cd {folder}")
        p.text("hello")
        p.wait("hello from the fake session")
        p.text("/file out.txt")
        ctx.check("/file sends the file", wait_for(lambda: any(str(s.get("attachment") or "").endswith("out.txt")
                                                                for s in p.tr.sent), 3.0))
        p.text("/file ../../etc/passwd")
        ctx.check("a path outside the session's folder is refused", p.wait("outside the session's folder"))
        p.text("/shot")
        ctx.check("/shot sends the capture", p.wait("Studio, now:"))


@test
def test_notify_and_notes(ctx):
    from tests.support import ACI_B, NUM_B
    with Phone() as p:
        p.pair()
        p.pair(ACI_B, NUM_B)
        p.text("/notify off supervisor", ACI_B, NUM_B)
        ctx.check("the phone's choice is said", p.wait("supervisor off", aci=ACI_B))
        from halo_signal.notes import Notes
        n = Notes(p.b, read=lambda cur: ([], cur), listen=lambda name: None)
        sent = n.deliver({"kind": "supervisor", "text": "Goal g-1 done: tidy the docs, $0.12"})
        ctx.check("the supervisor's note reaches only the phone that wants it", sent == 1
                  and p.wait("Goal g-1 done") and "Goal g-1" not in p.joined(ACI_B))
        p.text("/notify on steward", ACI_B, NUM_B)
        ctx.check("on adds a kind", p.wait("steward on", aci=ACI_B))


@test
def test_an_asks_note_about_the_attached_session_is_skipped(ctx):
    with Phone() as p:
        p.pair()
        p.text("hello")
        p.wait("hello from the fake session")
        from halo_signal.notes import Notes
        n = Notes(p.b, read=lambda cur: ([], cur), listen=lambda name: None)
        ctx.check("the attached session's card is not sent twice",
                  n.deliver({"kind": "asks", "text": "[pc] Permission", "session": p.session().sid}) == 0)
        ctx.check("another session's card is sent", n.deliver({"kind": "asks", "text": "[pc] Other", "session": "x"}) == 1)


@test
def test_live_status_cost(ctx):
    with Phone() as p:
        p.pair()
        p.text("/live")
        ctx.check("/live answers", p.wait("Waiting on you: 0"))
        p.text("/status")
        ctx.check("/status with no session says where a text starts one", p.wait("A text starts one in"))
        p.text("hello")
        p.wait("hello from the fake session")
        p.text("/cost")
        ctx.check("/cost says the spend", p.wait("This session so far: $0.0123"))


@test
def test_a_status_line_after_silence(ctx):
    from tests.support import FakeClock
    clock = FakeClock()
    with Phone(clock=clock) as p:
        p.pair()
        p.text("please ask first")
        p.wait("echo hi")
        rt = p.b.rts[ACI_A]
        rt.relay.tool("Bash", {"command": "make"})
        clock.advance(25)
        ctx.check("one status line after 20 s of silence", p.wait("still working: ran 1 command"))


if __name__ == "__main__":
    raise SystemExit(main(TESTS))
