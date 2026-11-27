#!/usr/bin/env python3
"""Run the complete offline validation suite for the generated site."""

import html.parser
import json
import os
import re
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
sys.path.insert(0, str(ROOT))


def _run(command, env=None):
    return subprocess.run(command, cwd=ROOT, env=env, text=True, capture_output=True)


def check_build():
    result = _run([sys.executable, "build.py", "--check"])
    return [] if result.returncode == 0 else [result.stdout + result.stderr]


def check_unittests():
    result = _run([sys.executable, "-m", "unittest", "discover", "-s", "tests"])
    return [] if result.returncode == 0 else [result.stdout + result.stderr]


class Links(html.parser.HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.ids = set()
        self.hrefs = []
        self.sources = []

    def handle_starttag(self, tag, attrs):
        data = dict(attrs)
        if data.get("id"):
            self.ids.add(data["id"])
        if data.get("href"):
            self.hrefs.append(data["href"])
        if data.get("src"):
            self.sources.append(data["src"])


def link_errors(site_root, page_path):
    errors = []
    page = Path(page_path)
    try:
        parser = Links()
        parser.feed(page.read_text(encoding="utf-8"))
    except (OSError, UnicodeError) as error:
        return [f"{page}: cannot read HTML: {error}"]
    for raw in parser.hrefs + parser.sources:
        url = urlsplit(raw)
        if url.scheme or url.netloc or raw.startswith("//"):
            continue
        target = (page.parent / unquote(url.path)).resolve() if url.path else page.resolve()
        if target.is_dir():
            target = target / "index.html"
        if not target.exists():
            errors.append(f"{page.relative_to(site_root)}: missing target {raw}")
        elif url.fragment and target.suffix.lower() in (".html", ""):
            target_parser = Links()
            try:
                target_parser.feed(target.read_text(encoding="utf-8"))
            except (OSError, UnicodeError) as error:
                errors.append(f"{target}: cannot read fragment target: {error}")
            else:
                if unquote(url.fragment) not in target_parser.ids:
                    errors.append(f"{page.relative_to(site_root)}: missing fragment #{url.fragment} in {raw}")
    return errors


def internal_link_check(site_root=SITE):
    pages = sorted(Path(site_root).rglob("*.html"))
    return [error for page in pages for error in link_errors(Path(site_root), page)]


def _section_ids(path):
    class Sections(html.parser.HTMLParser):
        def __init__(self):
            super().__init__()
            self.values = []

        def handle_starttag(self, tag, attrs):
            values = dict(attrs)
            if tag == "section" and values.get("id"):
                self.values.append(values["id"])

    parser = Sections()
    parser.feed(Path(path).read_text(encoding="utf-8"))
    return parser.values


def language_parity_check():
    errors = []
    en = json.loads((ROOT / "content/en.json").read_text(encoding="utf-8"))
    fi = json.loads((ROOT / "content/fi.json").read_text(encoding="utf-8"))
    now = json.loads((ROOT / "content/now.json").read_text(encoding="utf-8"))
    pairs = {"home": (SITE / "index.html", SITE / "fi/index.html"),
             "how": (SITE / en["slugs"]["how"] / "index.html", SITE / "fi" / fi["slugs"]["how"] / "index.html"),
             "changelog": (SITE / en["slugs"]["changelog"] / "index.html", SITE / "fi" / fi["slugs"]["changelog"] / "index.html")}
    if now.get("items"):
        pairs["now"] = (SITE / en["slugs"]["now"] / "index.html", SITE / "fi" / fi["slugs"]["now"] / "index.html")
    actual = {path.resolve() for path in SITE.rglob("*.html") if path.name != "404.html"}
    expected = {path.resolve() for pair in pairs.values() for path in pair}
    if actual != expected:
        errors.append("generated EN/FI page set does not match optional content pages")
    for key, pair in pairs.items():
        if not all(path.exists() for path in pair):
            errors.append(f"{key}: language page is missing")
        else:
            if _section_ids(pair[0]) != _section_ids(pair[1]):
                errors.append(f"{key}: section order differs between EN and FI")
    def compare_values(left, right, at="ui"):
        if isinstance(left, dict) and isinstance(right, dict):
            if left.keys() != right.keys():
                errors.append(f"{at}: translated UI keys differ")
                return
            for key in left:
                compare_values(left[key], right[key], at + "." + key)
        elif isinstance(left, str) and isinstance(right, str):
            if not left.strip() or not right.strip():
                errors.append(f"{at}: UI translation is empty")
            elif left == right and left.lower() not in {"demo", "lighthouse", "hackathon", "repo", "github", "linkedin"} and at != "ui.lighthouseFooter":
                errors.append(f"{at}: EN and FI UI strings are identical")
    compare_values(en["ui"], fi["ui"])
    return errors


class HTMLSanity(html.parser.HTMLParser):
    VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.errors = []
        self.ids = set()
        self.h1 = 0
        self.lang = ""

    def handle_starttag(self, tag, attrs):
        data = dict(attrs)
        if tag == "html":
            self.lang = data.get("lang", "")
        if tag == "h1":
            self.h1 += 1
        identifier = data.get("id")
        if identifier:
            if identifier in self.ids:
                self.errors.append(f"duplicate id: {identifier}")
            self.ids.add(identifier)
        if tag not in self.VOID:
            self.stack.append(tag)

    def handle_endtag(self, tag):
        if tag in self.VOID:
            return
        if not self.stack or self.stack[-1] != tag:
            self.errors.append(f"unexpected closing tag: {tag}")
            if tag in self.stack:
                while self.stack and self.stack[-1] != tag:
                    self.stack.pop()
                if self.stack:
                    self.stack.pop()
            return
        self.stack.pop()


def html_sanity_check(site_root=SITE):
    errors = []
    for page in sorted(Path(site_root).rglob("*.html")):
        parser = HTMLSanity()
        try:
            parser.feed(page.read_text(encoding="utf-8"))
            parser.close()
        except (OSError, UnicodeError) as error:
            errors.append(f"{page}: {error}")
            continue
        if parser.stack:
            errors.append(f"{page.relative_to(site_root)}: unclosed tags {parser.stack}")
        if parser.h1 != 1:
            errors.append(f"{page.relative_to(site_root)}: expected one h1, found {parser.h1}")
        relative_page = page.relative_to(Path(site_root))
        expected_lang = "fi" if relative_page.parts and relative_page.parts[0].lower() == "fi" else "en"
        if parser.lang != expected_lang:
            errors.append(f"{page.relative_to(site_root)}: expected lang={expected_lang}, got {parser.lang}")
        errors.extend(f"{page.relative_to(site_root)}: {item}" for item in parser.errors)
    return errors


class TopbarLinks(html.parser.HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.topbars = 0
        self.switch_depth = 0
        self.menu_depth = 0
        self.switch_hrefs = []
        self.menu_hrefs = []
        self.first_focusable = None

    def handle_starttag(self, tag, attrs):
        data = dict(attrs)
        classes = data.get("class", "").split()
        if self.first_focusable is None and (
            (tag == "a" and data.get("href")) or tag in {"button", "summary", "input", "select", "textarea"}
        ):
            self.first_focusable = "skip" if "skip-link" in classes else tag
        if tag == "header" and "topbar" in classes:
            self.topbars += 1
        if tag == "nav":
            if "language-switch" in classes:
                self.switch_depth += 1
            elif self.menu_depth:
                self.menu_depth += 1
        if tag == "details" and "menu-wrap" in classes:
            self.menu_depth += 1
        if tag == "a" and data.get("href"):
            if self.switch_depth:
                self.switch_hrefs.append(data["href"])
            if self.menu_depth:
                self.menu_hrefs.append(data["href"])

    def handle_endtag(self, tag):
        if tag == "nav" and self.switch_depth:
            self.switch_depth -= 1
        elif tag == "nav" and self.menu_depth > 1:
            self.menu_depth -= 1
        elif tag == "details" and self.menu_depth:
            self.menu_depth = 0


def topbar_check(site_root=SITE):
    from tools.sitebuilder import page_dirs
    errors = []
    en = json.loads((ROOT / "content/en.json").read_text(encoding="utf-8"))
    fi = json.loads((ROOT / "content/fi.json").read_text(encoding="utf-8"))
    now = json.loads((ROOT / "content/now.json").read_text(encoding="utf-8"))
    pages = page_dirs(en, fi, bool(now.get("items")))
    root = Path(site_root)

    def local_target(page, href):
        value = urlsplit(href)
        if value.scheme or value.netloc or href.startswith("//"):
            return None
        target = (page.parent / unquote(value.path)).resolve() if value.path else page.resolve()
        return (target / "index.html").resolve() if target.is_dir() else target

    def generated_page(path):
        relative = path.relative_to(root).as_posix()
        if relative == "404.html":
            return "home", "en"
        directory = "" if relative == "index.html" else relative[:-len("/index.html")]
        for key, langs in pages.items():
            for lang in ("en", "fi"):
                if directory == langs[lang]:
                    return key, lang
        return None, None

    for page in sorted(root.rglob("*.html")):
        parser = TopbarLinks()
        parser.feed(page.read_text(encoding="utf-8"))
        label = page.relative_to(root).as_posix()
        if parser.topbars != 1:
            errors.append(f"{label}: expected one header.topbar, found {parser.topbars}")
        if parser.first_focusable != "skip":
            errors.append(f"{label}: skip link is not the first focusable element")
        key, lang = generated_page(page)
        if not key:
            errors.append(f"{label}: page is not mapped to a generated language page")
            continue
        expected = [(lang, pages[key][lang]) for lang in ("en", "fi")]
        if len(parser.switch_hrefs) != 2:
            errors.append(f"{label}: language switch should contain EN and FI links")
        else:
            for href, (target_lang, directory) in zip(parser.switch_hrefs, expected):
                target = local_target(page, href)
                expected_path = (root / directory / "index.html").resolve() if directory else (root / "index.html").resolve()
                if target != expected_path or not expected_path.exists():
                    errors.append(f"{label}: language switch {target_lang} target is missing or not equivalent: {href}")
        for href in parser.menu_hrefs:
            target = local_target(page, href)
            if target is not None and not target.exists():
                errors.append(f"{label}: menu target is missing: {href}")
    return errors


def external_resource_check(site_root=SITE):
    from tools.sitebuilder import count_external_resources
    errors = []
    for page in Path(site_root).rglob("*.html"):
        count = count_external_resources(page.read_text(encoding="utf-8"))
        if count:
            errors.append(f"{page.relative_to(site_root)}: {count} external HTML resource(s)")
    for path in (Path(site_root) / "style.css",):
        if path.exists() and re.search(r"url\(\s*['\"]?https?://", path.read_text(encoding="utf-8"), re.I):
            errors.append(f"{path.relative_to(site_root)}: external CSS resource")
    return errors


def contrast_check():
    from tools.quality import contrast_report
    passed, values = contrast_report((SITE / "style.css").read_text(encoding="utf-8"))
    return [] if passed else ["contrast thresholds failed: " + json.dumps(values, sort_keys=True)]


def og_lock_check():
    from tools.make_og import LOCK, input_hash
    try:
        locked = LOCK.read_text(encoding="utf-8").strip()
    except OSError:
        locked = ""
    current = input_hash()
    if locked != current:
        return [f"WARNING: Open Graph images are stale or have no input lock; run `py -3 tools/make_og.py` to regenerate site/og.png, site/og-fi.png and tools/og.lock (current input hash: {current})."]
    return []


class PageMetadata(html.parser.HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title = ""
        self.in_title = False
        self.links = []
        self.meta = {}

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == "title":
            self.in_title = True
        elif tag == "link":
            self.links.append(values)
        elif tag == "meta":
            key = values.get("property") or values.get("name")
            if key:
                self.meta[key] = values.get("content", "")

    def handle_endtag(self, tag):
        if tag == "title":
            self.in_title = False

    def handle_data(self, data):
        if self.in_title:
            self.title += data


def domain_consistency_check(site_root=SITE):
    errors = []
    shared = json.loads((ROOT / "content/shared.json").read_text(encoding="utf-8"))
    domain = shared["domain"]
    expected_origin = (urlsplit(domain).scheme, urlsplit(domain).netloc)

    def same_origin(value):
        parsed = urlsplit(value)
        return (parsed.scheme, parsed.netloc) == expected_origin and bool(parsed.path.startswith("/"))

    root = Path(site_root)
    text_extensions = {".html", ".xml", ".txt", ".json", ".css", ".js", ".svg"}
    stale_host = ".".join(("pages", "dev"))
    for file in root.rglob("*"):
        if file.is_file() and file.suffix.lower() in text_extensions:
            if stale_host in file.read_text(encoding="utf-8", errors="replace").lower():
                errors.append(f"{file.relative_to(root)}: stale site-domain reference")

    for page in sorted(root.rglob("*.html")):
        parser = PageMetadata()
        parser.feed(page.read_text(encoding="utf-8"))
        relative = page.relative_to(root)
        label = relative.as_posix()
        locale = "fi_FI" if relative.parts and relative.parts[0] == "fi" else "en_US"
        if parser.title != parser.meta.get("og:title"):
            errors.append(f"{label}: og:title does not equal the page title")
        if parser.meta.get("og:locale") != locale:
            errors.append(f"{label}: wrong or missing og:locale")
        for key in (("og:image",) if label == "404.html" else ("og:url", "og:image")):
            if not same_origin(parser.meta.get(key, "")):
                errors.append(f"{label}: {key} does not use {domain}")
        if label == "404.html":
            continue
        canonicals = [item.get("href", "") for item in parser.links if item.get("rel") == "canonical"]
        alternates = [item.get("href", "") for item in parser.links if item.get("rel") == "alternate"]
        if len(canonicals) != 1 or not same_origin(canonicals[0]):
            errors.append(f"{label}: canonical does not use {domain}")
        if not alternates or any(not same_origin(value) for value in alternates):
            errors.append(f"{label}: hreflang links do not use {domain}")

    sitemap = root / "sitemap.xml"
    try:
        tree = ET.parse(sitemap)
        sitemap_urls = [node.text or "" for node in tree.iter() if node.tag.endswith("}loc")]
        sitemap_urls.extend(node.attrib.get("href", "") for node in tree.iter() if node.tag.endswith("}link"))
        if not sitemap_urls or any(not same_origin(value) for value in sitemap_urls):
            errors.append("sitemap.xml: a page or alternate URL does not use the configured domain")
    except (OSError, ET.ParseError) as error:
        errors.append(f"sitemap.xml: cannot parse: {error}")

    robots = root / "robots.txt"
    if not any(line.strip() == f"Sitemap: {domain}/sitemap.xml" for line in robots.read_text(encoding="utf-8").splitlines()):
        errors.append("robots.txt: sitemap URL does not use the configured domain")
    llms = (root / "llms.txt").read_text(encoding="utf-8")
    own_links = re.findall(r"\[[^\]]+\]\((https?://[^)]+)\)", llms)
    if not own_links or any(not same_origin(value) for value in own_links):
        errors.append("llms.txt: a CV page link does not use the configured domain")
    return errors


def code_overflow_check():
    css = (SITE / "style.css").read_text(encoding="utf-8")
    if re.search(r"overflow-x\s*:\s*(?:auto|scroll)\b", css, re.I):
        return ["style.css: horizontal auto/scroll overflow is enabled on a page element"]
    return []


def changelog_heading_check(site_root=SITE):
    en = json.loads((ROOT / "content/en.json").read_text(encoding="utf-8"))
    path = Path(site_root) / en["slugs"]["changelog"] / "index.html"

    class Headings(html.parser.HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.current = None
            self.values = []

        def handle_starttag(self, tag, attrs):
            if tag in ("h1", "h2"):
                self.current = [tag, ""]

        def handle_endtag(self, tag):
            if self.current and tag == self.current[0]:
                self.values.append(tuple(self.current))
                self.current = None

        def handle_data(self, data):
            if self.current:
                self.current[1] += data

    parser = Headings()
    parser.feed(path.read_text(encoding="utf-8"))
    matches = [heading for heading in parser.values if heading[1].strip() == en["ui"]["navChangelog"]]
    return [] if len(matches) == 1 else [f"{path.relative_to(site_root)}: expected one h1/h2 Changelog heading, found {len(matches)}"]


def privacy_check():
    errors = []
    phone_pattern = re.compile(r"(?<![\w])(?:\+?\d[\s().-]*){9,}(?![\w])")
    address_words = re.compile(r"\b(?:street|st\.?|road|rd\.?|avenue|ave\.?|boulevard|blvd\.?|katu|tie|kuja|polku|väylä)\b", re.I)
    for folder in (ROOT / "content", SITE):
        for path in folder.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in (".json", ".html", ".txt", ".svg", ".css", ".js"):
                continue
            value = path.read_text(encoding="utf-8", errors="replace")
            value = re.sub(r"\b\d{4}-\d{2}-\d{2}\b", "", value)
            if phone_pattern.search(value):
                errors.append(f"{path.relative_to(ROOT)}: phone-number-like sequence")
            if address_words.search(value):
                errors.append(f"{path.relative_to(ROOT)}: street-address word")
    return errors


def freshness_check():
    committed = (SITE / "index.html").read_text(encoding="utf-8")
    match = re.search(r"©\s+(\d{4})", committed)
    if not match:
        return ["site/index.html: could not read committed footer year"]
    env = os.environ.copy()
    env["CV_BUILD_YEAR"] = match.group(1)
    with tempfile.TemporaryDirectory(prefix="cv-build-") as temporary:
        result = _run([sys.executable, "build.py", "--output-dir", temporary], env=env)
        if result.returncode:
            return ["temporary build failed: " + result.stdout + result.stderr]
        generated = ("index.html", "fi/index.html", "404.html", "favicon.svg", "sitemap.xml", "robots.txt", "llms.txt")
        for en_name, fi_name in (("how-this-site-is-built/index.html", "fi/sivuston-rakenne/index.html"),
                                 ("changelog/index.html", "fi/muutosloki/index.html"),
                                 ("now/index.html", "fi/nyt/index.html")):
            for name in (en_name, fi_name):
                if (SITE / name).exists() or (Path(temporary) / name).exists():
                    generated += (name,)
        errors = []
        for name in generated:
            current, built = SITE / name, Path(temporary) / name
            if not current.exists() or not built.exists():
                errors.append(f"freshness mismatch: {name} missing")
            elif current.read_bytes() != built.read_bytes():
                errors.append(f"freshness mismatch: {name}")
        return errors


CHECKS = [
    ("content", "Build content validation passes.", "Sisällön muodostustarkistus läpäisee.", check_build),
    ("tests", "Unit tests pass.", "Yksikkötestit läpäisevät.", check_unittests),
    ("links", "Internal links, fragments and assets resolve.", "Sisäiset linkit, kohdat ja resurssit löytyvät.", internal_link_check),
    ("language", "English and Finnish pages and translations stay in parity.", "Englannin- ja suomenkieliset sivut ja käännökset pysyvät rinnakkain.", language_parity_check),
    ("html", "HTML tags, ids, headings and language attributes are valid.", "HTML-tunnisteet, tunnisteet, pääotsikot ja kielimerkinnät ovat kelvollisia.", html_sanity_check),
    ("topbar", "Every page has one top bar with valid language and menu links.", "Jokaisella sivulla on yksi yläpalkki ja toimivat kieli- ja valikkolinkit.", topbar_check),
    ("external", "HTML and CSS load no external resources.", "HTML ja CSS eivät lataa ulkoisia resursseja.", external_resource_check),
    ("domain", "Canonical, alternate and social URLs use the site domain.", "Canonical-, kieli- ja someosoitteissa käytetään sivuston verkkotunnusta.", domain_consistency_check),
    ("code-overflow", "Code panels have no horizontal auto/scroll overflow.", "Koodipaneeleissa ei ole vaakasuuntaista vieritystä.", code_overflow_check),
    ("changelog-heading", "The changelog has one page heading.", "Muutoslokissa on vain yksi sivuotsikko.", changelog_heading_check),
    ("contrast", "Both theme palettes pass measured contrast thresholds.", "Molempien teemojen värit läpäisevät mitatut kontrastirajat.", contrast_check),
    ("og-lock", "Open Graph images match their source inputs.", "Open Graph -kuvat vastaavat lähdesisältöään.", og_lock_check),
    ("privacy", "No private contact details are included.", "Yksityisiä yhteystietoja ei ole lisätty.", privacy_check),
    ("freshness", "Committed site files match a fresh temporary build.", "Julkaistut sivutiedostot vastaavat väliaikaista uutta koostetta.", freshness_check),
]


def main():
    failed = 0
    for name, _, _, check in CHECKS:
        try:
            errors = check()
        except Exception as error:  # Report a failed check rather than hiding its cause.
            errors = [f"{type(error).__name__}: {error}"]
        if errors:
            failed += 1
            print(f"FAIL {name}: {len(errors)} issue(s)")
            for error in errors:
                print("  " + error)
        else:
            print(f"PASS {name}")
    print(f"Summary: {len(CHECKS) - failed}/{len(CHECKS)} checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
