"""
Apify Actor: Open Source Repository Health & Security Auditor (GitHub MCP).
Monetization: Pay-Per-Event ($0.003 per repository audit). Zero proxy cost.
"""
import re
import asyncio
import requests


def audit_repo(target: str) -> dict:
    clean = target.strip()
    m = re.search(r"github\.com/([^/]+/[^/]+)", clean)
    slug = m.group(1) if m else clean
    slug = slug.strip("/ ")
    
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "RepoHealthAuditor/1.0"}
    r = requests.get(f"https://api.github.com/repos/{slug}", headers=headers, timeout=12)
    if r.status_code != 200:
        return {"repo": slug, "found": False, "status_code": r.status_code, "health_score": 0}

    data = r.json()
    stars = data.get("stargazers_count", 0)
    forks = data.get("forks_count", 0)
    open_issues = data.get("open_issues_count", 0)
    license_info = (data.get("license") or {}).get("spdx_id") or "UNKNOWN"
    archived = data.get("archived", False)
    default_branch = data.get("default_branch", "main")
    updated_at = data.get("pushed_at") or data.get("updated_at")

    rel_r = requests.get(f"https://api.github.com/repos/{slug}/releases/latest", headers=headers, timeout=8)
    latest_release = rel_r.json().get("tag_name") if rel_r.status_code == 200 else None

    # Cálculo heurístico de puntuación de salud y mantenimiento
    score = 100
    warnings = []
    if archived:
        score -= 70
        warnings.append("Repository is archived / abandoned")
    if license_info in ("UNKNOWN", "NOASSERTION", None):
        score -= 25
        warnings.append("No clear OSI-compliant license detected")
    if open_issues > 500 and stars < 5000:
        score -= 20
        warnings.append("High unresolved issue ratio")

    score = max(0, score)
    health = "EXCELLENT" if score >= 80 else ("MODERATE" if score >= 50 else "AT_RISK")

    return {
        "repo": slug,
        "found": True,
        "full_name": data.get("full_name"),
        "description": data.get("description"),
        "stars": stars,
        "forks": forks,
        "open_issues": open_issues,
        "license": license_info,
        "latest_release": latest_release,
        "is_archived": archived,
        "last_pushed_at": updated_at,
        "health_score": score,
        "status": health,
        "warnings": warnings
    }


async def main():
    from apify import Actor
    async with Actor:
        inp = await Actor.get_input() or {}
        repos = inp.get("repositories") or ["pallets/flask"]
        for repo_slug in repos[:30]:
            await Actor.push_data(audit_repo(repo_slug))


if __name__ == "__main__":
    asyncio.run(main())
