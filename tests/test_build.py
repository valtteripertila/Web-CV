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
from tools.media import image_dimensions
from tools import check, quality, sitebuilder


class BuildTests(unittest.TestCase):
    def test_validation_reports_missing_required_fields(self):
        errors = []
        build.validate({}, {}, {}, [], errors)
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
        text.update({"skills": [], "education": [], "certifications": [], "languages": [], "hero": {"status": []}})
        shared = {"email": "", "linkedin": "", "github": ""}
        output = sitebuilder.home_sections("en", shared, text, [], en["ui"])
        self.assertNotIn('id="timeline"', output)
        self.assertNotIn('id="profile"', output)
        self.assertNotIn('id="contact"', output)

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
            path = Path(temporary) / "timeline.json"
            path.write_text(json.dumps([{"title": "existing"}]), encoding="utf-8")
            with patch.object(add, "CONTENT", Path(temporary)):
                add.add_entry({"title": "new"})
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

    def test_html_language_check_uses_relative_path_parts(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            (root/"fi").mkdir()
            (root/"index.html").write_text('<html lang="en"><body><h1>Home</h1></body></html>',encoding="utf-8")
            (root/"fi"/"index.html").write_text('<html lang="fi"><body><h1>Etusivu</h1></body></html>',encoding="utf-8")
            self.assertEqual([],check.html_sanity_check(root))

    def test_empty_learned_and_links_are_omitted(self):
        en = json.loads((ROOT / "content/en.json").read_text(encoding="utf-8"))
        project = {"type":"project","date":"2025-03","title":"Example","role":{"en":"","fi":""},"description":{"en":"One","fi":"Yksi"},"tags":[],"links":{"demo":"","code":"","writeup":""},"media":[],"learned":{"en":"","fi":""}}
        output = sitebuilder.home_sections("en", {}, en, [project], en["ui"])
        self.assertIn("Example", output)
        self.assertNotIn("<details", output)
        self.assertNotIn("project-links", output)

    def test_date_formatting_and_chronological_sort(self):
        self.assertEqual("18–20 Sep 2026", sitebuilder.display_date({"date_start":"2026-09-18","date_end":"2026-09-20"},"en"))
        self.assertEqual("18.–20.9.2026", sitebuilder.display_date({"date_start":"2026-09-18","date_end":"2026-09-20"},"fi"))
        self.assertEqual("11/2026", sitebuilder.display_date({"date":"2026-11"},"fi"))
        self.assertEqual("08/2021", sitebuilder.display_date({"date":"2021-08"},"fi"))
        self.assertEqual("Nov 2026", sitebuilder.display_date({"date":"2026-11"},"en"))
        rows=list(enumerate([{"date":"[DATE]"},{"date":"2025-01"},{"date":"2026-02"}]))
        self.assertEqual([2,1,0],[i for i,_ in sorted(rows,key=sitebuilder.timeline_sort_key,reverse=True)])

    def test_finnish_profile_groups_transliterate_to_ascii_keys(self):
        self.assertEqual("tyokalut_ja_kaytannot", sitebuilder.profile_key("Työkalut ja käytännöt"))
        self.assertEqual("data_ja_tekoaly", sitebuilder.profile_key("Data ja tekoäly"))
        self.assertEqual("a", sitebuilder.profile_key("Å"))

    def test_localized_titles_and_tags_are_backward_compatible(self):
        project={"type":"project","date":"2026-11","title":{"en":"This CV site","fi":"Tämä CV-sivusto"},"role":{"en":"","fi":""},"description":{"en":"Description","fi":"Kuvaus"},"tags":[{"en":"Accessibility","fi":"Saavutettavuus"},"Python"],"links":{"demo":"","code":"","writeup":""},"media":[],"learned":{"en":"","fi":""}}
        errors=[]
        build.validate_timeline([project],errors)
        self.assertEqual([],errors)
        fi=json.loads((ROOT/"content/fi.json").read_text(encoding="utf-8"))
        output=sitebuilder.home_sections("fi",{},fi,[project],fi["ui"])
        self.assertIn("Tämä CV-sivusto",output)
        self.assertIn("#Saavutettavuus",output)
        self.assertIn("#Python",output)
        legacy=dict(project,title="Legacy title",tags=["Legacy tag"])
        legacy_errors=[]
        build.validate_timeline([legacy],legacy_errors)
        self.assertEqual([],legacy_errors)

    def test_junction_challenges_render_bilingually_in_a_code_panel(self):
        en=json.loads((ROOT/"content/en.json").read_text(encoding="utf-8"))
        fi=json.loads((ROOT/"content/fi.json").read_text(encoding="utf-8"))
        timeline=json.loads((ROOT/"content/timeline.json").read_text(encoding="utf-8"))
        junction=next(item for item in timeline if item.get("event")=="Junction 2026")
        errors=[]; build.validate_timeline([junction],errors)
        self.assertEqual([],errors)
        en_html=sitebuilder.home_sections("en",{},en,[junction],en["ui"])
        fi_html=sitebuilder.home_sections("fi",{},fi,[junction],fi["ui"])
        self.assertIn('class="code challenge-code"',en_html)
        self.assertIn("Hostinger main track",en_html)
        self.assertIn("Oxylabs tech track",en_html)
        self.assertIn("Hostingerin pääkilpailuraidalla",fi_html)
        self.assertIn("Oxylabsin teknologiaraidalla",fi_html)
        self.assertNotIn("serp",en_html.lower())

    def test_optional_commits_link_renders_after_demo_and_repo(self):
        en=json.loads((ROOT/"content/en.json").read_text(encoding="utf-8"))
        project={"type":"project","date":"2026-11","title":"Project","role":{"en":"","fi":""},"description":{"en":"Description","fi":"Kuvaus"},"tags":[],"links":{"demo":"https://example.com/demo","code":"https://example.com/repo","commits":"https://example.com/commits","writeup":""},"media":[],"learned":{"en":"","fi":""}}
        output=sitebuilder.home_sections("en",{},en,[project],en["ui"])
        positions=[output.index('href="https://example.com/'+part+'"') for part in ("demo","repo","commits")]
        self.assertEqual(sorted(positions),positions)
        self.assertIn('rel="noopener noreferrer">my commits</a>',output)
        fi=json.loads((ROOT/"content/fi.json").read_text(encoding="utf-8"))
        fi_output=sitebuilder.home_sections("fi",{},fi,[project],fi["ui"])
        self.assertIn('rel="noopener noreferrer">Koodi</a>',fi_output)
        self.assertIn('rel="noopener noreferrer">omat commitit</a>',fi_output)

    def test_domain_validation_rejects_uppercase_path_and_trailing_slash(self):
        shared=json.loads((ROOT/"content/shared.json").read_text(encoding="utf-8"))
        en=json.loads((ROOT/"content/en.json").read_text(encoding="utf-8"))
        fi=json.loads((ROOT/"content/fi.json").read_text(encoding="utf-8"))
        timeline=json.loads((ROOT/"content/timeline.json").read_text(encoding="utf-8"))
        for invalid in ("https://Example.com", "https://example.com/path", "https://example.com/"):
            with self.subTest(domain=invalid):
                candidate=dict(shared,domain=invalid)
                errors=[]
                build.validate(candidate,en,fi,timeline,errors)
                self.assertTrue(any("domain: must be a lowercase https:// origin" in issue for issue in errors))

    def test_generated_site_urls_and_open_graph_lock_are_consistent(self):
        self.assertEqual([],check.domain_consistency_check())
        self.assertEqual([],check.og_lock_check())
        self.assertEqual([],check.code_overflow_check())
        self.assertEqual([],check.changelog_heading_check())
        self.assertEqual((1200,630),image_dimensions(ROOT/"site/og.png"))
        self.assertEqual((1200,630),image_dimensions(ROOT/"site/og-fi.png"))

    def test_open_graph_lock_reports_regeneration_command_when_stale(self):
        with patch("tools.make_og.input_hash", return_value="stale"):
            errors=check.og_lock_check()
        self.assertTrue(errors)
        self.assertIn("py -3 tools/make_og.py",errors[0])

    def test_tokens_meet_aa_on_panel_surface(self):
        passed, report=quality.contrast_report((ROOT/"site/style.css").read_text(encoding="utf-8"))
        self.assertTrue(passed, report)
        self.assertGreaterEqual(report["dark"]["token_key_surface"],4.5)
        self.assertGreaterEqual(report["light"]["token_string_surface"],4.5)

    def test_media_validation_requires_existing_file_and_bilingual_alt(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary); (root/"img").mkdir()
            (root/"img"/"ok.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg" width="640" height="360"/>',encoding="utf-8")
            self.assertEqual((640,360),image_dimensions(root/"img"/"ok.svg"))
            errors=[]
            build.validate_media([{"file":"missing.png","alt":{"en":"SAMPLE alt","fi":"SAMPLE alt"}}],1,"media",root,errors)
            self.assertTrue(any("file must exist" in issue for issue in errors))
            alt_errors=[]
            build.validate_media([{"file":"ok.svg","alt":{"en":"","fi":""}}],1,"media",root,alt_errors)
            self.assertTrue(any("alt text is required" in issue for issue in alt_errors))

    def test_timeline_optional_empty_fields_are_valid_and_filters_need_two_types(self):
        project={"type":"project","date":"2025-03","title":"SAMPLE project","role":{"en":"","fi":""},"description":{"en":"","fi":""},"tags":[],"links":{"demo":"","code":"","writeup":""},"media":[],"learned":{"en":"","fi":""}}
        errors=[]; build.validate_timeline([project],errors)
        self.assertEqual([],errors)
        en=json.loads((ROOT/"content/en.json").read_text(encoding="utf-8"))
        output=sitebuilder.home_sections("en",{},en,[project],en["ui"])
        self.assertNotIn('class="filters"',output)

    def test_add_role_and_project_write_to_timeline(self):
        with tempfile.TemporaryDirectory() as temporary:
            content=Path(temporary)
            with patch.object(add,"CONTENT",content), patch("builtins.input",side_effect=["2025-01","","SAMPLE employer","SAMPLE role","SAMPLE rooli","SAMPLE point","","SAMPLE kohta",""]):
                add.add_role()
            role=json.loads((content/"timeline.json").read_text(encoding="utf-8"))[0]
            self.assertEqual("role",role["type"])
            with patch.object(add,"CONTENT",content), patch("builtins.input",side_effect=["2025-02","SAMPLE project","","","SAMPLE description","SAMPLE kuvaus","tag","","","","","","","","","","","","","","","","","","","","","","","","","","","","","","","","","","","",""]):
                add.add_project()
            entries=json.loads((content/"timeline.json").read_text(encoding="utf-8"))
            self.assertEqual("project",entries[0]["type"])
            self.assertEqual("role",entries[1]["type"])

    def test_add_hackathon_writes_new_schema(self):
        with tempfile.TemporaryDirectory() as temporary:
            with patch.object(add,"CONTENT",Path(temporary)), patch.object(add,"ask",side_effect=["2025-03-14","2025-03-16","SAMPLE event","SAMPLE team","5","SAMPLE build"]), patch.object(add,"bilingual",return_value={"en":"","fi":""}), patch.object(add,"tags",return_value=[]), patch.object(add,"links",return_value={"demo":"","code":"","writeup":""}):
                add.add_hackathon()
            item=json.loads((Path(temporary)/"timeline.json").read_text(encoding="utf-8"))[0]
            self.assertEqual("hackathon",item["type"])
            self.assertEqual("SAMPLE event",item["event"])
            self.assertEqual("SAMPLE build",item["project"]["title"])

    def test_media_cli_copies_without_overwriting(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary); content=root/"content"; site=root/"site"; content.mkdir(); site.mkdir()
            source=root/"source.svg"; source.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"/>',encoding="utf-8")
            entry={"type":"project","title":"SAMPLE media","date":"2025-01","media":[]}
            (content/"timeline.json").write_text(json.dumps([entry]),encoding="utf-8")
            answers=["1",str(source),"SAMPLE alt","SAMPLE alt fi",""," "]
            with patch.object(add,"CONTENT",content), patch.object(add,"SITE",site), patch("builtins.input",side_effect=answers):
                add.add_media()
            saved=json.loads((content/"timeline.json").read_text(encoding="utf-8"))[0]["media"][0]
            self.assertTrue((site/"img"/saved["file"]).is_file())
            self.assertEqual("SAMPLE alt",saved["alt"]["en"])


if __name__ == "__main__":
    unittest.main()
