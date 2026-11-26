#!/usr/bin/env python3
"""Build and validate the static bilingual CV site using only Python's standard library."""
import argparse
import html
import json
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CONTENT = ROOT / "content"
SITE = ROOT / "site"
UI_KEYS = ["skip", "about", "experience", "projects", "hackathons", "personalProjects", "education", "certifications", "skills", "languages", "contact", "present", "demo", "code", "writeup", "backToTop", "themeToLight", "themeToDark", "meta_title", "meta_description", "notFoundTitle", "notFoundText", "navNow", "navHome", "navHow", "navChangelog", "languageNav", "mainNav", "navMenu", "menuAbout", "menuMore", "overview", "architecture", "contentModel", "automatedChecks", "constraints", "source", "aiAssisted", "pageIntro", "contentDescriptions", "contentFile", "contentHolds", "cspLabel", "buildFacts", "externalRequests", "siteBytes", "contrastPass", "contrastFail", "writeupTeam", "writeupPart", "writeupLearned", "writeupSummary", "changelogIntro", "nowIntro", "updated", "buildChecked", "contrastLabel", "lighthouseLabel", "lighthouseFooter", "project", "home", "writeupMismatch", "sectionLabels"]


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
                writeup = item.get("writeup", {})
                if writeup and isinstance(writeup, dict):
                        for field, translations in writeup.items():
                                if not isinstance(translations, dict):
                                        errors.append(f"projects.json entry {number}: writeup.{field} must be an object")
                                        continue
                                en_value, fi_value = translations.get("en", ""), translations.get("fi", "")
                                if bool(en_value) != bool(fi_value):
                                        print(f"WARNING: projects.json entry {number}: write-up {field} is present in only one language")


def validate(shared, en, fi, experience, projects, errors):
        require(shared, ["name", "initials", "email", "linkedin", "github", "domain", "repo"], "shared.json", errors)
        for lang, data in (("en", en), ("fi", fi)):
                require(data, ["lang", "locale", "slugs", "headline", "summary", "location", "education", "certifications", "skills", "languages", "ui"], f"{lang}.json", errors)
                require(data.get("slugs", {}), ["how", "changelog", "now"], f"{lang}.json", errors, "slugs.")
                require(data.get("ui", {}), UI_KEYS, f"{lang}.json", errors, "ui.")
                for section in ("education", "skills"):
                        items = data.get(section, [])
                        if isinstance(items, list):
                                for index, item in enumerate(items, 1):
                                        if not isinstance(item, dict):
                                                errors.append(f"{lang}.json: {section} entry {index} must be an object")
        validate_experience(experience, errors)
        validate_projects(projects, errors)


def validate_extra(site_info, quality, changelog, now, errors):
        if not isinstance(site_info, dict):
                errors.append("site_info.json: root must be a JSON object")
        else:
                intro = site_info.get("intro", {})
                note = site_info.get("ai_note", {})
                for field, value in (("intro", intro), ("ai_note", note)):
                        if not isinstance(value, dict) or any(not isinstance(value.get(lang), str) for lang in ("en", "fi")):
                                errors.append(f"site_info.json: {field} must contain en and fi strings")
        if not isinstance(quality, dict):
                errors.append("quality.json: root must be a JSON object")
        if not isinstance(changelog, list):
                errors.append("changelog.json: root must be a JSON array")
        else:
                previous = None
                for index, item in enumerate(changelog, 1):
                        if not isinstance(item, dict):
                                errors.append(f"changelog.json entry {index}: must be an object")
                                continue
                        for key in ("date", "en", "fi"):
                                if key not in item:
                                        errors.append(f"changelog.json entry {index}: missing {key}")
                        try:
                                if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", item["date"]):
                                        raise ValueError("invalid date format")
                                entry_date = date.fromisoformat(item["date"])
                                if previous and entry_date > previous:
                                        errors.append("changelog.json: entries must be newest first")
                                previous = entry_date
                        except (KeyError, ValueError, TypeError):
                                errors.append(f"changelog.json entry {index}: date must be YYYY-MM-DD")
        if not isinstance(now, dict) or not isinstance(now.get("items"), list):
                errors.append("now.json: expected an object with an items array")
        elif now["items"]:
                try:
                        updated_text = now.get("updated", "")
                        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", updated_text):
                                raise ValueError("invalid date format")
                        updated = date.fromisoformat(updated_text)
                        if (date.today() - updated).days > 90:
                                print("WARNING: now.json updated date is more than 90 days old")
                except (ValueError, TypeError):
                        errors.append("now.json: updated must be a valid YYYY-MM-DD date when items exist")
                for index, item in enumerate(now["items"], 1):
                        if not isinstance(item, dict) or not all(isinstance(item.get(lang), str) and item[lang].strip() for lang in ("en", "fi")):
                                errors.append(f"now.json item {index}: en and fi text are required")


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


def main():
        parser = argparse.ArgumentParser(description="Generate and validate the bilingual CV website.")
        parser.add_argument("--check", action="store_true", help="validate content without writing generated files")
        parser.add_argument("--preview-sample", action="store_true", help="write sample-only layout pages to preview/")
        parser.add_argument("--output-dir", help=argparse.SUPPRESS)
        args = parser.parse_args()
        errors = []
        shared = load_object("shared.json", errors)
        en = load_object("en.json", errors)
        fi = load_object("fi.json", errors)
        experience = load_list("experience.json", errors)
        projects = load_list("projects.json", errors)
        site_info = load_object("site_info.json", errors)
        quality = load_object("quality.json", errors)
        changelog = load_list("changelog.json", errors)
        now = load_object("now.json", errors)
        validate(shared, en, fi, experience, projects, errors)
        validate_extra(site_info, quality, changelog, now, errors)
        if errors:
                for error in errors:
                        print("ERROR: " + error, file=sys.stderr)
                return 1
        warn_placeholders({"shared.json": shared, "en.json": en, "fi.json": fi,
                           "experience.json": experience, "projects.json": projects,
                           "site_info.json": site_info, "quality.json": quality,
                           "changelog.json": changelog, "now.json": now})
        if args.check:
                print("Content validation passed; no files written.")
                return 0
        from tools.sitebuilder import generate
        output = ROOT / "preview" if args.preview_sample else args.output_dir
        generate(ROOT, shared, en, fi, experience, projects, site_info, quality, changelog,
                 now, output_dir=output, sample=args.preview_sample)
        return 0

if __name__=="__main__":
        raise SystemExit(main())
