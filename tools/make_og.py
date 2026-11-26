#!/usr/bin/env python3
"""Optionally render a 1200x630 social preview when Playwright is installed."""

import html
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        sync_playwright = None
    shared = json.loads((ROOT / "content/shared.json").read_text(encoding="utf-8"))
    english = json.loads((ROOT / "content/en.json").read_text(encoding="utf-8"))
    document = """<!doctype html><html><head><meta charset="utf-8"><style>
      *{box-sizing:border-box}body{margin:0;width:1200px;height:630px;padding:76px;background:#101614;color:#edf4ef;font:32px/1.5 system-ui,sans-serif}
      main{height:100%;display:flex;flex-direction:column;justify-content:center;border-left:8px solid #8bd6ae;padding-left:54px}
      p{color:#8bd6ae;font:24px ui-monospace,monospace}h1{font-size:64px;line-height:1.08;margin:0 0 24px}h2{font-size:34px;font-weight:500;color:#bdc9c1;margin:0}
    </style></head><body><main><p>$ whoami</p><h1>""" + html.escape(shared.get("name", "")) + """</h1><h2>""" + html.escape(english.get("headline", "")) + """</h2></main></body></html>"""
    output = ROOT / "site" / "og.png"
    if sync_playwright:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1200, "height": 630}, device_scale_factor=1)
            page.set_content(document)
            page.screenshot(path=str(output), full_page=False)
            browser.close()
    else:
        candidates = [shutil.which(name) for name in ("chrome", "chrome.exe", "msedge", "msedge.exe")]
        candidates.extend((r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                           r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"))
        browser = next((Path(value) for value in candidates if value and Path(value).is_file()), None)
        if not browser:
            raise SystemExit("No Playwright, Chromium or Chrome browser is available; no image was generated.")
        with tempfile.TemporaryDirectory(prefix="cv-og-") as temporary:
            page = Path(temporary) / "og.html"
            page.write_text(document, encoding="utf-8")
            subprocess.run([str(browser), "--headless=new", "--disable-gpu", "--hide-scrollbars",
                            "--no-first-run", "--no-default-browser-check", "--force-device-scale-factor=1",
                            "--window-size=1200,630", f"--user-data-dir={Path(temporary) / 'profile'}",
                            f"--screenshot={output}", page.as_uri()], check=True, capture_output=True, text=True)
    print(f"Generated {output.relative_to(ROOT).as_posix()}")


if __name__ == "__main__":
    main()
