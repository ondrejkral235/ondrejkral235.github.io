import re
import html
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

SOURCE = "https://j50zavody.cz/zavody.php"
OUTPUT = "zavody.ics"

def clean(value):
    return re.sub(r"\s+", " ", html.unescape(value or "")).strip()

def ics_escape(value):
    return clean(value).replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")

r = requests.get(SOURCE, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
r.raise_for_status()
soup = BeautifulSoup(r.text, "html.parser")

events = []

# Each race on the J50 page is headed by an h3. The following h4 elements
# contain date, district, track type and race system.
headings = soup.find_all("h3")
for heading in headings:
    name = clean(heading.get_text(" ", strip=True))
    if not name or name in {"Filtrace", "Důležité odkazy", "Mohlo by vás zajímat", "Kontakt"}:
        continue

    values = []
    node = heading.find_next_sibling()
    steps = 0
    while node is not None and steps < 20:
        if getattr(node, "name", None) == "h3":
            break
        text = clean(node.get_text(" ", strip=True))
        if text:
            values.append(text)
        node = node.find_next_sibling()
        steps += 1

    block_text = " | ".join(values)
    date_match = re.search(r"(\d{1,2})\.\s*(\d{1,2})\.\s*(\d{4})", block_text)
    if not date_match:
        # Fallback: search a small parent block.
        parent = heading.parent
        block_text = clean(parent.get_text(" ", strip=True))
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

    link = None
    container = heading.parent
    for a in container.find_all("a", href=True):
        if "zobrazit závod" in clean(a.get_text(" ", strip=True)).lower():
            link = a
            break

    if link is None:
        # Search the nearest following "Zobrazit závod" link.
        a = heading.find_next("a", href=True)
        if a and "zobrazit závod" in clean(a.get_text(" ", strip=True)).lower():
            link = a

    url = link.get("href", SOURCE) if link else SOURCE
    if url.startswith("/"):
        url = "https://j50zavody.cz" + url
    elif not url.startswith("http"):
        url = SOURCE

    uid = re.sub(r"[^a-z0-9]+", "-", (name + "-" + date).lower()).strip("-")
    description_parts = []
    if typ:
        description_parts.append("Typ trati: " + typ)
    if system:
        description_parts.append("Systém: " + system)
    description = " | ".join(description_parts)

    events.append((uid, date, name, location, description, url))

unique = {event[0]: event for event in events}
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

lines.append("END:VCALENDAR")
with open(OUTPUT, "w", encoding="utf-8", newline="\n") as f:
    f.write("\n".join(lines) + "\n")

print(f"Generated {len(events)} calendar events.")
