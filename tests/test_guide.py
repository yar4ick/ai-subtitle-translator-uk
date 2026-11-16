import json
import re
import unittest
from pathlib import Path

from aisubs import __version__, cli, guide

ROOT = Path(__file__).parent.parent


class GuideTest(unittest.TestCase):
    def test_placeholders_filled(self):
        text = guide.text("My Film.srt", "aisubs")
        self.assertNotIn("{", text)
        self.assertIn("Run the tool as: aisubs", text)
        self.assertIn('`aisubs prepare "My Film.srt" --glossary`', text)
        self.assertIn('"My Film.aisubs/answer.txt"', text.replace("\\", "/"))

    def test_commands_and_options_exist(self):
        """Every `aisubs …` command and --option in the guide is one the CLI accepts."""
        parser = cli.build_parser()
        commands = parser._subparsers._group_actions[0].choices
        text = guide.text("film.srt", "aisubs")
        used = re.findall(r"`aisubs (\w+)([^`]*)`", text)
        self.assertGreater(len(used), 10)
        for name, rest in used:
            self.assertIn(name, commands, name)
            options = {o for a in commands[name]._actions for o in a.option_strings}
            for option in re.findall(r"--[\w-]+", rest):
                self.assertIn(option, options, f"aisubs {name} {option}")
        for option in re.findall(r"`(--[\w-]+)", text):
            self.assertTrue(any(option in {o for a in c._actions for o in a.option_strings} for c in commands.values()), option)


class QuoteTest(unittest.TestCase):
    def test_unusual_file_names_are_quoted(self):
        self.assertEqual(guide._quote("film.srt"), "film.srt")
        self.assertEqual(guide._quote("Leon(1994).srt"), '"Leon(1994).srt"')
        self.assertEqual(guide._quote("It's.a.Wonderful.Life.srt"), '"It\'s.a.Wonderful.Life.srt"')
        self.assertEqual(guide._quote("Tom&Jerry.srt"), '"Tom&Jerry.srt"')
        self.assertEqual(guide._quote('a "b".srt'), "'a \"b\".srt'")


class PluginTest(unittest.TestCase):
    def test_manifests(self):
        plugin = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
        market = json.loads((ROOT / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
        self.assertEqual(plugin["version"], __version__)
        self.assertEqual([p["name"] for p in market["plugins"]], [plugin["name"]])

    def test_skill_runs_the_package_directory(self):
        skill = (ROOT / "skills" / "translate" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("${CLAUDE_PLUGIN_ROOT}/aisubs guide", skill)
        self.assertTrue((ROOT / "aisubs" / "__main__.py").exists())


if __name__ == "__main__":
    unittest.main()
