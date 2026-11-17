import unittest

from aisubs import candidates
from aisubs.prepare import Item, Part


def items(*lines, speaker=""):
    return [Item(n * 10_000, n * 10_000 + 1000, [Part(t, speaker=speaker)]) for n, t in enumerate(lines)]


def names(its):
    return {c.name: (c.count, c.vocative) for c in candidates.find(its)}


class FindTest(unittest.TestCase):
    def test_names_and_vocatives(self):
        found = names(items(
            "We met Gloria at Night City Medical.",
            "Thanks, Gloria.",
            "Gloria, wait!",
            "Is that David's jacket?",
        ))
        self.assertEqual(found["Gloria"], (3, 2))
        self.assertEqual(found["David"], (1, 0))
        self.assertIn("Night City Medical", found)

    def test_sentence_start_words_are_not_names(self):
        found = names(items("Well, I don't know.", "Look, it's late. Okay?", "It's Tonto, downstairs.", "Come on, okay?"))
        self.assertEqual(found, {"Tonto": (1, 0)})

    def test_characters_naming_themselves(self):
        found = {c.name: c.intro for c in candidates.find(items(
            "<i>Katsuo here. Heard about your mom.</i>", "I'm Lucy.", "Sign here.", "From here on out, we run.",
            "It's Gloria. Call me back.", "Where is Lucy now?", "Thanks, Gloria."))}
        self.assertEqual(found, {"Katsuo": 1, "Lucy": 1, "Gloria": 1})  # Lucy and Gloria are named elsewhere

    def test_not_introductions(self):
        # Capitalized words are still candidates as names (London), but not as characters naming themselves
        found = {c.name for c in candidates.find(items(
            "Not here.", "Nothing here.", "You here?", "It's Christmas.", "This is London.", "I'm Italian.",
            "I'm Batman.", "Why here? Because.", "Katsuo here. Heard about your mom.")) if c.intro}
        self.assertEqual(found, {"Katsuo"})

    def test_lowercase_forms_of_address_need_two_uses(self):
        self.assertNotIn("kid", names(items("Easy, kid.")))
        self.assertEqual(names(items("Easy, kid.", "Run, kid!"))["kid"], (2, 2))

    def test_titles(self):
        self.assertIn("Mrs. Lando", names(items("Good morning, Mrs. Lando.")))

    def test_sdh_speakers_first(self):
        its = items("Where are you?", speaker="Sophie") + items("We saw Ethan there.", "Ethan is late.")
        found = candidates.find(its)
        self.assertEqual((found[0].name, found[0].speaker), ("Sophie", 1))
        self.assertEqual(found[0].examples, [])

    def test_examples_are_limited(self):
        c = candidates.find(items("I saw Leon.", "Ask Leon.", "Call Leon."))[0]
        self.assertEqual(c.examples, ["I saw Leon.", "Ask Leon."])


class SampleTest(unittest.TestCase):
    def test_first_lines_and_scene_openings(self):
        its = [Item(n * 1000, n * 1000 + 900, [Part(f"line {n}")]) for n in range(200)]
        for it in its[150:]:  # a second scene after a long pause
            it.start += 60_000
            it.end += 60_000
        sample = candidates.sample(its)
        self.assertEqual(sample[:2], ["line 0", "line 1"])
        self.assertIn("line 150", sample)
        self.assertNotIn("line 100", sample)
