#!/usr/bin/env python3
"""Build and validate the static bilingual CV site using only Python's standard library."""
import argparse
import html
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CONTENT = ROOT / "content"
SITE = ROOT / "site"
UI_KEYS = ["skip", "about", "experience", "projects", "hackathons", "personalProjects", "education", "certifications", "skills", "languages", "contact", "present", "demo", "code", "writeup", "backToTop", "themeToLight", "themeToDark", "meta_title", "meta_description", "notFoundTitle", "notFoundText"]


def esc(value):
        return html.escape(str(value), quote=True)


def load_object(filename, errors):
        try:
                data = json.loads((CONTENT / filename).read_text(encoding="utf-8"))
                if not isinstance(data, dict):
                        errors.append(f"{filename}: root must be a JSON object")
                        return {}
                return data
        except (OSError, json.JSONDecodeError) as error:
                errors.append(f"{filename}: {error}")
                return {}


def load_list(filename, errors):
        try:
                data = json.loads((CONTENT / filename).read_text(encoding="utf-8"))
                if not isinstance(data, list):
                        errors.append(f"{filename}: root must be a JSON array")
                        return []
                return data
        except (OSError, json.JSONDecodeError) as error:
                errors.append(f"{filename}: {error}")
                return []


def require(data, keys, filename, errors, prefix=""):
        for key in keys:
                if key not in data:
                        errors.append(f"{filename}: missing {prefix}{key}")


def validate_experience(entries, errors):
        for number, item in enumerate(entries, 1):
                if not isinstance(item, dict):
                        errors.append(f"experience.json entry {number}: must be an object")
                        continue
                for field in ("employer", "start", "role", "points"):
                        if field not in item:
                                errors.append(f"experience.json entry {number}: missing {field}")
                for field in ("role", "points"):
                        value = item.get(field, {})
                        if not isinstance(value, dict):
                                errors.append(f"experience.json entry {number}: {field} must be an object")
                                continue
                        for lang in ("en", "fi"):
                                if lang not in value:
                                        errors.append(f"experience.json entry {number}: missing {field}.{lang}")
                                elif field == "points" and not isinstance(value[lang], list):
                                        errors.append(f"experience.json entry {number}: {field}.{lang} must be a list")
                pts = item.get("points", {})
                if isinstance(pts, dict) and isinstance(pts.get("en"), list) and isinstance(pts.get("fi"), list) and len(pts["en"]) != len(pts["fi"]):
                        print(f"WARNING: experience.json entry {number}: points.en and points.fi have different lengths")


def validate_projects(entries, errors):
        for number, item in enumerate(entries, 1):
                if not isinstance(item, dict):
                        errors.append(f"projects.json entry {number}: must be an object")
                        continue
                for field in ("type", "title", "description"):
                        if field not in item:
                                errors.append(f"projects.json entry {number}: missing {field}")
                if item.get("type") not in ("hackathon", "personal"):
                        errors.append(f"projects.json entry {number}: type must be hackathon or personal")
                desc = item.get("description", {})
                if not isinstance(desc, dict):
                        errors.append(f"projects.json entry {number}: description must be an object")
                else:
                        for lang in ("en", "fi"):
                                if lang not in desc:
                                        errors.append(f"projects.json entry {number}: missing description.{lang}")


def validate(shared, en, fi, experience, projects, errors):
        require(shared, ["name", "initials", "email", "linkedin", "github", "domain"], "shared.json", errors)
        for lang, data in (("en", en), ("fi", fi)):
                require(data, ["lang", "locale", "headline", "summary", "location", "education", "certifications", "skills", "languages", "ui"], f"{lang}.json", errors)
                require(data.get("ui", {}), UI_KEYS, f"{lang}.json", errors, "ui.")
                for section in ("education", "skills"):
                        items = data.get(section, [])
                        if isinstance(items, list):
                                for index, item in enumerate(items, 1):
                                        if not isinstance(item, dict):
                                                errors.append(f"{lang}.json: {section} entry {index} must be an object")
        validate_experience(experience, errors)
        validate_projects(projects, errors)


def warn_placeholders(files):
        found = []
        def walk(filename, value, path):
                if isinstance(value, dict):
                        for key, child in value.items():
                                walk(filename, child, f"{path}.{key}" if path else key)
                elif isinstance(value, list):
                        for index, child in enumerate(value):
                                walk(filename, child, f"{path}[{index}]")
                elif isinstance(value, str) and "[" in value:
                        found.append((filename, path, value))
        for filename, data in files.items():
                walk(filename, data, "")
        for filename, path, value in found:
                print(f"WARNING: {filename} {path}: placeholder remains: {value}")
        print(f"Placeholder warning count: {len(found)}")


def link(url, label):
        if not url:
                return ""
        extra = ' target="_blank" rel="noopener noreferrer"' if str(url).startswith(("http://", "https://")) else ""
        return f'<a href="{esc(url)}"{extra}>{esc(label)}</a>'


def heading(label, title):
        return f'<h2><span class="section-label" data-label="{esc(label)}" aria-hidden="true"></span>{esc(title)}</h2>'


def build_page(lang, shared, text, experience, projects):
        fi = lang == "fi"
        root = "../" if fi else ""
        other = "../" if fi else "fi/"
        locale = text["locale"].replace("_", "-")
        domain = shared["domain"].rstrip("/")
        canonical = domain + ("/fi/" if fi else "/")
        en_url, fi_url = domain + "/", domain + "/fi/"
        ui = text["ui"]
        hero = text.get("hero", {"prompt": "whoami", "tagline": "[TAGLINE]", "status": [text["location"], "[WHAT I'M LOOKING FOR]", "[AVAILABILITY]"]})
        status = "".join(f"<li>{esc(line)}</li>" for line in hero.get("status", []))
        jobs = []
        for index, item in enumerate(experience, 1):
                end = item.get("end", "") or ui["present"]
                points = "".join(f"<li>{esc(value)}</li>" for value in item["points"][lang])
                jobs.append(f'<article class="job"><h3>{esc(item["role"][lang])}</h3><p class="job-meta"><span>{esc(item["employer"])}</span><time>{esc(item["start"])}</time><time>{esc(end)}</time></p><ul>{points}</ul></article>')
        project_groups = []
        for kind, label in (("hackathon", ui["hackathons"]), ("personal", ui["personalProjects"])):
                selected = [p for p in projects if p.get("type") == kind]
                selected = sorted(selected, key=lambda p: not p.get("featured", False))
                if not selected:
                        continue
                cards = []
                for index, item in enumerate(selected, 1):
                        date_line = f'<time>{esc(item.get("date", ""))}</time>' if item.get("date") else ""
                        event = f'<span>{esc(item.get("event", ""))}</span>' if kind == "hackathon" and item.get("event") else ""
                        result_value = item.get("result", {}).get(lang, "")
                        badge = f'<span class="result-badge">{esc(result_value)}</span>' if kind == "hackathon" and result_value else ""
                        meta = " · ".join(part for part in (date_line, event, badge) if part)
                        role = item.get("role", {}).get(lang, "")
                        tags = "".join(f'<span>#{esc(tag)}</span>' for tag in item.get("tags", []) if tag)
                        links = item.get("links", {})
                        link_html = " ".join(filter(None, (link(links.get("demo", ""), ui["demo"]), link(links.get("code", ""), ui["code"]), link(links.get("writeup", ""), ui["writeup"]))))
                        featured = " featured" if item.get("featured", False) else ""
                        cards.append(f'<article class="project-card{featured}"><h4>{esc(item.get("title", ""))}</h4>{f"<p class=project-meta>{meta}</p>" if meta else ""}{f"<p class=project-role>{esc(role)}</p>" if role else ""}<p>{esc(item.get("description", {}).get(lang, ""))}</p>{f"<p class=project-tags>{tags}</p>" if tags else ""}{f"<p class=project-links>{link_html}</p>" if link_html else ""}</article>')
                project_groups.append(f'<div class="project-subsection"><h3>{esc(label)}</h3><div class="project-grid">{"".join(cards)}</div></div>')
        skills = "".join(f'<div class="skill-group"><h3>{esc(item.get("group", ""))}</h3><p>{" · ".join(esc(value) for value in item.get("items", []))}</p></div>' for item in text["skills"])
        education = "".join(f'<article class="education-item"><h3>{esc(item.get("degree", ""))}</h3><p class="job-meta">{esc(item.get("school", ""))} · {esc(item.get("years", ""))}</p></article>' for item in text["education"])
        cert = f'<h3>{esc(ui["certifications"])}</h3><ul>{"".join(f"<li>{esc(v)}</li>" for v in text["certifications"])}</ul>' if text["certifications"] else ""
        contact = [link("mailto:" + shared["email"], shared["email"]), link(shared["linkedin"], "LinkedIn"), link(shared["github"], "GitHub"), esc(text["location"])]
        contacts = "".join(f"<li>{v}</li>" for v in contact if v)
        return "\n".join([
                '<!doctype html>', f'<html lang="{esc(lang)}">', '<head>',
                '  <meta charset="utf-8">', '  <meta name="viewport" content="width=device-width, initial-scale=1">',
                f'  <title>{esc(ui["meta_title"])}</title>', f'  <meta name="description" content="{esc(ui["meta_description"])}">',
                '  <meta name="color-scheme" content="dark light">', '  <meta name="theme-color" content="#101614">',
                f'  <link rel="canonical" href="{esc(canonical)}">', f'  <link rel="alternate" hreflang="en" href="{esc(en_url)}">', f'  <link rel="alternate" hreflang="fi" href="{esc(fi_url)}">', f'  <link rel="alternate" hreflang="x-default" href="{esc(en_url)}">',
                f'  <meta property="og:title" content="{esc(ui["meta_title"])}">', f'  <meta property="og:description" content="{esc(ui["meta_description"])}">', '  <meta property="og:type" content="website">', f'  <meta property="og:url" content="{esc(canonical)}">', f'  <meta property="og:locale" content="{esc(text["locale"])}">',
                f'  <link rel="icon" href="{root}favicon.svg" type="image/svg+xml">', f'  <script src="{root}theme.js"></script>', f'  <link rel="stylesheet" href="{root}style.css">', '</head>',
                '<body id="top">', f'  <a class="skip-link" href="#main">{esc(ui["skip"])}</a>', '  <header>', f'    <p class="terminal-prompt">$ {esc(hero["prompt"])}<span class="cursor" aria-hidden="true">_</span></p>', f'    <h1>{esc(shared["name"])}</h1>', f'    <p class="headline">{esc(text["headline"])}</p>', f'    <p class="hero-tagline">{esc(hero["tagline"])}</p>', f'    <ul class="hero-status">{status}</ul>', f'    <p class="summary">{esc(text["summary"])}</p>', '    <div class="topbar">', f'      <nav class="language-switch" aria-label="{"Kieli" if fi else "Language"}"><a href="{root}"{" aria-current=\"page\"" if not fi else ""}>EN</a><span aria-hidden="true">|</span><a href="{other}"{" aria-current=\"page\"" if fi else ""}>FI</a></nav>', f'      <button class="theme-toggle" type="button" aria-pressed="false" data-light-label="{esc(ui["themeToLight"])}" data-dark-label="{esc(ui["themeToDark"])}" aria-label="{esc(ui["themeToLight"])}">{esc(ui["themeToLight"])}</button>', '    </div>', '  </header>', '  <main id="main">', f'    <section id="projects">{heading(ui["sectionLabels"]["projects"],ui["projects"])}{"".join(project_groups)}</section>', f'    <section id="experience">{heading(ui["sectionLabels"]["experience"],ui["experience"])}{"".join(jobs)}</section>', f'    <section id="skills">{heading(ui["sectionLabels"]["skills"],ui["skills"])}<div class="skill-groups">{skills}</div></section>', f'    <section id="education">{heading(ui["sectionLabels"]["education"],ui["education"])}{education}{cert}</section>', f'    <section id="languages">{heading(ui["sectionLabels"]["languages"],ui["languages"])}<ul>{"".join(f"<li>{esc(v)}</li>" for v in text["languages"])}</ul></section>', f'    <section id="contact">{heading(ui["sectionLabels"]["contact"],ui["contact"])}<ul class="contact-list">{contacts}</ul></section>',
                '  </main>', f'  <footer><p>{esc(text.get("footer", "[SIGN-OFF]"))}</p><p>© {date.today().year} {esc(shared["name"])}</p><a class="back-to-top" href="#top">{esc(ui["backToTop"])}</a></footer>', '</body>', '</html>', ''
        ])


def not_found(en, fi):
        return "\n".join(['<!doctype html>','<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta name="color-scheme" content="dark light"><meta name="theme-color" content="#101614">',f'<title>{esc(en["ui"]["notFoundTitle"])} / {esc(fi["ui"]["notFoundTitle"])}</title>','<script src="theme.js"></script><link rel="stylesheet" href="style.css"></head><body id="top">',f'<a class="skip-link" href="#main">{esc(en["ui"]["skip"])}</a><header><h1>{esc(en["ui"]["notFoundTitle"])} / {esc(fi["ui"]["notFoundTitle"])}</h1></header><main id="main" class="not-found"><p lang="en">{esc(en["ui"]["notFoundText"])}</p><p lang="fi">{esc(fi["ui"]["notFoundText"])}</p><p><a href="index.html">EN</a> · <a href="fi/">FI</a></p></main></body></html>',''])


def main():
        parser=argparse.ArgumentParser(description="Generate and validate the bilingual CV website.")
        parser.add_argument("--check",action="store_true",help="validate content without writing generated files")
        args=parser.parse_args(); errors=[]
        shared=load_object("shared.json",errors); en=load_object("en.json",errors); fi=load_object("fi.json",errors)
        experience=load_list("experience.json",errors); projects=load_list("projects.json",errors)
        validate(shared,en,fi,experience,projects,errors)
        if errors:
                for error in errors: print("ERROR: "+error,file=sys.stderr)
                return 1
        warn_placeholders({"shared.json":shared,"en.json":en,"fi.json":fi,"experience.json":experience,"projects.json":projects})
        if args.check:
                print("Content validation passed; no files written.")
                return 0
        (SITE/"fi").mkdir(parents=True,exist_ok=True)
        en_html=build_page("en",shared,en,experience,projects); fi_html=build_page("fi",shared,fi,experience,projects)
        files={SITE/"index.html":en_html,SITE/"fi"/"index.html":fi_html,SITE/"404.html":not_found(en,fi),SITE/"favicon.svg":f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64" rx="10" fill="#8bd6ae"/><text x="32" y="42" text-anchor="middle" font-family="system-ui,sans-serif" font-size="30" font-weight="700" fill="#101614">{esc(shared["initials"])}</text></svg>',SITE/"sitemap.xml":f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>{esc(shared["domain"].rstrip("/")+"/")}</loc></url><url><loc>{esc(shared["domain"].rstrip("/")+"/fi/")}</loc></url></urlset>\n',SITE/"robots.txt":f'User-agent: *\nAllow: /\nSitemap: {shared["domain"].rstrip("/")}/sitemap.xml\n'}
        for path,content in files.items(): path.write_text(content,encoding="utf-8",newline="\n")
        print("Generated: site/index.html, site/fi/index.html, site/404.html, site/favicon.svg, site/sitemap.xml, site/robots.txt")
        return 0

if __name__=="__main__":
        raise SystemExit(main())
