#!/usr/bin/env python3
"""Build and validate the static bilingual CV site using only Python's standard library."""
import argparse
import html
import json
import re
import sys
from datetime import date
from pathlib import Path, PurePosixPath, PureWindowsPath
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent
CONTENT = ROOT / "content"
SITE = ROOT / "site"
UI_KEYS = [
        "skip", "contact", "present", "demo", "repo", "myCommits", "writeup", "github", "linkedin", "backToTop",
        "themeToLight", "themeToDark", "themeLabelLight", "themeLabelDark", "meta_title", "meta_description", "notFoundTitle", "notFoundText",
        "navNow", "navHome", "navHow", "navChangelog", "languageNav", "mainNav", "navMenu", "menuAbout",
        "menuMore", "overview", "architecture", "contentModel", "automatedChecks", "constraints", "source",
        "aiAssisted", "pageIntro", "contentDescriptions", "contentFile", "contentHolds", "cspLabel", "buildFacts",
        "externalRequests", "siteBytes", "contrastPass", "contrastFail", "changelogIntro", "nowIntro", "updated",
        "buildChecked", "contrastLabel", "lighthouseLabel", "lighthouseFooter", "timeline", "profile", "whatBuilt",
        "learned", "filterLegend", "filterAll", "filterHackathons", "filterProjects", "filterRoles", "hackathon",
        "project", "role", "teamSize", "proofSkill"
]


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


def value_present(value):
        return isinstance(value, str) and bool(value.strip())


def validate_localized_text(value, filename, number, field, errors, required=False):
        if isinstance(value, str):
                if required and not value_present(value):
                        errors.append(f"{filename} entry {number} field {field}: required")
                return
        if isinstance(value, dict):
                validate_bilingual(value, filename, number, field, errors)
                if required and any(not value_present(value.get(lang)) for lang in ("en", "fi")):
                        errors.append(f"{filename} entry {number} field {field}: English and Finnish text are required")
                return
        errors.append(f"{filename} entry {number} field {field}: must be a string or an object with en and fi")


def validate_tags(value, number, field, errors):
        if not isinstance(value, list):
                errors.append(f"timeline.json entry {number} field {field}: must be a list")
                return
        for index, tag in enumerate(value):
                if isinstance(tag, dict):
                        validate_bilingual(tag, "timeline.json", number, f"{field}[{index}]", errors)
                elif not isinstance(tag, str):
                        errors.append(f"timeline.json entry {number} field {field}[{index}]: must be a string or bilingual object")


def parse_date_key(value):
        if not isinstance(value, str):
                return None
        if re.fullmatch(r"\d{4}-\d{2}", value):
                year, month = (int(part) for part in value.split("-"))
                if 1 <= month <= 12:
                        return date(year, month, 1)
        elif re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
                try:
                        parsed = date.fromisoformat(value)
                        if parsed.isoformat() == value:
                                return parsed
                except ValueError:
                        return None
        return None


def validate_bilingual(value, filename, number, field, errors, expected="string"):
        if not isinstance(value, dict):
                errors.append(f"{filename} entry {number} field {field}: must be an object with en and fi")
                return
        values = []
        for lang in ("en", "fi"):
                if lang not in value:
                        errors.append(f"{filename} entry {number} field {field}.{lang}: missing")
                        continue
                child = value[lang]
                correct = isinstance(child, list) if expected == "list" else isinstance(child, str)
                if not correct:
                        errors.append(f"{filename} entry {number} field {field}.{lang}: must be a {expected}")
                elif expected == "list" and any(not isinstance(entry, str) for entry in child):
                        errors.append(f"{filename} entry {number} field {field}.{lang}: list values must be strings")
                values.append(bool(child) if correct else False)
        if len(values) == 2 and values[0] != values[1]:
                print(f"WARNING: {filename} entry {number} field {field}: content is present in only one language")


def validate_iso_field(item, number, field, required, errors, filename="timeline.json"):
        value = item.get(field, "")
        if not value_present(value):
                if required:
                        errors.append(f"{filename} entry {number} field {field}: required")
                return None
        parsed = parse_date_key(value)
        if parsed is None and "[" not in value:
                errors.append(f"{filename} entry {number} field {field}: expected YYYY-MM or YYYY-MM-DD")
        return parsed


def validate_urls(links, number, errors):
        if not isinstance(links, dict):
                errors.append(f"timeline.json entry {number} field links: must be an object")
                return
        for key in ("demo", "code", "commits", "writeup"):
                if key not in links:
                        if key == "commits":
                                continue
                        errors.append(f"timeline.json entry {number} field links.{key}: missing")
                        continue
                value = links[key]
                if not isinstance(value, str):
                        errors.append(f"timeline.json entry {number} field links.{key}: must be a string")
                        continue
                if value and (urlsplit(value).scheme not in ("http", "https") or not urlsplit(value).netloc):
                        errors.append(f"timeline.json entry {number} field links.{key}: must start with http:// or https:// and include a host")


def validate_media(media, number, field, site_root, errors):
        if not isinstance(media, list):
                errors.append(f"timeline.json entry {number} field {field}: must be a list")
                return
        root = Path(site_root) / "img"
        seen = set()
        for media_number, item in enumerate(media, 1):
                prefix = f"timeline.json entry {number} field {field}[{media_number - 1}]"
                if not isinstance(item, dict):
                        errors.append(f"{prefix}: must be an object")
                        continue
                filename = item.get("file", "")
                if not isinstance(filename, str) or not filename:
                        errors.append(f"{prefix}.file: required")
                        continue
                posix_path, windows_path = PurePosixPath(filename), PureWindowsPath(filename)
                if posix_path.is_absolute() or windows_path.is_absolute() or windows_path.drive or ".." in posix_path.parts or ".." in windows_path.parts:
                        errors.append(f"{prefix}.file: path must stay relative to site/img without '..'")
                        continue
                if filename in seen:
                        errors.append(f"{prefix}.file: duplicate file within this entry")
                seen.add(filename)
                target = root / Path(*posix_path.parts)
                allowed = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg", ".avif"}
                if target.suffix.lower() not in allowed:
                        errors.append(f"{prefix}.file: unsupported extension {target.suffix or '(none)'}")
                        continue
                try:
                        resolved_root = root.resolve()
                        resolved_target = target.resolve(strict=True)
                        resolved_target.relative_to(resolved_root)
                except (OSError, ValueError):
                        errors.append(f"{prefix}.file: file must exist under site/img")
                        continue
                if not resolved_target.is_file():
                        errors.append(f"{prefix}.file: must be a file")
                        continue
                size = resolved_target.stat().st_size
                if size > 5 * 1024 * 1024:
                        errors.append(f"{prefix}.file: exceeds 5 MB")
                elif size > 400 * 1024:
                        print(f"WARNING: {prefix}.file: larger than 400 KB ({size} bytes)")
                alt = item.get("alt")
                validate_bilingual(alt, "timeline.json", number, f"{field}[{media_number - 1}].alt", errors)
                if isinstance(alt, dict) and any(not value_present(alt.get(lang)) for lang in ("en", "fi")):
                        errors.append(f"{prefix}.alt: alt text is required in both languages")
                caption = item.get("caption", {"en": "", "fi": ""})
                validate_bilingual(caption, "timeline.json", number, f"{field}[{media_number - 1}].caption", errors)
                try:
                        from tools.media import image_dimensions
                        dimensions = image_dimensions(resolved_target)
                        if dimensions is None:
                                print(f"WARNING: {prefix}.file: image dimensions could not be read")
                        elif max(dimensions) > 1600:
                                print(f"WARNING: {prefix}.file: longest dimension is over 1600 px ({dimensions[0]}×{dimensions[1]})")
                        if target.suffix.lower() == ".svg":
                                svg = resolved_target.read_text(encoding="utf-8", errors="replace")
                                if re.search(r"(?:href|src)\s*=\s*['\"]https?://", svg, re.I):
                                        errors.append(f"{prefix}.file: SVG must not reference external resources")
                except (OSError, ValueError):
                        print(f"WARNING: {prefix}.file: image dimensions could not be read")


def validate_timeline(entries, errors, site_root=SITE):
        if not isinstance(entries, list):
                errors.append("timeline.json: root must be an array")
                return
        bilingual_fields = {
                "hackathon": ("what", "where", "theme", "role", "result", "learned"),
                "project": ("role", "description", "learned"),
                "role": ("role", "points"),
        }
        seen_ids = set()
        for number, item in enumerate(entries, 1):
                if not isinstance(item, dict):
                        errors.append(f"timeline.json entry {number}: must be an object")
                        continue
                entry_id = item.get("id", "")
                if entry_id:
                        if not isinstance(entry_id, str) or not re.fullmatch(r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*", entry_id):
                                errors.append(f"timeline.json entry {number} field id: must be a lowercase HTML id")
                        elif entry_id in seen_ids:
                                errors.append(f"timeline.json entry {number} field id: duplicate {entry_id}")
                        else:
                                seen_ids.add(entry_id)
                kind = item.get("type")
                if kind not in ("hackathon", "project", "role"):
                        errors.append(f"timeline.json entry {number} field type: must be hackathon, project or role")
                        continue
                required_by_kind = {
                        "hackathon": ("date_start", "date_end", "event", "what", "where", "theme", "team", "role", "result", "project", "learned"),
                        "project": ("date", "title", "role", "description", "tags", "links", "media", "learned"),
                        "role": ("start", "end", "employer", "role", "points"),
                }
                for required_field in required_by_kind[kind]:
                        if required_field not in item:
                                errors.append(f"timeline.json entry {number} field {required_field}: missing")
                if kind == "hackathon":
                        start = validate_iso_field(item, number, "date_start", True, errors)
                        end = validate_iso_field(item, number, "date_end", False, errors)
                        if start is None and "[" in str(item.get("date_start", "")):
                                print(f"WARNING: timeline.json entry {number} field date_start: unparseable placeholder sorts last")
                        if end and start and end < start:
                                errors.append(f"timeline.json entry {number} field date_end: cannot precede date_start")
                        if not value_present(item.get("event")):
                                errors.append(f"timeline.json entry {number} field event: required")
                        project = item.get("project")
                        if not isinstance(project, dict):
                                errors.append(f"timeline.json entry {number} field project: must be an object")
                                project = {}
                        validate_localized_text(project.get("title"), "timeline.json", number, "project.title", errors, required=True)
                        challenges = item.get("challenges", [])
                        if not isinstance(challenges, list):
                                errors.append(f"timeline.json entry {number} field challenges: must be a list")
                        else:
                                for challenge_index, challenge in enumerate(challenges):
                                        prefix = f"challenges[{challenge_index}]"
                                        if not isinstance(challenge, dict):
                                                errors.append(f"timeline.json entry {number} field {prefix}: must be an object")
                                                continue
                                        validate_bilingual(challenge.get("track"), "timeline.json", number, f"{prefix}.track", errors)
                                        validate_bilingual(challenge.get("description"), "timeline.json", number, f"{prefix}.description", errors)
                        team = item.get("team", {})
                        if not isinstance(team, dict):
                                errors.append(f"timeline.json entry {number} field team: must be an object")
                        else:
                                if not isinstance(team.get("name", ""), str):
                                        errors.append(f"timeline.json entry {number} field team.name: must be a string")
                                if type(team.get("size")) is not int or team.get("size", -1) < 0:
                                        errors.append(f"timeline.json entry {number} field team.size: must be a non-negative integer")
                        if isinstance(project, dict):
                                for required_field in ("title", "description", "tags", "links", "media"):
                                        if required_field not in project:
                                                errors.append(f"timeline.json entry {number} field project.{required_field}: missing")
                                if "subtitle" in project:
                                        validate_bilingual(project["subtitle"], "timeline.json", number, "project.subtitle", errors)
                                for field in ("description",):
                                        validate_bilingual(project.get(field, {"en": "", "fi": ""}), "timeline.json", number, f"project.{field}", errors)
                                validate_urls(project.get("links"), number, errors)
                                validate_media(project.get("media"), number, "project.media", site_root, errors)
                                validate_tags(project.get("tags"), number, "project.tags", errors)
                elif kind == "project":
                        parsed = validate_iso_field(item, number, "date", True, errors)
                        if parsed is None and "[" in str(item.get("date", "")):
                                print(f"WARNING: timeline.json entry {number} field date: unparseable placeholder sorts last")
                        validate_localized_text(item.get("title"), "timeline.json", number, "title", errors, required=True)
                        validate_urls(item.get("links"), number, errors)
                        validate_media(item.get("media"), number, "media", site_root, errors)
                        validate_tags(item.get("tags"), number, "tags", errors)
                else:
                        parsed = validate_iso_field(item, number, "start", True, errors)
                        if parsed is None and "[" in str(item.get("start", "")):
                                print(f"WARNING: timeline.json entry {number} field start: unparseable placeholder sorts last")
                        validate_iso_field(item, number, "end", False, errors)
                        if not value_present(item.get("employer")):
                                errors.append(f"timeline.json entry {number} field employer: required")
                for field in bilingual_fields[kind]:
                        if field not in item:
                                errors.append(f"timeline.json entry {number} field {field}: missing")
                        value = item.get(field, {"en": "", "fi": ""})
                        expected = "list" if kind == "role" and field == "points" else "string"
                        validate_bilingual(value, "timeline.json", number, field, errors, expected)
                if kind == "role" and "media" in item:
                        errors.append(f"timeline.json entry {number} field media: role entries cannot contain media")


def validate(shared, en, fi, timeline, errors, site_root=SITE):
        require(shared, ["name", "initials", "email", "linkedin", "github", "domain", "repo", "heroStatusKeys"], "shared.json", errors)
        domain = shared.get("domain", "")
        parsed_domain = urlsplit(domain) if isinstance(domain, str) else None
        if (parsed_domain is None or parsed_domain.scheme != "https" or not parsed_domain.netloc
                or parsed_domain.path or parsed_domain.query or parsed_domain.fragment
                or parsed_domain.username or parsed_domain.password or re.search(r"\s", domain)
                or domain.endswith("/") or domain != domain.lower()):
                errors.append("shared.json field domain: must be a lowercase https:// origin with no path or trailing slash")
        status_keys = shared.get("heroStatusKeys", [])
        if not isinstance(status_keys, list) or any(not isinstance(key, str) or not re.fullmatch(r"[a-z_][a-z0-9_]*", key) for key in status_keys):
                errors.append("shared.json field heroStatusKeys: expected unique code-style keys")
                status_keys = []
        elif len(status_keys) != len(set(status_keys)):
                errors.append("shared.json field heroStatusKeys: keys must be unique")
        for lang, data in (("en", en), ("fi", fi)):
                require(data, ["lang", "locale", "slugs", "headline", "summary", "education", "certifications", "skills", "languages", "ui", "hero"], f"{lang}.json", errors)
                require(data.get("slugs", {}), ["how", "changelog", "now"], f"{lang}.json", errors, "slugs.")
                require(data.get("ui", {}), UI_KEYS, f"{lang}.json", errors, "ui.")
                hero = data.get("hero", {})
                statuses = hero.get("status", []) if isinstance(hero, dict) else []
                if not isinstance(statuses, list):
                        errors.append(f"{lang}.json field hero.status: must be a list")
                        statuses = []
                keys = []
                for index, entry in enumerate(statuses, 1):
                        if not isinstance(entry, dict):
                                errors.append(f"{lang}.json field hero.status[{index - 1}]: must be an object")
                                continue
                        key = entry.get("key", "")
                        if not isinstance(key, str) or not re.fullmatch(r"[a-z_][a-z0-9_]*", key):
                                errors.append(f"{lang}.json field hero.status[{index - 1}].key: invalid identifier")
                        else:
                                keys.append(key)
                        if not isinstance(entry.get("value"), str):
                                errors.append(f"{lang}.json field hero.status[{index - 1}].value: must be a string")
                if keys != status_keys:
                        errors.append(f"{lang}.json field hero.status: keys must match shared.heroStatusKeys in order")
                for field in ("education", "skills", "certifications", "languages"):
                        if not isinstance(data.get(field), list):
                                errors.append(f"{lang}.json field {field}: must be a list")
                for group_index, group in enumerate(data.get("skills", [])):
                        if not isinstance(group, dict) or not isinstance(group.get("group"), str) or not isinstance(group.get("items"), list):
                                errors.append(f"{lang}.json skills[{group_index}]: expected a group name and items list")
                                continue
                        for item_index, skill in enumerate(group["items"]):
                                if isinstance(skill, str):
                                        continue
                                if not isinstance(skill, dict) or not value_present(skill.get("label")) or not re.fullmatch(r"#[a-z0-9]+(?:-[a-z0-9]+)*", str(skill.get("proof", ""))):
                                        errors.append(f"{lang}.json skills[{group_index}].items[{item_index}]: expected text or a labeled proof link")
        ids = {item.get("id") for item in timeline if isinstance(item, dict) and isinstance(item.get("id"), str)}
        for lang, data in (("en", en), ("fi", fi)):
                for group in data.get("skills", []):
                        if isinstance(group, dict):
                                for skill in group.get("items", []):
                                        if isinstance(skill, dict) and isinstance(skill.get("proof"), str) and skill["proof"][1:] not in ids:
                                                errors.append(f"{lang}.json skill {skill.get('label', '')}: proof target is missing from timeline")
        validate_timeline(timeline, errors, site_root)


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
        def walk(filename, value, path, entry_number=None):
                if isinstance(value, dict):
                        for key, child in value.items():
                                walk(filename, child, f"{path}.{key}" if path else key, entry_number)
                elif isinstance(value, list):
                        for index, child in enumerate(value):
                                next_number = index + 1 if filename == "timeline.json" and not path else entry_number
                                child_path = f"{path}[{index}]" if path or filename != "timeline.json" else ""
                                walk(filename, child, child_path, next_number)
                elif isinstance(value, str) and "[" in value:
                        found.append((filename, entry_number, path, value))
        for filename, data in files.items():
                walk(filename, data, "")
        for filename, entry_number, path, value in found:
                if filename == "timeline.json":
                        print(f"WARNING: {filename} entry {entry_number} field {path}: placeholder remains: {value}")
                else:
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
        timeline = load_list("timeline.json", errors)
        site_info = load_object("site_info.json", errors)
        quality = load_object("quality.json", errors)
        changelog = load_list("changelog.json", errors)
        now = load_object("now.json", errors)
        validate(shared, en, fi, timeline, errors, SITE)
        validate_extra(site_info, quality, changelog, now, errors)
        warn_placeholders({"shared.json": shared, "en.json": en, "fi.json": fi,
                           "timeline.json": timeline,
                           "site_info.json": site_info, "quality.json": quality,
                           "changelog.json": changelog, "now.json": now})
        if errors:
                for error in errors:
                        print("ERROR: " + error, file=sys.stderr)
                return 1
        if args.check:
                print("Content validation passed; no files written.")
                return 0
        from tools.sitebuilder import generate
        output = ROOT / "preview" if args.preview_sample else args.output_dir
        generate(ROOT, shared, en, fi, timeline, site_info, quality, changelog,
                 now, output_dir=output, sample=args.preview_sample)
        return 0

if __name__=="__main__":
        raise SystemExit(main())
