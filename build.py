#!/usr/bin/env python3
"""Build the static English and Finnish CV pages from JSON content."""

import argparse
import html
import json
import sys
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parent
CONTENT = ROOT / "content"
SITE = ROOT / "site"


def esc(value):
  return html.escape(str(value), quote=True)


def load_json(filename, errors):
  path = CONTENT / filename
  try:
    with path.open(encoding="utf-8") as handle:
      data = json.load(handle)
    if not isinstance(data, dict):
      errors.append(f"{filename}: root must be a JSON object")
      return {}
    return data
  except (OSError, json.JSONDecodeError) as error:
    errors.append(f"{filename}: {error}")
    return {}


def check_keys(data, keys, filename, errors, prefix=""):
  for key in keys:
    if key not in data:
      errors.append(f"{filename}: missing key {prefix}{key}")


def ids(items, filename, field, errors):
  if not isinstance(items, list):
    errors.append(f"{filename}: {field} must be a list")
    return []
  result = []
  for index, item in enumerate(items):
    if not isinstance(item, dict) or "id" not in item:
      errors.append(f"{filename}: {field}[{index}] is missing id")
    else:
      result.append(item["id"])
  if len(result) != len(set(result)):
    errors.append(f"{filename}: duplicate ids in {field}")
  return result


def validate(shared, en, fi, errors):
  check_keys(shared, ["name", "initials", "email", "linkedin", "github", "domain", "experience", "education", "projects"], "shared.json", errors)
  check_keys(en, ["lang", "locale", "headline", "summary", "location", "experience", "education", "certifications", "skills", "languages", "projects", "ui"], "en.json", errors)
  check_keys(fi, ["lang", "locale", "headline", "summary", "location", "experience", "education", "certifications", "skills", "languages", "projects", "ui"], "fi.json", errors)
  check_keys(en.get("ui", {}), ["skip", "about", "experience", "projects", "education", "certifications", "skills", "languages", "contact", "present", "viewProject", "code", "backToTop", "themeToLight", "themeToDark", "meta_title", "meta_description", "notFoundTitle", "notFoundText"], "en.json", errors, "ui.")
  check_keys(fi.get("ui", {}), ["skip", "about", "experience", "projects", "education", "certifications", "skills", "languages", "contact", "present", "viewProject", "code", "backToTop", "themeToLight", "themeToDark", "meta_title", "meta_description", "notFoundTitle", "notFoundText"], "fi.json", errors, "ui.")
  item_keys = {
    "shared.json": {"experience": ["id", "employer", "start", "end"], "education": ["id", "school", "years"], "projects": ["id", "tags", "url", "code"]},
    "en.json": {"experience": ["id", "role", "achievements"], "education": ["id", "degree"], "projects": ["id", "title", "description"]},
    "fi.json": {"experience": ["id", "role", "achievements"], "education": ["id", "degree"], "projects": ["id", "title", "description"]},
  }
  for filename, data in (("shared.json", shared), ("en.json", en), ("fi.json", fi)):
    for group, keys in item_keys[filename].items():
      items = data.get(group, [])
      if isinstance(items, list):
        for index, item in enumerate(items):
          if isinstance(item, dict):
            check_keys(item, keys, filename, errors, f"{group}[{index}].")
          else:
            errors.append(f"{filename}: {group}[{index}] must be an object")
  for filename, data in (("en.json", en), ("fi.json", fi)):
    for group, keys in (("skills", ["group", "items"]),):
      for index, item in enumerate(data.get(group, [])):
        if isinstance(item, dict):
          check_keys(item, keys, filename, errors, f"{group}[{index}].")
        else:
          errors.append(f"{filename}: {group}[{index}] must be an object")
  for group in ("experience", "education", "projects"):
    base = ids(shared.get(group, []), "shared.json", group, errors)
    for language, filename in ((en, "en.json"), (fi, "fi.json")):
      translated = ids(language.get(group, []), filename, group, errors)
      if set(translated) != set(base):
        errors.append(f"{filename}: {group} ids must match shared.json (missing: {sorted(set(base) - set(translated))}; extra: {sorted(set(translated) - set(base))})")
    other = fi if language is en else en
    if set(ids(en.get(group, []), "en.json", group, errors)) != set(ids(other.get(group, []), "fi.json", group, errors)):
      errors.append(f"{group} ids differ between en.json and fi.json")


def warnings(data_by_file):
  found = []
  def walk(filename, value, path):
    if isinstance(value, dict):
      for key, item in value.items():
        walk(filename, item, f"{path}.{key}" if path else key)
    elif isinstance(value, list):
      for index, item in enumerate(value):
        walk(filename, item, f"{path}[{index}]")
    elif isinstance(value, str) and "[" in value:
      found.append((filename, path, value))
  for filename, data in data_by_file.items():
    walk(filename, data, "")
  for filename, path, value in found:
    print(f"WARNING: {filename} {path}: placeholder remains: {value}")
  print(f"Placeholder warning count: {len(found)}")


def by_id(items):
  return {item["id"]: item for item in items}


def link(url, label, class_name=""):
  if not url:
    return ""
  cls = f' class="{esc(class_name)}"' if class_name else ""
  external = " target=\"_blank\" rel=\"noopener noreferrer\"" if str(url).startswith(("https://", "http://")) else ""
  return f'<a{cls} href="{esc(url)}"{external}>{esc(label)}</a>'


def page(lang, shared, text):
  fi = lang == "fi"
  root = "../" if fi else ""
  other_path = "../" if fi else "fi/"
  locale = text["locale"].replace("_", "-")
  domain = shared["domain"].rstrip("/")
  canonical = domain + ("/fi/" if fi else "/")
  en_path = domain + "/"
  fi_path = domain + "/fi/"
  same_as = [value for value in (shared["linkedin"], shared["github"]) if value]
  job_data, education_data, project_data = (by_id(shared[k]) for k in ("experience", "education", "projects"))
  jobs = []
  localized_jobs = by_id(text["experience"])
  for shared_item in shared["experience"]:
    item = localized_jobs[shared_item["id"]]
    end = shared_item["end"] or text["ui"]["present"]
    achievements = "\n".join(f"          <li>{esc(value)}</li>" for value in item["achievements"])
    jobs.append(f'''        <article class="job" id="{esc(item['id'])}">
          <h3>{esc(item['role'])}</h3>
          <p class="job-meta">{esc(shared_item['employer'])} · <time>{esc(shared_item['start'])}</time> – <time>{esc(end)}</time></p>
          <ul>
{achievements}
          </ul>
        </article>''')
  projects = []
  localized_projects = by_id(text["projects"])
  for shared_item in shared["projects"]:
    item = localized_projects[shared_item["id"]]
    tags = "".join(f"<span>{esc(tag)}</span>" for tag in shared_item["tags"])
    links = " ".join(filter(None, (link(shared_item["url"], text["ui"]["viewProject"]), link(shared_item["code"], text["ui"]["code"]))))
    projects.append(f'''        <article class="project-card" id="{esc(item['id'])}">
          <h3>{esc(item['title'])}</h3>
          <p>{esc(item['description'])}</p>
          <p class="project-tags">{tags}</p>
          <p class="project-links">{links}</p>
        </article>''')
  education = []
  localized_education = by_id(text["education"])
  for shared_item in shared["education"]:
    item = localized_education[shared_item["id"]]
    education.append(f'''        <article class="education-item" id="{esc(item['id'])}">
          <h3>{esc(item['degree'])}</h3>
          <p class="job-meta">{esc(shared_item['school'])} · {esc(shared_item['years'])}</p>
        </article>''')
  certifications = ""
  if text["certifications"]:
    certifications = f'''        <h3>{esc(text['ui']['certifications'])}</h3>
        <ul>{''.join(f'<li>{esc(value)}</li>' for value in text['certifications'])}</ul>'''
  skills = "\n".join(f'''          <div class="skill-group"><h3>{esc(group['group'])}</h3><p>{' · '.join(esc(value) for value in group['items'])}</p></div>''' for group in text["skills"])
  contact_links = [link("mailto:" + shared["email"], shared["email"]), link(shared["linkedin"], "LinkedIn"), link(shared["github"], "GitHub")]
  contact_list = "\n".join(f"          <li>{entry}</li>" for entry in contact_links if entry)
  initials = shared["initials"]
  favicon = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64" rx="10" fill="#315e68"/><text x="32" y="42" text-anchor="middle" font-family="system-ui,sans-serif" font-size="{max(12, 36 - len(initials) * 3)}" font-weight="700" fill="#fff">{esc(initials)}</text></svg>'''
  json_ld = {"@context": "https://schema.org", "@type": "Person", "name": shared["name"], "jobTitle": text["headline"], "email": "mailto:" + shared["email"], "sameAs": same_as}
  json_ld_text = json.dumps(json_ld, ensure_ascii=False).replace("</", "<\\/")
  return f'''<!doctype html>
<html lang="{esc(lang)}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{esc(text['ui']['meta_title'])}</title>
  <meta name="description" content="{esc(text['ui']['meta_description'])}">
  <meta name="color-scheme" content="dark light">
  <meta name="theme-color" content="#101614">
  <link rel="canonical" href="{esc(canonical)}">
  <link rel="alternate" hreflang="en" href="{esc(en_path)}">
  <link rel="alternate" hreflang="fi" href="{esc(fi_path)}">
  <link rel="alternate" hreflang="x-default" href="{esc(en_path)}">
  <meta property="og:title" content="{esc(text['ui']['meta_title'])}">
  <meta property="og:description" content="{esc(text['ui']['meta_description'])}">
  <meta property="og:type" content="website">
  <meta property="og:url" content="{esc(canonical)}">
  <meta property="og:locale" content="{esc(text['locale'])}">
  <link rel="icon" href="{root}favicon.svg" type="image/svg+xml">
  <script src="{root}theme.js"></script>
  <link rel="stylesheet" href="{root}style.css">
  <script type="application/ld+json">{json_ld_text}</script>
</head>
<body id="top">
  <a class="skip-link" href="#main">{esc(text['ui']['skip'])}</a>
  <header>
    <h1>{esc(shared['name'])}</h1>
    <p class="headline">{esc(text['headline'])}</p>
    <div class="topbar">
      <nav class="language-switch" aria-label="{'Kieli' if fi else 'Language'}">
        <a href="{root}"{' aria-current="page"' if not fi else ''}>EN</a><span aria-hidden="true">|</span><a href="{other_path}"{' aria-current="page"' if fi else ''}>FI</a>
      </nav>
      <button class="theme-toggle" type="button" aria-pressed="false" data-light-label="{esc(text['ui']['themeToLight'])}" data-dark-label="{esc(text['ui']['themeToDark'])}" aria-label="{esc(text['ui']['themeToLight'])}">{esc(text['ui']['themeToLight'])}</button>
    </div>
  </header>
  <main id="main">
    <section id="about"><h2>{esc(text['ui']['about'])}</h2><p>{esc(text['summary'])}</p></section>
    <section id="experience"><h2>{esc(text['ui']['experience'])}</h2>
{chr(10).join(jobs)}
    </section>
    <section id="projects"><h2>{esc(text['ui']['projects'])}</h2><div class="project-grid">
{chr(10).join(projects)}
    </div></section>
    <section id="education"><h2>{esc(text['ui']['education'])}</h2>
{chr(10).join(education)}
{certifications}
    </section>
    <section id="skills"><h2>{esc(text['ui']['skills'])}</h2><div class="skill-groups">
{skills}
    </div></section>
    <section id="languages"><h2>{esc(text['ui']['languages'])}</h2><ul>{''.join(f'<li>{esc(value)}</li>' for value in text['languages'])}</ul></section>
    <section id="contact"><h2>{esc(text['ui']['contact'])}</h2><ul class="contact-list">
{contact_list}
          <li>{esc(text['location'])}</li>
    </ul></section>
  </main>
  <footer><p>© {date.today().year} {esc(shared['name'])}</p><a class="back-to-top" href="#top">{esc(text['ui']['backToTop'])}</a></footer>
</body>
</html>
''', favicon


def not_found(en, fi):
  return f'''<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>{esc(en['ui']['notFoundTitle'])} / {esc(fi['ui']['notFoundTitle'])}</title><link rel="stylesheet" href="style.css"></head>
<body id="top"><a class="skip-link" href="#main">{esc(en['ui']['skip'])} / {esc(fi['ui']['skip'])}</a><header><h1>{esc(en['ui']['notFoundTitle'])} / {esc(fi['ui']['notFoundTitle'])}</h1></header><main id="main" class="not-found"><p lang="en">{esc(en['ui']['notFoundText'])}</p><p lang="fi">{esc(fi['ui']['notFoundText'])}</p><p><a href="index.html">EN</a> · <a href="fi/">FI</a></p></main></body></html>
'''


def main():
  parser = argparse.ArgumentParser(description="Generate and validate the bilingual CV website.")
  parser.add_argument("--check", action="store_true", help="validate content without writing generated files")
  args = parser.parse_args()
  errors = []
  shared = load_json("shared.json", errors)
  en = load_json("en.json", errors)
  fi = load_json("fi.json", errors)
  validate(shared, en, fi, errors)
  if errors:
    for error in errors:
      print(f"ERROR: {error}", file=sys.stderr)
    return 1
  warnings({"shared.json": shared, "en.json": en, "fi.json": fi})
  if args.check:
    print("Content validation passed; no files written.")
    return 0
  for directory in (SITE, SITE / "fi"):
    directory.mkdir(parents=True, exist_ok=True)
  en_html, favicon = page("en", shared, en)
  fi_html, _ = page("fi", shared, fi)
  files = {
    SITE / "index.html": en_html,
    SITE / "fi" / "index.html": fi_html,
    SITE / "404.html": not_found(en, fi),
    SITE / "favicon.svg": favicon,
    SITE / "sitemap.xml": f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>{esc(shared["domain"].rstrip("/") + "/")}</loc></url><url><loc>{esc(shared["domain"].rstrip("/") + "/fi/")}</loc></url></urlset>\n',
    SITE / "robots.txt": f'User-agent: *\nAllow: /\nSitemap: {shared["domain"].rstrip("/")}/sitemap.xml\n',
  }
  for path, content in files.items():
    path.write_text(content, encoding="utf-8", newline="\n")
  print("Generated: site/index.html, site/fi/index.html, site/404.html, site/favicon.svg, site/sitemap.xml, site/robots.txt")
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
