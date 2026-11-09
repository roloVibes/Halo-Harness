"""tests.test_conversation -- the signal pack's conversation (3.3.13.0 R3), over the stub transport and the fake
sessions: pairing in one message (signing off), a text with no session starting one in the phone's home folder, the
answer paragraph by paragraph (a code block whole, nothing cut mid-sentence), no "Done." after a plain answer and a
closing line after real work, reply.txt past four messages, the attachment kept across a restart, a stranger never
answered. Run: python -m tests.test_conversation (from the pack's folder)."""

from __future__ import annotations

from tests.support import ACI_B, NUM_B, data_message, main, now_ms, registry, wait_for
from tests.rig import Phone

test, TESTS = registry()


@test
def test_pairing_in_one_message(ctx):
    with Phone() as p:
        p.pair()
        peer = p.b.pairing.peer("00000000-0000-4000-8000-000000000001") or {}
        ctx.check("the phone is paired with signing off", peer and peer.get("signed") is False)
        ctx.check("its key was trusted while the phrase was open", p.tr.trusts and p.tr.trusts[0][0] == peer.get("aci"))
        ctx.check("the invite says paired, with the number masked", p.b.pairing.invite_state()["state"] == "paired"
                  and "0100" in str(p.b.pairing.invite_state()["paired"]))
        ctx.check("no phrase is kept in the clear", "phrase" not in str(p.b.pairing.invite_state()))


@test
def test_a_stranger_is_never_answered(ctx):
    with Phone() as p:
        p.text("hello there", ACI_B, NUM_B)
        wait_for(lambda: p.b.pairing.notices(), 2.0)
        ctx.check("nothing went back to the stranger", not p.texts(ACI_B))
        ctx.check("the computer has one notice", any(n["kind"] == "stranger" for n in p.b.pairing.notices()))


@test
def test_a_text_with_no_session_starts_one(ctx):
    with Phone() as p:
        p.pair()
        p.text("hello")
        ctx.check("it says where and on what first", p.wait("Starting a session in "))
        ctx.check("a session was started for the phone", wait_for(lambda: p.sessions.started, 3.0))
        ctx.check("the text reached it once attached", wait_for(lambda: p.session() and p.session().submitted, 3.0))
        ctx.check("the answer comes back", p.wait("hello from the fake session"))
        ctx.check("the submit says it came from this phone", p.session().submitted[0]["origin"]["via"] == "signal")
        wait_for(lambda: False, 0.3)
        ctx.check(f"no Done. line after a plain answer: {p.texts()}", not any(t.startswith("Done") for t in p.texts()))


@test
def test_the_answer_paragraph_by_paragraph(ctx):
    with Phone() as p:
        p.pair()
        p.text("paragraphs please")
        ctx.check("the last paragraph arrives", p.wait("The last paragraph ends it."))
        texts = [t for t in p.texts() if not t.startswith(("Paired", "Starting"))]
        ctx.check(f"four messages in order, got {texts}", texts[:4] and texts[0].startswith("The first paragraph")
                  and texts[0].endswith("a little.") and texts[1] == "The second one is short."
                  and "print('code stays together')\nprint(2)" in texts[2] and texts[3] == "The last paragraph ends it.")


@test
def test_real_work_gets_a_closing_line(ctx):
    with Phone() as p:
        p.pair()
        p.text("tools please")
        ctx.check("the closing line says the work and the cost",
                  p.wait("Done: ran 2 commands, edited 1 file (app.py) ($0.01)."))


@test
def test_a_long_answer_goes_as_reply_txt(ctx):
    with Phone() as p:
        p.pair()
        p.text("long one")
        ctx.check("the rest is attached", p.wait("attached as reply.txt"))
        att = [s for s in p.tr.sent if s.get("attachment")]
        ctx.check("one reply.txt with the whole answer", len(att) == 1 and "reply.txt" in att[0]["attachment"])
        ctx.check("four paragraphs went live first", "Paragraph 4." in p.joined() and "Paragraph 5." not in p.texts())


@test
def test_the_session_is_kept_across_a_restart(ctx):
    with Phone() as p:
        p.pair()
        p.text("hello")
        p.wait("hello from the fake session")
        sid, sessions, home = p.session().sid, p.sessions, p.home
    with Phone(sessions=sessions, home=home) as p2:
        p2.text("again")
        ctx.check("back in the same session", p2.wait("Back in "))
        ctx.check("no second session started", len(sessions.started) == 1)
        ctx.check("the text went to it", wait_for(lambda: len(sessions.rows[sid].submitted) == 2, 3.0))


@test
def test_cd_and_new(ctx):
    import tempfile
    folder = tempfile.mkdtemp(prefix="signal-work-")
    with Phone() as p:
        p.pair()
        p.text(f"/cd {folder}")
        ctx.check("the home folder is set", p.wait("New sessions start in"))
        p.text("/new")
        ctx.check("a session starts there", wait_for(lambda: p.sessions.started and
                                                     p.sessions.started[-1]["cwd"] == str(__import__("pathlib").Path(folder).resolve()), 3.0))


if __name__ == "__main__":
    raise SystemExit(main(TESTS))
