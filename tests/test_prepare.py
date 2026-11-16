import unittest

from aisubs import prepare, srt


def item(text: str, keep_sdh: bool = False) -> prepare.Item | None:
    return prepare.clean_cue(srt.Cue(0, 1000, text), keep_sdh)


def texts(it: prepare.Item) -> list[str]:
    return [p.text for p in it.parts]


class CleanCueTest(unittest.TestCase):
    def test_line_breaks_are_joined(self):
        self.assertEqual(texts(item("we were driving up into this\nreally nice neighborhood,")),
                         ["we were driving up into this really nice neighborhood,"])

    def test_whole_cue_italic(self):
        it = item("<i>So we met at a party,\nand it was magic.</i>")
        self.assertEqual(texts(it), ["So we met at a party, and it was magic."])
        self.assertTrue(it.parts[0].italic)

    def test_italic_per_line_is_whole_italic(self):
        it = item("<i>One</i>\n<i>two</i>")
        self.assertEqual((texts(it), it.parts[0].italic), (["One two"], True))

    def test_partial_italic_kept_inline(self):
        it = item("I said <i>never</i>.")
        self.assertEqual((texts(it), it.parts[0].italic), (["I said <i>never</i>."], False))

    def test_dialogue(self):
        it = item("- Yeah.\n- And stuff. Like I...")
        self.assertEqual(texts(it), ["Yeah.", "And stuff. Like I..."])

    def test_dialogue_without_first_dash(self):
        self.assertEqual(texts(item("Are you coming?\n- Sure.")), ["Are you coming?", "Sure."])

    def test_single_dash_is_not_dialogue(self):
        self.assertEqual(texts(item("- I mean, I'll try\nanything.")), ["I mean, I'll try anything."])

    def test_dialogue_italic_one_speaker(self):
        it = item("- Hello?\n<i>- I'm outside.</i>")
        self.assertEqual([p.italic for p in it.parts], [False, True])

    def test_position_tag_and_other_tags(self):
        it = item('{\\an8}<font color="#ffff00">Look &amp; see</font>')
        self.assertEqual((it.pos, texts(it)), ("{\\an8}", ["Look & see"]))

    def test_ads_are_dropped(self):
        self.assertIsNone(item("Subtitles by explosiveskull\nwww.OpenSubtitles.org"))
        self.assertIsNone(item("Synced and corrected by someone"))

    def test_sdh_is_stripped_and_speaker_kept(self):
        it = item("SOPHIE: [laughs] Where are you?")
        self.assertEqual(texts(it), ["Where are you?"])
        self.assertEqual(it.parts[0].speaker, "Sophie")

    def test_speaker_label_forms(self):
        it = item("MAN [on radio]: Copy that.")
        self.assertEqual((texts(it), it.parts[0].speaker), (["Copy that."], "Man"))
        it = item("Man: Where are you?")
        self.assertEqual((texts(it), it.parts[0].speaker), (["Where are you?"], "Man"))
        it = item("Woman #2: Over here!")
        self.assertEqual((texts(it), it.parts[0].speaker), (["Over here!"], "Woman #2"))
        it = item("Look: I told you.")  # not a role
        self.assertEqual((texts(it), it.parts[0].speaker), (["Look: I told you."], ""))

    def test_a_file_in_capitals_has_no_labels_but_roles(self):
        it = prepare.clean_cue(srt.Cue(0, 1000, "I TOLD YOU: GET OUT"), capitals=True)
        self.assertEqual((texts(it), it.parts[0].speaker), (["I TOLD YOU: GET OUT"], ""))
        cues = [srt.Cue(n * 2000, n * 2000 + 1000, t) for n, t in enumerate(["WHERE ARE YOU?"] * 12 + ["I TOLD YOU: GET OUT"] + ["OK."] * 5)]
        items, _ = prepare.make_items(cues)
        self.assertEqual(texts(items[12]), ["I TOLD YOU: GET OUT"])

    def test_web_address_in_the_film_is_kept(self):
        self.assertIsNotNone(prepare.clean_cue(srt.Cue(0, 1000, "Go to www.arasaka.com and log in."), edge=False))
        self.assertIsNone(prepare.clean_cue(srt.Cue(0, 1000, "Go to www.arasaka.com and log in."), edge=True))
        self.assertIsNone(prepare.clean_cue(srt.Cue(0, 1000, "Subtitles by someone"), edge=False))

    def test_sdh_only_cue_is_dropped(self):
        self.assertIsNone(item("[door slams]"))
        self.assertIsNone(item("<i>(phone ringing)</i>"))

    def test_sdh_dialogue_collapses(self):
        self.assertEqual(texts(item("- [laughs]\n- Hi.")), ["Hi."])

    def test_keep_sdh(self):
        it = item("SOPHIE: [laughs] Where are you?", keep_sdh=True)
        self.assertEqual(texts(it), ["SOPHIE: [laughs] Where are you?"])
        self.assertEqual(it.parts[0].speaker, "Sophie")

    def test_music_only_is_skipped_but_kept(self):
        it = item("♪ ♪")
        self.assertTrue(it.skip)
        self.assertEqual(it.source, "♪ ♪")

    def test_lyrics_are_translated(self):
        self.assertFalse(item("♪ Sail away ♪").skip)


class BannerTest(unittest.TestCase):
    def cues(self, texts):
        return [srt.Cue(n * 2000, n * 2000 + 1500, t) for n, t in enumerate(texts)]

    def test_title_card_of_the_file_is_dropped_at_the_edges(self):
        banner = '<font color="#ff00ff">Léon- The Professional (1994) Luc Besson Jean Reno.HI1</font>'
        texts = [banner] + [f"Line {n}." for n in range(10)] + [banner]
        items, dropped = prepare.make_items(self.cues(texts))
        self.assertEqual(dropped, 2)
        self.assertEqual(items[0].source, "Line 0.")

    def test_same_text_in_the_middle_is_kept(self):
        texts = [f"Line {n}." for n in range(5)] + ["Movie (1994) was great"] + [f"Line {n}." for n in range(5)]
        self.assertEqual(prepare.make_items(self.cues(texts))[1], 0)

    def test_dialogue_is_not_a_banner(self):
        self.assertFalse(prepare._is_banner("Hi, Mike!"))
        self.assertFalse(prepare._is_banner("Born in (1980)?"))
        self.assertTrue(prepare._is_banner("Film.2019.720p.BluRay.x264"))


class ChunksTest(unittest.TestCase):
    @staticmethod
    def items(starts: list[int]) -> list[prepare.Item]:
        return [prepare.Item(s, s + 900, [prepare.Part("x")]) for s in starts]

    def test_whole_scenes(self):
        # three scenes of 4 items, separated by 10 s pauses
        starts = [i * 1000 + (i // 4) * 10_000 for i in range(12)]
        self.assertEqual(prepare.make_chunks(self.items(starts), max_size=8), [(0, 8), (8, 12)])
        self.assertEqual(prepare.make_chunks(self.items(starts), max_size=5), [(0, 4), (4, 8), (8, 12)])

    def test_long_scene_is_split(self):
        chunks = prepare.make_chunks(self.items([i * 1000 for i in range(25)]), max_size=10)
        self.assertTrue(all(b - a <= 10 for a, b in chunks))
        self.assertEqual((chunks[0][0], chunks[-1][1]), (0, 25))

    def test_empty(self):
        self.assertEqual(prepare.make_chunks([]), [])


class TitleTest(unittest.TestCase):
    def test_guess(self):
        self.assertEqual(prepare.guess_title("The.One.I.Love.2014.LIMITED.720p.BluRay.x264-GECKOS.srt"), "The One I Love (2014)")
        self.assertEqual(prepare.guess_title("Blade.Runner.2049.2017.1080p.srt"), "Blade Runner 2049 (2017)")
        self.assertEqual(prepare.guess_title("2001.A.Space.Odyssey.1968.srt"), "2001 A Space Odyssey (1968)")
        self.assertEqual(prepare.guess_title("Cyberpunk.Edgerunners.S01E01.en.srt"), "Cyberpunk Edgerunners S01E01")
        self.assertEqual(prepare.guess_title("my film.srt"), "my film")


if __name__ == "__main__":
    unittest.main()
