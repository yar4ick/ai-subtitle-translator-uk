import unittest

from aisubs import exchange
from aisubs.prepare import Item, Part


def items(*texts) -> list[Item]:
    """Each argument is a cue: a string, a list of dialogue parts, or None for a skipped cue."""
    out = []
    for n, t in enumerate(texts):
        if t is None:
            out.append(Item(n * 1000, n * 1000 + 900, [Part("♪")], skip=True))
        else:
            parts = t if isinstance(t, list) else [t]
            out.append(Item(n * 1000, n * 1000 + 900, [Part(p) for p in parts]))
    return out


class KeysTest(unittest.TestCase):
    def test_numbering_skips_untranslatable_and_splits_dialogue(self):
        its = items("A", None, ["B", "C"], "D")
        self.assertEqual(exchange.chunk_keys(its, (0, 4)), [("1", 0, 0), ("2a", 2, 0), ("2b", 2, 1), ("3", 3, 0)])

    def test_numbering_restarts_per_chunk(self):
        its = items("A", "B", "C")
        self.assertEqual([k for k, _, _ in exchange.chunk_keys(its, (1, 3))], ["1", "2"])


class RequestTest(unittest.TestCase):
    def setUp(self):
        self.items = items("One", "Two", "Three", "Four", "Five")
        self.chunks = [(0, 2), (2, 4), (4, 5)]

    def test_first_chunk(self):
        text = exchange.build_request(self.items, self.chunks, 0, {}, "Film (2020)")
        self.assertIn("Film: Film (2020)", text)
        self.assertIn("TRANSLATE (part 1 of 3):\n1|One\n2|Two\n", text)
        self.assertIn("CONTEXT (following lines, do not translate):\nThree\nFour\n", text)

    def test_context_and_missing_only(self):
        done = {0: {"1": "Один", "2": "Два"}, 1: {"1": "Три"}}
        text = exchange.build_request(self.items, self.chunks, 1, done, "F", brief=True)
        self.assertTrue(text.startswith("CONTEXT (previous lines, already translated):\nOne => Один\nTwo => Два\n"))
        self.assertIn("TRANSLATE (part 2 of 3):\n2|Four\n", text)
        self.assertNotIn("1|Three", text)
        self.assertNotIn("Film:", text)


class ParseAnswerTest(unittest.TestCase):
    def test_plain(self):
        answer, ignored = exchange.parse_answer("1|Один\n2a|Так.\n2b?|Ти прийшла?\n")
        self.assertEqual(answer, {"1": ("Один", False), "2a": ("Так.", False), "2b": ("Ти прийшла?", True)})
        self.assertEqual(ignored, [])

    def test_fence_and_chatter(self):
        answer, ignored = exchange.parse_answer("Ось переклад:\n```\n1|Один\n```\nГотово!")
        self.assertEqual(answer, {"1": ("Один", False)})
        self.assertEqual(ignored, ["Ось переклад:", "Готово!"])

    def test_table(self):
        answer, _ = exchange.parse_answer("| ID | Переклад |\n|---|---|\n| 1 | Один |\n| 2? | Два |")
        self.assertEqual(answer, {"1": ("Один", False), "2": ("Два", True)})

    def test_pipe_inside_text_and_bold_id(self):
        answer, _ = exchange.parse_answer("**3**|Так | ні\n4 ? | Хто?")
        self.assertEqual(answer, {"3": ("Так | ні", False), "4": ("Хто?", True)})

    def test_question_mark_in_text_is_not_a_flag(self):
        self.assertEqual(exchange.parse_answer("5|Де ти?")[0], {"5": ("Де ти?", False)})


if __name__ == "__main__":
    unittest.main()
