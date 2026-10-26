"""halo_harness.tui.dialogs.ollama_found -- Halo 3.2.3.0 R2: the found
Ollama servers in the wizard. `FoundPanel` sits above the Ollama tab's
typed fields (`init_tabs.InitTabsApp` and `init_wizard.ProvidersStep`):
**Find Ollama servers** asks this machine's doors at once, **Scan this
network** sweeps the network with a progress line ("scanning <subnet>
... N s"); each found server is a row with a tick (a configured one ticked
and dimmed), and the tab's Save adds the ticked new rows through
`providers.ollama_discover.add_hosts`. The Local models step shows the
same rows read-only.

The Save and the calibrate offer that follows it live in
`tui/dialogs/ollama_calibrate_offer.py`.
"""

from __future__ import annotations

import time
from typing import Optional

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.content import Content
from textual.widgets import Button, Checkbox, Static

from halo_harness.tui.worker_guard import guarded_worker


def row_label(row) -> str:
    from halo_harness.providers.ollama_discover_hosts import host_port, models_text
    return (f"{row.name}  {host_port(row.url)}  {row.version or '?'}  {models_text(row.models)}  "
            f"({'configured' if row.configured else 'new'})")


class FoundPanel(Vertical):
    DEFAULT_CSS = """
    FoundPanel { height: auto; margin-top: 1; }
    FoundPanel .found-buttons { height: auto; }
    FoundPanel .found-buttons Button { margin-right: 1; }
    FoundPanel .found-progress { color: $text-muted; }
    FoundPanel .found-rows { height: auto; }
    FoundPanel .found-configured { color: $text-muted; }
    """

    def __init__(self, prefix: str, *, read_only: bool = False, auto_find: bool = False) -> None:
        super().__init__(id=f"{prefix}-found")
        self.prefix = prefix
        self.read_only = read_only
        self.auto_find = auto_find
        self.rows: list = []
        self._ticks: "dict[str, bool]" = {}
        self._scan_started: Optional[float] = None
        self._scan_label = "the network"
        self._timer = None
        self._gen = 0

    def compose(self) -> ComposeResult:
        if not self.read_only:
            with Horizontal(classes="found-buttons"):
                yield Button("Find Ollama servers", id=f"{self.prefix}-find")
                yield Button("Scan this network", id=f"{self.prefix}-scan")
        hint = "looking for Ollama servers on this machine…" if self.auto_find else \
            "Find asks this machine (a few seconds); Scan also sweeps the network (about 10 s)."
        yield Static(hint, id=f"{self.prefix}-found-progress", classes="found-progress")
        yield Vertical(id=f"{self.prefix}-found-rows", classes="found-rows")

    def on_mount(self) -> None:
        if self.auto_find:
            self.start_find(force=False)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id or ""
        if bid == f"{self.prefix}-find":
            event.stop()
            self.start_find(force=True)
        elif bid == f"{self.prefix}-scan":
            event.stop()
            self.start_scan()

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        cid = event.checkbox.id or ""
        if cid.startswith(f"{self.prefix}-found-g{self._gen}-row-"):
            try:
                self._ticks[self.rows[int(cid.rsplit("-", 1)[-1])].url] = bool(event.value)
            except (ValueError, IndexError):
                pass

    def _progress(self, text: str) -> None:
        try:
            self.query_one(f"#{self.prefix}-found-progress", Static).update(Content(text))
        except Exception:
            pass

    def start_find(self, *, force: bool = True) -> None:
        self._progress("looking for Ollama servers on this machine…")
        guarded_worker(self, lambda: self._find_worker(force), thread=True, name="ollama-find")

    def _find_worker(self, force: bool) -> None:
        from halo_harness.providers.ollama_discover import discover_local_cached
        result = discover_local_cached(force=force)
        self._post(self.apply_rows, list(result), list(result.notes), "on this machine")

    def start_scan(self) -> None:
        self._scan_started = time.monotonic()
        self._progress("scanning the network ... 0 s")
        if self._timer is None:
            self._timer = self.set_interval(1.0, self._tick)
        guarded_worker(self, self._scan_worker, thread=True, name="ollama-scan")

    def _scan_worker(self) -> None:
        from halo_harness.providers.ollama_discover import discover

        def _label(text: str) -> None:
            self._scan_label = text.replace("scanning ", "", 1).rstrip(" .")
        result = discover("lan", on_progress=_label)
        self._post(self.apply_rows, list(result), list(result.notes), "on the network")

    def _post(self, fn, *args) -> None:
        try:  # the app may have closed while the probe ran
            self.app.call_from_thread(fn, *args)
        except Exception:
            pass

    def _tick(self) -> None:
        if self._scan_started is not None:
            self._progress(f"scanning {self._scan_label} ... {int(time.monotonic() - self._scan_started)} s")

    def apply_rows(self, rows: list, notes: list, where: str) -> None:
        """Merges `rows` into the list shown (one row per server) and
        redraws the ticks, keeping every tick already set."""
        from halo_harness.providers.ollama_discover import dedupe
        if where == "on the network":
            self._scan_started = None
        self.rows = dedupe(self.rows + rows)
        text = f"{len(rows)} Ollama server{'' if len(rows) == 1 else 's'} found {where}"
        self._progress("; ".join([text] + list(notes)))
        self.redraw()

    def redraw(self) -> None:
        try:
            box = self.query_one(f"#{self.prefix}-found-rows", Vertical)
        except Exception:
            return
        box.remove_children()
        self._gen += 1
        for i, row in enumerate(self.rows):
            label = Content(row_label(row))
            dim = "found-configured" if row.configured else ""
            if self.read_only:
                box.mount(Static(label, classes=dim))
                continue
            ticked = True if row.configured else self._ticks.get(row.url, False)
            box.mount(Checkbox(label, value=ticked, disabled=row.configured, classes=dim,
                               id=f"{self.prefix}-found-g{self._gen}-row-{i}"))

    def ticked_new_rows(self) -> list:
        return [r for r in self.rows if not r.configured and self._ticks.get(r.url)]

    def save_ticked(self) -> "tuple[list[str], list[str], dict]":
        """Adds the ticked new rows; returns `(lines, host names added,
        {host name: models})` for the calibrate offer."""
        from halo_harness.providers.ollama_discover import add_hosts, url_key
        chosen = self.ticked_new_rows()
        if not chosen:
            return [], [], {}
        from halo_harness.providers.ollama import resolve_ollama_hosts
        before = {h.name for h in resolve_ollama_hosts()}
        lines = add_hosts(chosen)
        by_host: dict = {}
        for host in resolve_ollama_hosts():
            match = [r for r in chosen if url_key(r.url) == url_key(host.url)]
            if host.name not in before and match:
                by_host[host.name] = list(match[0].models)
                match[0].configured, match[0].name = True, host.name
        self._ticks = {u: v for u, v in self._ticks.items() if u not in {r.url for r in chosen}}
        self._progress("; ".join(lines) if lines else "nothing new to add")
        self.redraw()
        return lines, list(by_host), by_host
