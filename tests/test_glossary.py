import unittest

from aisubs import glossary

ANSWER = """Ось глосарій:
```
STYLE|аніме-кіберпанк, вуличний сленг; лайка міцна
PLOT|Підліток Девід після смерті матері стає найманцем.
C|Д|David Martinez|Девід Мартінес|ч|17, школяр|зухвалий, сленг
C|Ґ|Gloria Martinez|Ґлорія Мартінес|ж|його мати, парамедик|втомлена, тепла
P|Д|Ґ|ти
P|Л|Д|ти|спершу ви?
T|choom|чумба
T|eddies|едді
```
"""


class GlossaryTest(unittest.TestCase):
    def test_parse_and_dump(self):
        g, ignored = glossary.parse(ANSWER)
        self.assertEqual(ignored, ["Ось глосарій:"])
        self.assertEqual(g.style, "аніме-кіберпанк, вуличний сленг; лайка міцна")
        self.assertEqual(g.cast[1], ["Ґ", "Gloria Martinez", "Ґлорія Мартінес", "ж", "його мати, парамедик", "втомлена, тепла"])
        self.assertEqual(g.pairs[0], ["Д", "Ґ", "ти", ""])
        self.assertEqual(glossary.parse(glossary.dumps(g))[0], g)

    def test_render(self):
        text = glossary.render(glossary.parse(ANSWER)[0])
        self.assertIn("Д Девід Мартінес (David Martinez) — ч; 17, школяр; зухвалий, сленг", text)
        self.assertIn("PAIRS: Д→Ґ ти; Л→Д ти (спершу ви?)", text)
        self.assertIn("TERMS: choom=чумба; eddies=едді", text)

    def test_additions(self):
        g = glossary.parse(ANSWER)[0]
        additions = glossary.parse_additions("1|Привіт\n+|Night City=Найт-Сіті\n+| choom = чум\n")
        self.assertEqual(additions, [("Night City", "Найт-Сіті"), ("choom", "чум")])
        self.assertEqual(glossary.add_terms(g, additions), [("Night City", "Найт-Сіті")])
        self.assertEqual(g.terms[-1], ["Night City", "Найт-Сіті"])

    def test_empty(self):
        self.assertTrue(glossary.parse("nothing here")[0].is_empty())


if __name__ == "__main__":
    unittest.main()
