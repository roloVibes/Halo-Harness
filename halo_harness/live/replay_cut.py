"""halo_harness.live.replay_cut -- redaction rules for a text that was CUT SHORT before the redactor saw it.

live/history.py cuts a task to 200 characters and closes it with "..." before a replay is built, so the cut can
land inside a name ("... as zedteste...") or inside a path ("... and /h...", or a Windows home cut after its
first letters), where the
whole-name and whole-path rules of live/replay_private.py cannot match. These rules look only at the last run of
characters before a closing "..." (or the one-character ellipsis):

    cut_name_rule(names, word) -> rule(s)   a word of 3+ letters there that BEGINS a name is that name -> `word`
    cut_path_rule(homes, root) -> rule(s)   a run there that BEGINS the project folder -> ".", a home folder -> "~"

Both err towards rewriting: an ordinary word that happens to begin the user's name, right before the cut, is
replaced too. That is the right side to err on for a file meant to be handed to someone else.
"""
from __future__ import annotations

import re

_CUT_WORD = re.compile(r"([^\W_]{3,})(\.\.\.|…)$")
_CUT_RUN = re.compile(r"(\S{2,})(\.\.\.|…)$")


def cut_name_rule(names: list, word: str):
    low = [str(n).lower() for n in names if n]

    def rule(s: str) -> str:
        m = _CUT_WORD.search(s)
        if m and any(n.startswith(m.group(1).lower()) and n != m.group(1).lower() for n in low):
            return s[:m.start(1)] + word + m.group(2)
        return s
    return rule


def _forms(path) -> set:
    """Every spelling a folder can have in a text: both slash kinds, and backslashes doubled (a JSON or code string)."""
    p = str(path or "").rstrip("\\/")
    if len(p) < 2:
        return set()
    fwd, back = p.replace("\\", "/"), p.replace("/", "\\")
    return {v.lower() for v in (p, fwd, back, back.replace("\\", "\\\\"))}


def _starts_a_path(run: str, i: int) -> bool:
    return run[i] in "/\\~" or run[i + 1:i + 2] == ":"


def cut_path_rule(homes: list, root=None):
    home_forms = [f for h in homes for f in _forms(h)]
    root_forms = set(_forms(root))
    for h in home_forms:  # the home rules ran first: a project under a home already reads "~/..." or "~\..."
        for r in list(root_forms):
            if r.startswith(h) and len(r) > len(h):
                root_forms.add("~" + r[len(h):])
    # a stub that begins a home is "~" (it begins the project too, when the project is under that home); a longer
    # one that only begins the project is "."
    targets = [(f, "~") for f in home_forms] + [(f, ".") for f in sorted(root_forms, key=len, reverse=True)]

    def rule(s: str) -> str:
        m = _CUT_RUN.search(s)
        if not m:
            return s
        run = m.group(1)
        low = run.lower()
        for i in range(0, len(run) - 1):  # the path may follow a quote or a bracket inside the run
            if not _starts_a_path(run, i):
                continue
            stub = low[i:]
            for form, to in targets:
                if len(stub) >= 2 and form.startswith(stub) and form != stub:
                    return s[:m.start(1) + i] + to + m.group(2)
            break  # the run's first path-like position is the only candidate
        return s
    return rule
