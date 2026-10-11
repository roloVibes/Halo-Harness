"""halo_harness.tui.dialogs.remote_status -- the `/remote` dialog (Halo 2.0.9
round 4): the Signal bridge's state, the paired phones, the contact requests
waiting for you, and the pairing steps.

    a  approve the highlighted contact request (shows the one-time code, large)
    s  turn command signing on / off for the highlighted phone
    u  unpair the highlighted phone      v  reverify it (new safety number)
    o  Off: stop the bridge and set remote.signal.enabled to false
    r  refresh      w  "I wrote it down" (hides the signing phrase)      Esc  close

Everything that touches files runs on a worker thread
(`halo_harness.remote.dialog_model`) and is rendered on the UI thread. The
bridge is never started in this process: when it is not running the dialog
says to run `halo remote signal run`.
"""

from __future__ import annotations

from typing import Optional

from rich.text import Text
from textual._context import NoActiveAppError
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, OptionList, Static
from textual.widgets.option_list import Option

from halo_harness.remote import dialog_model as model
from halo_harness.tui.dialogs.remote_digits import _FONT, big_digits, when as _when  # noqa: F401

class RemoteStatus(ModalScreen):
    BINDINGS = [
        Binding("escape,q", "cancel", "Close", show=False),
        Binding("a", "approve", "Approve", show=False),
        Binding("s", "toggle_signed", "Signed", show=False),
        Binding("u", "unpair", "Unpair", show=False),
        Binding("v", "reverify", "Reverify", show=False),
        Binding("o", "kill", "Off", show=False),
        Binding("r", "refresh", "Refresh", show=False),
        Binding("w", "wrote_it_down", "Wrote it down", show=False),
    ]
    DEFAULT_CSS = """
    RemoteStatus { align: center middle; }
    RemoteStatus > Vertical { width: 94%; height: 96%; border: round $primary; background: $surface; padding: 0 2; }
    RemoteStatus OptionList { height: 4; border: none; padding: 0; }
    RemoteStatus VerticalScroll { height: 1fr; min-height: 11; }
    RemoteStatus Horizontal { height: 1; }
    RemoteStatus Button { margin-right: 1; min-width: 12; }
    """

    def __init__(self, snap: dict, *, poll: float = 2.0) -> None:
        super().__init__()
        self.snap = snap
        self.poll = poll
        self._awaiting: Optional[str] = None
        self._secret_shown = False
        self._warned = False
        self._busy = False

    def compose(self):
        with Vertical():
            yield Static("Remote control (Signal)", classes="dialog-title")
            yield Static("", id="remote-state")
            yield Static("Contact requests (a approves)", classes="dialog-subtitle")
            yield OptionList(id="remote-pending")
            yield Static("Paired phones (s signed on/off, u unpair, v reverify)", classes="dialog-subtitle")
            yield OptionList(id="remote-peers")
            with VerticalScroll():
                yield Static("", id="remote-code")
                yield Static("", id="remote-secret")
            with Horizontal():
                yield Button("Approve", id="btn-approve", compact=True)
                yield Button("Signed on/off", id="btn-signed", compact=True)
                yield Button("Unpair", id="btn-unpair", compact=True)
                yield Button("Reverify", id="btn-reverify", compact=True)
                yield Button("Off", id="btn-off", variant="error", compact=True)
                yield Button("I wrote it down", id="btn-wrote", compact=True)
            yield Static("a approve  s signed  u unpair  v reverify  o off (kill switch)  r refresh  w wrote it down  Esc close",
                         classes="dialog-subtitle")

    def on_mount(self) -> None:
        self._render_snapshot(self.snap)
        if self.poll:
            self.set_interval(self.poll, self.action_refresh)

    # ---- rendering (UI thread) -------------------------------------------------
    def _render_snapshot(self, snap: dict) -> None:
        self.snap = snap
        b = snap["bridge"]
        pid = f" (pid {b['pid']})" if b.get("pid") and b.get("running") else ""
        lines = [f"Bridge: {b['state']}{pid}    remote.signal.enabled: {str(snap['signal_enabled']).lower()}",
                 snap["control"].replace("\n", "    ")]
        if b["state"] in ("off", "stopped"):
            lines.append(model.RUN_HINT)
        self.query_one("#remote-state", Static).update(Text("\n".join(lines)))
        self._fill("#remote-pending", [
            (r["aci"], f"{r['index']}  {r['aci_prefix']}  {r['number'] or '(no number)'}  [{r['state']}]  safety "
                       f"{' '.join((r['safety_number'] or '(not known yet)').split())}") for r in snap["pending"]],
            "No contact requests. On the phone, send any message to the Halo number.")
        self._fill("#remote-peers", [
            (p["aci"], f"{p['aci_prefix']}  {p['number'] or '(no number)'}  paired {_when(p['paired_at'])}  "
                       f"{'signed' if p['signed'] else 'unsigned'}" + ("  BLOCKED - v to reverify" if p["blocked"] else ""))
            for p in snap["peers"]], "No paired phones.")

    def _fill(self, selector: str, rows: list, empty: str) -> None:
        ol = self.query_one(selector, OptionList)
        keep = self._selected(ol)
        ol.clear_options()
        if not rows:
            ol.add_option(Option(Text(empty), disabled=True))
            return
        ol.add_options([Option(Text(label), id=aci) for aci, label in rows])
        ids = [aci for aci, _ in rows]
        ol.highlighted = ids.index(keep) if keep in ids else 0

    @staticmethod
    def _selected(ol: OptionList) -> Optional[str]:
        if ol.highlighted is None or not ol.options:
            return None
        return ol.get_option_at_index(ol.highlighted).id

    def _show_code(self, res: dict) -> None:
        text = big_digits(res["code"]) + f"\n\nPairing code, valid until {_when(res['expires'])}. On the phone, send exactly this code."
        if not res.get("trusted"):
            text += "\nThe bridge finishes the trust step; " + model.RUN_HINT
        self.query_one("#remote-code", Static).update(Text(text, style="bold"))

    def _show_secret(self, view: dict) -> None:
        self._secret_shown = True
        self.query_one("#remote-code", Static).update("")
        self.query_one("#remote-secret", Static).update(Text(
            "Paired. Signing secret, shown once (press w when you have written it down):\n" + view["phrase"] + "\n\n" + view["link"]
            + "\n`halo remote signal pair` shows this as a QR code too.", style="bold"))

    # ---- worker plumbing ---------------------------------------------------------
    def _deliver(self, fn, *args) -> None:
        try:
            self.app.call_from_thread(fn, *args)
        except (NoActiveAppError, RuntimeError):
            return

    def _work(self, job, then=None) -> None:
        def body() -> None:
            try:
                result = job()
            except Exception as e:  # a bad file must not close the TUI
                result = {"ok": False, "error": f"{type(e).__name__}: {e}"}
            if then is not None:
                self._deliver(then, result)
        self.app.run_worker(body, thread=True, name="remote-dialog", group="remote-dialog", exit_on_error=False)

    # ---- actions -----------------------------------------------------------------
    def action_refresh(self) -> None:
        if self._busy:
            return
        self._busy = True
        awaiting = self._awaiting

        def job() -> dict:
            snap = model.snapshot()
            view = model.paired_view(awaiting) if awaiting else None
            return {"snap": snap, "notices": model.pop_notices(), "view": view}
        self._work(job, self._refreshed)

    def _refreshed(self, res: dict) -> None:
        self._busy = False
        if "snap" not in res:
            return
        for n in res["notices"]:
            self.app.notify(str(n.get("text") or n.get("kind")), title="Remote control", severity="warning")
        self._render_snapshot(res["snap"])
        if res["view"] and self._awaiting:
            self._awaiting = None
            self._show_secret(res["view"])

    def action_approve(self) -> None:
        aci = self._selected(self.query_one("#remote-pending", OptionList))
        if not aci:
            self.app.notify("Select a contact request first (Tab switches lists).", title="Remote control")
            return
        self._work(lambda: model.approve(aci), self._approved)

    def _approved(self, res: dict) -> None:
        if not res.get("ok"):
            self.app.notify(res.get("error", "could not approve"), title="Remote control", severity="error")
            return
        self._awaiting = res["aci"]
        self._show_code(res)
        self.action_refresh()

    def _peer_action(self, fn, done: str) -> None:
        aci = self._selected(self.query_one("#remote-peers", OptionList))
        if not aci:
            self.app.notify("Select a paired phone first (Tab switches lists).", title="Remote control")
            return
        self._work(lambda: fn(aci), lambda res: (self.app.notify(done if res is not False else "nothing changed",
                                                                  title="Remote control"), self.action_refresh()))

    def action_toggle_signed(self) -> None:
        aci = self._selected(self.query_one("#remote-peers", OptionList))
        peer = next((p for p in self.snap["peers"] if p["aci"] == aci), None)
        if peer is None:
            self.app.notify("Select a paired phone first (Tab switches lists).", title="Remote control")
            return
        self._work(lambda: model.set_signed(aci, not peer["signed"]),
                   lambda res: (self.app.notify(f"Signing is now {'off' if peer['signed'] else 'on'} for {peer['aci_prefix']}.",
                                                title="Remote control"), self.action_refresh()))

    def action_unpair(self) -> None:
        self._peer_action(model.unpair, "Unpaired. Its signing secret is gone.")

    def action_reverify(self) -> None:
        self._peer_action(lambda aci: model.reverify(aci).get("ok", False) or False, "Reverify queued; the bridge finishes it.")

    def action_kill(self) -> None:
        self._work(model.kill_switch, lambda res: (self.app.notify(
            "Stopped the bridge; remote.signal.enabled is false." if res.get("was_running") else
            "No bridge was running; remote.signal.enabled is false.", title="Remote control"), self.action_refresh()))

    def action_wrote_it_down(self) -> None:
        self._secret_shown = False
        self.query_one("#remote-secret", Static).update("")

    def on_button_pressed(self, event) -> None:
        {"btn-approve": self.action_approve, "btn-signed": self.action_toggle_signed, "btn-unpair": self.action_unpair,
         "btn-reverify": self.action_reverify, "btn-off": self.action_kill,
         "btn-wrote": self.action_wrote_it_down}[event.button.id]()

    def action_cancel(self) -> None:
        if self._secret_shown and not self._warned:
            self._warned = True
            self.app.notify("The signing phrase is shown once. Press w when you have written it down; Esc again closes anyway.",
                            title="Remote control")
            return
        self.dismiss(None)
