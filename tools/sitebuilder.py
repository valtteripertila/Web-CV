"""Page renderers used by the existing build.py entry point."""

import html
import json
import os
import posixpath
import re
import shutil
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

from tools.quality import contrast_report


def esc(value):
    return html.escape(str(value), quote=True)


def real(value):
    return isinstance(value, str) and bool(value.strip()) and not value.strip().startswith("[")


def filled(value):
    return isinstance(value, str) and bool(value.strip())


def rel_dir(source, target):
    path = posixpath.relpath(target or ".", source or ".")
    return ("./" if path == "." else path.rstrip("/") + "/")


def page_file(base, directory):
    return base / directory / "index.html" if directory else base / "index.html"


def clean_url(value):
    return value.rstrip("/") + "/" if value else ""


def build_year():
    return os.environ.get("CV_BUILD_YEAR", str(date.today().year))


def link(url, label):
    if not url:
        return ""
    external = str(url).startswith(("http://", "https://"))
    attrs = ' target="_blank" rel="noopener noreferrer"' if external else ""
    return f'<a href="{esc(url)}"{attrs}>{esc(label)}</a>'


def heading(label, title):
    return f'<h2><span class="section-label" data-label="{esc(label)}" aria-hidden="true"></span>{esc(title)}</h2>'


def json_ld(data):
    return json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")


def content_model(content_dir, ui, sample=False):
    descriptions = ui.get("contentDescriptions", {})
    rows = []
    for path in sorted(content_dir.glob("*.json"), key=lambda item: item.name):
        key = path.stem
        detail = descriptions.get(key, "Structured project content." if ui.get("lang") == "en" else "Rakenteinen projektisisältö.")
        filename = ("SAMPLE " if sample else "") + path.name
        description = ("SAMPLE " if sample else "") + detail
        rows.append(f"<tr><th scope=\"row\"><code>{esc(filename)}</code></th><td>{esc(description)}</td></tr>")
    return "<table><thead><tr><th scope=\"col\">" + esc(ui["contentFile"]) + "</th><th scope=\"col\">" + esc(ui["contentHolds"]) + "</th></tr></thead><tbody>" + "".join(rows) + "</tbody></table>"


def check_registry(lang, sample=False):
    from tools.check import CHECKS
    index = 1 if lang == "en" else 2
    return "<ul>" + "".join(f"<li>{esc(('SAMPLE ' if sample else '') + item[index])}</li>" for item in CHECKS) + "</ul>"


def page_dirs(en, fi, has_now):
    pages = {"home": {"en": "", "fi": "fi"},
             "how": {"en": en["slugs"]["how"], "fi": "fi/" + fi["slugs"]["how"]},
             "changelog": {"en": en["slugs"]["changelog"], "fi": "fi/" + fi["slugs"]["changelog"]}}
    if has_now:
        pages["now"] = {"en": en["slugs"]["now"], "fi": "fi/" + fi["slugs"]["now"]}
    return pages


def page_url(domain, directory):
    return clean_url(domain) + (directory.rstrip("/") + "/" if directory else "")


def language_switch(lang, page, pages, ui):
    current = pages[page][lang]
    other_lang = "fi" if lang == "en" else "en"
    href = rel_dir(current, pages[page][other_lang])
    current_mark = ' aria-current="page"'
    en_mark = current_mark if lang == "en" else ""
    fi_mark = current_mark if lang == "fi" else ""
    return (f'<nav class="language-switch" aria-label="{esc(ui["languageNav"])}">'
            f'<a href="{rel_dir(current, pages[page]["en"])}"{en_mark}>EN</a><span aria-hidden="true">|</span>'
            f'<a href="{rel_dir(current, pages[page]["fi"])}"{fi_mark}>FI</a></nav>')


def site_menu(lang, page, pages, text, sample=False):
    ui = text["ui"]
    labels = (("home", ui["navHome"]), ("now", ui["navNow"]), ("how", ui["navHow"]), ("changelog", ui["navChangelog"]))
    items = []
    for key, label in labels:
        if key not in pages:
            continue
        items.append(f'<a href="{rel_dir(pages[page][lang], pages[key][lang])}">{esc(label)}</a>')
    prefix = "SAMPLE " if sample else ""
    return (f'<details class="site-menu"><summary aria-label="{esc(ui["navMenu"])}">{esc(prefix + ui["navMenu"])}</summary>'
            f'<nav aria-label="{esc(ui["mainNav"])}">{"".join(items)}</nav></details>')


def structured_data(page, lang, shared, text, experience, projects, domain, pages):
    person = {"@type": "Person"}
    for key, value in (("name", shared.get("name")), ("email", shared.get("email")), ("jobTitle", text.get("headline"))):
        if real(value):
            person[key] = value
    same_as = [value for value in (shared.get("linkedin"), shared.get("github"), shared.get("repo")) if real(value)]
    if same_as:
        person["sameAs"] = same_as
    skills = [entry.get("group", "") for entry in text.get("skills", []) if real(entry.get("group"))]
    skills.extend(item for entry in text.get("skills", []) for item in entry.get("items", []) if real(item))
    if skills:
        person["knowsAbout"] = skills
    if page == "home":
        graph = [person, {"@type": "WebSite", "name": shared["name"], "url": page_url(domain, pages["home"][lang]), "inLanguage": text["lang"]}]
        return {"@context": "https://schema.org", "@graph": graph}
    current_url = page_url(domain, pages[page][lang])
    home_url = page_url(domain, pages["home"][lang])
    return {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": 1, "name": text["ui"]["navHome"], "item": home_url},
        {"@type": "ListItem", "position": 2, "name": text["ui"].get("navHow" if page == "how" else "navChangelog" if page == "changelog" else "navNow"), "item": current_url}]}


def home_sections(lang, shared, text, experience, projects, ui, sample=False):
    result = []
    groups = []
    for kind, label in (("hackathon", ui["hackathons"]), ("personal", ui["personalProjects"])):
        selected = [item for item in projects if item.get("type") == kind]
        selected.sort(key=lambda item: not item.get("featured", False))
        if not selected:
            continue
        cards = []
        for item in selected:
            date_line = f'<time>{esc(item.get("date", ""))}</time>' if item.get("date") else ""
            event = f'<span>{esc(item["event"])}</span>' if kind == "hackathon" and filled(item.get("event")) else ""
            result_value = item.get("result", {}).get(lang, "")
            badge = f'<span class="result-badge">{esc(result_value)}</span>' if kind == "hackathon" and filled(result_value) else ""
            meta = " · ".join(part for part in (date_line, event, badge) if part)
            role = item.get("role", {}).get(lang, "")
            tag_prefix = "SAMPLE #" if sample else "#"
            tags = "".join(f'<span>{tag_prefix}{esc(tag[7:] if sample and tag.startswith("SAMPLE ") else tag)}</span>' for tag in item.get("tags", []) if filled(tag))
            links = item.get("links", {})
            link_html = " ".join(filter(None, (link(links.get("demo", ""), ui["demo"]), link(links.get("code", ""), ui["code"]), link(links.get("writeup", ""), ui["writeup"])) ))
            writeup = item.get("writeup", {})
            writeup_parts = []
            for field, label_key in (("team", "writeupTeam"), ("part", "writeupPart"), ("learned", "writeupLearned")):
                value = writeup.get(field, {}).get(lang, "")
                if filled(value):
                    writeup_parts.append(f'<p><strong>{esc(ui[label_key])}:</strong> {esc(value)}</p>')
            details = f'<details class="project-writeup"><summary>{esc(ui["writeupSummary"])}</summary>{"".join(writeup_parts)}</details>' if writeup_parts else ""
            featured = " featured" if item.get("featured", False) else ""
            title = item.get("title", "") if filled(item.get("title")) else ""
            description = item.get("description", {}).get(lang, "")
            if not any((title, meta, filled(role), filled(description), tags, link_html, details)):
                continue
            cards.append(f'<article class="project-card{featured}">{f"<h4>{esc(title)}</h4>" if title else ""}{f"<p class=project-meta>{meta}</p>" if meta else ""}{f"<p class=project-role>{esc(role)}</p>" if filled(role) else ""}{f"<p>{esc(description)}</p>" if filled(description) else ""}{f"<p class=project-tags>{tags}</p>" if tags else ""}{f"<p class=project-links>{link_html}</p>" if link_html else ""}{details}</article>')
        if cards:
            groups.append(f'<div class="project-subsection"><h3>{esc(label)}</h3><div class="project-grid">{"".join(cards)}</div></div>')
    if groups:
        result.append(f'<section id="projects">{heading(ui["sectionLabels"]["projects"], ui["projects"])}{"".join(groups)}</section>')
    jobs = []
    for item in experience:
        role = item.get("role", {}).get(lang, "")
        points = "".join(f"<li>{esc(value)}</li>" for value in item.get("points", {}).get(lang, []) if filled(value))
        fields = [item.get("employer", ""), item.get("start", ""), item.get("end", "") or ui["present"]]
        meta = "".join(f"<span>{esc(value)}</span>" for value in fields if filled(value))
        if filled(role) or meta or points:
            jobs.append(f'<article class="job">{f"<h3>{esc(role)}</h3>" if filled(role) else ""}{f"<p class=job-meta>{meta}</p>" if meta else ""}{f"<ul>{points}</ul>" if points else ""}</article>')
    if jobs:
        result.append(f'<section id="experience">{heading(ui["sectionLabels"]["experience"], ui["experience"])}{"".join(jobs)}</section>')
    skill_groups = []
    for item in text.get("skills", []):
        group = item.get("group", "")
        values = [value for value in item.get("items", []) if filled(value)]
        if filled(group) or values:
            skill_groups.append(f'<div class="skill-group">{f"<h3>{esc(group)}</h3>" if filled(group) else ""}{f"<p>{" · ".join(esc(value) for value in values)}</p>" if values else ""}</div>')
    if skill_groups:
        result.append(f'<section id="skills">{heading(ui["sectionLabels"]["skills"], ui["skills"])}<div class="skill-groups">{"".join(skill_groups)}</div></section>')
    education = []
    for item in text.get("education", []):
        degree = item.get("degree", "")
        school_years = " · ".join(esc(value) for value in (item.get("school", ""), item.get("years", "")) if filled(value))
        if filled(degree) or school_years:
            education.append(f'<article class="education-item">{f"<h3>{esc(degree)}</h3>" if filled(degree) else ""}{f"<p class=job-meta>{school_years}</p>" if school_years else ""}</article>')
    certs = [value for value in text.get("certifications", []) if filled(value)]
    if education or certs:
        cert_html = f'<h3>{esc(ui["certifications"])}</h3><ul>{"".join(f"<li>{esc(value)}</li>" for value in certs)}</ul>' if certs else ""
        result.append(f'<section id="education">{heading(ui["sectionLabels"]["education"], ui["education"])}{"".join(education)}{cert_html}</section>')
    languages = [value for value in text.get("languages", []) if filled(value)]
    if languages:
        result.append(f'<section id="languages">{heading(ui["sectionLabels"]["languages"], ui["languages"])}<ul>{"".join(f"<li>{esc(value)}</li>" for value in languages)}</ul></section>')
    email = shared.get("email", "")
    contact_items = [link("mailto:" + email, email) if filled(email) else "",
                     link(shared.get("linkedin", ""), ("SAMPLE " if sample else "") + "LinkedIn"),
                     link(shared.get("github", ""), ("SAMPLE " if sample else "") + "GitHub"),
                     esc(text.get("location", "")) if filled(text.get("location")) else ""]
    contact_items = [value for value in contact_items if value]
    if contact_items:
        result.append(f'<section id="contact">{heading(ui["sectionLabels"]["contact"], ui["contact"])}<ul class="contact-list">{"".join(f"<li>{value}</li>" for value in contact_items)}</ul></section>')
    return "".join(result)


def how_body(lang, shared, text, site_info, quality, pages, sizes, contrast_pass, root, sample=False):
    ui = text["ui"]
    labels = ui["sectionLabels"]
    intro = site_info.get("intro", {}).get(lang, "")
    architecture_lines = ["content/*.json", "  -> build.py", "  -> site/", "  -> GitHub main", "  -> Cloudflare Pages"]
    if sample:
        architecture_lines = ["SAMPLE " + line for line in architecture_lines]
    diagram = "\n".join(architecture_lines)
    files_table = content_model(root / "content", ui, sample)
    checks = check_registry(lang, sample)
    csp = ""
    headers = root / "site" / "_headers"
    if headers.exists():
        for line in headers.read_text(encoding="utf-8").splitlines():
            if "Content-Security-Policy:" in line:
                csp = line.split("Content-Security-Policy:", 1)[1].strip()
                break
    if sample and csp:
        csp = "SAMPLE " + csp
    fact_text = f'{ui["externalRequests"]}: {sizes["external"]}; {ui["siteBytes"]}: {sizes[lang] / 1000:.1f} KB; {ui["contrastPass"] if contrast_pass else ui["contrastFail"]}.'
    score = quality.get("lighthouse", {}) if isinstance(quality, dict) else {}
    if valid_lighthouse(score):
        fact_text += " " + ui["lighthouseLabel"] + ": " + ", ".join(f"{name.replace('_', ' ')} {score[name]}" for name in ("performance", "accessibility", "best_practices", "seo")) + f" ({score['measured_on']})."
    sections = [
        f'<section id="overview">{heading(labels["overview"], ui["overview"])}<p>{esc(intro)}</p></section>',
        f'<section id="architecture">{heading(labels["architecture"], ui["architecture"])}<pre aria-label="{esc(ui["architecture"])}">{esc(diagram)}</pre></section>',
        f'<section id="content-model">{heading(labels["contentModel"], ui["contentModel"])}{files_table}</section>',
        f'<section id="automated-checks">{heading(labels["automatedChecks"], ui["automatedChecks"])}{checks}</section>',
        f'<section id="constraints">{heading(labels["constraints"], ui["constraints"])}<h3>{esc(ui["cspLabel"])}</h3><pre>{esc(csp)}</pre><h3>{esc(ui["buildFacts"])}</h3><p>{esc(fact_text)}</p></section>'
    ]
    if real(shared.get("repo")) and urlparse(shared["repo"]).scheme in ("http", "https"):
        sections.append(f'<section id="source">{heading(labels["source"], ui["source"])}<p>{link(shared["repo"], ui["source"])}</p></section>')
    note = site_info.get("ai_note", {}).get(lang, "")
    if real(note):
        sections.append(f'<section id="ai-assisted">{heading(labels["aiAssisted"], ui["aiAssisted"])}<p>{esc(note)}</p></section>')
    return "".join(sections)


def changelog_body(lang, text, changelog):
    ui = text["ui"]
    entries = []
    for item in changelog:
        value = item.get(lang, "")
        if real(value):
            entries.append(f'<li><time datetime="{esc(item["date"])}">{esc(item["date"])}</time> — {esc(value)}</li>')
    label = ui["sectionLabels"]["entries"]
    return f'<section id="entries">{heading(label, ui["navChangelog"])}<p>{esc(ui["changelogIntro"])}</p><ol class="changelog-list">{"".join(entries)}</ol></section>'


def now_body(lang, text, now):
    ui = text["ui"]
    entries = [item.get(lang, "") for item in now.get("items", []) if real(item.get(lang, ""))]
    return (f'<section id="now">{heading(ui["sectionLabels"]["now"], ui["navNow"])}'
            f'<p>{esc(ui["nowIntro"])}</p><p><strong>{esc(ui["updated"])}:</strong> <time datetime="{esc(now["updated"])}">{esc(now["updated"])}</time></p>'
            f'<ul>{"".join(f"<li>{esc(value)}</li>" for value in entries)}</ul></section>')


def count_external_resources(document):
    tags = re.findall(r"<(?:script|img|iframe|source|video|audio|link)\b[^>]*>", document, re.I)
    count = 0
    for tag in tags:
        rel = re.search(r'\brel=["\']([^"\']+)', tag, re.I)
        if tag.lower().startswith("<link") and rel and not set(rel.group(1).lower().split()) & {"stylesheet", "icon", "preload", "modulepreload", "manifest"}:
            continue
        for attr in ("src", "href"):
            match = re.search(rf'\b{attr}=["\']([^"\']+)', tag, re.I)
            if match and urlparse(match.group(1)).scheme in ("http", "https"):
                count += 1
    return count


def external_request_count(document, stylesheet, script, favicon):
    count = count_external_resources(document)
    count += len(re.findall(r"url\(\s*['\"]?https?://", stylesheet, re.I))
    count += len(re.findall(r"(?:import\s*\(|from\s*|src\s*=\s*)['\"]https?://", script, re.I))
    count += len(re.findall(r"(?:href|src)=['\"]https?://", favicon, re.I))
    return count


def size_line(lang, ui, byte_count, external, contrast_pass, quality=None):
    contrast = ui["contrastLabel"] if contrast_pass else ""
    value = ui["buildChecked"].format(external=external, size=f"{byte_count / 1000:.1f}", contrast=contrast)
    quality = quality or {}
    if valid_lighthouse(quality.get("lighthouse", {})):
        value += ui["lighthouseFooter"].format(**quality["lighthouse"])
    return value


def valid_lighthouse(value):
    if not isinstance(value, dict):
        return False
    required = ("performance", "accessibility", "best_practices", "seo", "measured_on", "source")
    if any(key not in value or value[key] in (None, "") for key in required):
        return False
    try:
        if any(not isinstance(value[key], (int, float)) or not 0 <= value[key] <= 100 for key in required[:4]):
            return False
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value["measured_on"]):
            return False
        date.fromisoformat(value["measured_on"])
    except (ValueError, TypeError):
        return False
    return True


def render_document(page, lang, shared, text, body, pages, domain, sizes, contrast_pass, root, sample=False):
    directory = pages[page][lang]
    depth = rel_dir(directory, "")
    asset_prefix = "" if not directory else depth
    if asset_prefix == "./":
        asset_prefix = ""
    ui = text["ui"]
    page_title = shared["name"] if page == "home" else ui["navHow"] if page == "how" else ui["navChangelog"] if page == "changelog" else ui["navNow"]
    description = text.get("ui", {}).get("meta_description", "")
    canonical = page_url(domain, directory)
    counterpart = page_url(domain, pages[page]["fi" if lang == "en" else "en"])
    lang_alts = (f'<link rel="alternate" hreflang="en" href="{esc(page_url(domain, pages[page]["en"]))}">'
                 f'<link rel="alternate" hreflang="fi" href="{esc(page_url(domain, pages[page]["fi"]))}">'
                 f'<link rel="alternate" hreflang="x-default" href="{esc(page_url(domain, pages[page]["en"]))}">')
    depth_path = asset_prefix
    switch = language_switch(lang, page, pages, ui)
    toggle = f'<button class="theme-toggle" type="button" aria-pressed="false" data-light-label="{esc(ui["themeToLight"])}" data-dark-label="{esc(ui["themeToDark"])}" aria-label="{esc(ui["themeToLight"])}">{esc(ui["themeToLight"])}</button>'
    structured = structured_data(page, lang, shared, text, [], [], domain, pages)
    structured_tag = '<script type="application/ld+json">' + json_ld(structured) + "</script>"
    og = ""
    if (root / "site" / "og.png").exists():
        og = '<meta property="og:image" content="' + esc(clean_url(domain) + "og.png") + '"><meta name="twitter:card" content="summary_large_image">'
    menu = site_menu(lang, page, pages, text, sample)
    fact = size_line(lang, ui, sizes[lang], sizes["external"], contrast_pass, sizes.get("quality"))
    title = page_title if real(page_title) else ui["navHome"]
    if page == "home":
        hero = text.get("hero", {})
        prompt = esc(hero.get("prompt", "whoami"))
        header_h1 = esc(shared.get("name", ""))
        headline = text.get("headline", "")
        tagline = hero.get("tagline", "")
        status = "".join(f"<li>{esc(value)}</li>" for value in hero.get("status", []))
        page_intro = (f'<p class="headline">{esc(headline)}</p>' if headline else "")
        page_intro += (f'<p class="hero-tagline">{esc(tagline)}</p>' if tagline else "")
        page_intro += (f'<ul class="hero-status">{status}</ul>' if status else "")
        page_intro += (f'<p class="summary">{esc(text.get("summary", ""))}</p>' if text.get("summary") else "")
        title_tag = text.get("ui", {}).get("meta_title", title)
    else:
        prompt = ("SAMPLE " if sample else "") + "cat " + page
        header_h1 = esc(title)
        page_intro = f'<p class="page-intro">{esc(ui["pageIntro"])}</p>'
        title_tag = title
    if sample:
        fact = "SAMPLE " + fact
        switch = switch.replace(">EN<", ">SAMPLE EN<").replace(">FI<", ">SAMPLE FI<")
    footer = (f'<footer><p>{"SAMPLE " if sample else ""}© {build_year()} {esc(shared["name"])}</p>'
              f'<a class="build-facts" href="{rel_dir(directory, pages["how"][lang])}#automated-checks">{esc(fact)}</a>'
              f'<a class="back-to-top" href="#top">{esc(ui["backToTop"])}</a></footer>')
    prefix = "SAMPLE " if sample else ""
    return "\n".join([
        "<!doctype html>", f'<html lang="{esc(lang)}"><head>',
        '  <meta charset="utf-8">', '  <meta name="viewport" content="width=device-width, initial-scale=1">',
        f'  <title>{esc(title_tag)}</title>', f'  <meta name="description" content="{esc(description)}">',
        '  <meta name="color-scheme" content="dark light">', '  <meta name="theme-color" content="#101614">',
        f'  <link rel="canonical" href="{esc(canonical)}">', f'  {lang_alts}',
        f'  <meta property="og:title" content="{esc(title)}">', f'  <meta property="og:description" content="{esc(description)}">',
        f'  <meta property="og:type" content="website"><meta property="og:url" content="{esc(canonical)}">{og}',
        f'  <link rel="icon" href="{depth_path}favicon.svg" type="image/svg+xml">',
        f'  <script src="{depth_path}theme.js"></script>', f'  <link rel="stylesheet" href="{depth_path}style.css">', f'  {structured_tag}',
        '</head><body id="top">', f'  <a class="skip-link" href="#main">{esc(ui["skip"])}</a>',
        '  <header>', f'    <p class="terminal-prompt">$ {prompt}<span class="cursor" aria-hidden="true">_</span></p>',
        f'    <h1>{header_h1}</h1>', page_intro,
        f'    <div class="topbar">{switch}{menu}{toggle}</div>', '  </header>', f'  <main id="main">{body}</main>', f'  {footer}', '</body></html>', ""
    ])


def make_llms(shared, en, fi, projects, pages, domain):
    lines = ["# " + shared["name"], ""]
    for lang, text in (("en", en), ("fi", fi)):
        if real(text.get("headline")):
            lines.append(text["headline"])
        if real(text.get("summary")):
            lines.append(text["summary"])
        lines.append(f"- [{lang.upper()} CV]({page_url(domain, pages['home'][lang])})")
        lines.append(f"- [{text['ui']['navHow']}]({page_url(domain, pages['how'][lang])})")
        lines.append(f"- [{text['ui']['navChangelog']}]({page_url(domain, pages['changelog'][lang])})")
        if "now" in pages:
            lines.append(f"- [{text['ui']['navNow']}]({page_url(domain, pages['now'][lang])})")
    for label, value in (("GitHub", shared.get("github")), ("LinkedIn", shared.get("linkedin"))):
        if real(value):
            lines.append(f"- {label}: {value}")
    real_projects = [item for item in projects if real(item.get("title"))]
    if real_projects:
        lines.extend(["", "## Projects"])
        for item in real_projects:
            links = item.get("links", {})
            destinations = [links[key] for key in ("demo", "code", "writeup") if real(links.get(key))]
            suffix = " — " + ", ".join(destinations) if destinations else ""
            lines.append(f"- {item['title']}{suffix}")
    return "\n".join(lines) + "\n"


def generate(root, shared, en, fi, experience, projects, site_info, quality, changelog, now, output_dir=None, sample=False):
    root = Path(root)
    content_dir = root / "content"
    out = Path(output_dir) if output_dir else root / "site"
    out.mkdir(parents=True, exist_ok=True)
    if sample:
        project_types = [item.get("type") for item in projects]
        def sample_value(value):
            if isinstance(value, dict):
                return {key: sample_value(child) for key, child in value.items()}
            if isinstance(value, list):
                return [sample_value(child) for child in value]
            if isinstance(value, str) and value:
                return "SAMPLE " + value
            return value
        shared, en, fi = sample_value(shared), sample_value(en), sample_value(fi)
        experience, projects = sample_value(experience), sample_value(projects)
        for index, item in enumerate(projects):
            item["type"] = project_types[index]
        site_info, quality = sample_value(site_info), sample_value(quality)
        changelog = sample_value(changelog)
        shared["domain"] = "https://example.invalid"
        for item in projects:
            if item.get("type") == "hackathon":
                item["writeup"] = {key: {"en": "SAMPLE preview text", "fi": "SAMPLE esimerkkiteksti"} for key in ("team", "part", "learned")}
        # Slugs remain safe for a preview URL while all displayed copy is sample-labelled.
        en["slugs"] = {"how": "how-this-site-is-built", "changelog": "changelog", "now": "now"}
        fi["slugs"] = {"how": "sivuston-rakenne", "changelog": "muutosloki", "now": "nyt"}
        now = {"updated": "2026-11-26", "items": []}
    has_now = bool(now.get("items"))
    pages = page_dirs(en, fi, has_now)
    domain = shared.get("domain", "")
    stylesheet = (root / "site" / "style.css").read_text(encoding="utf-8")
    theme = (root / "site" / "theme.js").read_text(encoding="utf-8")
    contrast_pass, _ = contrast_report(stylesheet)
    favicon = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64" rx="10" fill="#8bd6ae"/><text x="32" y="42" text-anchor="middle" font-family="system-ui,sans-serif" font-size="30" font-weight="700" fill="#101614">{esc(shared.get("initials", ""))}</text></svg>'
    css_bytes, js_bytes, icon_bytes = map(lambda value: len(value.encode("utf-8")), (stylesheet, theme, favicon))
    size = {"external": external_request_count("", stylesheet, theme, favicon), "en": 0, "fi": 0, "quality": quality}
    rendered = {}
    for lang, text in (("en", en), ("fi", fi)):
        body = home_sections(lang, shared, text, experience, projects, text["ui"], sample=sample)
        rendered[("home", lang)] = body
        # Iterate to account for the measured footer line in the HTML byte total.
        total = css_bytes + js_bytes + icon_bytes
        for _ in range(6):
            size[lang] = total
            rendered_doc = render_document("home", lang, shared, text, body, pages, domain,
                                           size, contrast_pass, root, sample)
            size["external"] = external_request_count(rendered_doc, stylesheet, theme, favicon)
            updated = len(rendered_doc.encode("utf-8")) + css_bytes + js_bytes + icon_bytes
            if updated == total:
                break
            total = updated
        size[lang] = total
    out_files = {}
    for page in ("home", "how", "changelog", "now"):
        if page not in pages:
            continue
        for lang, text in (("en", en), ("fi", fi)):
            if page == "home":
                body = rendered[(page, lang)]
            elif page == "how":
                body = how_body(lang, shared, text, site_info, quality, pages, size, contrast_pass, root, sample)
            elif page == "changelog":
                body = changelog_body(lang, text, changelog)
            else:
                body = now_body(lang, text, now)
            document = render_document(page, lang, shared, text, body, pages, domain, size, contrast_pass, root, sample)
            out_files[page_file(out, pages[page][lang])] = document
    for path, content in out_files.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8", newline="\n")
    # Remove only stale generated optional pages when their content has been emptied.
    if not has_now:
        for directory in (en["slugs"]["now"], "fi/" + fi["slugs"]["now"]):
            path = page_file(out, directory)
            if path.exists():
                path.unlink()
    (out / "favicon.svg").write_text(favicon, encoding="utf-8", newline="\n")
    llms = make_llms(shared, en, fi, projects, pages, domain)
    if sample:
        llms = "SAMPLE " + llms
    (out / "llms.txt").write_text(llms, encoding="utf-8", newline="\n")
    (out / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {domain.rstrip('/')}/sitemap.xml\n", encoding="utf-8", newline="\n")
    sitemap_urls = []
    for page, langs in pages.items():
        for lang in ("en", "fi"):
            sitemap_urls.append((page, lang, page_url(domain, langs[lang])))
    sitemap = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">']
    for page, lang, url in sitemap_urls:
        sitemap.append(f'  <url><loc>{esc(url)}</loc>')
        for alt_lang in ("en", "fi"):
            sitemap.append(f'    <xhtml:link rel="alternate" hreflang="{alt_lang}" href="{esc(page_url(domain, pages[page][alt_lang]))}" />')
        if lang == "en":
            sitemap.append(f'    <xhtml:link rel="alternate" hreflang="x-default" href="{esc(url)}" />')
        sitemap.append("  </url>")
    sitemap.append("</urlset>")
    (out / "sitemap.xml").write_text("\n".join(sitemap) + "\n", encoding="utf-8", newline="\n")
    (out / "404.html").write_text(not_found(shared, en, fi, pages, size, contrast_pass, sample), encoding="utf-8", newline="\n")
    if sample:
        shutil.copy2(root / "site" / "style.css", out / "style.css")
        shutil.copy2(root / "site" / "theme.js", out / "theme.js")
        shutil.copy2(root / "site" / "_headers", out / "_headers")
    print("Generated: " + ", ".join(str(path.relative_to(out)).replace("\\", "/") for path in sorted(out_files)))
    return out_files


def not_found(shared, en, fi, pages, sizes, contrast_pass, sample=False):
    en_ui, fi_ui = en["ui"], fi["ui"]
    sample_prefix = "SAMPLE " if sample else ""
    menu = site_menu("en", "home", pages, en, sample)
    facts = []
    for lang, ui in (("en", en_ui), ("fi", fi_ui)):
        href = rel_dir("", pages["how"][lang]) + "#automated-checks"
        facts.append(f'<a class="build-facts" href="{href}">{esc(sample_prefix + size_line(lang, ui, sizes[lang], sizes["external"], contrast_pass, sizes.get("quality")))}</a>')
    return "\n".join(["<!doctype html>", '<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta name="color-scheme" content="dark light"><meta name="theme-color" content="#101614">',
        f'<title>{esc(en["ui"]["notFoundTitle"])} / {esc(fi["ui"]["notFoundTitle"])}</title>',
        '<script src="theme.js"></script><link rel="stylesheet" href="style.css"></head><body id="top">',
        f'<a class="skip-link" href="#main">{esc(sample_prefix + en["ui"]["skip"])}</a><header><h1>{esc(sample_prefix + en["ui"]["notFoundTitle"])} / {esc(sample_prefix + fi["ui"]["notFoundTitle"])}</h1><div class="topbar">{menu}</div></header>',
        f'<main id="main" class="not-found"><p lang="en">{esc(sample_prefix + en["ui"]["notFoundText"])}</p><p lang="fi">{esc(sample_prefix + fi["ui"]["notFoundText"])}</p><p><a href="index.html">{sample_prefix}EN</a> · <a href="fi/">{sample_prefix}FI</a></p></main>',
        f'<footer><p>{sample_prefix}© {build_year()} {esc(shared["name"])}</p>{"".join(facts)}</footer>', '</body></html>', ""])
