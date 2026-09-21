import re
import html
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

SOURCE = "https://j50zavody.cz/zavody.php"
OUTPUT = "zavody.ics"

def clean(value):
    return re.sub(r"\\s+", " ", html.unescape(value or "")).strip()

def ics_escape(value):
    return clean(value).replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")

r = requests.get(SOURCE, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
r.raise_for_status()
soup = BeautifulSoup(r.text, "html.parser")

# The J50 page presents each race as a block containing its name,
# "Kdy", date, "Okres", district, "Typ trati", and "Systém závodu".
# Find dates first, then use the nearby text block as the event record.
events = []
for date_node in soup.find_all(string=re.compile(r"^\\s*\\d{1,2}\\.\\s*\\d{1,2}\\.\\s*\\d{4}\\s*$")):
    date_text = clean(date_node)
    m = re.search(r"(\\d{1,2})\\.\\s*(\\d{1,2})\\.\\s*(\\d{4})", date_text)
    if not m:
        continue
    day, month, year = map(int, m.groups())
    date = f"{year:04d}{month:02d}{day:02d}"

    # Walk upward until a reasonably self-contained race block is found.
    node = date_node.parent
    block = node
    for _ in range(8):
        if block is None:
            break
        txt = clean(block.get_text(" ", strip=True))
        if "Kdy" in txt and "Okres" in txt and "Typ trati" in txt:
            break
        block = block.parent

    if block is None:
        continue

    txt = clean(block.get_text(" ", strip=True))

    # Prefer the first heading in the block as the race name.
    heading = block.find(["h1", "h2", "h3", "h4", "h5", "h6"])
    if heading:
        name = clean(heading.get_text(" ", strip=True))
    else:
        # Fallback: text immediately before "Kdy".
        before = txt.split(" Kdy", 1)[0]
        name = clean(before)

    # Ignore filter/header blocks.
    if not name or name.lower() in {"seznam závodů", "filtrace"}:
        continue

    okres = ""
    typ = ""
    system = ""

    parts = re.split(r"\\s+(?=Kdy\\b|Okres\\b|Typ trati\\b|Systém závodu\\b)", txt)
    for part in parts:
        if part.startswith("Okres"):
            okres = clean(re.sub(r"^Okres\\s*", "", part))
        elif part.startswith("Typ trati"):
            typ = clean(re.sub(r"^Typ trati\\s*", "", part))
        elif part.startswith("Systém závodu"):
            system = clean(re.sub(r"^Systém závodu\\s*", "", part))

    # Find the race detail link in this block.
    link = None
    for a in block.find_all("a", href=True):
        label = clean(a.get_text(" ", strip=True)).lower()
        if "zobrazit závod" in label:
            link = a
            break

    url = link.get("href", SOURCE) if link else SOURCE
    if url.startswith("/"):
        url = "https://j50zavody.cz" + url
    elif not url.startswith("http"):
        url = SOURCE

    uid = re.sub(r"[^a-z0-9]+", "-", (name + "-" + date).lower()).strip("-")
    description = "Typ trati: " + typ
    if system:
        description += " | Systém: " + system
    events.append((uid, date, name, okres, description, url))

# De-duplicate and sort by date/name.
unique = {}
for event in events:
    unique[event[0]] = event
events = sorted(unique.values(), key=lambda e: (e[1], e[2]))

lines = [
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
    lines += [
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

lines += ["END:VCALENDAR"]

with open(OUTPUT, "w", encoding="utf-8", newline="\n") as f:
    f.write("\n".join(lines) + "\n")

print(f"Generated {len(events)} calendar events.")
