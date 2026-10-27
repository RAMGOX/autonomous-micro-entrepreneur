"""
Apify Actor: Global Natural Disaster & Climate Risk Tracker (NASA EONET v3 MCP).
Monetization: Pay-Per-Event ($0.003 per event record). Zero proxy cost.
"""
import asyncio
import requests

EONET_EVENTS_URL = "https://eonet.gsfc.nasa.gov/api/v3/events"


def fetch_natural_events(category: str = "all", status: str = "open", limit: int = 20) -> list:
    params = {"status": status, "limit": min(max(1, int(limit)), 100)}
    if category and category.lower() != "all":
        params["category"] = category.strip()
    r = requests.get(EONET_EVENTS_URL, params=params, headers={"Accept": "application/json"}, timeout=15)
    r.raise_for_status()
    raw_events = r.json().get("events", [])
    results = []
    for ev in raw_events:
        cats = [c.get("title") for c in ev.get("categories", []) if isinstance(c, dict)]
        geoms = ev.get("geometry", [])
        latest_geom = geoms[-1] if geoms else {}
        results.append({
            "event_id": ev.get("id"),
            "title": ev.get("title"),
            "link": ev.get("link"),
            "categories": cats,
            "closed": ev.get("closed"),
            "latest_coordinates": latest_geom.get("coordinates"),
            "latest_timestamp": latest_geom.get("date"),
            "sources": [s.get("url") for s in ev.get("sources", []) if isinstance(s, dict)]
        })
    return results


async def main():
    from apify import Actor
    async with Actor:
        inp = await Actor.get_input() or {}
        items = fetch_natural_events(
            category=inp.get("category", "all"),
            status=inp.get("status", "open"),
            limit=inp.get("maxItems", 20)
        )
        for item in items:
            await Actor.push_data(item)


if __name__ == "__main__":
    asyncio.run(main())
