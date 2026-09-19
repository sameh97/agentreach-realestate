"""
Node 3.5 — Real Estate Signal Enricher
=======================================
This is the niche-specific step that makes AgentReach worth more than a
generic "scrape Google Maps" tool. It re-reads the website already found
during the email-enrichment step (no extra API cost — just one more
fetch of pages we already have the URL for) and pulls out signals a
B2B vendor selling INTO real estate actually cares about:

  team_size            solo | small_team | large_team | brokerage | unknown
  specializations       list[str] — luxury, commercial, new_construction,
                         relocation, first_time_buyer, waterfront, land,
                         vacation_rental, senior_55plus
  license_detected      bool  — a license/DRE/Lic number is shown (compliance
                         + "this is a real, working licensee" signal)
  idx_detected          bool  — has a live IDX/MLS search widget (active,
                         maintained site vs. a placeholder page)
  testimonial_count     int   — rough count of client testimonials/reviews
                         embedded on the site (social proof density)
  years_in_business     int   — best-effort, from "since 20XX" / "X years
                         of experience" style phrases
  service_area_count    int   — number of distinct places mentioned after
                         "serving" / "areas we serve" (reach proxy)
  recent_activity       bool  — site has a recent-looking year/date
                         (blog, news, copyright footer) — flags dead sites

Demo-sourced leads already carry these fields (see maps_scraper.py) and
are skipped here to avoid pointless network calls.
"""
import os, re, logging, asyncio
from datetime import datetime
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from app.agents.state import LeadState

logger = logging.getLogger(__name__)

UA = "Mozilla/5.0 (compatible; AgentReachBot/1.0)"
_THIS_YEAR = datetime.now().year

# ── Keyword tables ──────────────────────────────────────────────────────────

_SPECIALIZATION_KWS = {
    "luxury":            ["luxury home", "luxury real estate", "high-end home", "estate home"],
    "commercial":        ["commercial real estate", "commercial property", "commercial listing"],
    "new_construction":  ["new construction", "new build home", "new home community"],
    "relocation":        ["relocation specialist", "relocating to", "corporate relocation"],
    "first_time_buyer":  ["first-time buyer", "first time buyer", "first time home buyer"],
    "waterfront":        ["waterfront", "beachfront", "lakefront", "oceanfront"],
    "land":              ["land for sale", "acreage", "farm and ranch", "vacant land"],
    "vacation_rental":   ["vacation rental", "short-term rental", "investment property"],
    "senior_55plus":     ["55+ community", "55 plus community", "senior living", "retirement community"],
}

_TEAM_MULTI_KWS  = ["our agents", "our team of", "meet the team", "meet our agents", "our realtors"]
_TEAM_SOLO_KWS   = ["i am a", "i've been helping", "i specialize", "as your agent"]
_BROKERAGE_KWS   = ["brokerage", "realty group", "properties llc", "real estate firm"]

_LICENSE_RE = re.compile(
    r"(?:DRE|BRE|Lic(?:ense)?)\.?\s*#?\s*\d{4,9}", re.IGNORECASE
)
_TEAM_COUNT_RE = re.compile(
    r"(?:team of|our\s+)(\d{1,3})\s+(?:agents|realtors)", re.IGNORECASE
)
_YEARS_EXPERIENCE_RE = re.compile(
    r"(\d{1,2})\+?\s+years?\s+(?:of\s+)?experience", re.IGNORECASE
)
_SINCE_YEAR_RE = re.compile(r"\bsince\s+(19|20)\d{2}\b", re.IGNORECASE)
_IDX_KWS = ["idx", "mls search", "search all listings", "search homes", "property search", "advanced search"]
_TESTIMONIAL_KWS = ["testimonial", "what our clients say", "client review", "5 star review", "★★★★★"]
_SERVING_RE = re.compile(
    r"(?:serving|areas we serve|service area[s]?)\s*[:\-]?\s*([A-Za-z,\s&]+?)(?:\.|\n|<)", re.IGNORECASE
)


def _detect_specializations(text: str) -> list[str]:
    found = []
    for tag, kws in _SPECIALIZATION_KWS.items():
        if any(kw in text for kw in kws):
            found.append(tag)
    return found


def _detect_team_size(text: str, category: str) -> str:
    m = _TEAM_COUNT_RE.search(text)
    if m:
        n = int(m.group(1))
        return "large_team" if n >= 6 else "small_team"

    cat = category.lower()
    if "agency" in cat or any(k in text for k in _BROKERAGE_KWS):
        return "brokerage"
    if any(k in text for k in _TEAM_MULTI_KWS):
        return "small_team"
    if any(k in text for k in _TEAM_SOLO_KWS):
        return "solo"
    return "unknown"


def _detect_years_in_business(text: str) -> int:
    m = _YEARS_EXPERIENCE_RE.search(text)
    if m:
        return int(m.group(1))
    m = _SINCE_YEAR_RE.search(text)
    if m:
        year = int(m.group(0)[-4:])
        return max(0, _THIS_YEAR - year)
    return 0


def _detect_service_area_count(text: str) -> int:
    m = _SERVING_RE.search(text)
    if not m:
        return 0
    chunk = m.group(1)
    places = [p.strip() for p in re.split(r",|&|\band\b", chunk) if p.strip()]
    # sanity cap — long runs of matched text are usually false positives
    return min(len(places), 15)


def _detect_recent_activity(text: str) -> bool:
    years_found = {int(y) for y in re.findall(r"\b(20\d{2})\b", text)}
    return any(y >= _THIS_YEAR - 1 for y in years_found)


async def _fetch_text(url: str) -> str:
    if not url:
        return ""
    if not url.startswith("http"):
        url = f"https://{url}"
    pages = [url, urljoin(url, "/about"), urljoin(url, "/agents")]
    combined = []
    async with httpx.AsyncClient(timeout=10, follow_redirects=True) as c:
        for page in pages:
            try:
                r = await c.get(page, headers={"User-Agent": UA})
                if "text/html" not in r.headers.get("content-type", ""):
                    continue
                soup = BeautifulSoup(r.text, "lxml")
                combined.append(soup.get_text(separator=" ").lower())
                # also check for IDX widget scripts, not just visible text
                for tag in soup.find_all(["script", "iframe"], src=True):
                    combined.append(tag["src"].lower())
            except Exception:
                pass
    return " ".join(combined)


async def _enrich_one(lead: dict) -> dict:
    if lead.get("source") == "demo":
        return lead  # already has realistic signal fields baked in

    website = lead.get("website", "")
    if not website:
        return {**lead, "team_size": "unknown"}

    try:
        text = await _fetch_text(website)
    except Exception as e:
        logger.debug(f"[re_signals] fetch failed for {website}: {e}")
        return {**lead, "team_size": "unknown"}

    if not text:
        return {**lead, "team_size": "unknown"}

    license_detected = bool(_LICENSE_RE.search(text))
    idx_detected      = any(kw in text for kw in _IDX_KWS)
    testimonial_count = sum(text.count(kw) for kw in _TESTIMONIAL_KWS)

    return {
        **lead,
        "team_size":          _detect_team_size(text, lead.get("category", "")),
        "specializations":    _detect_specializations(text),
        "license_detected":   license_detected,
        "idx_detected":       idx_detected,
        "testimonial_count":  min(testimonial_count, 50),
        "years_in_business":  _detect_years_in_business(text),
        "service_area_count": _detect_service_area_count(text),
        "recent_activity":    _detect_recent_activity(text),
    }


async def _run_all(leads: list[dict]) -> tuple[list[dict], list[str]]:
    sem = asyncio.Semaphore(8)
    errors: list[str] = []

    async def safe(lead: dict) -> dict:
        async with sem:
            try:
                return await _enrich_one(lead)
            except Exception as e:
                errors.append(f"{lead.get('name', '?')}: {e}")
                return lead

    results = await asyncio.gather(*[safe(l) for l in leads])
    return list(results), errors


def enrich_real_estate_signals_node(state: LeadState) -> LeadState:
    leads = state.get("enriched_leads", [])
    logger.info(f"[re_signals] scanning {len(leads)} sites for real-estate signals")

    enriched, errors = asyncio.run(_run_all(leads))

    brokerages = sum(1 for l in enriched if l.get("team_size") == "brokerage")
    with_specialization = sum(1 for l in enriched if l.get("specializations"))
    logger.info(
        f"[re_signals] {brokerages} brokerages · "
        f"{with_specialization} with a detected specialization"
    )

    return {**state, "enriched_leads": enriched, "re_signal_errors": errors}
