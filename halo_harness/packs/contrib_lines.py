"""halo_harness.packs.contrib_lines -- the four 3.4.0.0 B contributions in one place for the manifest (draft, API 1.3):
`contributes.cli` (contrib_cli.py), `.slash` (contrib_slash.py), `.doctor` (contrib_doctor.py) and `.settings`
(contrib_settings.py). packs/manifest.py reads `needs` (the grants they take) and `contrib_lines` (one line per
problem) from here, so each contribution's own rules stay in its own module.
"""

from __future__ import annotations


def _modules() -> tuple:
    from halo_harness.packs import contrib_cli, contrib_doctor, contrib_settings, contrib_slash
    return contrib_cli, contrib_slash, contrib_doctor, contrib_settings


def needs(data) -> "list[tuple[str, str]]":
    out: "list[tuple[str, str]]" = []
    for m in _modules():
        out += m.needs(data) if hasattr(m, "needs") else []
    return out


def contrib_lines(data, root=None) -> "list[str]":
    out: "list[str]" = []
    for m in _modules():
        out += m.lines(data, root)
    return out
