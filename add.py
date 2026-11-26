#!/usr/bin/env python3
"""Add a bilingual role or project without replacing existing entries."""
import json
import sys
from datetime import date
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
        kind=ask("Type (hackathon or personal)").lower()
        if kind not in ("hackathon","personal"): raise ValueError("Type must be hackathon or personal")
        entry={"type":kind,"featured":ask("Featured? (y/N)").lower() in ("y","yes"),"title":ask("Title"),"date":ask("Date (YYYY or MM/YYYY)"),"event":ask("Event (blank for none)"),"result":{"en":ask("Result EN (blank for none)"),"fi":ask("Result FI (blank for none)")},"role":{"en":ask("Role EN (blank for none)"),"fi":ask("Role FI (blank for none)")},"description":{"en":ask("Description EN"),"fi":ask("Description FI")},"tags":[v.strip() for v in ask("Tags (comma-separated)").split(",") if v.strip()],"links":{"demo":ask("Demo URL (blank for none)"),"code":ask("Code URL (blank for none)"),"writeup":ask("Write-up URL (blank for none)")}}
        if kind == "hackathon" and ask("Add a project write-up? (y/N)").lower() in ("y", "yes"):
                writeup = {}
                for field, label in (("team", "Team and setting"), ("part", "My part"), ("learned", "What I learned")):
                        writeup[field] = {"en": ask(label + " EN (blank to skip)"), "fi": ask(label + " FI (blank to skip)")}
                if any(value for pair in writeup.values() for value in pair.values()):
                        entry["writeup"] = writeup
        add_entry("projects.json",entry)


def add_now():
        entries = []
        while True:
                english = ask("Now item EN (blank to finish)")
                if not english:
                        break
                entries.append({"en": english, "fi": ask("Now item FI")})
        if not entries:
                print("No items entered; now.json was not changed.")
                return
        path = CONTENT / "now.json"
        data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"updated": "", "items": []}
        data["updated"] = date.today().isoformat()
        data.setdefault("items", [])
        data["items"] = entries + data["items"]
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def add_changelog():
        path = CONTENT / "changelog.json"
        entries = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
        entry_date = ask("Date (YYYY-MM-DD; blank for today)") or date.today().isoformat()
        if date.fromisoformat(entry_date).isoformat() != entry_date:
                raise ValueError("Date must use YYYY-MM-DD")
        entry = {"date": entry_date, "en": ask("Entry EN"), "fi": ask("Entry FI")}
        entries.insert(0, entry)
        path.write_text(json.dumps(entries, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
        actions = {"role": add_role, "project": add_project, "now": add_now, "changelog": add_changelog}
        if len(sys.argv) != 2 or sys.argv[1] not in actions:
                raise SystemExit("Usage: python3 add.py role|project|now|changelog")
        actions[sys.argv[1]]()
