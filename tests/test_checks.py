import unittest

from aisubs import checks

CAST = {"Д": "ч", "Гл": "ж", "ч": "ч", "ж": "ж"}


class GenderTest(unittest.TestCase):
    def check(self, text, speakers):
        return checks.gender_conflicts(text, speakers, CAST)

    def test_speaker(self):
        self.assertEqual(self.check("Я ж казав, що просто забув.", "Гл>Д"), ["«я казав», but S is ж"])
        self.assertEqual(self.check("Я ж казала, що просто забула.", "Гл>Д"), [])

    def test_addressee(self):
        self.assertEqual(self.check("Ти першого разу сказав, що грошей нема.", "Д>Гл"), ["«ти сказав», but A is ж"])

    def test_objects_and_nouns_are_not_verbs(self):
        self.assertEqual(self.check("Я не бачила тебе багато років.", "Гл>Д"), [])
        self.assertEqual(self.check("Я тут уже багато років.", "Гл>Д"), [])

    def test_mixed_sentence(self):
        self.assertEqual(self.check("Я пішов, а ти лишилась.", "Д>Гл"), [])

    def test_unknown_or_gender_letters(self):
        self.assertEqual(self.check("Я хотів сказати.", "?>Д"), [])
        self.assertEqual(self.check("Я хотів сказати.", "ж>ч"), ["«я хотів», but S is ж"])

    def test_codes_with_doubt_or_numbers(self):
        self.assertEqual(self.check("Я хотів сказати.", "Гл?>Д"), ["«я хотів», but S is ж"])
        self.assertEqual(self.check("Я хотіла сказати.", "ч1>Д"), ["«я хотіла», but S is ч"])
        self.assertEqual(self.check("Я хотіла сказати.", "x>Д"), [])

    def test_genders_from_glossary(self):
        from aisubs.glossary import Glossary
        g = Glossary(cast=[["Гл", "Gloria", "Глорія", "ж", "", ""], ["Ло", "Lonnie", "Лонні", "ч?", "", ""]])
        self.assertEqual(checks.genders(g), {"ч": "ч", "ж": "ж", "Гл": "ж"})  # "ч?" is a guess: not checked


if __name__ == "__main__":
    unittest.main()
