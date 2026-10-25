"""
Apify Actor: EU Public Tenders & Government Contracts Extractor (TED API v3).
Monetization: Pay-Per-Event ($0.005 per tender extracted). Zero proxy cost.
"""
import asyncio
import requests

TED_SEARCH_URL = "https://api.ted.europa.eu/v3/notices/search"


def fetch_ted_tenders(keyword: str = "software", country: str = "ESP", limit: int = 20) -> list:
    clauses = [f'FT ~ "{keyword}"']
    if country and len(country.strip()) == 3:
        clauses.append(f'CY = "{country.strip().upper()}"')
    query_str = " AND ".join(clauses)
    payload = {
        "query": query_str,
        "fields": ["ND", "PD", "TI", "CY", "AU"],
        "page": 1,
        "limit": min(max(1, int(limit)), 100)
    }
    r = requests.post(TED_SEARCH_URL, json=payload, headers={"Accept": "application/json", "Content-Type": "application/json"}, timeout=20)
    r.raise_for_status()
    notices = r.json().get("notices", [])
    results = []
    for n in notices:
        nd = n.get("ND", "")
        results.append({
            "notice_id": nd,
            "publication_date": n.get("PD"),
            "country": n.get("CY"),
            "title": n.get("TI"),
            "buyer": n.get("AU"),
            "url": f"https://ted.europa.eu/en/notice/-/detail/{nd}" if nd else ""
        })
    return results


async def main():
    from apify import Actor
    async with Actor:
        inp = await Actor.get_input() or {}
        items = fetch_ted_tenders(
            keyword=inp.get("keyword", "software"),
            country=inp.get("country", "ESP"),
            limit=inp.get("maxItems", 25)
        )
        for item in items:
            await Actor.push_data(item)


if __name__ == "__main__":
    asyncio.run(main())
