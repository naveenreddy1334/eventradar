# Event Radar — Leap Interactive

Internal dashboard to scout upcoming events (concerts, corporate launches, sports,
festivals, etc.) across India, for pitching event tech / drone shows / AI booths.

Runs itself: a scraper pulls fresh listings every 6 hours via GitHub Actions,
and GitHub Pages hosts the dashboard for free. No server to maintain.

## One-time setup (15 minutes)

1. **Create a GitHub repo** (if you don't have one already) and push this folder to it.
   ```
   git init
   git add .
   git commit -m "Initial event radar"
   git branch -M main
   git remote add origin https://github.com/<your-org>/event-radar.git
   git push -u origin main
   ```

2. **Enable GitHub Pages**: repo Settings → Pages → Source: "Deploy from a branch"
   → Branch: `main`, folder: `/docs`. Save. Your team's URL will be
   `https://<your-org>.github.io/event-radar/` (or your org's equivalent).

3. **Enable Actions**: repo Settings → Actions → General → make sure "Allow all
   actions" is on, and under Workflow permissions, set "Read and write
   permissions" (the scraper needs to commit its own updates).

4. **Trigger the first run manually**: Actions tab → "Scrape events" → Run workflow.
   This populates `docs/data.json` with real scraped data instead of the seed
   data that ships with this repo. Takes 2–3 minutes.

That's it — from here it runs every 6 hours on its own.

## What runs where

- `scraper/allevents_scraper.py` — pulls from allevents.in using their embedded
  structured data (JSON-LD). This is the sturdier source; it doesn't depend on
  guessing CSS class names.
- `scraper/bookmyshow_scraper.py` — pulls from BookMyShow using a headless
  browser (Playwright), since their site is a JS-rendered app. **This is the
  part most likely to need occasional fixing** — see the comment at the top of
  that file for how to fix it if BookMyShow changes their layout.
- `scraper/merge.py` — combines both, removes duplicates, drops events whose
  date has passed, and — importantly — if either scraper fails, keeps that
  source's last successful data instead of wiping the dashboard blank.
- `docs/index.html` — the dashboard your team visits. Reads `docs/data.json`.
- `.github/workflows/scrape.yml` — the automation: runs the scrapers on a
  schedule and commits the result.

## Adding cities

Both scraper files have a `CITIES` dict near the top — add or remove city
names and URLs there.

## Adding corporate / school events manually

These rarely show up on public ticketing sites. Open `docs/data.json` (or ask
Claude to add one), and append an entry to the `events` array in this shape:

```json
{"name":"Example Corp Launch","date":"2026-10-12","city":"Bengaluru","venue":"UB City","cat":"corporate","source":"manual"}
```

Valid `cat` values: `concert`, `comedy`, `theatre`, `sports`, `festival`,
`education`, `corporate`.

## If the dashboard looks stale or wrong

1. Check the Actions tab for the latest "Scrape events" run — click in and read
   the logs. Each scraper prints how many events it found per city.
2. If BookMyShow shows 0 events, their site likely changed — see the fix
   instructions at the top of `scraper/bookmyshow_scraper.py`.
3. The dashboard footer shows per-source status (ok / failed) and when data
   was last refreshed, so your team can see at a glance if something's off.
