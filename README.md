# Personal CV website

A static bilingual (English and Finnish) CV generated with Python's standard library and hosted on Cloudflare Pages. The deployed `site/` directory contains the generated HTML and hand-written assets; Cloudflare Pages needs no build command.

## Project structure

```text
content/       Editable shared data and English/Finnish text
build.py       Standard-library site generator and validator
site/          Generated pages and static deployment assets
```

## Edit content

- `content/shared.json`: name, initials, contacts, links, domain, dates, project tags and URLs.
- `content/en.json` and `content/fi.json`: all English and Finnish text.
- Add a job, education item or project by adding the same `id` in `shared.json` and both language files.

## Update workflow

1. Edit the content files.
2. Run `python3 build.py` from this directory (on Windows, `py -3 build.py` also works).
3. Check `git status`.
4. Run `git add -A` and `git commit -m "Update CV"`.

The build prints warnings for every remaining `[PLACEHOLDER]`. Use `python3 build.py --check` to validate without writing generated files.

Change the accent color by editing `--accent` near the top of `site/style.css`.

## Git and publishing

The repository root is `cv-project/`, the default branch is `main`, and no remote is set. To publish later, create an **empty** GitHub repository (private is fine; the deployed site is public), then run:

```sh
git remote add origin <URL>
git push -u origin main
```

On Cloudflare Pages, either upload the `site/` folder directly or connect the Git repository with no build command and `site` as the build output directory. Pushes to `main` then update the site.

Set `domain` in `content/shared.json` once the final URL is known, then rebuild.
