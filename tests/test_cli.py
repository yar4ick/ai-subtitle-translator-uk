import contextlib
import io
import re
import shutil
import tempfile
import unittest
from pathlib import Path

from aisubs import cli, srt

FIXTURES = Path(__file__).parent / "fixtures"


def run(*argv, stdin: str = "") -> tuple[int, str]:
    out = io.StringIO()
    old_stdin = cli.sys.stdin
    cli.sys.stdin = io.StringIO(stdin)
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            code = cli.main(list(argv))
    finally:
        cli.sys.stdin = old_stdin
    return code, out.getvalue()


def fake_translate(request: str, drop: str | None = None) -> str:
    """Answer every TRANSLATE line with "UK:" + text, optionally leaving one key out."""
    body = request.split("TRANSLATE")[1].split("CONTEXT (following")[0]
    lines = []
    for key, text in re.findall(r"^(\d+[a-z]?)\|(?:S=[^|]+\|)?(?:≤\d+\|)?(.*)$", body, re.M):
        if key != drop:
            lines.append(f"{key}|UK:{text}")
    return "```\n" + "\n".join(lines) + "\n```\n"


def ukrainian(request: str) -> str:
    """A short Ukrainian answer for every ID of a request, which passes the checks."""
    body = request.split("TRANSLATE")[1].split("CONTEXT (following")[0]
    keys = [line.split("|")[0] for line in body.splitlines() if line[:1].isdigit()]
    return "".join(f"{key}|ж>ч|Що?\n" for key in keys)


class EndToEndTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.film = self.tmp / "Lighthouse.2021.en.srt"
        shutil.copy(FIXTURES / "basic.srt", self.film)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_full_cycle(self):
        code, out = run("prepare", str(self.film), "--chunk-size", "3")
        self.assertEqual(code, 0, out)
        self.assertIn("Title: Lighthouse (2021)", out)

        code, request = run("next", str(self.film))
        self.assertIn("Translate film subtitles", request)
        code, out = run("import", str(self.film), stdin=fake_translate(request, drop="1"))
        self.assertEqual(code, 2)
        self.assertIn("missing 1 lines: 1", out)

        code, request = run("next", str(self.film), "--brief")
        self.assertNotIn("Translate film subtitles", request)
        self.assertIn("TRANSLATE (part 1 of", request)
        run("import", str(self.film), stdin=fake_translate(request))

        code, out = run("assemble", str(self.film))
        self.assertEqual(code, 1)  # other parts are not translated yet
        while True:
            code, request = run("next", str(self.film), "--brief")
            if "TRANSLATE" not in request:
                break
            run("import", str(self.film), stdin=fake_translate(request))

        code, out = run("assemble", str(self.film))
        self.assertEqual(code, 0, out)
        result = srt.read(self.tmp / "Lighthouse.2021.uk.srt").cues
        source = srt.read(self.film).cues
        # [waves crashing] is SDH-only and dropped; other timings are unchanged
        del source[2]
        self.assertEqual([(c.start, c.end) for c in result], [(c.start, c.end) for c in source])
        self.assertEqual(result[0].text, "<i>UK:The lighthouse keeper\ncounted the ships every night.</i>")
        self.assertEqual(result[1].text, "-UK:Did you see that?\n-UK:See what?")
        self.assertEqual(result[2].text, "UK:Nobody comes here anymore.")  # SDH label stripped

    def test_sintel(self):
        film = self.tmp / "sintel_en.srt"
        shutil.copy(FIXTURES / "sintel_en.srt", film)
        code, out = run("prepare", str(film), "--title", "Sintel (2010)")
        self.assertEqual(code, 0, out)
        self.assertNotIn("warning", out)
        _, request = run("next", str(film))
        self.assertIn("1|This blade has a dark past.", request)
        self.assertIn("3|≤58|You're a fool for traveling alone, so completely unprepared.", request)
        self.assertIn("4|You're lucky your blood's still flowing.", request)
        run("import", str(film), stdin=fake_translate(request))
        code, out = run("assemble", str(film))
        self.assertEqual(code, 0, out)
        result = srt.read(self.tmp / "sintel.uk.srt")
        self.assertEqual(len(result.cues), 26)
        self.assertEqual(result.warnings, [])

    def test_import_next_prints_the_next_request(self):
        run("prepare", str(self.film), "--chunk-size", "3")
        _, request = run("next", str(self.film))
        code, out = run("import", str(self.film), "--next", stdin=fake_translate(request))
        self.assertEqual(code, 0)
        self.assertIn("TRANSLATE (part 2 of", out)
        self.assertNotIn("Translate film subtitles", out)
        _, request = run("next", str(self.film))
        first = request.split("TRANSLATE (part 2 of")[1].splitlines()[1].split("|")[0]
        self.assertNotEqual(first, "1")  # IDs run through the film
        code, out = run("import", str(self.film), "--next", stdin=fake_translate(request, drop=first))
        self.assertEqual(code, 2)
        self.assertIn("TRANSLATE (part 2 of", out)

    def test_every_fourth_part_comes_in_full(self):
        film = self.tmp / "sintel.srt"
        shutil.copy(FIXTURES / "sintel_en.srt", film)
        run("prepare", str(film), "--chunk-size", "2")
        _, request = run("next", str(film))
        seen = []
        for part in range(2, 7):
            code, out = run("import", str(film), "--next", stdin=ukrainian(request))
            self.assertIn(f"TRANSLATE (part {part} of", out)
            seen.append("Translate film subtitles" in out)
            request = out
        self.assertEqual(seen, [False, False, False, True, False])  # part 5 is full

    def test_an_answer_sent_twice_is_not_taken_for_the_next_part(self):
        run("prepare", str(self.film), "--chunk-size", "2")
        _, request = run("next", str(self.film))
        answer = fake_translate(request)
        run("import", str(self.film), stdin=answer)
        code, out = run("import", str(self.film), "--next", stdin=answer)
        self.assertEqual(code, 0, out)
        self.assertIn("from part 1, which is already translated: nothing saved", out)
        self.assertIn("TRANSLATE (part 2 of", out)
        _, out = run("status", str(self.film))
        self.assertRegex(out, r"part +2/\d+: todo")

    def test_prepare_again_continues_instead_of_deleting(self):
        run("prepare", str(self.film), "--chunk-size", "2")
        _, request = run("next", str(self.film))
        run("import", str(self.film), stdin=fake_translate(request))
        code, out = run("prepare", str(self.film))
        self.assertEqual(code, 0, out)
        self.assertIn("Already prepared", out)
        self.assertIn("(part 2 of", out)
        _, out = run("status", str(self.film))
        self.assertRegex(out, r"part +1/\d+: done")

    def test_fewer_steps_for_an_agent(self):
        code, out = run("prepare", str(self.film), "--glossary")
        self.assertIn("Build a translation glossary", out)
        code, out = run("glossary", str(self.film), "-", "--next", stdin="C|М|Marta|Марта|ж|доглядачка|сувора\n")
        self.assertIn("Names: Марта (ж)", out)
        self.assertIn("Translate film subtitles", out)  # the first full request
        request = out.split("Names: Марта (ж)")[1]
        code, out = run("import", str(self.film), "--next", stdin=ukrainian(request))
        self.assertIn("Done.", out)
        self.assertTrue((self.tmp / "Lighthouse.2021.uk.srt").exists())

    def test_a_foreign_uk_srt_is_not_overwritten(self):
        own = self.tmp / "Lighthouse.2021.uk.srt"
        own.write_text("1\n00:00:01,000 --> 00:00:02,000\nчужий переклад\n", encoding="utf-8")
        run("prepare", str(self.film))
        _, request = run("next", str(self.film))
        code, out = run("import", str(self.film), "--next", stdin=ukrainian(request))
        self.assertEqual(code, 4)
        self.assertIn("was not written by aisubs: NOT overwritten", out)
        code, out = run("assemble", str(self.film))
        self.assertEqual(code, 1)
        self.assertIn("чужий переклад", own.read_text(encoding="utf-8"))
        code, out = run("assemble", str(self.film), "--force")
        self.assertEqual(code, 0, out)
        code, out = run("assemble", str(self.film))  # now it is ours
        self.assertEqual(code, 0, out)

    def test_translator_adds_a_character(self):
        run("prepare", str(self.film))
        run("glossary", str(self.film), "-", stdin="C|М|Marta|Марта|ж|доглядачка|сувора\n")
        _, request = run("next", str(self.film))
        code, out = run("import", str(self.film), stdin=fake_translate(request) + "+|C|К|Katsuo|Кацуо|ч|однокласник\n+|C|М|Mike|Майк|ч|x\n+|gonk=бовдур\n")
        self.assertIn("glossary: new characters К Кацуо (ч)", out)
        self.assertIn("glossary: added gonk=бовдур", out)
        text = (self.tmp / "Lighthouse.2021.en.aisubs" / "glossary.txt").read_text(encoding="utf-8")
        self.assertIn("C|К|Katsuo|Кацуо|ч|однокласник", text)
        self.assertNotIn("Майк", text)  # the code М is taken

    def test_an_answer_for_another_unfinished_part_goes_there(self):
        run("prepare", str(self.film), "--chunk-size", "2")
        _, request = run("next", str(self.film), "--part", "2")
        code, out = run("import", str(self.film), stdin=fake_translate(request))
        self.assertRegex(out, r"part 2/\d+: accepted")

    def test_glossary_flow(self):
        run("prepare", str(self.film))
        code, request = run("glossary", str(self.film))
        self.assertIn("Build a translation glossary", request)
        self.assertIn("\nMarta: Nobody comes here anymore.\n", request)  # SDH speaker kept in the sample
        code, out = run("glossary", str(self.film), "-", stdin="C|М|Marta|Марта|ж|доглядачка маяка|сувора\nT|lighthouse|маяк\n")
        self.assertEqual(code, 0, out)
        self.assertIn("1 characters, 0 pairs, 1 terms", out)
        _, request = run("next", str(self.film))
        self.assertIn("GLOSSARY\nCAST (code name — gender; role; voice):\nМ Марта (Marta) — ж; доглядачка маяка; сувора\nTERMS: lighthouse=маяк\n", request)
        _, brief = run("next", str(self.film), "--brief")
        self.assertNotIn("GLOSSARY", brief)
        answer = fake_translate(request) + "+|keeper=доглядач\n"
        code, out = run("import", str(self.film), stdin=answer)
        self.assertIn("glossary: added keeper=доглядач", out)
        self.assertNotIn("ignored", out)

    def test_prepare_refuses_to_overwrite_translations(self):
        run("prepare", str(self.film))
        _, request = run("next", str(self.film))
        run("import", str(self.film), stdin=fake_translate(request))
        code, out = run("prepare", str(self.film))
        self.assertEqual(code, 0)
        self.assertIn("All parts are translated", out.replace("all parts", "All parts"))
        self.assertIn("--force", out)  # mentioned, but only for starting over
        self.assertTrue(any((self.tmp / "Lighthouse.2021.en.aisubs" / "done").glob("*.json")))

    def test_changed_source_is_detected(self):
        run("prepare", str(self.film))
        self.film.write_text(self.film.read_text(encoding="utf-8") + "\n6\n02:00:02,000 --> 02:00:03,000\nMore\n", encoding="utf-8")
        code, out = run("next", str(self.film))
        self.assertEqual(code, 1)
        self.assertIn("changed since prepare", out)


if __name__ == "__main__":
    unittest.main()
