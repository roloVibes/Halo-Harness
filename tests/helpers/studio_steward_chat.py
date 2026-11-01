"""tests.helpers.studio_steward_chat -- Local -> Steward's chat box (Halo 3.3.7.0 R5) in headless Chrome: real typing
and clicks over tests/helpers/chat_rig.ChatHome (a fake model on 127.0.0.1:0 answering fixed JSON: a card read, then an
answer) served by a real Studio on 127.0.0.1:0. No provider request, no real model:

`chat`: open Local -> Steward; the chat names the steward's model; type a question, press Ask; the question, the tool
line and the answer appear, the answer with its cost chip ("local, N s"); the candidates block lists the steward's
model. The last stdout line is the JSON of what it saw (exit 2: no Chrome)."""
from __future__ import annotations

import sys
from contextlib import contextmanager
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tools"))

from tests.helpers.chrome_driver import Driver  # noqa: E402
from tests.helpers.studio_local import PAGE  # noqa: E402
from tests.helpers.studio_packs_steps import q, qa  # noqa: E402
from tests.helpers.studio_settings import press  # noqa: E402

ANSWER = "The card on loop is 24 GB and nothing else holds it; the 27B's prompts reach 31k of 32k."


def chat(c, url, ctx) -> dict:
    c.go(f"{ctx['base']}?mode=local&page=steward&tour=off#{ctx['frag']}")
    c.wait(f"{PAGE} === 'steward'", 40)
    out = {"model": c.wait(f"{q('[data-testid=steward-chat-model]')}?.textContent.includes('steward-mock') && "
                           f"{q('[data-testid=steward-chat-model]')}.textContent", 30)}
    inp = q("[data-testid=steward-chat-input]")
    c.js(f"{inp}.scrollIntoView({{block: 'center'}}); 1")
    c.click_on(inp)
    c.js(f"{inp}.focus(); 1")  # the page's scroll box can move under the pointer: the field has the focus either way
    out["focused"] = c.js("document.activeElement?.dataset?.testid || document.activeElement?.tagName || ''")
    c.type_text("what holds the card on loop?")
    out["typed"] = c.wait(f"{inp}.value", 10)
    c.wait(f"!{q('[data-testid=steward-chat-ask]')}.disabled", 10)
    press(c, q("[data-testid=steward-chat-ask]"), f"{qa('[data-testid=steward-chat-a]')}.length >= 1")
    out["q"] = c.js(f"{qa('[data-testid=steward-chat-q]')}.map((x) => x.textContent)")
    out["tools"] = c.js(f"{qa('[data-testid=steward-chat-tool]')}.map((x) => x.textContent)")
    out["answer"] = c.js(f"{q('[data-testid=steward-chat-a] .lc-chat-text')}?.textContent || ''")
    out["cost"] = c.js(f"{q('[data-testid=steward-chat-cost]')}?.textContent || ''")
    out["candidates"] = c.wait(f"{qa('[data-testid=steward-candidate]')}.length >= 1 && "
                               f"{qa('[data-testid=steward-candidate]')}.map((x) => x.dataset.ref)", 20)
    out["calls"] = ctx["home"].calls("steward-mock:1b")
    return out


class ChatDriver(Driver):
    no_chrome = {"skip": "no Chrome found"}

    @contextmanager
    def session(self, c):
        from capture_studio import serve
        from tests.helpers.chat_rig import ChatHome
        with ChatHome([{"tool": "card", "args": {"host": "loop"}}, {"answer": ANSWER}]) as home:
            srv, url = serve(home.state, True)
            base, frag = url.split("?", 1)[0], url.split("#", 1)[1]
            try:
                yield ((chat, (c, url, {"base": base, "frag": frag, "home": home})),)
            finally:
                srv.shutdown()
                srv.server_close()


if __name__ == "__main__":
    sys.exit(ChatDriver(sys.argv[1:]).main())
