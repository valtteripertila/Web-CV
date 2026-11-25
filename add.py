#!/usr/bin/env python3
"""Add a bilingual role or project without replacing existing entries."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CONTENT = ROOT / "content"


def ask(prompt):
  return input(prompt + ": ").strip()


def bullets(prompt):
  print(prompt + " (one per line; blank line to finish)")
  result = []
  while True:
    value = input("- ").strip()
    if not value:
      return result
    result.append(value)


def add_entry(filename, entry):
  path = CONTENT / filename
  if path.exists():
    entries = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(entries, list):
      raise ValueError(filename + " must contain a JSON array")
  else:
    entries = []
  entries.insert(0, entry)
  temp = path.with_suffix(path.suffix + ".tmp")
  temp.write_text(json.dumps(entries, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
  temp.replace(path)


def add_role():
  entry = {
    "employer": ask("Employer"),
    "start": ask("Start (MM/YYYY)"),
    "end": ask("End (MM/YYYY or blank for present)"),
    "role": {"en": ask("Role EN"), "fi": ask("Role FI")},
    "points": {"en": bullets("Bullet points EN"), "fi": bullets("Bullet points FI")},
  }
  add_entry("experience.json", entry)


def add_project():
  kind = ask("Type (hackathon or personal)").lower()
  if kind not in ("hackathon", "personal"):
    raise ValueError("Type must be hackathon or personal")
  featured = ask("Featured? (y/N)").lower() in ("y", "yes")
  entry = {
    "type": kind, "featured": featured, "title": ask("Title"), "date": ask("Date (YYYY or MM/YYYY)"),
    "event": ask("Event (hackathons only; blank otherwise)"),
    "result": {"en": ask("Result EN (blank if none)"), "fi": ask("Result FI (blank if none)")},
    "role": {"en": ask("Role EN (blank if none)"), "fi": ask("Role FI (blank if none)")},
    "description": {"en": ask("Description EN"), "fi": ask("Description FI")},
    "tags": [tag.strip() for tag in ask("Tags (comma-separated)").split(",") if tag.strip()],
    "links": {"demo": ask("Demo URL (blank if none)"), "code": ask("Code URL (blank if none)"), "writeup": ask("Write-up URL (blank if none)")},
  }
  add_entry("projects.json", entry)


def add_project():
  kind=ask("Type (hackathon or personal)").lower()
  if kind not in ("hackathon","personal"): raise ValueError("Type must be hackathon or personal")
  entry={"type":kind,"featured":ask("Featured? (y/N)").lower() in ("y","yes"),"title":ask("Title"),"date":ask("Date (YYYY or MM/YYYY)"),"event":ask("Event (blank for none)"),"result":{"en":ask("Result EN (blank for none)"),"fi":ask("Result FI (blank for none)")},"role":{"en":ask("Role EN (blank for none)"),"fi":ask("Role FI (blank for none)")},"description":{"en":ask("Description EN"),"fi":ask("Description FI")},"tags":[v.strip() for v in ask("Tags (comma-separated)").split(",") if v.strip()],"links":{"demo":ask("Demo URL (blank for none)"),"code":ask("Code URL (blank for none)"),"writeup":ask("Write-up URL (blank for none)")}}
  add_entry("projects.json",entry)


if __name__ == "__main__":
  if len(sys.argv) != 2 or sys.argv[1] not in ("role", "project"):
    raise SystemExit("Usage: python3 add.py role|project")
  (add_role if sys.argv[1] == "role" else add_project)()
