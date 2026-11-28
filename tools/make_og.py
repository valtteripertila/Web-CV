#!/usr/bin/env python3
"""Render localized 1200x630 social images and lock their source inputs."""

import hashlib
import html
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.quality import parse_colors

LOCK = ROOT / "tools" / "og.lock"


def image_inputs():
    shared = json.loads((ROOT / "content/shared.json").read_text(encoding="utf-8"))
    english = json.loads((ROOT / "content/en.json").read_text(encoding="utf-8"))
    finnish = json.loads((ROOT / "content/fi.json").read_text(encoding="utf-8"))
    palettes = parse_colors((ROOT / "site/style.css").read_text(encoding="utf-8"))
    return {
        "name": shared["name"],
        "headlines": {"en": english["headline"], "fi": finnish["headline"]},
        "availability": {
            "en": next(row["value"] for row in english["hero"]["status"] if row["key"] == "availability"),
            "fi": next(row["value"] for row in finnish["hero"]["status"] if row["key"] == "availability"),
        },
        "palettes": palettes,
    }


def input_hash():
    encoded = json.dumps(image_inputs(), ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def page_document(name, headline, availability, palette):
    background = palette["--background"]
    text = palette["--text"]
    accent = palette["--accent"]
    muted = palette["--muted"]
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>
      *{{box-sizing:border-box}}body{{margin:0;width:1200px;height:630px;padding:76px;background:{background};color:{text};font:32px/1.5 system-ui,sans-serif}}
      main{{height:100%;display:flex;flex-direction:column;justify-content:center;border-left:8px solid {accent};padding-left:54px}}
      p{{color:{accent};font:24px ui-monospace,monospace}}h1{{font-size:64px;line-height:1.08;margin:0 0 24px}}h2{{max-width:950px;font-size:34px;line-height:1.25;font-weight:500;color:{muted};margin:0}}.availability{{max-width:950px;margin:22px 0 0;color:{muted};font:22px/1.35 system-ui,sans-serif}}
    </style></head><body><main><p>$ whoami</p><h1>{html.escape(name)}</h1><h2>{html.escape(headline)}</h2><div class="availability">{html.escape(availability)}</div></main></body></html>"""


def render_with_playwright(playwright, output, document):
    browser = playwright.chromium.launch(headless=True)
    try:
        page = browser.new_page(viewport={"width": 1200, "height": 630}, device_scale_factor=1)
        page.set_content(document)
        page.screenshot(path=str(output), full_page=False)
    finally:
        browser.close()


def render_with_browser(browser, output, document, temporary):
    page = Path(temporary) / "og.html"
    page.write_text(document, encoding="utf-8")
    subprocess.run([str(browser), "--headless=new", "--disable-gpu", "--hide-scrollbars",
                    "--no-first-run", "--no-default-browser-check", "--force-device-scale-factor=1",
                    "--window-size=1200,630", f"--user-data-dir={Path(temporary) / 'profile'}",
                    f"--screenshot={output}", page.as_uri()], check=True, capture_output=True, text=True)


def main():
    inputs = image_inputs()
    palettes = inputs["palettes"]
    targets = (("en", "og.png"), ("fi", "og-fi.png"))
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        sync_playwright = None

    if sync_playwright:
        with sync_playwright() as playwright:
            for lang, filename in targets:
                render_with_playwright(playwright, ROOT / "site" / filename,
                                       page_document(inputs["name"], inputs["headlines"][lang], inputs["availability"][lang], palettes["dark"]))
    else:
        candidates = [shutil.which(name) for name in ("chrome", "chrome.exe", "msedge", "msedge.exe")]
        candidates.extend((r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                           r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"))
        browser = next((Path(value) for value in candidates if value and Path(value).is_file()), None)
        if not browser:
            raise SystemExit("No Playwright, Chromium or Chrome browser is available; run `py -3 tools/make_og.py` when one is available. Images and lock were not changed.")
        with tempfile.TemporaryDirectory(prefix="cv-og-") as temporary:
            for lang, filename in targets:
                render_with_browser(browser, ROOT / "site" / filename,
                                    page_document(inputs["name"], inputs["headlines"][lang], inputs["availability"][lang], palettes["dark"]), temporary)

    LOCK.write_text(input_hash() + "\n", encoding="utf-8", newline="\n")
    print("Generated site/og.png and site/og-fi.png; updated tools/og.lock")


if __name__ == "__main__":
    main()
