"""halo_harness.providers.copilot_catalog -- `cp:work`'s catalog row (Halo 3.3.17.0 R2).

One row, listed once Copilot is set up and signed in (`halo models`, the `/model` picker, Studio's model lists, the
best-at index Auto reads):

    takes      text, files (OneDrive/SharePoint URLs), web     (`takes`, read by model_takes.takes_words)
    tools      no  (`tools: False`: Auto's candidates never include it, the loop offers it none)
    context    unknown (None)
    price      "Copilot Credits or your licence" -- never a dollar figure (no price_in/out)
    strength   work-data: "research over your work data" (models_auto_work.py picks it for that need)
"""

from __future__ import annotations

from halo_harness.providers.copilot_config import REF

PRICE_WORDS = "Copilot Credits or your licence"
TAKES = ("text", "files", "web")
STRENGTH = "work-data"
STRENGTH_WORDS = "research over your work data"
GROUP = "Copilot at work"


def row() -> dict:
    return {"ref": REF, "provider": "copilot", "group": GROUP, "context_tokens": None, "max_output_tokens": None,
            "price_in_per_m": None, "price_out_per_m": None, "price_words": PRICE_WORDS,
            "detail": f"your work's Copilot · {PRICE_WORDS} · takes text, files (OneDrive/SharePoint URLs), web · "
                      f"tools: no · good at: {STRENGTH_WORDS}",
            "modalities_in": ["text"], "modalities_out": ["text"], "tools": False, "reasoning": None,
            "open_weights": False, "takes": list(TAKES), "strengths": [STRENGTH]}


def copilot_rows() -> list:
    """[the row] once signed in; [] otherwise (and on any error: a catalog read never fails on this)."""
    try:
        from halo_harness.providers.copilot_route import signed_in
        return [row()] if signed_in() else []
    except Exception:
        return []


def print_rows(say=print) -> None:
    """`halo models`' Copilot section: the row with its takes and its price words, never a dollar figure."""
    rows = copilot_rows()
    if not rows:
        return
    say(f"\n{GROUP} (signed in; halo copilot status says who):")
    for r in rows:
        say(f"{r['ref']:<48} {'?':>8} {'?':>8} {'credits':>10} {'licence':>10}  {','.join(r['takes'])}  "
            f"(tools: no; {PRICE_WORDS})")
