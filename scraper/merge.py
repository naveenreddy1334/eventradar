"""
Merges the outputs of allevents_scraper.py and bookmyshow_scraper.py into the
single docs/data.json the dashboard reads.

Key behavior: if a source's scrape FAILED (ok: false / 0 events), this keeps
that source's events from the previous data.json instead of wiping them out.
This is what stops one broken scraper from blanking the whole dashboard.

Usage: python merge.py allevents_raw.json bookmyshow_raw.json
"""
import json
import sys
from datetime import datetime, timedelta

OUTPUT_PATH = "docs/data.json"


def load_json_arg(path):
    try:
        with open(path) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def load_previous():
    try:
        with open(OUTPUT_PATH) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"events": [], "sources": {}}


def dedupe(events):
    seen = set()
    out = []
    for e in events:
        key = (e["name"].lower().strip(), e["date"], e["city"].lower().strip())
        if key in seen:
            continue
        seen.add(key)
        out.append(e)
    return out


def drop_stale(events, days=1):
    """Drop events whose date is more than `days` in the past."""
    cutoff = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d")
    return [e for e in events if e["date"] >= cutoff]


def main():
    if len(sys.argv) < 2:
        print("Usage: merge.py <scraper_output.json> [more...]", file=sys.stderr)
        sys.exit(1)

    previous = load_previous()
    prev_sources = previous.get("sources", {})
    prev_events_by_source = {}
    for e in previous.get("events", []):
        prev_events_by_source.setdefault(e.get("source", "unknown"), []).append(e)

    merged_events = []
    source_status = {}

    for path in sys.argv[1:]:
        result = load_json_arg(path)
        if result is None:
            print(f"[merge] could not read {path}, skipping", file=sys.stderr)
            continue

        source_name = result.get("source", path)
        if result.get("ok") and result.get("events"):
            merged_events.extend(result["events"])
            source_status[source_name] = {
                "last_success": result.get("scraped_at"),
                "event_count": len(result["events"]),
                "status": "ok",
            }
            print(f"[merge] {source_name}: {len(result['events'])} fresh events", file=sys.stderr)
        else:
            fallback = prev_events_by_source.get(source_name, [])
            merged_events.extend(fallback)
            source_status[source_name] = {
                "last_success": prev_sources.get(source_name, {}).get("last_success", "unknown"),
                "event_count": len(fallback),
                "status": "FAILED — showing last known data",
            }
            print(f"[merge] {source_name} FAILED, keeping {len(fallback)} events from last good run", file=sys.stderr)

    merged_events = dedupe(merged_events)
    merged_events = drop_stale(merged_events)
    merged_events.sort(key=lambda e: e["date"])

    failed_sources = [name for name, s in source_status.items() if s["status"] != "ok"]

    output = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "sources": source_status,
        "failed_sources": failed_sources,
        "events": merged_events,
    }

    import os
    os.makedirs("docs", exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(output, f, indent=2)

    print(f"[merge] wrote {len(merged_events)} total events to {OUTPUT_PATH}", file=sys.stderr)

    # Exit code 1 signals the workflow to send a failure notification, without
    # failing the whole job (data.json still gets committed either way).
    if failed_sources:
        print(f"[merge] sources failed: {failed_sources}", file=sys.stderr)
        with open("failed_sources.txt", "w") as f:
            f.write(",".join(failed_sources))


if __name__ == "__main__":
    main()
