"""basket.py -- the Orchestra walkthrough: a dict of name -> [unit price (Decimal), quantity]."""
from decimal import Decimal


def add_item(basket, name, price, qty=1):
    """Add `qty` of `name` at `price` to the basket and return the basket."""
    raise NotImplementedError


def remove_item(basket, name, qty=1):
    """Take `qty` of `name` out of the basket (the name goes when none is left); return the basket."""
    raise NotImplementedError


def subtotal(basket):
    """The sum of price * quantity over the basket, as a Decimal."""
    raise NotImplementedError


def apply_discount(amount, percent):
    """`amount` less `percent` per cent, rounded to cents (a Decimal)."""
    raise NotImplementedError


def total(basket, percent=0):
    """The basket's subtotal less `percent` per cent, rounded to cents (a Decimal)."""
    raise NotImplementedError
