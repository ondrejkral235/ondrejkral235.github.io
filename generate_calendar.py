import re
import html
import requests
from datetime import datetime, timedelta

SOURCE = "https://j50zavody.cz/zavody.php"
READER = "https://r.jina.ai/http://j50zavody.cz/zavody.php"
OUTPUT = "zavody.ics"

def clean(value):
    return re.sub(r"\s+", " ", html.unescape(value or "")).strip()

def ics_escape(value):
    return clean(value).replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")

r = requests.get(READER, timeout=60, headers={"User-Agent": "Mozilla/5.0"})
r.raise_for_status()
text = r.text

events = []
lines = text.splitlines()

for i, line in enumerate(lines):
    # Jina renders the J50 race names as level-3 Markdown headings.
    if not line.startswith("### "):
        continue

    name = clean(re.sub(r"^###\s+", "", line))
    if not name or name in {"Seznam závodů", "Filtrace", "Důležité odkazy", "Mohlo by vás zajímat", "Kontakt"}:
        continue

    block = []
    for nxt in lines[i + 1:i + 18]:
        if nxt.startswith("### "):
            break
        block.append(clean(re.sub(r"^#+\s*", "", nxt)))

    block_text = " | ".join(x for x in block if x)
    date_match = re.search(r"(\d{1,2})\.\s*(\d{1,2})\.\s*(\d{4})", block_text)
    if not date_match:
        continue

    day, month, year = map(int, date_match.groups())
    date = f"{year:04d}{month:02d}{day:02d}"

    okres_match = re.search(r"Okres\s+(.+?)(?=\s+Typ trati\b|\s+Systém závodu\b|$)", block_text)
    typ_match = re.search(r"Typ trati\s+(.+?)(?=\s+Systém závodu\b|$)", block_text)
    system_match = re.search(r"Systém závodu\s+(.+)$", block_text)

    location = clean(okres_match.group(1)) if okres_match else ""
    typ = clean(typ_match.group(1)) if typ_match else ""
    system = clean(system_match.group(1)) if system_match else ""

    description_parts = []
    if typ:
        description_parts.append("Typ trati: " + typ)
    if system:
        description_parts.append("Systém: " + system)
    description = " | ".join(description_parts)

    uid = re.sub(r"[^a-z0-9]+", "-", (name + "-" + date).lower()).strip("-")
    events.append((uid, date, name, location, description, SOURCE))

unique = {event[0]: event for event in events}
events = sorted(unique.values(), key=lambda e: (e[1], e[2]))

lines_out = [
    "BEGIN:VCALENDAR",
    "VERSION:2.0",
    "PRODID:-//OndrejKral235//J50 Zavodni kalendar//CS",
    "CALSCALE:GREGORIAN",
    "METHOD:PUBLISH",
]

stamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
for uid, date, name, location, description, url in events:
    start = datetime.strptime(date, "%Y%m%d")
    end = start + timedelta(days=1)
    lines_out += [
        "BEGIN:VEVENT",
        f"UID:{ics_escape(uid)}@ondrejkral235.github.io",
        f"DTSTAMP:{stamp}",
        f"DTSTART;VALUE=DATE:{date}",
        f"DTEND;VALUE=DATE:{end.strftime('%Y%m%d')}",
        f"SUMMARY:{ics_escape(name)}",
        f"LOCATION:{ics_escape(location)}",
        f"DESCRIPTION:{ics_escape(description)}",
        f"URL:{url}",
        "END:VEVENT",
    ]

lines_out.append("END:VCALENDAR")
with open(OUTPUT, "w", encoding="utf-8", newline="\n") as f:
    f.write("\n".join(lines_out) + "\n")

print(f"Generated {len(events)} calendar events.")
