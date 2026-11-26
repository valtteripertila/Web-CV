# Pertila-CV

A bilingual static CV site generated from structured English and Finnish content.

[Live site](https://pertila-cv.pages.dev/) · [![CI](https://github.com/valtteripertila/Web-CV/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/valtteripertila/Web-CV/actions/workflows/ci.yml)

## Features

- English and Finnish pages with page-by-page language switching.
- Dark default theme with a light-theme toggle.
- Static HTML generated with Python's standard library.
- Local checks for content, links, HTML, language parity, privacy patterns, theme contrast and build freshness.
- Generated pages use same-origin CSS, JavaScript and images; the local check confirms no external resource loads in HTML or CSS.
- Optional changelog, current-focus page, project write-ups and social preview image.

## How it works

```mermaid
flowchart LR
  A[content JSON] --> B[build.py]
  B --> C[site/ static files]
  C --> D[GitHub main]
  D --> E[Cloudflare Pages]
```

The JSON files are the editable source. Run the generator and commit both the content and generated `site/` files; Cloudflare serves the static output from the repository.

## Project structure

```text
content/                  CV and optional page content
  en.json, fi.json        Translated CV fields and interface text
  shared.json             Name, contact details, site URL and optional repo URL
  experience.json         Bilingual work-history entries
  projects.json           Bilingual project entries
  site_info.json          Site overview and optional AI note
  changelog.json          Bilingual project history
  now.json                Optional current-focus entries
  quality.json            Optional recorded Lighthouse results
build.py                  Content validation and static-site entry point
add.py                    Interactive content-entry helper
tools/check.py            Offline check registry and runner
tools/quality.py          Shared contrast measurement
tools/sitebuilder.py      Page renderers used by build.py
tools/make_og.py           Optional browser-based social image tool
tests/                    Standard-library unit tests
.github/workflows/ci.yml  CI and Lighthouse jobs
site/                     Generated pages and static assets
```

## Quick start

From the repository root:

```sh
python3 build.py
python3 tools/check.py
python3 -m http.server 8000 --directory site
```

On Windows, use `py -3 build.py`, `py -3 tools/check.py`, and `py -3 -m http.server 8000 --directory site`. Open `http://localhost:8000/` to preview the generated site. `python3 build.py --preview-sample` creates isolated, ignored sample pages in `preview/`.

## Editing content

| File | Edit |
| --- | --- |
| `content/shared.json` | Name, initials, email, profile URLs, site domain and optional repository URL |
| `content/en.json`, `content/fi.json` | Translated CV fields, interface text and page slugs |
| `content/experience.json` | Roles and bilingual achievement lists |
| `content/projects.json` | Hackathon and personal-project details; optional bilingual write-ups |
| `content/site_info.json` | Site overview and optional AI note |
| `content/changelog.json` | Dated bilingual history entries, newest first |
| `content/now.json` | Current focus; the page is absent while the item list is empty |
| `content/quality.json` | Optional manually measured Lighthouse result |

Use `py -3 add.py role` or `python3 add.py role` to insert a role at the top. Use `add.py project`, `add.py now`, or `add.py changelog` for those entry types. Blank write-up answers skip those optional fields. The Now page is generated only after you enter at least one bilingual item.

The following JSON snippets are README-only illustrations with invented example values. Replace every example value with verified information before adding an entry to the real content files.

**Role example**

```json
{
  "employer": "Example employer (README example only)",
  "start": "Example date (replace before use)",
  "end": "",
  "role": {"en": "Example role (replace before use)", "fi": "Esimerkkitehtävä (vaihda ennen käyttöä)"},
  "points": {
    "en": ["Example responsibility (replace before use)"],
    "fi": ["Esimerkkivastuu (vaihda ennen käyttöä)"]
  }
}
```

**Hackathon project example**

```json
{
  "type": "hackathon",
  "featured": false,
  "title": "Example hackathon title (README example only)",
  "event": "Example event (replace before use)",
  "role": {"en": "Example role", "fi": "Esimerkkitehtävä"},
  "description": {
    "en": "Example description (replace before use)",
    "fi": "Esimerkkikuvaus (vaihda ennen käyttöä)"
  },
  "links": {"demo": "", "code": "", "writeup": ""}
}
```

## Checks and CI

Run `python3 tools/check.py` locally. It runs content validation, unit tests, local link and fragment resolution, language parity, HTML checks, external-resource and contrast checks, privacy-pattern checks and a temporary-build freshness comparison. The GitHub Actions workflow runs the checks and a Lighthouse audit for both home pages. Actions are not run locally.

The Lighthouse report is an audit result, not a score claim for this site. To record a measurement, run the `lighthouse` job in GitHub Actions and use its uploaded report artifact. In `content/quality.json`, add a `lighthouse` object with the report's `performance`, `accessibility`, `best_practices` and `seo` scores from 0 to 100, the actual `measured_on` date and a short `source` note naming the workflow run. The footer displays these values only when every field is valid; do not enter estimates or reuse the configured minimum thresholds as results.

## Deploying

Cloudflare Pages settings:

- Production branch: `main`
- Framework preset: `None`
- Build command: leave empty
- Build output directory: `site`

For each update, edit the content or code, run `py -3 build.py`, run `py -3 tools/check.py`, review the generated diff, then commit and push to `main`.

## Design decisions

- Static output keeps the deployed site simple to host.
- The build and checks use the Python standard library.
- One small theme script handles the dark/light toggle.
- The CSP restricts resource sources to the same origin.
- Content stays separate from page rendering code.
- English and Finnish entries are stored together where they describe the same item.
