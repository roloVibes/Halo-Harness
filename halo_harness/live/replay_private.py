"""halo_harness.live.replay_private -- `halo audit privacy --replays`: every saved replay of this home checked for this
machine's home path, user name and machine name (audit; it leaves with the replays). 3.6.0.3: the scrub that was here
moved to halo_harness/privacy_scrub.py with no change of behaviour; every name of it is re-exported here (the same
objects) until the batch that deletes this module.
"""

from __future__ import annotations

import re

from halo_harness.privacy_scrub import (_ACCOUNT_COMMANDS, _ACCOUNT_FLAGS, _account_slots, _ARGS, _CMD_AT, _CMD_WORD,
                                        COMMON_NAMES, _CONTROLS, cut_name_rule, cut_path_rule, _CUT_RUN, _CUT_WORD,
                                        _forms, _homes, ID_KEYS, _json_unescape, _LEAD, _LOGIN_AT, _machines, _MARK,
                                        _name_patterns, _name_rule, OWNER_KEYS, _prefix, project_root, _rule, scrub,
                                        _SEGMENT_END, _SEGMENT_LEAD, SEP, _short_paths, _starts_a_path, _TAIL,
                                        _TOKEN, _users, _variants)  # noqa: F401


def audit(state_dir) -> list:
    """`halo audit privacy --replays`: every saved replay of this home (`<state>/replays/*.halo-replay`) checked by the
    audit's own rules (privacy_scan.scan_text_content) and for this machine's home path (any spelling), user name
    and machine name outside the owner's own text; `{kind, path, line, excerpt, commit}` rows, the value masked."""
    import json
    from halo_harness.live.replay_file import SUFFIX, replays_dir
    from halo_harness.privacy_scan import _masked_excerpt, scan_text_content
    homes = _homes()
    own = [(re.compile(_LEAD + src), "home-path") for src in filter(None, map(_prefix, homes))]
    # 3.6.0.1: the scrub's own name rules (a common-word name only as a home segment; never inside '<user>')
    own += [(pat, "user-name") for pat in _name_patterns(_users(homes), machines=_machines())]
    own += [(pat, "machine-name") for pat in _name_patterns(_machines(), segments=False)]
    folder = replays_dir(state_dir)
    out: list = []
    for path in sorted(folder.glob(f"*{SUFFIX}")) if folder.is_dir() else []:
        try:
            text = path.read_text(encoding="utf-8")
            data = json.loads(text)
        except (OSError, ValueError):
            continue
        rel = f"replays/{path.name}"
        rows = scan_text_content(text, rel_path=rel, allowlist=set())
        if isinstance(data, dict):  # the owner's own text (the title, the lineup's names) may name them
            text = json.dumps({k: v for k, v in data.items() if k not in OWNER_KEYS}, ensure_ascii=False, indent=0)
        for pat, kind in own:
            rows += [{"kind": kind, "line": text.count("\n", 0, m.start()) + 1,
                      "excerpt": _masked_excerpt(text, m.start(), m.end())} for m in pat.finditer(text)]
        for r in rows:  # an excerpt's context may hold another of them: masked too
            for pat, _kind in own:
                r["excerpt"] = pat.sub("<redacted>", r["excerpt"])
        out += [dict(r, path=rel, commit=None) for r in rows]
    return out
