"""tests.test_copilot_adapter -- the `copilot` adapter over both doors (Halo 3.3.17.0 R1, providers/copilot.py):
Work IQ's JSON-RPC SendMessage with `A2A-Version: 1.0`, the time zone and the contextId kept for the second turn;
Graph beta's conversation made once and the chat body (text, time zone, the file URIs, web off); both answers in the
one shape; and every error line: a 401 retried once with a fresh token, then consent; 403 consent; no licence;
billing (a 402 and a JSON-RPC error); a 429 waited out once, then said; not signed in; not set up; offline mode.
Mock server only.

Run: python -m tests.test_copilot_adapter
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.copilot_rig import CopilotRig  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
KEYS = {"text", "citations", "sensitivity", "conversation", "api"}


def _err(fn):
    from halo_harness.providers.copilot_net import CopilotError
    try:
        fn()
    except CopilotError as e:
        return e
    return None


@test
def test_workiq_two_turns_one_context(ctx: Ctx):
    from halo_harness.providers.copilot import Conversation, ask
    with CopilotRig() as r:
        r.signin()
        conv = Conversation()
        a = ask("what is on my calendar tomorrow", conversation=conv)
        ctx.check(f"the one shape, got {sorted(a)}", set(a) == KEYS and a["api"] == "workiq")
        ctx.check(f"the answer carries the prompt and the time zone, got {a['text']!r}",
                  "what is on my calendar tomorrow" in a["text"] and "Europe/London" in a["text"])
        ctx.check(f"two citations, got {a['citations']}", [c["title"] for c in a["citations"]] == ["Q3 plan.docx", "Standup notes"]
                  and a["citations"][0]["url"].startswith("https://"))
        ctx.check("the sensitivity label and the context", a["sensitivity"] == "General" and a["conversation"] == "ctx-1")
        call = r.mock.calls("/a2a")[0]
        body = call[3]
        ctx.check("JSON-RPC SendMessage with A2A-Version 1.0 and a bearer",
                  body["method"] == "SendMessage" and body["jsonrpc"] == "2.0" and call[2].get("A2A-Version") == "1.0"
                  and call[2].get("Authorization", "").startswith("Bearer at-"))
        ctx.check("the first turn has no contextId", "contextId" not in body["params"]["message"])
        ask("and the day after", conversation=conv, files=["https://pretend.sharepoint.com/x.docx"])
        second = r.mock.calls("/a2a")[1][3]["params"]["message"]
        ctx.check("the second turn carries the contextId", second.get("contextId") == "ctx-1")
        ctx.check("a file is named in the turn's text", "https://pretend.sharepoint.com/x.docx" in second["parts"][0]["text"])


@test
def test_graph_beta_conversation_and_chat(ctx: Ctx):
    from halo_harness.providers.copilot import Conversation, ask, format_answer
    with CopilotRig(api="graph-beta") as r:
        r.signin(api="graph-beta")
        conv = Conversation()
        a = ask("summarize the budget", files=["https://pretend.sharepoint.com/budget.xlsx"], web=False, conversation=conv)
        ctx.check(f"the one shape, got {sorted(a)}", set(a) == KEYS and a["api"] == "graph-beta" and a["conversation"] == "conv-1")
        ctx.check(f"the file echoed, web off, the zone, got {a['text']!r}", "budget.xlsx" in a["text"] and "web off" in a["text"]
                  and "Europe/London" in a["text"])
        ctx.check("two attributions as citations", [c["title"] for c in a["citations"]] == ["Budget.xlsx", "Team meeting"])
        ctx.check("the sensitivity label", a["sensitivity"] == "Confidential")
        chat = [b for m, p, h, b in r.mock.requests if p.endswith("/chat")][0]
        ctx.check(f"the chat body, got {chat}", chat["message"]["text"] == "summarize the budget"
                  and chat["locationHint"]["timeZone"] == "Europe/London"
                  and chat["contextualResources"]["files"] == [{"uri": "https://pretend.sharepoint.com/budget.xlsx"}]
                  and chat["contextualResources"]["webContext"]["isWebEnabled"] is False)
        ask("and last year", conversation=conv, context="Answer in one line.")
        made = [p for m, p, h, b in r.mock.requests if p.rstrip("/").endswith("/conversations")]
        ctx.check(f"one conversation for both turns, got {made}", len(made) == 1)
        last = [b for m, p, h, b in r.mock.requests if p.endswith("/chat")][-1]
        ctx.check("additionalContext sent when given", last.get("additionalContext") == [{"text": "Answer in one line."}])
        out = format_answer(a)
        ctx.check(f"the citations numbered, got {out!r}", "[1] Budget.xlsx -- https://pretend.sharepoint.com/budget.xlsx" in out
                  and "[2] Team meeting" in out and "Sensitivity: Confidential" in out)


@test
def test_a_401_gets_one_fresh_token_then_says_consent(ctx: Ctx):
    from halo_harness.providers.copilot import ask
    with CopilotRig() as r:
        r.signin()
        r.mock.scenario["workiq"] = "401"
        a = ask("hello")
        ctx.check("a 401 once: a refresh and the retry answered", a["text"].startswith("Work IQ heard")
                  and [b["grant_type"] for m, p, h, b in r.mock.requests if p.endswith("/token")][-1] == "refresh_token")
        r.mock.scenario["workiq"] = "401!"
        e = _err(lambda: ask("hello"))
        ctx.check(f"a 401 after the fresh token: the scope and the admin, got {e and e.line!r}", e is not None
                  and e.kind == "consent" and "https://workiq.svc.cloud.microsoft/.default" in e.line and "admin" in e.line)


@test
def test_every_error_line(ctx: Ctx):
    from halo_harness.providers.copilot import ask
    with CopilotRig() as r:
        r.signin()
        cases = (("403-consent", "consent", "admin must grant consent"), ("403-licence", "licence", "no Microsoft 365 Copilot licence"),
                 ("402", "billing", "consumptive billing"), ("rpc-error", "billing", "consumptive billing"),
                 ("429!", "throttled", "throttled (429) again"))
        for mode, kind, words in cases:
            r.mock.scenario["workiq"] = mode
            e = _err(lambda: ask("hello"))
            ctx.check(f"{mode}: {kind}, got {e and (e.kind, e.line)}", e is not None and e.kind == kind and words in e.line
                      and e.line.startswith("Copilot: ") and "\n" not in e.line)
            r.mock.scenario.pop("workiq", None)
        r.mock.scenario["workiq"] = "429"
        r.waits.clear()
        a = ask("hello")
        ctx.check(f"a 429 once: waited (Retry-After) and answered, got {r.waits}", a["text"] and len(r.waits) == 1)
    with CopilotRig() as r:
        e = _err(lambda: ask("hello"))
        ctx.check(f"not signed in, got {e and e.line!r}", e is not None and e.kind == "signin" and "halo copilot signin" in e.line)
    with CopilotRig(configured=False) as r:
        e = _err(lambda: ask("hello"))
        ctx.check(f"not set up, got {e and e.line!r}", e is not None and e.kind == "setup" and "copilot.tenant" in e.line)
    with CopilotRig() as r:
        r.signin()
        os.environ.pop("HALO_COPILOT_WORKIQ_URL")
        os.environ["HALO_OFFLINE"] = "1"
        e = _err(lambda: ask("hello"))
        ctx.check(f"offline: the existing refusal line, got {e and e.line!r}", e is not None and e.kind == "offline"
                  and "offline mode: not connecting to workiq.svc.cloud.microsoft" in e.line)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
