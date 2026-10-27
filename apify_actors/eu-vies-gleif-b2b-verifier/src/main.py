"""
Apify Actor: EU VIES VAT & Global LEI Corporate KYB Verifier (MCP Ready).
Monetization: Pay-Per-Event ($0.004 per corporate KYB verification). Zero proxy cost.
"""
import re
import asyncio
import requests

VIES_URL_TPL = "https://ec.europa.eu/taxation_customs/vies/rest-api/ms/{country}/vat/{number}"
GLEIF_SEARCH_URL = "https://api.gleif.org/api/v1/lei-records"


def verify_eu_vat(full_vat: str) -> dict:
    clean = re.sub(r"[^A-Za-z0-9]", "", full_vat or "").upper()
    if len(clean) < 4:
        return {"query": full_vat, "type": "eu_vies_vat", "is_valid": False, "error": "Invalid VAT format"}
    country = clean[:2]
    number = clean[2:]
    url = VIES_URL_TPL.format(country=country, number=number)
    r = requests.get(url, headers={"Accept": "application/json"}, timeout=15)
    if r.status_code != 200:
        return {"query": clean, "type": "eu_vies_vat", "country": country, "vat_number": number, "is_valid": False, "http_status": r.status_code}
    data = r.json()
    return {
        "query": clean,
        "type": "eu_vies_vat",
        "country": country,
        "vat_number": data.get("vatNumber") or number,
        "is_valid": bool(data.get("isValid")),
        "status_code": data.get("userError"),
        "company_name": None if data.get("name") in (None, "---") else data.get("name"),
        "registered_address": None if data.get("address") in (None, "---") else data.get("address"),
        "checked_at": data.get("requestDate")
    }


def search_gleif_lei(company_name: str, limit: int = 3) -> list:
    q = (company_name or "").strip()
    if not q:
        return []
    r = requests.get(
        GLEIF_SEARCH_URL,
        params={"filter[entity.legalName]": q, "page[size]": min(max(1, int(limit)), 10)},
        headers={"Accept": "application/vnd.api+json"},
        timeout=15
    )
    if r.status_code != 200:
        return []
    records = []
    for item in r.json().get("data", []):
        attrs = item.get("attributes", {})
        ent = attrs.get("entity", {})
        reg = attrs.get("registration", {})
        hq = ent.get("headquartersAddress", {})
        records.append({
            "query": q,
            "type": "gleif_lei",
            "lei": attrs.get("lei"),
            "legal_name": (ent.get("legalName") or {}).get("name"),
            "jurisdiction": ent.get("jurisdiction"),
            "entity_status": ent.get("status"),
            "registration_status": reg.get("status"),
            "city": hq.get("city"),
            "country": hq.get("country"),
            "initial_registration_date": reg.get("initialRegistrationDate"),
            "next_renewal_date": reg.get("nextRenewalDate")
        })
    return records


async def main():
    from apify import Actor
    async with Actor:
        inp = await Actor.get_input() or {}
        vats = inp.get("vatNumbers") or ["IE6388047V"]
        names = inp.get("companyNames") or ["TELEFONICA SA"]
        for v in vats[:50]:
            await Actor.push_data(verify_eu_vat(v))
        for name in names[:25]:
            for rec in search_gleif_lei(name, limit=2):
                await Actor.push_data(rec)


if __name__ == "__main__":
    asyncio.run(main())
