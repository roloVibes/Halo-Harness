"""halo_harness.crew.runner_when -- does a step run for this request? (Halo 3.6.0.0 R2, crew/runner.py)

A step's `when` (workflow/1): `always` (or none), `{needs: [...]}`, `{says: [words]}` or `ask`. The words are the
router's (workflows/when.py `word_hit`, workflows/router.py `gaps`): no third matcher.

    always            it runs
    {needs: [pdf]}    the task needs one of them: the router's gaps for the request and its files (a PDF, an image,
                      audio, video named or attached; the asks plan / review / research), what the session's model
                      takes left out of it -- "the task needs", not "the model lacks"; a need the gaps never name
                      (code, reasoning, long-text) is the word itself in the request
    {says: [fix]}     the request says one of the words (a whole word)
    ask               only when I ask: the request names the step or one of its agents

    decide(when, request, files, step) -> (runs: bool, why: str)
"""

from __future__ import annotations

from halo_harness.workflows.when import ALIASES, Rule, word_hit

_SAY = {"images": "an image", "vision": "an image", "pdf": "a PDF", "audio": "audio", "video": "video"}


def _need(word: str) -> str:
    w = str(word or "").strip().lower()
    return {"images": "vision"}.get(w, ALIASES.get(w, w))


def decide(when, request: str, files=(), step=None) -> "tuple[bool, str]":
    step = step or {}
    if when in (None, "always"):
        return True, "always"
    if when == "ask":
        names = [str(step.get("name") or "")] + [str(a) for a in step.get("agents") or []]
        hit = word_hit(Rule(words=[n.lower() for n in names if n.strip()]), request)
        return (True, f'asked for: the request names "{hit}"') if hit else \
            (False, "skipped: only when you ask, and the request does not name this step or its agents")
    if isinstance(when, dict) and isinstance(when.get("says"), list):
        words = [str(w).strip().lower() for w in when["says"] if str(w).strip()]
        hit = word_hit(Rule(words=words), request)
        return (True, f'the request says "{hit}"') if hit else (False, f"skipped: the request says none of {', '.join(words)}")
    if isinstance(when, dict) and isinstance(when.get("needs"), list):
        from halo_harness.workflows.router import gaps
        try:
            have = set(gaps(request, list(files or ()), takes=()))
        except Exception:
            have = set()
        for n in when["needs"]:
            w = _need(n)
            if w in have or word_hit(Rule(words=[str(n).lower()]), request):
                return True, f"the task needs {_SAY.get(w, n)}"
        return False, f"skipped: the task needs none of {', '.join(map(str, when['needs']))}"
    return True, "always"
