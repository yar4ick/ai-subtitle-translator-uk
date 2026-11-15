import importlib.util
import unittest
from pathlib import Path

from aisubs.srt import Cue

_spec = importlib.util.spec_from_file_location("compare", Path(__file__).parent.parent / "tools" / "compare.py")
compare = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(compare)

EN = ["I did it.", "Did you come?", "This is Ethan.", "Fine.", "They left.", "Thank you."]
OURS = ["Я це зробила.", "Ти прийшов?", "Це Ітан.", "Добре.", "Вони пішли.", "Дякую вам."]
REF = ["Я це зробив.", "Ви прийшли?", "Це Ітен.", "Гаразд.", "Вони пішли.", "Дякую тобі."]
SCALE, OFFSET = 25 / 23.976, 2400


def cues(texts, scale=1.0, offset=0):
    return [Cue(round((k * 60_000 - offset) / scale), round((k * 60_000 + 2000 - offset) / scale), t) for k, t in enumerate(texts, 1)]


class CompareTest(unittest.TestCase):
    def test_timing_is_detected(self):
        name, _, offset = compare.detect_timing(cues(OURS), cues(REF, SCALE, OFFSET))
        self.assertEqual(name, "25→23.976")
        self.assertAlmostEqual(offset, OFFSET, delta=200)

    def test_alignment(self):
        groups = compare.align(cues(OURS), cues(REF, SCALE, OFFSET), SCALE, OFFSET)
        self.assertEqual(groups, [([k], [k]) for k in range(6)])

    def test_gender_and_formality(self):
        self.assertEqual(compare.gender_marks("Я це зробила, а вони пішли"), {"зроби": "ж", "піш": "мн"})
        self.assertEqual(compare.formality("Дякую вам"), "ви")
        self.assertEqual(compare.formality("Ти і ви"), "")

    def test_report(self):
        text = compare.report(cues(EN), cues(OURS), cues(REF, SCALE, OFFSET), "Test", samples=3)
        self.assertIn("## Розбіжності в роді й числі (1)", text)
        self.assertIn("| 1 | I did it. | Я це зробила. | Я це зробив. | зроби-: ж≠ч |", text)
        self.assertIn("## Розбіжності ти / ви (2)", text)
        self.assertIn("| Ітан | 1 | Ітен | 1 |", text)
        self.assertIn("частота кадрів 25→23.976", text)


if __name__ == "__main__":
    unittest.main()
