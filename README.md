# Bilingual CV website

A static English and Finnish personal website generated with Python 3's standard library. The generated `site/` directory is deployed to Cloudflare Pages without a build command.

## Project structure

```text
content/shared.json       Name, initials, email, profile links and canonical domain
content/en.json           English hero, summary, skills, education and UI strings
content/fi.json           Finnish hero, summary, skills, education and UI strings
content/experience.json   Work history with both languages in each entry
content/projects.json     Hackathon and personal project entries
build.py                  Validator and static HTML generator
add.py                    Interactive role and project entry helper
site/                     Generated pages plus hand-written CSS and theme script
```

## Edit the content

- Put shared identity and contact details in `content/shared.json`.
- Put translated text, skills, education and interface labels in `content/en.json` and `content/fi.json`.
- Each entry in `content/experience.json` stores employer, dates, role translations and achievement lists together.
- Each entry in `content/projects.json` stores a hackathon or personal project and all translated fields together. List order controls display order; featured cards appear first within each subsection.
- Text in square brackets is a placeholder to replace. The build lists every remaining placeholder by file and field path.

### Add a role

You can add an entry by hand at the top of `content/experience.json`:

```json
{
  "employer": "[EMPLOYER]",
  "start": "[MM/YYYY]",
  "end": "",
  "role": { "en": "[ROLE EN]", "fi": "[ROLE FI]" },
  "points": { "en": ["[POINT EN]"], "fi": ["[POINT FI]"] }
}
```

Or run `python3 add.py role` (on Windows, `py -3 add.py role`). Answer the prompts; enter one achievement per line and finish each language with a blank line. The helper inserts the new entry at the top and preserves the existing entries.

### Add a project

Add an entry by hand at the top of `content/projects.json`:

```json
{
  "type": "hackathon",
  "featured": true,
  "title": "[TITLE]",
  "date": "[YYYY or MM/YYYY]",
  "event": "[EVENT]",
  "result": { "en": "[RESULT EN]", "fi": "[RESULT FI]" },
  "role": { "en": "[ROLE EN]", "fi": "[ROLE FI]" },
  "description": { "en": "[DESCRIPTION EN]", "fi": "[DESCRIPTION FI]" },
  "tags": ["[TAG]"],
  "links": { "demo": "", "code": "", "writeup": "" }
}
```

Or run `python3 add.py project` (on Windows, `py -3 add.py project`) and answer the prompts. It inserts the entry at the top without replacing prior projects.

## Theme

The site starts in dark mode. The header button switches to light mode and back, and saves the selected theme in browser storage. If JavaScript is unavailable, the page remains dark and the toggle stays hidden. Palette colors are custom properties near the top of `site/style.css`; edit the accent property for each theme to change its accent color.

## Build and commit

From the repository root, edit the content files, then run:

```sh
python3 build.py
python3 build.py --check
```

On Windows, use `py -3 build.py` and `py -3 build.py --check`. The check command validates without writing generated files. Review `git status`, then commit the updated content and generated site:

```sh
git add -A
git commit -m "Update CV"
```

## Cloudflare Pages

Deploy the `site/` directory. You can upload that folder directly, or connect the Git repository and set the build command to empty and the build output directory to `site`. The website is public after deployment, even if the repository is private. Set `domain` in `content/shared.json` to the final public URL and rebuild before deploying.
