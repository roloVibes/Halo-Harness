"""tests.fake_session -- sessions as the bridge sees them (session.Sessions' surface), scripted, in process.

    FakeSessions(): .live() .connect(sid) .start(cwd, model, by) ; .add(title, cwd) -> FakeSession ; .started
    FakeSession: what its control socket answers. A submitted text runs a scripted turn:
        "paragraphs"  three paragraphs and a code block, cut into chunks mid-sentence
        "ask"         a permission card first (the rest after the answer)
        "question"    a question card with two options
        "plan"        a plan card
        "tools"       two Bash runs and an Edit before the answer
        "long"        nine paragraphs (past the live budget: reply.txt)
        anything else one paragraph: "hello from the fake session"
    Every frame carries `via`/`by` from the submit's origin on its `user_message`, as the real session does.
"""

from __future__ import annotations

import queue
import threading
import uuid

PARAS = ("The first paragraph says what it found, in two sentences. It goes on a little.\n\n"
         "The second one is short.\n\n```\nprint('code stays together')\nprint(2)\n```\n\nThe last paragraph ends it.")


class FakeSession:
    def __init__(self, title: str, cwd: str, started: float) -> None:
        self.sid = uuid.uuid4().hex
        self.row = {"session_id": self.sid, "title": title, "cwd": cwd, "started": started, "kind": "headless",
                    "model": "mock/fake", "pid": 1}
        self.feeds: list = []
        self.submitted: list = []
        self.answers: list = []
        self.notes: list = []
        self.pending = {"permission": [], "question": [], "plan": False, "approval": []}
        self.rest: list = []
        self.lock = threading.Lock()
        self.cost = 0.0123

    def emit(self, event: str, data: dict) -> None:
        with self.lock:
            for q in self.feeds:
                q.put({"event": event, "data": data, "turn": 1, "agent_id": None})

    def run_turn(self, text: str, origin: dict) -> None:
        self.emit("user_message", {"text": text, "via": origin.get("via"), "by": origin.get("by")})
        self.emit("message_start", {})
        t = text.lower()
        if "paragraphs" in t:
            for piece in (PARAS[:30], PARAS[30:95], PARAS[95:150], PARAS[150:]):
                self.emit("text_chunk", {"text": piece})
            return self.done()
        if "long" in t:
            self.emit("text_chunk", {"text": "".join(f"Paragraph {i}.\n\n" for i in range(1, 10))})
            return self.done()
        if "tools" in t:
            for name, inp in (("Bash", {"command": "ls"}), ("Bash", {"command": "pytest"}),
                              ("Edit", {"file_path": "/x/src/app.py"})):
                self.emit("tool_use_ready", {"name": name, "input": inp})
            self.emit("text_chunk", {"text": "Fixed it.\n"})
            return self.done()
        if "ask" in t:
            self.pending["permission"] = ["perm_1"]
            self.emit("permission_request", {"id": "perm_1", "name": "Bash", "input": {"command": "echo hi"},
                                             "reason": "needs approval", "suggested_rule": "Bash(echo:*)"})
            self.rest = [("text_chunk", {"text": "It ran.\n"})]
            return
        if "question" in t:
            self.pending["question"] = ["q_1"]
            self.emit("question", {"id": "q_1", "name": "AskUserQuestion", "input": {"questions": [
                {"question": "which?", "options": [{"label": "red"}, {"label": "blue"}]}]}})
            self.rest = [("text_chunk", {"text": "Blue it is.\n"})]
            return
        if "plan" in t:
            self.pending["plan"] = True
            self.emit("plan_review", {"id": "plan_1", "plan": "do the thing", "path": ""})
            self.rest = [("text_chunk", {"text": "Planned.\n"})]
            return
        self.emit("text_chunk", {"text": "hello from the fake session\n"})
        self.done()

    def done(self) -> None:
        for ev, data in self.rest:
            self.emit(ev, data)
        self.rest = []
        self.emit("turn_done", {"reason": "end_turn"})

    def answer(self, fields: dict) -> dict:
        self.answers.append(fields)
        kind = fields.get("kind")
        if kind == "permission":
            self.pending["permission"] = []
        elif kind == "question":
            self.pending["question"] = []
        elif kind == "plan":
            self.pending["plan"] = False
        self.done()
        return {"ok": True, "result": {"answered": True}}


class FakeClient:
    def __init__(self, s: FakeSession) -> None:
        self.s, self.q, self.closed = s, None, False

    def call(self, cmd: str, **fields) -> dict:
        s = self.s
        if cmd == "ping":
            return {"ok": True, "result": {"pong": True}}
        if cmd == "subscribe":
            self.q = queue.Queue()
            with s.lock:
                s.feeds.append(self.q)
            return {"ok": True, "result": {"subscribed": True}}
        if cmd == "status":
            return {"ok": True, "result": {"phase": "idle", "pending": dict(s.pending), "cost_usd": s.cost,
                                           "model": "mock/fake", "total_input_tokens": 10, "total_output_tokens": 5}}
        if cmd == "submit":
            s.submitted.append(fields)
            threading.Thread(target=s.run_turn, args=(fields.get("text") or "", fields.get("origin") or {}),
                             daemon=True).start()
            return {"ok": True, "result": {"steered": False}}
        if cmd == "answer":
            return s.answer(fields)
        if cmd == "note":
            s.notes.append(fields)
            return {"ok": True, "result": {}}
        if cmd == "tail":
            return {"ok": True, "result": {"markdown": "the last lines"}}
        if cmd == "slash":
            return {"ok": True, "result": {"output": f"ran {fields.get('line')}"}}
        return {"ok": True, "result": {}}

    def next_event(self, timeout: float = 0.4):
        if self.q is None:
            return None
        try:
            return self.q.get(timeout=timeout)
        except queue.Empty:
            return None

    def close(self) -> None:
        self.closed = True
        if self.q is not None:
            with self.s.lock:
                if self.q in self.s.feeds:
                    self.s.feeds.remove(self.q)


class FakeSessions:
    def __init__(self) -> None:
        self.rows: dict = {}
        self.started: list = []
        self.n = 0

    def add(self, title: str, cwd: str) -> FakeSession:
        self.n += 1
        s = FakeSession(title, cwd, 1000.0 + self.n)
        self.rows[s.sid] = s
        return s

    def live(self) -> list:
        rows = [s.row for s in self.rows.values()]  # newest first; one start time: the later added first
        return [r for _, r in sorted(enumerate(rows), key=lambda p: (p[1]["started"], p[0]), reverse=True)]

    def connect(self, sid: str):
        s = self.rows.get(sid)
        return FakeClient(s) if s is not None else None

    def start(self, cwd: str, model: str, by: str):
        s = self.add("new session", cwd)
        self.started.append({"cwd": cwd, "model": model, "by": by})
        return s.row, ""
