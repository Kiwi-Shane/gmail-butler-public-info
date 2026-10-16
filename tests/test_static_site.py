import importlib.util
from pathlib import Path
import tempfile
import unittest


def checker():
    spec = importlib.util.spec_from_file_location(
        "site_checker", Path(__file__).parents[1] / "scripts/check_static_site.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class StaticSiteTests(unittest.TestCase):
    def page(self, root, body):
        (root / "index.html").write_text(
            '<!doctype html><html lang="en"><head><title>Fixture</title></head>'
            '<body><main><h1>Fixture</h1>' + body + '</main></body></html>', encoding="utf-8"
        )

    def test_relative_target_and_fragment_are_valid(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.page(root, '<a href="index.html#detail">Detail</a><p id="detail">Text</p>')
            self.assertEqual(checker().check(root, ["index.html"]), [])

    def test_missing_local_target_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.page(root, '<a href="missing.html">Missing</a>')
            self.assertTrue(any("missing target" in e for e in checker().check(root, ["index.html"])))

    def test_missing_fragment_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.page(root, '<a href="#missing">Missing</a>')
            self.assertTrue(any("missing fragment" in e for e in checker().check(root, ["index.html"])))

    def test_malformed_required_structure_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "index.html").write_text('<html><body>Incomplete</body></html>', encoding="utf-8")
            self.assertTrue(any("required structure" in e for e in checker().check(root, ["index.html"])))

    def test_crossed_required_tags_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "index.html").write_text(
                '<!doctype html><html lang="en"><head><title>Fixture</title></head>'
                '<body><main><h1>Fixture</main></h1></body></html>',
                encoding="utf-8",
            )
            errors = checker().check(root, ["index.html"])
            self.assertTrue(any("required tag nesting" in e for e in errors), errors)

    def test_balanced_required_structure_with_void_tags_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "pixel.svg").write_text("<svg></svg>", encoding="utf-8")
            self.page(root, '<img src="pixel.svg" alt="fixture"><br>')
            self.assertEqual(checker().check(root, ["index.html"]), [])

    def test_escaping_target_fails_without_reading_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.page(root, '<a href="../outside.html">Outside</a>')
            self.assertTrue(any("outside site" in e for e in checker().check(root, ["index.html"])))


if __name__ == "__main__":
    unittest.main()
