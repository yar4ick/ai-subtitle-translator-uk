import shutil
import tempfile
import unittest
from pathlib import Path

from aisubs import glossary, validate
from aisubs.project import Project

from tests.test_cli import FIXTURES, run

GLOSSARY = """C|Л|Leon|Леон|ч|кілер|стриманий
C|С|Norman Stansfield|Норман Стенсфілд|ж|агент|лютий
C|Б|Benny|Бенні|ч|поплічник|грубий
"""


class CheckerTest(unittest.TestCase):
    def setUp(self):
        self.c = validate.Checker(glossary.parse(GLOSSARY)[0])

    def problems(self, source, text, speakers="", limit=None):
        return [m for _, m in self.c.line(source, text, speakers, limit)]

    def test_clean_line(self):
        self.assertEqual(self.problems("Leon, wait!", "Леоне, стривай!"), [])
        self.assertEqual(self.problems("Stansfield is here.", "Стенсфілд тут."), [])

    def test_not_translated(self):
        self.assertEqual(self.problems("Wait here.", "Wait here."), ["not translated"])
        self.assertEqual(self.problems("OK.", "OK."), ["not translated"])

    def test_english_name_left(self):
        self.assertEqual(self.problems("Ask Leon.", "Спитай Leon."), ["name left in English: Leon (glossary: Леон)"])

    def test_latin_inside_a_ukrainian_line(self):
        self.assertEqual(self.problems("All AVs vacate.", "Усім AV звільнити."), ["Latin letters left: AV (transliterate or translate)"])
        self.assertEqual(self.problems("The Strongarms 400.", "Strongarms 400 справді."), ["Latin letters left: Strongarms (transliterate or translate)"])
        self.assertEqual(self.problems("Louis XIV.", "Людовік XIV."), [])  # Roman numerals

    def test_russian_letters(self):
        self.assertEqual(self.problems("Yes.", "Ещё бы."), ["Russian letters: ыё"])

    def test_format_junk_and_tags(self):
        self.assertIn("pieces of the answer format", self.problems("Hi.", "Л>М|Привіт.")[0])
        self.assertIn("pieces of the answer format", self.problems("Hi.", "≤12|Привіт.")[0])
        self.assertEqual(self.problems("Hi.", "<i>Привіт.</i>"), [])
        self.assertIn("broken tags", self.problems("Hi.", "<(i>Привіт.")[0])
        self.assertIn("broken tags", self.problems("Hi.", "<i>Привіт.")[0])

    def test_too_long(self):
        self.assertEqual(self.problems("Hi.", "Привіт.", limit=5), ["too long: 7 characters"])
        self.assertEqual(self.problems("Hi.", "Привіт.", limit=7), [])

    def test_gender(self):
        self.assertEqual(self.problems("I forgot.", "Я забув.", "С>Л"), ["gender: «я забув», but S is ж"])

    def test_a_guessed_gender_is_not_checked(self):
        c = validate.Checker(glossary.parse("C|Х|Alex|Алекс|ж?|?|?\nC|Л|Leon|Леон|ч|кілер|тихий\n")[0])
        self.assertEqual(c.line("I forgot.", "Я забув.", "Х>Л"), [])

    def test_plural_nouns_in_iv_are_not_verbs(self):
        self.assertEqual(self.problems("I'll call the cops.", "Я покличу копів.", "С>Л"), [])
        self.assertEqual(self.problems("I'm afraid of these dogs.", "Я боюся цих псів.", "С>Л"), [])
        self.assertEqual(self.problems("I wanted it.", "Я хотів цього.", "С>Л"), ["gender: «я хотів», but S is ж"])
        self.assertEqual(self.problems("I really wanted it.", "Я так хотів цього.", "С>Л"), ["gender: «я хотів», but S is ж"])

    def test_misspelled_name_only_when_the_source_has_it(self):
        self.assertEqual(self.problems("Stansfield!", "Стенсфільд!"), ["name spelled «Стенсфільд», glossary: «Стенсфілд»"])
        self.assertEqual(self.problems("Bonnie and Clyde.", "Бонні й Клайд."), [])
        self.assertEqual(self.problems("Benny!", "Бенні! Бенні!"), [])
        self.assertEqual(self.problems("With Stansfield.", "Зі Стенсфілдом."), [])  # a case form


def answer_all(request: str, text_for=lambda key, source: "Що?") -> str:
    lines = []
    for line in request.splitlines():
        key, sep, rest = line.partition("|")
        if sep and key[:1].isdigit():
            lines.append(f"{key}|Л>Б|{text_for(key, rest)}")
    return "\n".join(lines) + "\n"


class FixFlowTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.film = self.tmp / "Lighthouse.2021.en.srt"
        shutil.copy(FIXTURES / "basic.srt", self.film)
        run("prepare", str(self.film))

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_one_retry_then_review(self):
        _, request = run("next", str(self.film))
        bad = answer_all(request, lambda key, src: "Що?" * 30 if key == "2b" else "Що?")
        code, out = run("import", str(self.film), stdin=bad)
        self.assertEqual(code, 0, out)
        self.assertIn("To fix (the AI gets these lines again): 1", out)
        self.assertIn("Next: aisubs fix", out)

        code, out = run("validate", str(self.film))
        self.assertEqual(code, 2)
        self.assertTrue((self.tmp / "Lighthouse.2021.en.aisubs" / "report.txt").exists())

        code, request = run("fix", str(self.film), "--brief")
        self.assertIn("FIX (part 1 of 1)", request)
        self.assertIn("2b|≤", request)
        self.assertIn("  wrong: too long", request)
        self.assertIn("  before: Did you see that? => Що?", request)
        self.assertIn("  after: Nobody comes here anymore. => Що?", request)
        self.assertNotIn("\n1|", request)

        # Still too long after the retry: it goes to review, the AI is not asked again
        code, out = run("import", str(self.film), "--fix", stdin="2b|Б>Л|" + "Що?" * 30 + "\n1|Л>Б|Інше.\n")
        self.assertEqual(code, 0, out)
        self.assertIn("accepted 1 lines", out)  # 1 was not asked for
        self.assertIn("(after a retry)", out)
        self.assertIn("Nothing to fix", out)
        project = Project(self.film).load()
        self.assertEqual(project.retries()[0], {"2b": 1})
        self.assertEqual(project.done()[0]["1"], "Що?")

    def test_fix_and_next(self):
        _, request = run("next", str(self.film))
        run("import", str(self.film), stdin=answer_all(request, lambda key, src: "Wait." if key == "1" else "Що?"))
        code, out = run("import", str(self.film), "--fix", "--next", stdin="1|Л>Б|Чекай.\n")
        self.assertIn("Nothing to fix.", out)
        self.assertIn("Lighthouse.2021.uk.srt. Done.", out)  # --next finishes the job
        self.assertTrue((self.tmp / "Lighthouse.2021.uk.srt").exists())

    def test_refusal(self):
        _, request = run("next", str(self.film))
        code, out = run("import", str(self.film), stdin="I'm sorry, but I can't help with this request.")
        self.assertEqual(code, 3)
        self.assertIn("refused", out)
        _, out = run("status", str(self.film))
        self.assertIn("refused", out)
        run("import", str(self.film), stdin=answer_all(request))
        _, out = run("status", str(self.film))
        self.assertNotIn("refused", out)


class ReviewTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.film = self.tmp / "Lighthouse.2021.en.srt"
        shutil.copy(FIXTURES / "basic.srt", self.film)
        run("prepare", str(self.film))
        _, self.glossary_out = run("glossary", str(self.film), "-", stdin="PLOT|Марта сама на маяку.\nC|М|Marta|Марта|ж|доглядачка|сувора\n")
        _, request = run("next", str(self.film))
        answer = answer_all(request).replace("2a|Л>Б|", "2a|М?>Б|")
        run("import", str(self.film), stdin=answer + "@|1-4|Marta alone. 4=М\n")
        self.path = self.tmp / "Lighthouse.2021.en.aisubs" / "review.txt"

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_glossary_names_without_spoilers(self):
        self.assertIn("Names: Марта (ж)", self.glossary_out)
        self.assertNotIn("доглядачка", self.glossary_out)
        self.assertNotIn("маяку", self.glossary_out)

    def test_write_edit_apply(self):
        code, out = run("review", str(self.film))
        self.assertEqual(code, 0, out)
        self.assertIn("1 lines to look at", out)
        text = self.path.read_text(encoding="utf-8")
        self.assertIn("# Codes: М Марта", text)
        self.assertIn("   AI note 1–4: Marta alone. 4=М", text)
        self.assertIn("   Did you see that?\n!  the model was unsure who speaks (?)\n1:2a|М?>Б|Що?\n", text)

        self.path.write_text(text.replace("1:2a|М?>Б|Що?", "1:2a|М>Б|Я забув?"), encoding="utf-8")
        code, out = run("review", str(self.film))
        self.assertEqual(code, 1)
        self.assertIn("not saved yet", out)

        code, out = run("review", str(self.film), "--apply")
        self.assertIn("Saved 1 changed lines: 1:2a", out)
        self.assertIn("gender check: 1:2a|М>Б|Я забув? — «я забув», but S is ж", out)
        project = Project(self.film).load()
        self.assertEqual(project.done()[0]["2a"], "Я забув?")
        self.assertEqual(project.flags()[0], [])

        code, out = run("review", str(self.film))
        self.assertIn("Nothing to review", out)
        code, out = run("validate", str(self.film))
        self.assertNotIn("To fix", out)  # the edited line is not sent back to the AI


if __name__ == "__main__":
    unittest.main()
