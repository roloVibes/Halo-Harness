"""tests.helpers.studio_bench -- Studio's Local -> Benchmarks (Halo 3.3.6.0 R5) in headless Chrome: real clicks through
tests/helpers/studio_local.LocalDriver's session (R1's seeded home; `box` a fake Ollama on 127.0.0.1:0, Ollama 0.40.6 on
its card), with two fixture speed cards on box (qwen3.5:9b measured on 0.40.6, qwen3-coder:30b on 0.40.5: stale) and one
change the steward made (until-restart). No provider request, no model call, nothing sent but to the fake:

`bench`: the page's three blocks; the table's rows (benched, the stale mark "measured on 0.40.5", the window chips with
the spill); the tuning report for box (its lines, Halo-side and server-side options, a server option's line and its
revert); a Halo-side option applied with the scope "until halo exits" -> its change in the list with that scope and
the profile written; Revert on it -> the line that says what it put back and the profile as it was; the steward's
change listed with its scope; Settings -> Local's block lists the same.
`lan` (3.3.8.1): box as another machine's host (served_here False for its address, the link fixed, the bench a seam):
Bench on the unbenched row -> the confirm's cost line, `via` and offer; Run -> the row's over-the-LAN chip.
The last stdout line is the JSON of what it saw (exit 2: no Chrome)."""
from __future__ import annotations

import sys
import time
from contextlib import contextmanager
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tools"))

from tests.helpers.studio_local import PAGE, LocalDriver, config, page  # noqa: E402
from tests.helpers.studio_packs_steps import q, qa  # noqa: E402
from tests.helpers.studio_settings import press, set_field  # noqa: E402


def _card(model: str, digest: str, version: str, windows: list, gpu: int) -> dict:
    rows = [{"window": w, "prompt_tok_s": 2400.0 - w / 100, "tok_s": t, "ttft_ms": int(w * 0.4), "size": 2 * 10 ** 10,
             "size_vram": 2 * 10 ** 10 if w <= gpu else 16 * 10 ** 9, "layers": None, "on_gpu": w <= gpu} for w, t in windows]
    return {"model": model, "host": "box", "digest": digest, "ollama_version": version, "at": time.time() - 3600,
            "cold_load_s": 21.0, "windows": rows, "max_gpu_window": gpu, "planner_window": windows[-1][0],
            "reserve_floor": 256, "reserve_probes": [{"num_predict": 128, "cut": True}, {"num_predict": 256, "cut": False}],
            "quick": False, "kv": {"type": "f16", "verified_window": gpu}, "took_s": 300.0}


def seed(state) -> str:
    from halo_harness.ollama_steward import changes as C
    from halo_harness.ollama_steward.profiles import set_field as put
    from halo_harness.providers.local_bench_runs import save
    save(state, _card("qwen3.5:9b", "sha256:b00", "0.40.6", [(8192, 120.0), (32768, 104.0), (65536, 88.0)], 65536))
    save(state, _card("qwen3-coder:30b", "sha256:b01", "0.40.5", [(8192, 190.0), (32768, 166.0), (122880, 23.0)], 32768))
    put("box|qwen3-coder:30b", "keep_alive", "30m", by="steward")
    return C.record(state, by="steward", key="box|qwen3-coder:30b", field="keep_alive", before=None, after="30m",
                    scope="until-restart", why="the steward keeps it warm")["id"]


def bench(c, url, ctx) -> dict:
    sid = seed(ctx["state"])
    c.go(f"{ctx['base']}?mode=local&page=benchmarks&tour=off#{ctx['frag']}")
    c.wait(f"{PAGE} === 'benchmarks'", 40)
    page(c, "benchmarks")
    rows = "[data-testid=bench-row][data-host=box]"
    out = {"blocks": c.wait(f"{qa('[data-testid=bench-block]')}.length === 3 && {qa('[data-testid=bench-block]')}.map((b) => b.dataset.block)", 20),
           # the stale mark needs the host's version read, which lands after the rows: wait for it too, and long
           # (the Windows runner took past 20 s on 0ec52632)
           "rows": c.wait(f"{qa(rows)}.length >= 3 && {qa(rows)}.some((r) => !!r.dataset.stale) && "
                          f"{qa(rows)}.map((r) => [r.dataset.model, !!r.dataset.benched, r.dataset.stale || ''])", 60)}
    coder = q(f'{rows}[data-model="qwen3-coder:30b"]')
    out["stale"] = c.js(f"{coder}.querySelector('[data-testid=bench-stale]')?.textContent || ''")
    out["windows"] = c.js(f"[...{coder}.querySelectorAll('[data-testid=bench-window]')].map((w) => [w.textContent, w.dataset.gpu])")
    out["gpu"] = c.js(f"{coder}.querySelector('[data-testid=bench-gpu]').textContent")
    tune = q("[data-testid=tune-report]")
    c.wait(f"!!{q('[data-testid=tune-host]')}", 20)
    set_field(c, q("[data-testid=tune-host]"), "box", event="change")
    c.wait(f"{tune}?.dataset.host === 'box' && !!{q('[data-testid=tune-says]')}", 20)
    out["says"] = c.wait(f"{q('[data-testid=tune-report][data-host=box] [data-testid=tune-says]')}?.textContent", 20)
    out["models"] = c.js(f"{qa('[data-testid=tune-model]')}.map((x) => x.textContent)")
    out["kinds"] = c.js(f"{qa('[data-testid=tune-option]')}.map((x) => x.dataset.kind)")
    out["server_line"] = c.js(f"{q('[data-testid=tune-option][data-kind=server] [data-testid=tune-set]')}?.textContent || ''")
    out["server_revert"] = c.js(f"{q('[data-testid=tune-option][data-kind=server] [data-testid=tune-revert]')}?.textContent || ''")
    opt = q("[data-testid=tune-option][data-kind=halo]")
    out["option"] = c.wait(f"{opt}?.querySelector('.tune-line')?.textContent", 20)
    before = dict((config(ctx).get("ollama") or {}).get("profiles") or {})
    # pinned to the option's id: which option is first depends on whether the Local sampler's first sample (18 GB held by
    # others on the fake machine) landed before the report was read, and an applied option often leaves the report --
    # its line then stays on a landed row with the same id (TuneReport.tsx)
    mine = q(f'[data-testid=tune-option][data-id="{c.js(f"{opt}.dataset.id")}"]')
    press(c, f"{mine}?.querySelector('[data-testid=tune-scope-opt][data-scope=until-restart]')",
          f"{mine}?.querySelector('[data-testid=tune-scope]')?.dataset.value === 'until-restart'")
    press(c, f"{mine}?.querySelector('[data-testid=tune-apply]')", f"!!{mine}?.querySelector('[data-testid=tune-said]')")
    out["applied"] = c.js(f"{mine}.querySelector('[data-testid=tune-said]').textContent")
    chg = "[data-testid=change-row][data-by=user]"
    out["change"] = c.wait(f"!!{q(chg)} && [{q(chg)}.dataset.scope, {q(chg)}.querySelector('[data-testid=change-line]').textContent]", 20)
    out["written"] = {k: v for k, v in ((config(ctx).get("ollama") or {}).get("profiles") or {}).items() if v != before.get(k)}
    press(c, f"{q(chg)}.querySelector('[data-testid=change-revert]')", f"!{q(chg)}")
    out["reverted"] = c.wait(f"{q('[data-testid=change-reverted]')}?.textContent", 20)
    time.sleep(0.3)
    out["after"] = {k: v for k, v in ((config(ctx).get("ollama") or {}).get("profiles") or {}).items() if v != before.get(k)}
    steward = q(f'[data-testid=change-row][data-id="{sid}"]')
    out["steward"] = c.wait(f"!!{steward} && [{steward}.dataset.scope, {steward}.dataset.by]", 20)
    c.go(f"{ctx['base']}?mode=settings&group=local&tour=off#{ctx['frag']}")
    out["settings"] = c.wait(f"!!{q('[data-testid=settings-local-block] [data-testid=change-row]')} && "
                             f"{qa('[data-testid=settings-local-block] [data-testid=change-row]')}.length", 30)
    return out


def _lan_bench(host, model, *, lan=None, state_dir=None, on_line=None, **_kw) -> dict:
    """The bench seam for `lan`: a card as the bench leaves it (no model call), stamped with the LAN fields."""
    from halo_harness.providers.local_bench_link import stamp
    from halo_harness.providers.local_bench_runs import save
    card = _card(model, "sha256:b02", "0.40.6", [(2048, 310.0)], 2048)
    card.update(at=time.time(), quick=True)
    stamp(card, lan)
    if on_line and lan:
        on_line(lan["label"])
    save(state_dir, card)
    return {"ok": True, **card}


def lan(c, url, ctx) -> dict:
    """3.3.8.1: box as another machine's host with no halo host on it -- Bench on a row that has no card: the confirm says
    the via and the offer, Run, and the row's chip names where it was measured and the link (the wait reads them)."""
    from halo_harness.fleet import ollama_share as S
    from halo_harness.providers import local_bench as LB, local_bench_link as L, local_bench_runs as R
    real, saved = S.served_here, (S.served_here, L.link_of, L.from_where, R.busy, LB.bench)
    S.served_here = lambda u: False if str(u).rstrip("/") == ctx["box"].rstrip("/") else real(u)
    L.link_of = lambda _h, _s=None: {"rtt_ms": 1.8, "kind": "wired", "line": "RTT 1.8 ms, wired"}
    L.from_where = lambda _s=None: "mac"
    R.busy, LB.bench = (lambda *_a, **_k: ""), _lan_bench
    try:
        c.go(f"{ctx['base']}?mode=local&page=benchmarks&tour=off#{ctx['frag']}")
        row = q('[data-testid=bench-row][data-host=box][data-model="nomic-embed-text"]')
        c.wait(f"!!{row} && !{row}.dataset.benched", 40)
        conf = q("[data-testid=bench-confirm]")
        press(c, f"{row}.querySelector('[data-testid=bench-run]')", f"!!{conf}?.querySelector('[data-testid=bench-offer]')")
        out = {"lan_confirm": c.wait(f"!!{conf}?.querySelector('[data-testid=bench-via]') && ['bench-cost', 'bench-via', "
                                     f"'bench-offer'].map((t) => {conf}.querySelector(`[data-testid=${{t}}]`).textContent)", 20)}
        press(c, f"{conf}.querySelector('[data-testid=bench-go]')", f"!!{row}?.querySelector('[data-testid=bench-over-lan]')")
        chip = f"{row}.querySelector('[data-testid=bench-over-lan]')"
        out["lan_row"] = c.wait(f"!!{row}?.dataset.benched && !!{chip} && [{chip}.textContent, {chip}.title]", 20)
        return out
    finally:
        S.served_here, L.link_of, L.from_where, R.busy, LB.bench = saved


class BenchDriver(LocalDriver):
    @contextmanager
    def session(self, c):
        with super().session(c) as steps:
            yield ((bench, steps[0][1]), (lan, steps[0][1]))  # `bench` reads the unbenched rows before `lan` benches one


if __name__ == "__main__":
    sys.exit(BenchDriver(sys.argv[1:]).main())
