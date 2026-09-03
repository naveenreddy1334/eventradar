"""
Scrapes BookMyShow city "explore events" pages for concerts, plays, and sports.

IMPORTANT — read this before you rely on it:
BookMyShow is a JS-rendered React app, not static HTML, so this uses a headless
browser (Playwright) instead of requests+BeautifulSoup. It is the most fragile
part of this pipeline: BookMyShow can change their DOM/class names at any time,
which will silently return 0 events until the selectors below are updated.

If this starts returning 0 events:
1. Run `playwright codegen https://in.bookmyshow.com/explore/events-bengaluru`
   to open a real browser and inspect the current card structure.
2. Update the SELECTORS dict below to match.
3. This script is written so a total failure here does NOT break the dashboard
   — merge.py keeps the last known-good BookMyShow data if this returns nothing.

Usage: python bookmyshow_scraper.py > bookmyshow_raw.json
"""
import json
import re
import sys
import time
from datetime import datetime

from playwright.sync_api import sync_playwright

CITIES = {
    "bangalore": "https://in.bookmyshow.com/explore/events-bengaluru",
    "mumbai": "https://in.bookmyshow.com/explore/events-mumbai",
    "delhi": "https://in.bookmyshow.com/explore/events-national-capital-region-ncr",
    "hyderabad": "https://in.bookmyshow.com/explore/events-hyderabad",
    "pune": "https://in.bookmyshow.com/explore/events-pune",
    "chennai": "https://in.bookmyshow.com/explore/events-chennai",
}

# These selectors are best-effort based on BookMyShow's general card-list
# pattern as of writing. THEY WILL LIKELY NEED ADJUSTMENT — see docstring above.
SELECTORS = {
    "card": "[class*='card' i], [class*='Card' i], a[href*='/events/']",
    "title": "[class*='title' i], [class*='name' i], h3, h2",
    "date": "[class*='date' i]",
    "venue": "[class*='venue' i], [class*='location' i]",
}

CATEGORY_KEYWORDS = {
    "comedy": "comedy",
    "stand-up": "comedy",
    "theatre": "theatre",
    "play": "theatre",
    "cricket": "sports",
    "football": "sports",
    "marathon": "sports",
    "sports": "sports",
    "workshop": "education",
    "conference": "corporate",
    "summit": "corporate",
    "expo": "corporate",
}


def guess_category(text):
    text = (text or "").lower()
    for key, cat in CATEGORY_KEYWORDS.items():
        if key in text:
            return cat
    return "concert"


def parse_date(raw_text):
    """BookMyShow dates come in varied free-text formats. Best-effort parse;
    returns None if unparseable so the caller can drop the event rather than
    guess wrong."""
    if not raw_text:
        return None
    raw_text = raw_text.strip()
    formats = ["%d %b %Y", "%d %B %Y", "%a, %d %b", "%d %b, %Y"]
    for fmt in formats:
        try:
            dt = datetime.strptime(raw_text, fmt)
            if dt.year == 1900:
                dt = dt.replace(year=datetime.utcnow().year)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def fetch_city(city_name, url, page):
    events = []
    try:
        page.goto(url, timeout=30000, wait_until="domcontentloaded")
        page.wait_for_timeout(3000)  # let JS render cards
    except Exception as exc:
        print(f"[bookmyshow] FAILED to load {city_name}: {exc}", file=sys.stderr)
        return events

    cards = page.query_selector_all(SELECTORS["card"])
    seen_names = set()

    for card in cards:
        try:
            title_el = card.query_selector(SELECTORS["title"])
            name = title_el.inner_text().strip() if title_el else None
            if not name or name in seen_names or len(name) < 3:
                continue
            seen_names.add(name)

            date_el = card.query_selector(SELECTORS["date"])
            date_text = date_el.inner_text().strip() if date_el else ""
            parsed_date = parse_date(date_text)
            if not parsed_date:
                continue  # skip rather than guess a wrong date

            venue_el = card.query_selector(SELECTORS["venue"])
            venue = venue_el.inner_text().strip() if venue_el else "TBA"

            href = card.get_attribute("href") or ""
            source_url = href if href.startswith("http") else f"https://in.bookmyshow.com{href}"

            events.append({
                "name": name,
                "date": parsed_date,
                "city": city_name.title(),
                "venue": venue,
                "cat": guess_category(name),
                "source": "bookmyshow.com",
                "source_url": source_url,
            })
        except Exception as exc:
            print(f"[bookmyshow] skipped a card in {city_name}: {exc}", file=sys.stderr)
            continue

    print(f"[bookmyshow] {city_name}: {len(events)} events", file=sys.stderr)
    return events


def main():
    all_events = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ))
        for city_name, url in CITIES.items():
            all_events.extend(fetch_city(city_name, url, page))
            time.sleep(2)
        browser.close()

    print(json.dumps({
        "scraped_at": datetime.utcnow().isoformat() + "Z",
        "source": "bookmyshow.com",
        "ok": len(all_events) > 0,
        "events": all_events,
    }))


if __name__ == "__main__":
    main()
