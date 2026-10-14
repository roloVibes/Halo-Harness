"""test_basket.py -- the tests the Orchestra walkthrough's gate runs (`python -m unittest`)."""
import unittest
from decimal import Decimal

import basket as b


class BasketTest(unittest.TestCase):
    def test_add_item(self):
        basket = b.add_item({}, "apple", Decimal("0.50"), 3)
        b.add_item(basket, "apple", Decimal("0.50"))
        self.assertEqual(basket, {"apple": [Decimal("0.50"), 4]})

    def test_remove_item(self):
        basket = {"apple": [Decimal("0.50"), 4], "pear": [Decimal("0.75"), 1]}
        b.remove_item(basket, "apple", 3)
        b.remove_item(basket, "pear")
        self.assertEqual(basket, {"apple": [Decimal("0.50"), 1]})

    def test_subtotal(self):
        basket = {"apple": [Decimal("0.50"), 4], "pear": [Decimal("0.75"), 2]}
        self.assertEqual(b.subtotal(basket), Decimal("3.50"))
        self.assertEqual(b.subtotal({}), Decimal("0"))

    def test_apply_discount(self):
        self.assertEqual(b.apply_discount(Decimal("10.00"), 15), Decimal("8.50"))
        self.assertEqual(b.apply_discount(Decimal("0.97"), 50), Decimal("0.49"))  # half a cent rounds up

    def test_total(self):
        basket = {"apple": [Decimal("0.50"), 4], "pear": [Decimal("0.75"), 2]}
        self.assertEqual(b.total(basket), Decimal("3.50"))
        self.assertEqual(b.total(basket, 10), Decimal("3.15"))


if __name__ == "__main__":
    unittest.main()
