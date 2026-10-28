"""halo_harness.ollama_steward.rules_card -- Halo 3.3.5.0 R0b (e): the steward
knows the model card (providers/model_card.py).

`called-wrong`: a ledger line whose body contradicts the model's card -- a
`think` value sent to a model that does not think, a tool catalog sent to
one with no tool calling, images sent to one without vision (the line's
`body_flags`, ledger_call.py) -- is a finding, and its fix is the card's own
`how` line, so the steward's note says how the model should be called. The
card is built from the host's catalog row (the rules' `catalogs`) and the
tool-call probe's cache; a model with no catalog row is not judged.
"""

from __future__ import annotations

from halo_harness.ollama_steward.rules import finding

PARTS = (("think", "a think value", "it does not think"),
         ("tools", "a tool catalog", "it has no tool calling here"),
         ("images", "images", "it has no vision"))


def _card(g: dict, ctx: dict):
    row = (ctx.get("catalogs") or {}).get(g["host"], {}).get(g["model"])
    if not row:
        return None
    from halo_harness.providers.model_card import card_of
    try:
        return card_of(f"ol:{g['model']}@{g['host']}", state_dir=ctx.get("state_dir"), catalog=row,
                       host=g.get("host_obj"))
    except Exception:
        return None


def _wrong(card: dict, flags: dict) -> list:
    out = []
    think = flags.get("think")
    if think not in (None, False) and card.get("thinks") == "no":
        out.append("think")
    if flags.get("tools") and card.get("tools") == "none":
        out.append("tools")
    if flags.get("images") and not card.get("vision"):
        out.append("images")
    return out


def _fix(card: dict, parts: list) -> str:
    how = card.get("how") or []
    pick = {"think": lambda h: "think" in h, "tools": lambda h: "tools" in h, "images": lambda h: "images" in h}
    lines = [next((h for h in how if pick[p](h)), "") for p in parts]
    return "; ".join(dict.fromkeys(x for x in lines if x))


def called_wrong(g: dict, ctx: dict) -> list:
    lines = [x for x in g["lines"] if isinstance(x.get("body_flags"), dict) and x.get("kind") != "calibrate"]
    if not lines:
        return []
    card = _card(g, ctx)
    if card is None:
        return []
    bad, seen = [], []
    for x in lines:
        wrong = _wrong(card, x["body_flags"])
        if wrong:
            bad.append(x)
            seen.extend(w for w in wrong if w not in seen)
    if not bad:
        return []
    sent = " and ".join(what for key, what, _why in PARTS if key in seen)
    why = "; ".join(why for key, _what, why in PARTS if key in seen)
    n = len(bad)
    return [finding("called-wrong", g, "warn",
                    f"{n} call{'' if n == 1 else 's'} to {g['model']} sent {sent}, which its card says it cannot take "
                    f"({why}): call it the card's way -- {_fix(card, seen)}", calls=bad,
                    numbers={"calls": n, **{k: sum(1 for x in bad if k in _wrong(card, x["body_flags"])) for k in seen}},
                    fix=_fix(card, seen), parts=seen)]


RULES = [called_wrong]
