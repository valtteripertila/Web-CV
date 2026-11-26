import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import add
import build
from tools import check, quality, sitebuilder


class BuildTests(unittest.TestCase):
    def test_validation_reports_missing_required_fields(self):
        errors = []
        build.validate({}, {}, {}, [], [], errors)
        self.assertTrue(any("shared.json: missing name" in value for value in errors))
        self.assertTrue(any("en.json: missing headline" in value for value in errors))

    def test_malformed_json_is_reported(self):
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "broken.json"
            target.write_text("{oops", encoding="utf-8")
            with patch.object(build, "CONTENT", Path(temporary)):
                errors = []
                self.assertEqual({}, build.load_object("broken.json", errors))
            self.assertTrue(errors)

    def test_placeholder_detection_reports_values(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            build.warn_placeholders({"sample.json": {"headline": "[HEADLINE]"}})
        self.assertIn("placeholder remains", output.getvalue())
        self.assertIn("Placeholder warning count: 1", output.getvalue())

    def test_content_is_html_escaped(self):
        self.assertEqual("&lt;script&gt;&quot;&amp;", sitebuilder.esc('<script>"&'))

    def test_empty_links_and_optional_sections_are_omitted(self):
        self.assertEqual("", sitebuilder.link("", "Demo"))
        en = json.loads((ROOT / "content/en.json").read_text(encoding="utf-8"))
        text = dict(en)
        text.update({"skills": [], "education": [], "certifications": [], "languages": [], "location": ""})
        shared = {"email": "", "linkedin": "", "github": ""}
        output = sitebuilder.home_sections("en", shared, text, [], [], en["ui"])
        self.assertEqual("", output)

    def test_language_switch_maps_equivalent_subpage(self):
        en = json.loads((ROOT / "content/en.json").read_text(encoding="utf-8"))
        fi = json.loads((ROOT / "content/fi.json").read_text(encoding="utf-8"))
        pages = sitebuilder.page_dirs(en, fi, False)
        value = sitebuilder.language_switch("en", "how", pages, en["ui"])
        self.assertIn('../fi/sivuston-rakenne/', value)
        self.assertIn('aria-current="true"', value)

    def test_site_menu_is_omitted_when_empty(self):
        en = json.loads((ROOT / "content/en.json").read_text(encoding="utf-8"))
        self.assertEqual("", sitebuilder.site_menu("en", "home", {}, {}, en))

    def test_site_menu_omits_empty_groups_and_missing_links(self):
        en = json.loads((ROOT / "content/en.json").read_text(encoding="utf-8"))
        pages = {"home": {"en": "", "fi": "fi"}, "now": {"en": "now", "fi": "fi/nyt"}}
        menu = sitebuilder.site_menu("en", "home", pages, {"github": "", "linkedin": "[PROFILE URL]"}, en)
        self.assertIn("// More", menu)
        self.assertIn("Now", menu)
        self.assertNotIn("About this site", menu)
        self.assertNotIn("GitHub", menu)
        self.assertNotIn("LinkedIn", menu)

    def test_site_menu_uses_relative_paths_for_subpages(self):
        en = json.loads((ROOT / "content/en.json").read_text(encoding="utf-8"))
        fi = json.loads((ROOT / "content/fi.json").read_text(encoding="utf-8"))
        pages = sitebuilder.page_dirs(en, fi, True)
        menu = sitebuilder.site_menu("fi", "how", pages, {}, fi)
        self.assertIn('href="../muutosloki/"', menu)
        self.assertIn('href="../nyt/"', menu)

    def test_brand_uses_name_without_handle_decoration(self):
        value = sitebuilder.brand_link("Valtteri Pertilä", "./")
        self.assertIn('<span class="first">Valtteri</span> <span class="last">Pertilä</span>', value)
        self.assertNotIn("@", value)
        self.assertEqual('<a class="brand" href="./"><span class="first">Single</span></a>', sitebuilder.brand_link("Single", "./"))

    def test_two_builds_are_byte_identical(self):
        env = os.environ.copy()
        env["CV_BUILD_YEAR"] = "2026"
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            for destination in (first, second):
                result = subprocess.run([sys.executable, "build.py", "--output-dir", destination], cwd=ROOT, env=env, capture_output=True, text=True)
                self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            first_files = {path.relative_to(first).as_posix(): path.read_bytes() for path in Path(first).rglob("*") if path.is_file()}
            second_files = {path.relative_to(second).as_posix(): path.read_bytes() for path in Path(second).rglob("*") if path.is_file()}
            self.assertEqual(first_files, second_files)

    def test_add_entry_inserts_at_top_without_overwriting(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "entries.json"
            path.write_text(json.dumps([{"title": "existing"}]), encoding="utf-8")
            with patch.object(add, "CONTENT", Path(temporary)):
                add.add_entry("entries.json", {"title": "new"})
            self.assertEqual([{"title": "new"}, {"title": "existing"}], json.loads(path.read_text(encoding="utf-8")))

    def test_known_contrast_ratio(self):
        self.assertAlmostEqual(21.0, quality.contrast_ratio("#000000", "#ffffff"), places=4)

    def test_link_checker_finds_broken_file_and_fragment(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            page = root / "index.html"
            page.write_text('<a href="missing.html#target">broken</a>', encoding="utf-8")
            errors = check.link_errors(root, page)
            self.assertEqual(1, len(errors))
            self.assertIn("missing target", errors[0])

    def test_writeup_is_omitted_until_language_has_content(self):
        en = json.loads((ROOT / "content/en.json").read_text(encoding="utf-8"))
        project = {"type": "hackathon", "title": "Event", "description": {"en": "One", "fi": "Yksi"},
                   "writeup": {"team": {"en": "Team text", "fi": ""}}}
        output = sitebuilder.home_sections("en", {}, en, [], [project], en["ui"])
        self.assertIn("<details", output)
        self.assertIn("Team text", output)
        fi_output = sitebuilder.home_sections("fi", {}, json.loads((ROOT / "content/fi.json").read_text(encoding="utf-8")), [], [project], json.loads((ROOT / "content/fi.json").read_text(encoding="utf-8"))["ui"])
        self.assertNotIn("<details", fi_output)


if __name__ == "__main__":
    unittest.main()
