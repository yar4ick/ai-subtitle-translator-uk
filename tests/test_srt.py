import codecs
import tempfile
import unittest
from pathlib import Path

from aisubs import srt

FIXTURES = Path(__file__).parent / "fixtures"


def parse_str(text: str) -> srt.SrtFile:
    return srt.parse(text.encode("utf-8"))


class RoundTripTest(unittest.TestCase):
    def test_canonical_file_is_unchanged(self):
        data = (FIXTURES / "basic.srt").read_bytes()
        parsed = srt.parse(data)
        self.assertEqual(parsed.warnings, [])
        self.assertEqual(srt.dumps(parsed.cues).encode("utf-8"), data)

    def test_crlf_and_bom_are_kept_when_asked(self):
        text = (FIXTURES / "basic.srt").read_text(encoding="utf-8")
        data = codecs.BOM_UTF8 + text.replace("\n", "\r\n").encode("utf-8")
        parsed = srt.parse(data)
        self.assertTrue(parsed.bom)
        self.assertEqual(parsed.newline, "\r\n")
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "out.srt"
            srt.write(out, parsed.cues, bom=parsed.bom, newline=parsed.newline)
            self.assertEqual(out.read_bytes(), data)


class ParseTest(unittest.TestCase):
    def test_fields(self):
        cues = srt.read(FIXTURES / "basic.srt").cues
        self.assertEqual(len(cues), 5)
        self.assertEqual(cues[0].start, 1000)
        self.assertEqual(cues[0].end, 3500)
        self.assertEqual(cues[0].text, "<i>The lighthouse keeper\ncounted the ships every night.</i>")
        self.assertEqual(cues[4].start, 7_199_999)

    def test_dot_and_short_fraction_in_time(self):
        cues = parse_str("1\n00:00:01.5 --> 00:00:02.25\nHi\n").cues
        self.assertEqual((cues[0].start, cues[0].end), (1500, 2250))

    def test_missing_blank_lines(self):
        cues = parse_str("1\n00:00:01,000 --> 00:00:02,000\nOne\n2\n00:00:03,000 --> 00:00:04,000\nTwo\n").cues
        self.assertEqual([c.text for c in cues], ["One", "Two"])

    def test_blank_lines_inside_text_and_trailing_spaces(self):
        cues = parse_str("1\n00:00:01,000 --> 00:00:02,000\nOne  \n\n\ntwo\n\n\n\n2\n00:00:03,000 --> 00:00:04,000\nThree").cues
        self.assertEqual([c.text for c in cues], ["One\ntwo", "Three"])

    def test_broken_and_missing_numbers(self):
        parsed = parse_str(
            "7\n00:00:01,000 --> 00:00:02,000\nA\n\n"
            "00:00:03,000 --> 00:00:04,000\nB\n\n"
            "7\n00:00:05,000 --> 00:00:06,000\nC\n"
        )
        self.assertEqual([c.text for c in parsed.cues], ["A", "B", "C"])
        self.assertIn("cue 2: missing number", parsed.warnings)
        self.assertIn("cue numbers are not sequential; output is renumbered", parsed.warnings)
        self.assertTrue(srt.dumps(parsed.cues).startswith("1\n"))

    def test_position_suffix_is_kept(self):
        text = "1\n00:00:01,000 --> 00:00:02,000  X1:100 X2:200 Y1:10 Y2:20\nHi\n"
        self.assertEqual(srt.dumps(parse_str(text).cues), text)

    def test_empty_cue(self):
        parsed = parse_str("1\n00:00:01,000 --> 00:00:02,000\n\n2\n00:00:03,000 --> 00:00:04,000\nB\n")
        self.assertEqual([c.text for c in parsed.cues], ["", "B"])
        self.assertEqual(srt.parse(srt.dumps(parsed.cues).encode()).cues, parsed.cues)

    def test_garbage_before_first_cue(self):
        parsed = parse_str("Subtitles downloaded from somewhere\n\n1\n00:00:01,000 --> 00:00:02,000\nA\n")
        self.assertEqual(len(parsed.cues), 1)
        self.assertIn("ignored text before the first cue", parsed.warnings)

    def test_timing_warnings(self):
        parsed = parse_str(
            "1\n00:00:05,000 --> 00:00:04,000\nA\n\n"
            "2\n00:00:06,000 --> 00:00:08,000\nB\n\n"
            "3\n00:00:07,000 --> 00:00:09,000\nC\n\n"
            "4\n00:00:01,000 --> 00:00:02,000\nD\n"
        )
        self.assertEqual(
            parsed.warnings,
            ["cue 1: ends before it starts", "cue 3: overlaps the previous cue", "cue 4: starts before the previous cue"],
        )

    def test_no_cues(self):
        self.assertEqual(parse_str("just text").warnings, ["no timing lines found"])


class EncodingTest(unittest.TestCase):
    TEXT = "1\n00:00:01,000 --> 00:00:02,000\n“Café” — naïve\n"

    def test_utf8(self):
        parsed = srt.parse(self.TEXT.encode("utf-8"))
        self.assertEqual((parsed.encoding, parsed.bom), ("utf-8", False))
        self.assertEqual(parsed.cues[0].text, "“Café” — naïve")

    def test_utf16_with_bom(self):
        for codec in ("utf-16-le", "utf-16-be"):
            bom = codecs.BOM_UTF16_LE if codec.endswith("le") else codecs.BOM_UTF16_BE
            parsed = srt.parse(bom + self.TEXT.encode(codec))
            self.assertEqual(parsed.encoding, "utf-16")
            self.assertEqual(parsed.cues[0].text, "“Café” — naïve")

    def test_cp1252_fallback(self):
        parsed = srt.parse(self.TEXT.encode("cp1252"))
        self.assertEqual(parsed.encoding, "cp1252")
        self.assertEqual(parsed.cues[0].text, "“Café” — naïve")

    def test_explicit_encoding(self):
        parsed = srt.parse("1\n00:00:01,000 --> 00:00:02,000\nÄpfel\n".encode("latin-1"), encoding="latin-1")
        self.assertEqual(parsed.cues[0].text, "Äpfel")

    def test_explicit_utf8_strips_bom(self):
        parsed = srt.parse(codecs.BOM_UTF8 + self.TEXT.encode("utf-8"), encoding="utf-8")
        self.assertTrue(parsed.bom)
        self.assertEqual(parsed.cues[0].start, 1000)


class TimeTest(unittest.TestCase):
    def test_format(self):
        self.assertEqual(srt.format_time(0), "00:00:00,000")
        self.assertEqual(srt.format_time(7_199_999), "01:59:59,999")


if __name__ == "__main__":
    unittest.main()
