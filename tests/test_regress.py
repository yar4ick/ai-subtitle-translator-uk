import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

import regress  # noqa: E402


class RegressTest(unittest.TestCase):
    def test_request_has_every_line(self):
        request = regress.build(regress.SCENES)
        self.assertIn("GLOSSARY", request)
        _, lines, _ = regress.load(regress.SCENES)
        for key, _, english, _ in lines:
            self.assertIn(f"{key}|", request)
            self.assertIn(english, request)
        self.assertNotIn("##", request)

    def test_check(self):
        answer = "1|Е>Р|Знову запізнився, тату? Ключі забула?\n8|Р>Т|Лайно.\n17|-|Ласкаво просимо до Ріверсайда.\n"
        n, failed = regress.check(answer, regress.SCENES)
        self.assertEqual(n["gender"], 1)  # «забула» about Р
        self.assertEqual(n["forbidden"], 1)  # «Лайно» for «No shit.»
        self.assertEqual(n["required"], 1)  # neither «забув» nor «лишив»
        self.assertEqual(n["missing"], n["lines"] - 3)


if __name__ == "__main__":
    unittest.main()
