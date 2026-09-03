"""
Scrapes allevents.in city pages for structured event data (schema.org JSON-LD).
This is the MORE RELIABLE source: allevents.in embeds clean JSON-LD blocks per
event, so this doesn't depend on guessing CSS classes that change on redesign.

Usage: python allevents_scraper.py > allevents_raw.json
"""
import json
import re
import sys
import time
from datetime import datetime

import requests
from bs4 import BeautifulSoup

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

# Add / remove cities here. allevents.in URL pattern: allevents.in/<city>/<city>
CITIES = {
    "bangalore": "https://allevents.in/bangalore/bengaluru",
    "mumbai": "https://allevents.in/mumbai",
    "delhi": "https://allevents.in/delhi",
    "hyderabad": "https://allevents.in/hyderabad",
    "pune": "https://allevents.in/pune",
    "chennai": "https://allevents.in/chennai",
}

CATEGORY_MAP = {
    "music": "concert",
    "concert": "concert",
    "nightlife": "concert",
    "comedy": "comedy",
    "theatre": "theatre",
    "theater": "theatre",
    "sports": "sports",
    "sport": "sports",
    "festival": "festival",
    "food": "festival",
    "business": "corporate",
    "corporate": "corporate",
    "networking": "corporate",
    "education": "education",
    "workshop": "education",
}


def guess_category(text):
    text = (text or "").lower()
    for key, cat in CATEGORY_MAP.items():
        if key in text:
            return cat
    return "concert"


def fetch_city(city_name, url, session):
    events = []
    try:
        resp = session.get(url, headers={"User-Agent": USER_AGENT}, timeout=20)
        resp.raise_for_status()
    except requests.RequestException as exc:
        print(f"[allevents] FAILED to fetch {city_name}: {exc}", file=sys.stderr)
        return events

    soup = BeautifulSoup(resp.text, "html.parser")
    scripts = soup.find_all("script", type="application/ld+json")

    for script in scripts:
        try:
            data = json.loads(script.string or "{}")
        except (json.JSONDecodeError, TypeError):
            continue

        # JSON-LD can be a single object or a list
        items = data if isinstance(data, list) else [data]
        for item in items:
            if not isinstance(item, dict):
                continue
            if item.get("@type") not in ("Event", "MusicEvent", "SocialEvent",
                                          "TheaterEvent", "SportsEvent",
                                          "BusinessEvent", "EducationEvent"):
                continue
            try:
                name = item.get("name", "").strip()
                start_date = item.get("startDate", "")[:10]
                if not name or not start_date:
                    continue
                location = item.get("location", {}) or {}
                loc_name = location.get("name", "") if isinstance(location, dict) else ""
                address = location.get("address", {}) if isinstance(location, dict) else {}
                locality = address.get("addressLocality", city_name.title()) if isinstance(address, dict) else city_name.title()

                events.append({
                    "name": name,
                    "date": start_date,
                    "city": locality or city_name.title(),
                    "venue": loc_name or "TBA",
                    "cat": guess_category(item.get("@type", "") + " " + name),
                    "source": "allevents.in",
                    "source_url": item.get("url", url),
                })
            except Exception as exc:
                print(f"[allevents] skipped malformed event in {city_name}: {exc}", file=sys.stderr)
                continue

    print(f"[allevents] {city_name}: {len(events)} events", file=sys.stderr)
    return events


def main():
    session = requests.Session()
    all_events = []
    for city_name, url in CITIES.items():
        all_events.extend(fetch_city(city_name, url, session))
        time.sleep(2)  # be polite, avoid rate limiting

    print(json.dumps({
        "scraped_at": datetime.utcnow().isoformat() + "Z",
        "source": "allevents.in",
        "ok": len(all_events) > 0,
        "events": all_events,
    }))


if __name__ == "__main__":
    main()
