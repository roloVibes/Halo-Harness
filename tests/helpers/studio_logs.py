"""tests.helpers.studio_logs -- Studio's Local -> Logs (Halo 3.3.6.0 R3) in headless Chrome: real clicks through
tests/helpers/studio_local.LocalDriver's session (R1's seeded home; `box` a fake Ollama on 127.0.0.1:0, so its log is
this home's server.log). Seeded here: a fixture log on box (a load of qwen3.8:27b that spilled, a CUDA illegal memory
access and the runner's death, a cut prompt), read into events the way the steward reads it, and a ledger session
that called box. No provider request, no model call, never a real ssh:

`logs`: the page opens from its door (`?page=logs`), box picked; the status line names the state and the path, Copy
the tail command says it on its row; the per-model row for qwen3.8:27b says spilled with 59/66 layers, its cut
prompt, its error lines and "crashed here"; the tail's lines carry their groups, the truncation filter keeps the cut
line only; Live on, a line appended to the log arrives within a poll. The last stdout line is the JSON of what it saw
(exit 2: no Chrome)."""
from __future__ import annotations

import sys
import time
from contextlib import contextmanager
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tools"))

from tests.helpers.studio_local import PAGE, LocalDriver  # noqa: E402
from tests.helpers.studio_packs_steps import q, qa  # noqa: E402
from tests.helpers.studio_settings import press, set_field  # noqa: E402

TRIM = 'time={t} level=WARN source=llama_server.go:334 msg="truncating input prompt" limit=2050 prompt=23536 keep=4 new=2050'


def _seed(ctx) -> Path:
    from halo_harness.ollama_steward.hardware_readers import server_log_path
    from halo_harness.ollama_steward.ledger import blank_line, now_iso, record_call
    from halo_harness.ollama_steward.server_log import scan
    from halo_harness.providers.ollama import resolve_ollama_host
    from tests.helpers.logs_rig import GIN, T, crash_log
    log = server_log_path()
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text(crash_log("qwen3.8:27b", 0.0) + TRIM.format(t=T(40)) + "\n" + GIN(41) + "\n", encoding="utf-8")
    box = resolve_ollama_host("box")
    record_call(ctx["state"], blank_line(host={"name": "box", "url": box.url}, model="qwen3.8:27b", at=now_iso(time.time() - 115),
                                         status=200, session="s-logs", num_ctx_sent=65536))
    scan(ctx["state"], box, from_start=True)
    return log


def logs(c, url, ctx) -> dict:
    from tests.helpers.logs_rig import GIN
    log = _seed(ctx)
    c.go(f"{ctx['base']}?mode=local&page=logs&tour=off#{ctx['frag']}")
    c.wait(f"{PAGE} === 'logs'", 40)
    host = q("[data-testid=local-logs-host]")
    c.wait(f"!!{host}", 30)
    set_field(c, host, "box", "change")
    status = q("[data-testid=local-logs-status-line]")
    out = {"host": c.wait(f"{q('[data-testid=local-logs]')}?.dataset.host === 'box' && 'box'", 20),
           "status": c.wait(f"{status} && {status}.textContent.includes('server.log') && [{status}.dataset.state, {status}.textContent]", 30)}
    out["path"] = c.js(f"{q('[data-testid=local-logs-path]')}?.textContent || ''")
    out["debug"] = c.js(f"{q('[data-testid=local-logs-debug]')}.textContent")
    out["helps"] = c.js(f"{qa('[data-testid$=-help]')}.map((x) => x.dataset.testid)")
    row = q('[data-testid=local-logs-model][data-model="qwen3.8:27b"]')
    out["row"] = c.wait(f"!!{row} && [{row}.dataset.load, {row}.querySelector('[data-testid=local-logs-load]').textContent]", 30)
    out["truncations"] = c.js(f"[...{row}.querySelectorAll('[data-testid=local-logs-truncation]')].map((x) => x.textContent)")
    out["errors"] = c.js(f"[...{row}.querySelectorAll('[data-testid=local-logs-error-line]')].map((x) => x.dataset.kind)")
    out["crashed"] = c.js(f"{row}.querySelector('[data-testid=local-logs-crash-line]')?.textContent || ''")
    lines = qa("[data-testid=local-logs-line]")
    out["groups"] = c.wait(f"{lines}.length > 3 && [...new Set({lines}.map((x) => x.dataset.group))]", 30)
    press(c, q("[data-testid=local-logs-kind][data-kind=truncation]"), f"{q('[data-testid=local-logs-tail]')}?.dataset.kind === 'truncation'")
    out["filtered"] = c.wait(f"{lines}.length > 0 && {lines}.every((x) => x.dataset.group === 'truncation') && {lines}.map((x) => x.textContent)", 20)
    press(c, q("[data-testid=local-logs-kind][data-kind=all]"), f"{q('[data-testid=local-logs-tail]')}?.dataset.kind === 'all'")
    press(c, q("[data-testid=local-logs-copy-tail]"), f"!!{q('[data-testid=local-logs-said]')}")
    out["copied"] = c.js(f"{q('[data-testid=local-logs-said]')}.textContent")
    press(c, q("[data-testid=local-logs-live]"), f"{q('[data-testid=local-logs-live]')}.checked")
    with open(log, "a", encoding="utf-8") as f:
        f.write(GIN(90, 499, "4.2862269s") + "\n")
    out["live"] = c.wait(f"{lines}.some((x) => x.textContent.includes('| 499 |')) && 'arrived'", 20)
    out["dialogs"] = c.js("document.querySelectorAll('[role=dialog]').length")
    return out


class LogsDriver(LocalDriver):
    @contextmanager
    def session(self, c):
        with super().session(c) as steps:
            yield ((logs, steps[0][1]),)


if __name__ == "__main__":
    sys.exit(LogsDriver(sys.argv[1:]).main())
