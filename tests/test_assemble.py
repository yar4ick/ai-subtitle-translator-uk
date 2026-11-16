import unittest

from aisubs import assemble
from aisubs.prepare import Item, Part


class WrapTest(unittest.TestCase):
    def test_short_line(self):
        self.assertEqual(assemble.wrap("Коротко."), ["Коротко."])

    def test_lines_fit_and_break_after_comma(self):
        lines = assemble.wrap("Ми їхали в цей дуже гарний район, і всі вже спали")
        self.assertEqual(lines, ["Ми їхали в цей дуже гарний район,", "і всі вже спали"])

    def test_does_not_end_line_with_preposition(self):
        lines = assemble.wrap("Він сказав, що прийде завтра до нашого старого будинку")
        self.assertEqual(len(lines), 2)
        self.assertTrue(all(len(l) <= 42 for l in lines))
        self.assertNotIn(lines[0].split()[-1], assemble._GLUE_WORDS)

    def test_tags_do_not_count(self):
        self.assertEqual(assemble.wrap("<i>" + "а" * 42 + "</i>"), ["<i>" + "а" * 42 + "</i>"])


class TypographyTest(unittest.TestCase):
    def test_ellipsis_and_quotes(self):
        self.assertEqual(assemble.typography('Він сказав "так"...'), "Він сказав «так»…")
        self.assertEqual(assemble.typography("Якщо це через учора—"), "Якщо це через учора…")
        self.assertEqual(assemble.typography("<i>Зміна пішла б на—</i>"), "<i>Зміна пішла б на…</i>")
        self.assertEqual(assemble.typography("Це — правда."), "Це — правда.")


class CueTextTest(unittest.TestCase):
    def test_dialogue(self):
        it = Item(0, 1, [Part("Yeah."), Part("Stuff.", italic=True)])
        self.assertEqual(assemble.cue_text(it, ["Ага.", "Таке."]), "-Ага.\n<i>-Таке.</i>")

    def test_italic_wrapped_with_position(self):
        it = Item(0, 1, [Part("x", italic=True)], pos="{\\an8}")
        out = assemble.cue_text(it, ["Ми їхали в цей дуже гарний район, і всі вже спали"])
        self.assertEqual(out, "{\\an8}<i>Ми їхали в цей дуже гарний район,\nі всі вже спали</i>")

    def test_skip_copies_source(self):
        it = Item(0, 1, [Part("♪")], skip=True, source="♪ ♪")
        self.assertEqual(assemble.cue_text(it, [None]), "♪ ♪")


if __name__ == "__main__":
    unittest.main()
