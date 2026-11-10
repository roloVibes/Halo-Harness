"""tests.helpers.studio_pack_policy -- the Pack Manager's policy chip (Halo 3.3.10.0 R2), one step of
tests/helpers/studio_pack_manager.py's driver run (after Remove, so the earlier steps' rows stay as they were):
the `policy-fence` fixture installed into the served home, enabled with hooks, its mode on, one verdict asked
through the session's gate (a real process), then the page re-opened: the row's `pm-policy` chip names the armed
policy and the last verdict.
"""
from __future__ import annotations

import shutil

from tests.helpers.studio_packs_steps import CUR, TABS, alt, q

ROW = "[data-testid=pm-installed-row][data-id=policy-fence]"


def _text(sel: str) -> str:
    return f"({q(sel)}?.textContent || '')"


def policy_row(c, url, ctx) -> dict:
    from halo_harness.agent import policy_gate as G
    from halo_harness.packs import mode_state as M
    from halo_harness.packs import policy as P
    from halo_harness.packs import registry
    from halo_harness.packs.discover import find
    from halo_harness.packs.grants import enable as enable_pack
    from halo_harness.packs.install import install
    from tests.helpers.packs_home import fixture
    proj = ctx["state"].parent / "project"
    src = ctx["state"].parent / "policy-src" / "policy-fence"
    shutil.copytree(fixture("policy-fence"), src, ignore=shutil.ignore_patterns("__pycache__"))
    ok, lines = install(str(src), cwd=proj)
    assert ok, lines
    ok, lines = enable_pack(find("policy-fence", cwd=proj), grant=["hooks"])
    assert ok, lines
    ok, lines = M.set_mode("policy-fence", "fenced", True, cwd=proj)
    assert ok, lines
    try:
        v = G.before("Write", {"file_path": str(ctx["state"].parent / "elsewhere.txt")}, cwd=proj, session="pm-ui")
    finally:
        P.stop_all()
    registry.invalidate()
    c.go("about:blank")  # the same address again is a fragment hop: a blank page first, so the rows are fetched anew
    c.go(url)
    c.wait(f"{TABS}.length >= 6", 40)  # 3.3.16.0 R2: six core sections
    alt(c, 4)  # 3.3.16.0 R1: Packs
    c.wait(f"{CUR}.startsWith('Packs')", 15)
    chip = f"{ROW} [data-testid=pm-policy]"
    try:
        text = c.wait(f"{_text(chip)}.includes('last:') && {_text(chip)}", 30)
    except TimeoutError as e:  # a red run says which part is missing: the verdict, the row, the chip
        raise TimeoutError(f"{e}; the verdict: {v}; the row: {c.js(_text(ROW))!r}; "
                           f"rows: {c.js('[...document.querySelectorAll(' + chr(39) + '[data-testid=pm-installed-row]' + chr(39) + ')].map((r) => r.dataset.id)')}") from None
    return {"policy_verdict": v.action if v is not None else None, "policy_chip": text,
            "policy_armed": c.js(f"{q(chip)}?.dataset.armed || ''")}
