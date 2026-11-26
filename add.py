#!/usr/bin/env python3
"""Add timeline, Now, and changelog content without replacing existing entries."""
import json
import re
import shutil
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CONTENT = ROOT / "content"
SITE = ROOT / "site"


def ask(prompt): return input(prompt + ": ").strip()
def bilingual(prompt): return {"en": ask(prompt + " EN"), "fi": ask(prompt + " FI")}
def links(): return {key: ask(label + " URL (blank to skip)") for key,label in (("demo","Demo"),("code","Code"),("writeup","Write-up"))}
def tags(): return [v.strip() for v in ask("Tags (comma-separated)").split(",") if v.strip()]
def add_entry(entry):
    path=CONTENT/"timeline.json"
    entries=json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
    entries.insert(0,entry)
    temp=path.with_suffix(".json.tmp")
    temp.write_text(json.dumps(entries,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    temp.replace(path)

def add_role():
    add_entry({"type":"role","start":ask("Start (YYYY-MM or YYYY-MM-DD)"),"end":ask("End (YYYY-MM, YYYY-MM-DD, or blank for present)"),"employer":ask("Employer"),"role":bilingual("Role"),"points":{"en":_lines("Achievement EN"),"fi":_lines("Achievement FI")}})

def _lines(prompt):
    print(prompt+" (blank line to finish)"); rows=[]
    while True:
        row=input("- ").strip()
        if not row: return rows
        rows.append(row)

def add_project():
    add_entry({"type":"project","date":ask("Date (YYYY-MM or YYYY-MM-DD)"),"title":ask("Title"),"role":bilingual("Role"),"description":bilingual("Description"),"tags":tags(),"links":links(),"media":[],"learned":bilingual("What I learned (blank to skip)")})

def add_hackathon():
    entry={"type":"hackathon","date_start":ask("Start (YYYY-MM-DD)"),"date_end":ask("End (YYYY-MM-DD or blank)") or "","event":ask("Event name"),"what":bilingual("Event and build details"),"where":bilingual("Venue"),"theme":bilingual("Theme"),"team":{"name":ask("Team name (blank to skip)"),"size":int(ask("Team size (0 if unknown)"))},"role":bilingual("My role"),"result":bilingual("Result or award (blank to skip)"),"project":{"title":ask("Project title"),"description":bilingual("Project description"),"tags":tags(),"links":links(),"media":[]},"learned":bilingual("What I learned (blank to skip)")}
    add_entry(entry)

def add_media():
    entries=json.loads((CONTENT/"timeline.json").read_text(encoding="utf-8"))
    candidates=[(i,e) for i,e in enumerate(entries) if e.get("type") in ("hackathon","project")]
    for number,(i,e) in enumerate(candidates,1):
        title=e.get("event") or e.get("title") or e.get("project",{}).get("title","")
        print(f"{number}. {title}")
    selection=int(ask("Entry number"))-1
    if selection<0 or selection>=len(candidates): raise ValueError("Entry number is out of range")
    idx,entry=candidates[selection]
    bucket=entry["project"] if entry["type"]=="hackathon" else entry
    source=Path(ask("Image file path")).expanduser()
    if not source.is_file(): raise ValueError("Image file does not exist")
    title=entry.get("event") or entry.get("title") or entry.get("project",{}).get("title","")
    slug=re.sub(r"[^a-z0-9]+","-",title.lower()).strip("-") or "entry"
    dest_dir=SITE/"img"/slug; dest_dir.mkdir(parents=True,exist_ok=True)
    dest=dest_dir/source.name; suffix=2
    while dest.exists():
        dest=dest_dir/f"{source.stem}-{suffix}{source.suffix}"; suffix+=1
    shutil.copy2(source,dest)
    rel=dest.relative_to(SITE/"img").as_posix()
    item={"file":rel,"alt":bilingual("Alt text"),"caption":bilingual("Caption (blank to skip)")}
    bucket.setdefault("media",[]).append(item)
    (CONTENT/"timeline.json").write_text(json.dumps(entries,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")

def add_now():
    path=CONTENT/"now.json"; data=json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"updated":"","items":[]}
    rows=[]
    while True:
        en=ask("Now item EN (blank to finish)")
        if not en: break
        rows.append({"en":en,"fi":ask("Now item FI")})
    if rows: data["updated"]=date.today().isoformat(); data["items"]=rows+data.get("items",[]); path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")

def add_changelog():
    path=CONTENT/"changelog.json"; entries=json.loads(path.read_text(encoding="utf-8")); when=ask("Date (YYYY-MM-DD; blank for today)") or date.today().isoformat(); date.fromisoformat(when)
    entries.insert(0,{"date":when,**bilingual("Entry")}); path.write_text(json.dumps(entries,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")

if __name__=="__main__":
    actions={"hackathon":add_hackathon,"project":add_project,"role":add_role,"media":add_media,"now":add_now,"changelog":add_changelog}
    if len(sys.argv)!=2 or sys.argv[1] not in actions: raise SystemExit("Usage: python add.py hackathon|project|role|media|now|changelog")
    actions[sys.argv[1]]()
