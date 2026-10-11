"""halo_harness.tui.slash_review -- the TUI side of `/review` (Halo 2.0.10).

`/review [target] [--level L] [--dimensions a,b] [--fix] [--no-verify]` runs
the review on a worker thread (the UI never blocks). The reviewers, the judge
and the fixer are ordinary sub-agents, so they show as cards in the transcript
and as rows in `/tasks`; Esc aborts every one of them through the session's
shared abort Event. The result lands as a header line plus one `ReviewCard`
per finding.
"""

from __future__ import annotations

USAGE = ("Usage: /review [target] [--level low|medium|high] [--dimensions a,b] [--fix] [--no-verify]\n"
         "target: a..b range, branch, PR number (#123), or paths/globs; default: this branch against its base.")


async def handle_review(app, args: str) -> None:
    from halo_harness.review.cli import _ArgError, parse_args, split_args
    try:
        _ns, opts = parse_args(split_args(args), cli=False, prog="/review")
    except _ArgError as e:
        await app.transcript.add_note(f"/review: {e}\n{USAGE}", kind="error")
        return
    except ValueError as e:      # an unbalanced quote in the arguments
        await app.transcript.add_note(f"/review: {e}\n{USAGE}", kind="error")
        return
    session = getattr(app.controller, "session", None)
    if session is None or getattr(session, "agent_runtime", None) is None:
        await app.transcript.add_note("/review can only run once a session is running.", kind="error")
        return
    app.run_worker(lambda: review_worker(app, opts), thread=True, name="review", group="review", exit_on_error=False)


def review_worker(app, opts) -> None:
    from halo_harness.review.run import run_review
    from halo_harness.review.target_model import TargetError
    session = app.controller.session
    session.abort.clear()      # an Esc pressed while idle must not cancel this review before it starts

    def say(text: str, kind: str = "command") -> None:
        app.call_from_thread(app.transcript.add_note, text, kind=kind)

    say(f"/review: starting ({opts.level}, {', '.join(opts.dimensions)}{', fix' if opts.fix else ''})")
    try:
        result = run_review(session.agent_runtime, opts, sink=app.controller.events.put, progress=lambda m: say(f"/review: {m}"))
    except TargetError as e:
        say(f"/review: {e}", "error")
        return
    except Exception as e:
        say(f"/review failed: {type(e).__name__}: {e}", "error")
        return
    app.call_from_thread(show_result, app, result)


async def show_result(app, result) -> None:
    from halo_harness.review.render import header_line, to_json
    from halo_harness.tui.widgets.review_cards import ReviewCard, ReviewHeader
    data = to_json(result)
    head = header_line(result) + (" (interrupted)" if result.aborted else "")
    await app.transcript.mount_widget(ReviewHeader(f"Review of {result.target.label}: {head}"))
    app.transcript.plain_log.append(f"Review of {result.target.label}: {head}")
    if not data["findings"]:
        await app.transcript.add_note("No findings.", kind="command")
    for i, finding in enumerate(data["findings"], 1):
        card = ReviewCard(finding, i)
        await app.transcript.mount_widget(card)
        app.transcript.plain_log.append("\n".join(card.plain_lines()))
    for r in data["reviewers"]:
        if not r.get("ok"):
            await app.transcript.add_note(f"reviewer {r['dimension']} ({r['part']}) did not finish: {r.get('error')}",
                                          kind="error")
    for n in data.get("notes", []):
        await app.transcript.add_note(f"/review: {n}", kind="command")
    session = getattr(app.controller, "session", None)
    if session is not None and hasattr(session, "status_event"):
        app.controller.events.put(session.status_event())
