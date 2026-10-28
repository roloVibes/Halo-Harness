"""halo_harness.teams_apply_answer -- Halo 3.3.5.0 R0 (h): the lineup-apply
answer in one line.

`teams_yaml.resolve_role_table` leaves one note per role it left out of the
role table; most of them say the same thing ("main: agent 'x' has no
models.preference/fallback of its own -- left out of the role table (falls
through to the session model)"). Shown one per line they buried the answer
(and, as a toast, covered Setup's Next). `apply_answer(name, notes)` folds
them into

    lineup 'local-first' applied; main, small, researcher and judge run on
    the session model (their agents name none)

with the per-role sentences kept as the details (Setup's `<details>`, the
TUI's indented lines under `/teams apply`).
"""

from __future__ import annotations

NO_MODEL = "has no models.preference/fallback of its own"


def words(names: list) -> str:
    """"main", "main and small", "main, small and judge"."""
    names = [str(n) for n in names if n]
    if len(names) <= 1:
        return "".join(names)
    return ", ".join(names[:-1]) + " and " + names[-1]


def apply_answer(name: str, notes: "list[str]") -> "tuple[str, list[str]]":
    """(the one line, the details: every note as it was)."""
    notes = [str(n) for n in notes or []]
    fall = [n.split(":", 1)[0].strip() for n in notes if NO_MODEL in n]
    rest = [n for n in notes if NO_MODEL not in n]
    line = f"lineup {name!r} applied"
    if fall:
        one = len(fall) == 1
        line += (f"; {words(fall)} {'runs' if one else 'run'} on the session model "
                 f"({'its agent names' if one else 'their agents name'} none)")
    if rest:
        line += f"; {len(rest)} more note{'' if len(rest) == 1 else 's'} in the details"
    return line, notes
