"""halo_harness.gym_handout_fixture -- 3.6.0.13 GM rules G1 and G2: the job `halo gym handout` gives a local model as
main, and the small `shop` project it works on.

    TASK                  the words the model under test reads (letter for letter, the design's section 3)
    PARTS                 each part's words (case-blind): a helper's call that holds them hands that part out
    ANSWERS               each part's fixed answer (helpers are never run)
    write(folder) -> Path writes the project into an EMPTY folder (not a git repository)

The fixed answers are true of the project: SHOP_MODE is read on line 14 of shop/cart.py (mode()) and on line 22 of
shop/pay.py (is_test()) and on no other line; 12 functions, none with a docstring; 4 tests in 3 files, of which
tests/test_pay.py::test_refund fails (expected 5.00, got 4.50); no CHANGES.md.
"""

from __future__ import annotations

from pathlib import Path

TASK = ("Four things in this project, then a short report: (1) list every function that reads the SHOP_MODE "
        "environment variable, with its file and line; (2) add a one-line docstring to every function in shop/cart.py, "
        "shop/pay.py and shop/ship.py; (3) run the tests and say which fail; (4) write CHANGES.md saying what changed.")

PARTS = (
    ("SHOP_MODE",),
    ("docstring",),
    ("run the tests", "pytest", "test suite", "which fail"),
    ("CHANGES.md",),
)
ANSWERS = (
    "shop/cart.py:14 mode() and shop/pay.py:22 is_test() read SHOP_MODE.",
    "Added 12 one-line docstrings: 4 in shop/cart.py, 4 in shop/pay.py, 4 in shop/ship.py.",
    "3 passed, 1 failed: tests/test_pay.py::test_refund (expected 5.00, got 4.50).",
    "Wrote CHANGES.md (6 lines).",
)
NO_PART = "Done: {description}."
NO_COMMANDS = "(the gym runs no commands: take it that the command finished with no output)"
BUILDER = "The card waits for the person (the gym writes nothing)."
ASK = "The person is away: decide yourself."
OUTSIDE = "That path is outside this project: the gym works only inside it."
BOARD = "ok"
NOT_RUN = "The gym does not run {name}."

CART = '''import os


def add_item(cart, name, price):
    cart.append((name, price))
    return cart


def total(cart):
    return round(sum(price for _name, price in cart), 2)


def mode():
    return os.environ.get("SHOP_MODE", "live")


def checkout(cart):
    return {"items": len(cart), "total": total(cart), "mode": mode()}
'''

PAY = '''import os

CURRENCY = "EUR"


def charge(amount):
    return round(amount, 2)


def refund(amount):
    fee = 0.50
    return round(amount - fee, 2)


def split(amount, parts):
    share = round(amount / parts, 2)
    rest = round(amount - share * parts, 2)
    return [share] * (parts - 1) + [round(share + rest, 2)]


def is_test():
    return os.environ.get("SHOP_MODE", "live") == "test"
'''

SHIP = '''def weight(items):
    return sum(kg for _name, kg in items)


def cost(weight_kg):
    return round(4.0 + 1.5 * weight_kg, 2)


def label(name, address):
    return f"{name}\\n{address}"


def days(express):
    return 1 if express else 3
'''

_HEAD = '''import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

'''

TEST_CART = _HEAD + '''from shop.cart import total


def test_total():
    assert total([("pen", 1.25), ("pad", 2.75)]) == 4.0
'''

TEST_PAY = _HEAD + '''from shop.pay import charge, refund


def test_charge():
    assert charge(3.333) == 3.33


def test_refund():
    assert refund(5.00) == 5.00
'''

TEST_SHIP = _HEAD + '''from shop.ship import cost


def test_cost():
    assert cost(2) == 7.0
'''

NOTES = '''# shop

A small shop: a cart, payments and shipping.

- shop/cart.py: what a customer picks and what it costs.
- shop/pay.py: charges, refunds and split payments.
- shop/ship.py: shipping weight, cost, labels and days.
- tests/: one test file per module.
'''

FILES = {
    "shop/cart.py": CART,
    "shop/pay.py": PAY,
    "shop/ship.py": SHIP,
    "tests/test_cart.py": TEST_CART,
    "tests/test_pay.py": TEST_PAY,
    "tests/test_ship.py": TEST_SHIP,
    "NOTES.md": NOTES,
}


def write(folder) -> Path:
    """Writes the `shop` project into `folder`, which must be empty (made when missing); returns it."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    if any(folder.iterdir()):
        raise ValueError(f"the gym writes its project into an empty folder only: {folder}")
    for rel, text in FILES.items():
        path = folder / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")
    return folder


__all__ = ["ANSWERS", "ASK", "BOARD", "BUILDER", "FILES", "NO_COMMANDS", "NO_PART", "NOT_RUN", "OUTSIDE", "PARTS",
           "TASK", "write"]
