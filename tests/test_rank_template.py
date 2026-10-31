import unittest
from pathlib import Path


class RankTemplateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.template = Path("templates/rank.html.j2").read_text(encoding="utf-8")

    def test_uses_depth_independent_static_assets(self):
        self.assertIn("static_asset('css/karma.css')", self.template)
        self.assertNotIn("url_for('static'", self.template)

    def test_does_not_embed_svg_markup(self):
        self.assertNotIn("<svg", self.template)
        self.assertIn("assets/svg/caret-", self.template)
        self.assertIn("assets/svg/arrow-", self.template)


if __name__ == "__main__":
    unittest.main()
