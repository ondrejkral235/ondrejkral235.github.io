import re
import html
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from email.utils import format_datetime

SOURCE = "https://j50zavody.cz/zavody.php"
OUTPUT = "zavody.ics"

def clean(value):
    return re.sub(r"\\s+", " ", html.unescape(value or "")).strip()

def ics_escape(value):
    return clean(value).replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")

def date_to_ics(value):
    m = re.search(r"(\\d{1,2})[.\\-/](\\d{1,2})[.\\-/](\\d{4})", value)
    if not m:
        return None
    d, mo, y = map(int, m.groups())
    return f"{y:04d}{mo:02d}{d:02d}"

r = requests.get(SOURCE, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
r.raise_for_status()
soup = BeautifulSoup(r.text, "html.parser")

events = []
for row in soup.find_all("tr"):
    cells = [clean(c.get_text(" ", strip=True)) for c in row.find_all(["td", "th"])]
    if len(cells) < 2:
        continue
    text = " | ".join(cells)
    date = date_to_ics(text)
    if not date:
        continue

    link = row.find("a", href=True)
    url = link.get("href", SOURCE) if link else SOURCE
    if url.startswith("/"):
        url = "https://j50zavody.cz" + url
    elif not url.startswith("http"):
        url = SOURCE

    name = clean(link.get_text(" ", strip=True)) if link else cells[0]
    if not name or name.lower() in {"datum", "date"}:
        name = cells[0]

    location = cells[1] if len(cells) > 1 else ""
    description = " | ".join(cells)

    uid = re.sub(r"[^a-z0-9]+", "-", (name + "-" + date).lower()).strip("-")
    events.append((uid, date, name, location, description, url))

# Remove exact duplicates while preserving order.
unique = []
seen = set()
for e in events:
    if e[0] not in seen:
        seen.add(e[0])
        unique.append(e)

lines = [
    "BEGIN:VCALENDAR",
    "VERSION:2.0",
    "PRODID:-//OndrejKral235//J50 Zavodni kalendar//CS",
    "CALSCALE:GREGORIAN",
    "METHOD:PUBLISH",
]

stamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
for uid, date, name, location, description, url in unique:
    from datetime import datetime as dt, timedelta
    start = dt.strptime(date, "%Y%m%d")
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

print(f"Generated {len(unique)} calendar events.")
