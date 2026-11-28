"""Page renderers used by the existing build.py entry point."""

import html
import json
import os
import posixpath
import re
import shutil
from datetime import date
from pathlib import Path
from urllib.parse import quote, urlparse

from tools.quality import contrast_report


def esc(value):
    return html.escape(str(value), quote=True)


def real(value):
    return isinstance(value, str) and bool(value.strip()) and not value.strip().startswith("[")


def filled(value):
    return isinstance(value, str) and bool(value.strip())


def localized_text(value, lang):
    if isinstance(value, dict):
        value = value.get(lang, "")
    return value if isinstance(value, str) else ""


def profile_key(value):
    transliteration = str.maketrans({"ä": "a", "ö": "o", "å": "a"})
    normalized = value.lower().translate(transliteration)
    return re.sub(r"[^a-z0-9]+", "_", normalized).strip("_") or "skills"


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
    attrs = ' rel="noopener noreferrer"' if external else ""
    return f'<a href="{esc(url)}"{attrs}>{esc(label)}</a>'


def heading(title, ignored=None):
    return f'<h2>{esc(title)}</h2>'


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
    current_mark = ' aria-current="true"'
    en_mark = current_mark if lang == "en" else ""
    fi_mark = current_mark if lang == "fi" else ""
    return (f'<nav class="language-switch" aria-label="{esc(ui["languageNav"])}">'
            f'<a href="{rel_dir(current, pages[page]["en"])}"{en_mark}>EN</a><span aria-hidden="true">|</span>'
            f'<a href="{rel_dir(current, pages[page]["fi"])}"{fi_mark}>FI</a></nav>')


def brand_link(name, href):
    parts = name.split(" ", 1)
    brand = f'<span class="first">{esc(parts[0])}</span>'
    if len(parts) == 2 and parts[1]:
        brand += f' <span class="last">{esc(parts[1])}</span>'
    return f'<a class="brand" href="{esc(href)}">{brand}</a>'


def site_menu(lang, page, pages, shared, text):
    ui = text["ui"]
    groups = []
    about = [(key, ui[label]) for key, label in (("how", "navHow"), ("changelog", "navChangelog")) if key in pages]
    more = [("now", ui["navNow"])] if "now" in pages else []
    more.extend((key, label) for key, label, url in (("github", "GitHub", shared.get("github")), ("linkedin", "LinkedIn", shared.get("linkedin"))) if real(url))
    for label, entries in ((ui["menuAbout"], about), (ui["menuMore"], more)):
        if not entries:
            continue
        links = []
        for key, title in entries:
            external = key in ("github", "linkedin")
            href = shared[key] if external else rel_dir(pages[page][lang], pages[key][lang])
            marker = "↗" if external else "→"
            attrs = ' rel="noopener noreferrer"' if external else ""
            links.append(f'<a href="{esc(href)}"{attrs}>{esc(title)}<span aria-hidden="true">{marker}</span></a>')
        groups.append(f'<div class="menu-group"><p class="menu-label">// {esc(label)}</p>{"".join(links)}</div>')
    if not groups:
        return ""
    return (f'<details class="menu-wrap"><summary aria-label="{esc(ui["navMenu"])}"><span class="menu-icon" aria-hidden="true"><i></i><i></i><i></i></span></summary>'
            f'<nav aria-label="{esc(ui["mainNav"])}">{"".join(groups)}</nav></details>')


def top_bar(lang, page, pages, shared, text, sample=False):
    ui = text["ui"]
    home_href = rel_dir(pages[page][lang], pages["home"][lang])
    brand = brand_link(shared.get("name", ""), home_href)
    menu = site_menu(lang, page, pages, shared, text)
    switch = language_switch(lang, page, pages, ui)
    if sample:
        switch = switch.replace(">EN<", ">SAMPLE EN<").replace(">FI<", ">SAMPLE FI<")
    toggle = (f'<button class="theme-toggle" type="button" aria-pressed="false" '
              f'data-light-label="{esc(ui["themeLabelLight"])}" data-dark-label="{esc(ui["themeLabelDark"])}" '
              f'data-light-aria="{esc(ui["themeToLight"])}" data-dark-aria="{esc(ui["themeToDark"])}" '
              f'aria-label="{esc(ui["themeToLight"])}">{esc(ui["themeLabelLight"])}</button>')
    return f'<header class="topbar">{brand}<div class="topbar-controls">{switch}{toggle}{menu}</div></header>'


def structured_data(page, lang, shared, text, domain, pages):
    person = {"@type": "Person"}
    for key, value in (("name", shared.get("name")), ("email", shared.get("email")), ("jobTitle", text.get("headline"))):
        if real(value):
            person[key] = value
    same_as = [value for value in (shared.get("linkedin"), shared.get("github"), shared.get("repo")) if real(value)]
    if same_as:
        person["sameAs"] = same_as
    skills = [entry.get("group", "") for entry in text.get("skills", []) if real(entry.get("group"))]
    skills.extend(item.get("label", "") if isinstance(item, dict) else item
                  for entry in text.get("skills", []) for item in entry.get("items", [])
                  if real(item.get("label", "") if isinstance(item, dict) else item))
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


def code_panel(lines, cls="", ui=None):
    if not lines: return ""
    rows = []
    for key, vals in lines:
        if isinstance(vals, list):
            items = []
            for value in vals:
                if isinstance(value, dict) and value.get("proof"):
                    label = value.get("label", "")
                    aria = (ui or {}).get("proofSkill", "See proof for {skill}").format(skill=label)
                    items.append(f'<li><a class="skill-proof" href="{esc(value["proof"])}" aria-label="{esc(aria)}">{esc(label)}</a></li>')
                else:
                    items.append(f"<li>{esc(value.get('label', '') if isinstance(value, dict) else value)}</li>")
            rows.append(f'<div class="code-line"><dt>{esc(key)}</dt><dd class="array"><ul>{"".join(items)}</ul></dd></div>')
        else:
            rows.append(f'<div class="code-line"><dt>{esc(key)}</dt><dd>{esc(vals)}</dd></div>')
    return f'<div class="code {cls}"><dl>{"".join(rows)}</dl></div>'


def display_date(item, lang):
    value = item.get("date_start") or item.get("start") or item.get("date", "")
    end = item.get("date_end", "")
    if not re.fullmatch(r"\d{4}-\d{2}(-\d{2})?", str(value)): return str(value)
    y, m = int(value[:4]), int(value[5:7])
    months = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
    months_fi = ("tammi", "helmi", "maalis", "huhti", "touko", "kesä", "heinä", "elo", "syys", "loka", "marras", "joulu")
    if len(value) == 7: return f"{m:02d}/{y}" if lang == "fi" else f"{months[m-1]} {y}"
    d = int(value[8:10])
    if lang == "fi": return f"{d}.–{int(end[8:10])}.{m}.{y}" if len(end) == 10 and end[:7] == value[:7] else f"{d}.{m}.{y}"
    return f"{d}–{int(end[8:10])} {months[m-1]} {y}" if len(end) == 10 and end[:7] == value[:7] else f"{d} {months[m-1]} {y}"


def timeline_sort_key(pair):
    index, item = pair
    value = item.get("date_start") or item.get("start") or item.get("date", "")
    if re.fullmatch(r"\d{4}-\d{2}", str(value)):
        value += "-01"
    try:
        return (1, date.fromisoformat(value).toordinal(), -index)
    except (TypeError, ValueError):
        return (0, 0, -index)


def home_sections(lang, shared, text, timeline, ui, sample=False, root=None):
    result = []
    hero = text.get("hero", {})
    status = [(row.get("key", ""), row.get("value", "")) for row in hero.get("status", []) if filled(row.get("value"))]
    email = shared.get("email", "")
    subject = quote(ui["emailSubject"], safe="") if email else ""
    email_cta = f'<a class="email-cta" href="{esc("mailto:" + email + "?subject=" + subject)}">{esc(ui["emailMe"])}</a>' if email else ""
    hero_links = " ".join(filter(None, (email_cta, link(shared.get("github"), ui["github"]), link(shared.get("linkedin"), ui["linkedin"]))))
    hero_links_html = f'<div class="contact-buttons hero-links">{hero_links}</div>' if hero_links else ""
    result.append(f'<section class="hero"><p class="shell-prompt">$ {esc(hero.get("prompt", "whoami"))}</p><h1>{esc(shared.get("name", ""))}</h1><p class="headline">{esc(text.get("headline", ""))}</p><p class="summary">{esc(text.get("summary", ""))}</p>{code_panel(status,"hero-code")}{hero_links_html}</section>')
    visible_items = [(index, item) for index, item in enumerate(timeline)
                     if item.get("type") != "role" or item.get("employer") == "Forward Forever"]
    items = sorted(visible_items, key=timeline_sort_key, reverse=True)
    entries = [item for _, item in items]
    kinds = [k for k in ("hackathon", "project", "role") if any(x.get("type")==k for x in entries)]
    filters = ""
    if len(kinds) > 1:
        choices = [("all", ui["filterAll"])] + [(k,ui["filterHackathons"] if k=="hackathon" else ui["filterProjects"] if k=="project" else ui["filterRoles"]) for k in kinds]
        filters = f'<fieldset class="filters"><legend>{esc(ui["filterLegend"])}</legend>' + "".join(f'<input type="radio" name="timeline-filter" id="f-{k}" {"checked" if k=="all" else ""}><label for="f-{k}">{esc(v)} ({sum(x.get("type")==k for x in entries) if k!="all" else len(entries)})</label>' for k,v in choices) + "</fieldset>"
    cards=[]
    for item in entries:
        kind=item.get("type"); date_text=display_date(item,lang); date_text=("SAMPLE " + date_text) if sample else date_text; links=item.get("links",{}); media=""
        if kind == "hackathon": links=item.get("project",{}).get("links",{})
        media_rows=item.get("project",{}).get("media",[]) if kind=="hackathon" else item.get("media",[])
        figures=[]
        for media_index, m in enumerate(media_rows, 1):
            src=("../" if lang=="fi" else "")+"img/"+m.get("file",""); alt=m.get("alt",{}).get(lang,"")
            if src!="img/" and alt:
                base=(root/"preview"/"img" if sample else root/"site"/"img") if root else Path()
                try:
                    from tools.media import image_dimensions
                    dims=image_dimensions(base/m.get("file",""))
                except (OSError,ValueError): dims=None
                dimensions=f' width="{dims[0]}" height="{dims[1]}"' if dims else ""
                caption=m.get("caption",{}).get(lang,"")
                caption_text=("SAMPLE " if sample else "")+f"fig.{media_index} — {caption}" if caption else ""
                figures.append(f'<figure><a href="{esc(src)}"><img src="{esc(src)}" alt="{esc(alt)}"{dimensions} loading="lazy" decoding="async"></a>{f"<figcaption>{esc(caption_text)}</figcaption>" if caption_text else ""}</figure>')
        if figures: media=f'<div class="media-gallery">{"".join(figures)}</div>'
        tagrows=item.get("project",{}).get("tags",[]) if kind=="hackathon" else item.get("tags",[])
        tag_values=[localized_text(tag,lang) for tag in tagrows]
        tags="".join(f'<span>{("SAMPLE #"+esc(t[7:] if t.startswith("SAMPLE ") else t)) if sample else "#"+esc(t)}</span>' for t in tag_values if filled(t))
        linkrows=" ".join(filter(None,(link(links.get("demo"),ui["demo"]),link(links.get("code"),ui["repo"]),link(links.get("commits"),ui["myCommits"]),link(links.get("writeup"),ui["writeup"]))))
        if kind=="role":
            points=item.get("points",{}).get(lang,[]); role=item.get("role",{}).get(lang,"")
            content=f'<span class="entry-kind">{esc(ui["role"])} · {esc(item.get("employer",""))}</span><h3>{esc(role)}</h3>{"<ul>"+"".join(f"<li>{esc(p)}</li>" for p in points)+"</ul>" if points else ""}'
            end_value=item.get("end","")
            if end_value:
                end=display_date({"date":end_value},lang)
                if end_value != item.get("start",""): date_text += f" – {end}"
            else:
                date_text += f" – {ui['present']}"
        elif kind=="hackathon":
            p=item.get("project",{}); info=[]
            for key in ("what","where","theme"):
                value=item.get(key,{}).get(lang,"")
                if value: info.append((key,value))
            size=item.get("team",{}).get("size")
            if size: info.append(("team",ui["teamSize"].format(count=size)))
            role=item.get("role",{}).get(lang,"")
            if role: info.append(("my_role",role))
            resultval=item.get("result",{}).get(lang,"")
            result_lines=[line.strip() for line in resultval.splitlines() if line.strip()] if isinstance(resultval,str) else []
            result_items="".join("<li class=\"result-panel\">"+esc(line)+"</li>" for line in result_lines)
            results_html=f'<ul class="result-panels">{result_items}</ul>' if result_lines else ""
            challenge_rows = [(localized_text(challenge.get("track", ""), lang), challenge.get("description", {}).get(lang, ""))
                              for challenge in item.get("challenges", []) if isinstance(challenge, dict)]
            challenges_html = code_panel(challenge_rows, "challenge-code")
            project_title=localized_text(p.get("title", ""),lang); project_description=p.get("description",{}).get(lang,"")
            project_subtitle=p.get("subtitle",{}).get(lang,"") if isinstance(p.get("subtitle"),dict) else ""
            title_html=f"<h4>{esc(project_title)}</h4>" if project_title else ""
            subtitle_html=f'<p class="project-subtitle">{esc(project_subtitle)}</p>' if project_subtitle else ""
            description_html=f"<p>{esc(project_description)}</p>" if project_description else ""
            event=esc(item.get("event", ""))
            learned_value=item.get("learned",{}).get(lang,"")
            learned_html=f'<details><summary>{esc(ui["learned"])}</summary><p>{esc(learned_value)}</p></details>' if learned_value else ""
            what_built=("SAMPLE // "+esc(ui["whatBuilt"][7:])) if sample and ui["whatBuilt"].startswith("SAMPLE ") else "// "+esc(ui["whatBuilt"])
            content=f'<span class="entry-kind">{ui["hackathon"]}</span><h3>{event}</h3>{results_html}{challenges_html}{code_panel(info,"hackathon-code")}<p class="what-built">{what_built}</p>{title_html}{subtitle_html}{description_html}{media}{learned_html}'
        else:
            title=localized_text(item.get("title", ""),lang); role=item.get("role",{}).get(lang,""); desc=item.get("description",{}).get(lang,"")
            learned_value=item.get("learned",{}).get(lang,"")
            learned_html=f'<details><summary>{esc(ui["learned"])}</summary><p>{esc(learned_value)}</p></details>' if learned_value else ""
            content=f'<span class="entry-kind">{ui["project"]}</span>{f"<h3>{esc(title)}</h3>" if title else ""}{f"<p class=project-role>{esc(role)}</p>" if role else ""}{f"<p>{esc(desc)}</p>" if desc else ""}{media}{learned_html}'
        content+=f'<p class="project-tags">{tags}</p>' if tags else ""
        content+=f'<p class="project-links">{linkrows}</p>' if linkrows else ""
        entry_id = f' id="{esc(item["id"])}"' if item.get("id") else ""
        cards.append(f'<article{entry_id} class="timeline-entry" data-kind="{kind}"><div class="entry-date">{esc(date_text)}</div><div class="entry-card">{content}</div></article>')
    if cards: result.append(f'<section id="timeline">{heading(ui["timeline"])}{filters}<div class="timeline">{"".join(cards)}</div></section>')
    profile=[]
    for group in text.get("skills",[]):
        key=profile_key(group.get("group", ""))
        vals=[v for v in group.get("items",[]) if filled(v.get("label", "") if isinstance(v, dict) else v)]
        if vals: profile.append((key,vals))
    education=[" · ".join(str(x.get(k,"")) for k in ("degree","school","years") if filled(x.get(k))) for x in text.get("education",[])]
    if any(education): profile.append(("education",[v for v in education if v]))
    certs=[v for v in text.get("certifications",[]) if filled(v)]
    if certs: profile.append(("certifications",certs))
    langs=[v for v in text.get("languages",[]) if filled(v)]
    if langs: profile.append(("spoken",langs))
    if profile: result.append(f'<section id="profile">{heading(ui["profile"])}{code_panel(profile,"profile-code",ui)}</section>')
    email=shared.get("email",""); contact=f'<p class="mail-line">$ mail {link("mailto:"+email,email)}</p>' if email else ""
    socials=" ".join(filter(None,(link(shared.get("github"),ui["github"]),link(shared.get("linkedin"),ui["linkedin"]))))
    if contact or socials: result.append(f'<section id="contact">{heading(ui["contact"])}{contact}{f"<div class=contact-buttons>{socials}</div>" if socials else ""}</section>')
    return "".join(result)


def how_body(lang, shared, text, site_info, quality, pages, sizes, contrast_pass, root, sample=False):
    ui = text["ui"]
    labels = ui
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
    return f'<section id="entries"><p>{esc(ui["changelogIntro"])}</p><ol class="changelog-list">{"".join(entries)}</ol></section>'


def now_body(lang, text, now):
    ui = text["ui"]
    entries = [item.get(lang, "") for item in now.get("items", []) if real(item.get(lang, ""))]
    return (f'<section id="now">{heading(ui["navNow"])}'
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
    size = f"{byte_count / 1000:.1f}"
    if lang == "fi":
        size = size.replace(".", ",")
    value = ui["buildChecked"].format(external=external, size=size, contrast=contrast)
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
    structured = structured_data(page, lang, shared, text, domain, pages)
    structured_tag = '<script type="application/ld+json">' + json_ld(structured) + "</script>"
    og_image = "og.png" if lang == "en" else "og-fi.png"
    og = ""
    if not sample and (root / "site" / og_image).exists():
        og = '<meta property="og:image" content="' + esc(clean_url(domain) + og_image) + '"><meta name="twitter:card" content="summary_large_image">'
    bar = top_bar(lang, page, pages, shared, text, sample)
    fact = size_line(lang, ui, sizes[lang], sizes["external"], contrast_pass, sizes.get("quality"))
    title = page_title if real(page_title) else ui["navHome"]
    if page == "home":
        prompt = ""
        header_h1 = ""
        page_intro = ""
        title_tag = text.get("ui", {}).get("meta_title", title)
    else:
        prompt = ("SAMPLE " if sample else "") + "cat " + page
        header_h1 = esc(title)
        page_intro = f'<p class="page-intro">{esc(ui["pageIntro"])}</p>'
        title_tag = title
    if sample:
        fact = "SAMPLE " + fact
    footer = (f'<footer><p>{"SAMPLE " if sample else ""}© {build_year()} {esc(shared["name"])}</p>'
              f'<span class="build-facts">{esc(fact)}</span>'
              f'<a class="back-to-top" href="#top">{esc(ui["backToTop"])}</a></footer>')
    prefix = "SAMPLE " if sample else ""
    return "\n".join([
        "<!doctype html>", f'<html lang="{esc(lang)}"><head>',
        '  <meta charset="utf-8">', '  <meta name="viewport" content="width=device-width, initial-scale=1">',
        f'  <title>{esc(title_tag)}</title>', f'  <meta name="description" content="{esc(description)}">',
        '  <meta name="color-scheme" content="dark light">', '  <meta name="theme-color" content="#101614">',
        f'  <link rel="canonical" href="{esc(canonical)}">', f'  {lang_alts}',
        f'  <meta property="og:title" content="{esc(title_tag)}">', f'  <meta property="og:locale" content="{esc(text.get("locale", "en_US" if lang == "en" else "fi_FI"))}">', f'  <meta property="og:description" content="{esc(description)}">',
        f'  <meta property="og:type" content="website"><meta property="og:url" content="{esc(canonical)}">{og}',
        f'  <link rel="icon" href="{depth_path}favicon.svg" type="image/svg+xml">',
        f'  <script src="{depth_path}theme.js"></script>', f'  <link rel="stylesheet" href="{depth_path}style.css">', f'  {structured_tag}',
        '</head><body id="top">', f'  <a class="skip-link" href="#main">{esc(ui["skip"])}</a>',
        f'  {bar}',
        f'  <main id="main">{("<section class=page-hero><p class=shell-prompt>$ cat "+esc(page)+"</p><h1>"+esc(title)+"</h1><p class=page-intro>"+esc(ui["pageIntro"])+"</p></section>" if page != "home" else "")}{body}</main>', f'  {footer}', '</body></html>', ""
    ])


def make_llms(shared, en, fi, timeline, pages, domain):
    lines = ["# " + shared["name"], ""]
    for lang, text in (("en", en), ("fi", fi)):
        if real(text.get("headline")):
            lines.append(text["headline"])
        if real(text.get("summary")):
            lines.append(text["summary"])
        availability = next((row.get("value", "") for row in text.get("hero", {}).get("status", []) if row.get("key") == "availability"), "")
        if real(availability):
            lines.append(("Availability: " if lang == "en" else "Saatavuus: ") + availability)
        lines.append(f"- [{lang.upper()} CV]({page_url(domain, pages['home'][lang])})")
        lines.append(f"- [{text['ui']['navHow']}]({page_url(domain, pages['how'][lang])})")
        lines.append(f"- [{text['ui']['navChangelog']}]({page_url(domain, pages['changelog'][lang])})")
        if "now" in pages:
            lines.append(f"- [{text['ui']['navNow']}]({page_url(domain, pages['now'][lang])})")
    for label, value in (("GitHub", shared.get("github")), ("LinkedIn", shared.get("linkedin"))):
        if real(value):
            lines.append(f"- {label}: {value}")
    named = [(item.get("event") if item.get("type")=="hackathon" else localized_text(item.get("title"),"en"), item) for item in timeline]
    named = [(name,item) for name,item in named if real(name)]
    if named:
        lines.extend(["", "## Projects"])
        for name, item in named:
            links = item.get("project",{}).get("links",{}) if item.get("type")=="hackathon" else item.get("links", {})
            destinations = [links[key] for key in ("demo", "code", "commits", "writeup") if real(links.get(key))]
            suffix = " — " + ", ".join(destinations) if destinations else ""
            lines.append(f"- {name}{suffix}")
    return "\n".join(lines) + "\n"


def generate(root, shared, en, fi, timeline, site_info, quality, changelog, now, output_dir=None, sample=False):
    root = Path(root)
    content_dir = root / "content"
    out = Path(output_dir) if output_dir else root / "site"
    out.mkdir(parents=True, exist_ok=True)
    if sample and out.resolve() != (root / "preview").resolve():
        raise ValueError("sample output is restricted to preview/")
    if sample:
        def label(value):
            if isinstance(value, dict): return {k: label(v) for k,v in value.items()}
            if isinstance(value, list): return [label(v) for v in value]
            if isinstance(value, str) and value and not value.startswith("SAMPLE "): return "SAMPLE " + value
            return value
        shared, en, fi = label(shared), label(en), label(fi)
        shared.update({"name":"SAMPLE Person","initials":"SAMPLE","email":"","github":"","linkedin":"","repo":""})
        en.update({"headline":"SAMPLE Computer science student","summary":"SAMPLE Building small software projects and learning through team work.","education":[{"degree":"SAMPLE First-year student","school":"SAMPLE Example University","years":"SAMPLE 2026–present"}],"certifications":["SAMPLE Certificate"],"skills":[{"group":"SAMPLE Tools","items":["SAMPLE Python","SAMPLE Git"]}],"languages":["SAMPLE Finnish","SAMPLE English"],"hero":{"prompt":"SAMPLE whoami","status":[{"key":"location","value":"SAMPLE Espoo"},{"key":"looking_for","value":"SAMPLE learning opportunities"},{"key":"availability","value":"SAMPLE available"}]}})
        fi.update({"headline":"SAMPLE Tietojenkäsittelytieteen opiskelija","summary":"SAMPLE Rakennan ohjelmistoprojekteja ja opin tiimityössä.","education":[{"degree":"SAMPLE Ensimmäisen vuoden opiskelija","school":"SAMPLE Esimerkkikorkeakoulu","years":"SAMPLE 2026–nykyhetki"}],"certifications":["SAMPLE Todistus"],"skills":[{"group":"SAMPLE Työkalut","items":["SAMPLE Python","SAMPLE Git"]}],"languages":["SAMPLE suomi","SAMPLE englanti"],"hero":{"prompt":"SAMPLE whoami","status":[{"key":"location","value":"SAMPLE Espoo"},{"key":"looking_for","value":"SAMPLE oppimismahdollisuudet"},{"key":"availability","value":"SAMPLE käytettävissä"}]}})
        changelog=[]
        site_info={"intro":{"en":"SAMPLE This page documents the example site.","fi":"SAMPLE Tämä sivu kuvaa esimerkkisivustoa."},"ai_note":{"en":"","fi":""}}
        site_info, quality, changelog = label(site_info), label(quality), label(changelog)
        shared["domain"] = ""
        preview_img=out / "img"; preview_img.mkdir(parents=True,exist_ok=True)
        def sample_media(count, prefix):
            rows=[]
            for n in range(1,count+1):
                name=f"{prefix}-{n}.svg"; target=preview_img/name
                target.write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 360"><rect width="640" height="360" fill="#1a2420"/><text x="320" y="190" text-anchor="middle" fill="#8bd6ae" font-family="monospace" font-size="42">SAMPLE</text></svg>\n',encoding="utf-8")
                rows.append({"file":name,"alt":{"en":"SAMPLE preview image","fi":"SAMPLE esimerkkikuva"},"caption":{"en":"SAMPLE preview","fi":"SAMPLE esikatselu"}})
            return rows
        blank_links={"demo":"","code":"","writeup":""}
        blank_bi={"en":"SAMPLE preview text","fi":"SAMPLE esimerkkiteksti"}
        preview_hack={"type":"hackathon","date_start":"2026-09-18","date_end":"2026-09-20","event":"SAMPLE Hackathon","what":blank_bi,"where":blank_bi,"theme":blank_bi,"team":{"name":"SAMPLE Team","size":5},"role":blank_bi,"result":blank_bi,"project":{"title":"SAMPLE Build","description":blank_bi,"tags":["SAMPLE Data"],"links":blank_links,"media":sample_media(4,"SAMPLE-hackathon")},"learned":blank_bi}
        timeline=[preview_hack,
          {"type":"project","date":"2026-08","title":"SAMPLE One image project","role":blank_bi,"description":blank_bi,"tags":["SAMPLE Build"],"links":blank_links,"media":sample_media(1,"SAMPLE-project-one"),"learned":blank_bi},
          {"type":"project","date":"2026-07","title":"SAMPLE Two image project","role":blank_bi,"description":blank_bi,"tags":[],"links":blank_links,"media":sample_media(2,"SAMPLE-project-two"),"learned":blank_bi},
          {"type":"project","date":"2026-06","title":"SAMPLE Text project","role":blank_bi,"description":blank_bi,"tags":[],"links":blank_links,"media":[],"learned":blank_bi},
          {"type":"hackathon","date_start":"2026-05-01","date_end":"","event":"SAMPLE Hackathon without images","what":blank_bi,"where":blank_bi,"theme":blank_bi,"team":{"name":"","size":0},"role":blank_bi,"result":{"en":"","fi":""},"project":{"title":"SAMPLE Entry","description":blank_bi,"tags":[],"links":blank_links,"media":[]},"learned":{"en":"","fi":""}},
          {"type":"role","start":"2026-04","end":"","employer":"SAMPLE Employer","role":blank_bi,"points":{"en":["SAMPLE Contribution"],"fi":["SAMPLE Työpanos"]}},
          {"type":"role","start":"2026-03","end":"2026-04","employer":"SAMPLE Employer","role":blank_bi,"points":{"en":[],"fi":[]}}]
        en["slugs"]={"how":"how-this-site-is-built","changelog":"changelog","now":"now"}
        fi["slugs"]={"how":"sivuston-rakenne","changelog":"muutosloki","now":"nyt"}
        now={"updated":"","items":[]}
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
        body = home_sections(lang, shared, text, timeline, text["ui"], sample=sample, root=root)
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
    llms = make_llms(shared, en, fi, timeline, pages, domain)
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
    (out / "404.html").write_text(not_found(shared, en, fi, pages, size, contrast_pass, domain, sample), encoding="utf-8", newline="\n")
    if sample:
        shutil.copy2(root / "site" / "style.css", out / "style.css")
        shutil.copy2(root / "site" / "theme.js", out / "theme.js")
        shutil.copy2(root / "site" / "_headers", out / "_headers")
    print("Generated: " + ", ".join(str(path.relative_to(out)).replace("\\", "/") for path in sorted(out_files)))
    return out_files


def not_found(shared, en, fi, pages, sizes, contrast_pass, domain, sample=False):
    en_ui, fi_ui = en["ui"], fi["ui"]
    sample_prefix = "SAMPLE " if sample else ""
    bar = top_bar("en", "home", pages, shared, en, sample)
    facts = []
    for lang, ui in (("en", en_ui), ("fi", fi_ui)):
        facts.append(f'<span class="build-facts">{esc(sample_prefix + size_line(lang, ui, sizes[lang], sizes["external"], contrast_pass, sizes.get("quality")))}</span>')
    not_found_title = f'{en["ui"]["notFoundTitle"]} / {fi["ui"]["notFoundTitle"]}'
    og_image = clean_url(domain) + "og.png"
    return "\n".join(["<!doctype html>", '<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta name="color-scheme" content="dark light"><meta name="theme-color" content="#101614">',
        f'<title>{esc(not_found_title)}</title>', f'<meta property="og:title" content="{esc(not_found_title)}"><meta property="og:locale" content="en_US"><meta property="og:image" content="{esc(og_image)}"><meta name="twitter:card" content="summary_large_image">',
        '<script src="theme.js"></script><link rel="stylesheet" href="style.css"></head><body id="top">',
        f'<a class="skip-link" href="#main">{esc(sample_prefix + en["ui"]["skip"])}</a>{bar}',
        f'<main id="main" class="not-found"><section class="hero"><h1>{esc(sample_prefix + en["ui"]["notFoundTitle"])} / {esc(sample_prefix + fi["ui"]["notFoundTitle"])}</h1></section><p lang="en">{esc(sample_prefix + en["ui"]["notFoundText"])}</p><p lang="fi">{esc(sample_prefix + fi["ui"]["notFoundText"])}</p></main>',
        f'<footer><p>{sample_prefix}© {build_year()} {esc(shared["name"])}</p>{"".join(facts)}<a class="back-to-top" href="#top">{esc(sample_prefix + en["ui"]["backToTop"])}</a></footer>', '</body></html>', ""])
