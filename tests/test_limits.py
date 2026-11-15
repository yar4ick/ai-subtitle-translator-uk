import unittest

from aisubs import limits
from aisubs.prepare import Item, Part


class LimitsTest(unittest.TestCase):
    def test_cps(self):
        self.assertEqual(limits.cps("<i>abcd\nefgh</i>", 0, 2000), 4.0)
        self.assertEqual(limits.cps("abcd", 0, 100), 8.0)  # rated as 0.5 s

    def test_single_part_budget(self):
        self.assertEqual(limits.budgets(Item(0, 2000, [Part("x")])), [34])
        self.assertEqual(limits.budgets(Item(0, 10_000, [Part("x")])), [84])  # two lines max

    def test_dialogue_budget_is_shared(self):
        item = Item(0, 3000, [Part("Yes."), Part("Where were you last night?")])
        self.assertEqual(limits.budgets(item), [6, 42])

    def test_tight(self):
        self.assertTrue(limits.is_tight("You're lucky your blood's still flowing.", 40))
        self.assertFalse(limits.is_tight("Thank you.", 40))


if __name__ == "__main__":
    unittest.main()
