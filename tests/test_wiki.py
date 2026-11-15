import unittest
from unittest import mock

from aisubs import glossary, wiki

EN = """Intro text.
== Plot ==
Someone does something.
== Cast ==
{{cast listing|
* [[Jean Reno]] as Léon<ref name="a">{{cite web|title=x}}</ref>
* [[Natalie Portman]] as [[Mathilda Lando|Mathilda]], a girl next door. She is twelve.
* {{sortname|Peter|Appel}} as Malky (seasons 1–2)
* Frank Senger as Fatman
}}
=== Notes ===
* [[Some One]] as Extra Person
== Production ==
* [[Not Cast]] as Nothing
"""

UK = """== Ролі ==
=== Головні ролі ===
{{Gallery
|width=165
|Файл:Jeanreno22.jpg|[[Жан Рено]] — ''Леон Монтана''
}}
=== Другорядні ролі ===
* Пітер Еппел&nbsp;— Малкі<ref>[http://example.org IMDb]</ref>
== Примітки ==
"""

ANIME = """==Characters==
;{{Nihongo|David Martinez|デイビッド|Deibiddo}}
:{{Voiced by|Kenn|Zach Aguilar}}
:A reckless street kid. He becomes an edgerunner.
;Gloria Martinez
:David's mother.
==Production==
"""


class ParseTest(unittest.TestCase):
    def test_english_cast(self):
        self.assertEqual(wiki.entries(EN, wiki._CAST_EN), [
            "Jean Reno as Léon",
            "Natalie Portman as Mathilda, a girl next door.",
            "Peter Appel as Malky",
            "Frank Senger as Fatman",
            "Some One as Extra Person",
        ])

    def test_ukrainian_cast(self):
        self.assertEqual(wiki.entries(UK, wiki._CAST_UK), ["Жан Рено — Леон Монтана", "Пітер Еппел — Малкі"])

    def test_definition_list(self):
        self.assertEqual(wiki.entries(ANIME, wiki._CAST_EN), [
            "David Martinez: A reckless street kid.",
            "Gloria Martinez: David's mother.",
        ])

    def test_character(self):
        self.assertEqual(wiki.character("Natalie Portman as Mathilda, a girl"), "Mathilda")
        self.assertEqual(wiki.character("Пітер Еппел — Малкі"), "Малкі")
        self.assertEqual(wiki.character("David Martinez: A kid."), "David Martinez")

    def test_check_marks_names_missing_from_the_subtitles(self):
        entries, share = wiki.check(["Jean Reno as Léon", "Frank Senger as Fatman", "E R as Mathilda's Sister"], {"leon", "mathilda"})
        self.assertEqual(entries, ["Jean Reno as Léon", "Frank Senger as Fatman [not in the subtitles]", "E R as Mathilda's Sister"])
        self.assertAlmostEqual(share, 2 / 3)


class FetchTest(unittest.TestCase):
    def fake_api(self, host, **params):
        if params.get("list") == "search":
            self.assertIn("Léon The Professional 1994 film", params["srsearch"])
            return {"query": {"search": [{"title": "Professional (disambiguation)"}, {"title": "Léon: The Professional"}]}}
        if host.startswith("en."):
            return {"parse": {"title": "Léon: The Professional", "wikitext": EN, "langlinks": [{"lang": "uk", "title": "Леон (фільм)"}]}}
        return {"parse": {"title": "Леон (фільм)", "wikitext": UK}}

    def test_fetch(self):
        with mock.patch.object(wiki, "_api", self.fake_api):
            title, en, uk_title, uk = wiki.fetch("Léon The Professional (1994)")
        self.assertEqual(title, "Léon: The Professional")
        self.assertEqual(len(en), 5)
        self.assertEqual(uk_title, "Леон (фільм)")
        self.assertIn("UKRAINIAN WIKIPEDIA", wiki.render(title, en, uk_title, uk))

    def test_tv_episode_title(self):
        seen = []

        def api(host, **params):
            seen.append(params["srsearch"])
            return {"query": {"search": [{"title": "Stranger Things"}]}}

        with mock.patch.object(wiki, "_api", api):
            self.assertEqual(wiki.find_article("Stranger Things S01E01 (2016)"), "Stranger Things")
        self.assertEqual(seen, ["Stranger Things 2016 TV series"])

    def test_no_match(self):
        with mock.patch.object(wiki, "_api", lambda host, **p: {"query": {"search": [{"title": "Something Else"}]}}):
            with self.assertRaises(wiki.WikiError):
                wiki.find_article("Lighthouse (2021)")


class CrossCheckTest(unittest.TestCase):
    def test_warnings(self):
        g, _ = glossary.parse("C|Л|Léon|Леон|ч|кілер|тихий\nC|Х|Hans Gruber|Ганс|ч|?|?\n")
        found = [{"name": "Hans", "count": 7}, {"name": "Mathilda", "count": 12}, {"name": "Mom", "count": 9}, {"name": "Leon", "count": 30}, {"name": "Tony", "count": 2}]
        warnings = glossary.cross_check(g, found, {"leon", "mathilda", "tony"})
        self.assertEqual(warnings, [
            "Х Hans Gruber: the name never occurs in the subtitles (another film? a guess?)",
            "Mathilda occurs 12 times but is not in CAST or TERMS",
        ])



class GenderCheckTest(unittest.TestCase):
    LINES = [
        "Where's Gloria? She was here.", "Gloria said she'd call.", "Did you see her?",
        "Mrs. Martinez is late.", "Gloria, wait!", "David, she's gone.",
        "- Who is David?\n- Her new boyfriend.",
    ]

    def test_contradiction(self):
        g, _ = glossary.parse("C|Г|Gloria Martinez|Глорія|ч|мати|тепла\nC|Д|David Martinez|Девід|ч|син|зухвалий\n")
        self.assertEqual(glossary.gender_warnings(g, self.LINES), [
            "Г Gloria Martinez: CAST says ч, but the subtitles say she/her about them (4 vs 0); check the gender"])

    def test_no_warning_when_right_or_spoken_to(self):
        g, _ = glossary.parse("C|Г|Gloria Martinez|Глорія|ж|мати|тепла\nC|Д|David Martinez|Девід|ч|син|зухвалий\n")
        self.assertEqual(glossary.gender_warnings(g, self.LINES), [])  # "David, she's…" and "- Her…" are not about David
        self.assertEqual(glossary.gender_evidence(self.LINES, "David"), (0, 0))


class CommandTest(unittest.TestCase):
    def test_prepare_with_wikipedia(self):
        import shutil, tempfile
        from pathlib import Path
        from tests.test_cli import FIXTURES, run

        tmp = Path(tempfile.mkdtemp())
        try:
            film = tmp / "Lighthouse.2021.en.srt"
            shutil.copy(FIXTURES / "basic.srt", film)
            cast = "== Cast ==\n* [[A B]] as Marta\n* [[C D]] as Hans Gruber\n"

            def api(host, **params):
                if params.get("list") == "search":
                    return {"query": {"search": [{"title": "Lighthouse (2021 film)"}]}}
                return {"parse": {"title": "Lighthouse (2021 film)", "wikitext": cast, "langlinks": []}}

            with mock.patch.object(wiki, "_api", api):
                code, out = run("prepare", str(film), "--wikipedia")
            self.assertEqual(code, 0, out)
            self.assertIn("Wikipedia: 2 cast entries", out)
            _, request = run("glossary", str(film))
            self.assertIn("A B as Marta\nC D as Hans Gruber [not in the subtitles]\n", request)

            def offline(host, **params):
                raise wiki.WikiError("no network")

            with mock.patch.object(wiki, "_api", offline):
                code, out = run("prepare", str(film), "--force", "--wikipedia")
            self.assertEqual(code, 0, out)
            self.assertIn("Wikipedia: skipped (no network)", out)
            _, request = run("glossary", str(film))
            self.assertNotIn("WIKIPEDIA (cast", request)  # the old list went with --force
        finally:
            shutil.rmtree(tmp)


if __name__ == "__main__":
    unittest.main()
