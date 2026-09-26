"""
Node 2 — Maps Scraper (Real Estate vertical — locked)
======================================================
Primary:  RapidAPI "Local Business Data" (OpenWeb Ninja) — 100 free req/month
Fallback 1: SearchApi.io "google_maps" engine — separate account/quota,
            used per-term if the primary call fails (e.g. 429).
Fallback 2: Demo data — only if BOTH the above are unavailable/fail.

Always searches for real estate agents AND brokerages in the target
location — business_type from state is ignored on purpose since
AgentReach is a single-vertical product.

RapidAPI endpoint:  https://rapidapi.com/letscrape-6bRBa3QguO5/api/local-business-data
SearchApi endpoint: https://www.searchapi.io/docs/google-maps

NOTE on rate limiting: the two search terms used to be fired concurrently
via asyncio.gather. RapidAPI enforces a requests-per-second burst limit
independently of the monthly quota, and firing both terms at once (then,
on a 0-result response, immediately looping back through the graph's
retry with no backoff) could burst past that limit and return 429 even
with plenty of monthly quota left. Fixed by running the terms one at a
time with a small delay between them, plus a short backoff-and-retry on
a 429 response.

NOTE on the SearchApi fallback: it does NOT return emails/contacts the
way Local Business Data's extract_emails_and_contacts does — that's
fine, enricher.py already scrapes each business's website as a free
fallback for email discovery regardless of which source found the
business in the first place.
"""
import os, logging, asyncio, time
import httpx
from app.agents.state import LeadState

logger = logging.getLogger(__name__)

RAPIDAPI_KEY  = os.getenv("RAPIDAPI_KEY", "")
SEARCHAPI_KEY = os.getenv("SEARCHAPI_KEY", "")
_SEARCHAPI_URL = "https://www.searchapi.io/api/v1/search"

# Two searches per location so we catch both solo agents (usually tagged
# "Real estate agent" on Maps) and firms (usually tagged "Real estate agency").
_SEARCH_TERMS = ["real estate agent", "real estate agency"]

# Per OpenWeb Ninja's documented /search endpoint, `limit` itself accepts
# 1-500 directly — there is NO `page`/`offset` param on this endpoint (that
# only exists on the separate bulk POST /search endpoint). An earlier
# version of this file paged with `page=1,2,3...`, which the API silently
# ignored — it just returned the same first 20 results every time. Fixed:
# ask for what we actually want in one call.
_MAX_LIMIT_PER_CALL = 500

# Delay between the two sequential search-term calls, to stay under
# RapidAPI's per-second burst limit. Tune this up if you're still seeing
# 429s on a low-tier plan.
_DELAY_BETWEEN_REQUESTS_SEC = 1.5

# On a 429, wait this long and retry once before giving up on that term.
_RATE_LIMIT_BACKOFF_SEC = 3.0

# If RapidAPI is still 429 after that retry (monthly quota gone or throttled),
# skip it for this long — or until its X-RateLimit-Requests-Reset, if sent —
# so every search doesn't pay the 429 + backoff before reaching SearchApi.
_RAPIDAPI_COOLDOWN_SEC     = 600.0
_RAPIDAPI_MAX_COOLDOWN_SEC = 6 * 3600.0
_rapidapi_blocked_until    = 0.0


async def _search_local_business(query: str, location: str, limit: int, retry_on_429: bool = True) -> list[dict]:
    """
    RapidAPI Local Business Data — OpenWeb Ninja
    Endpoint: /search
    Returns: business name, address, phone, website, rating, reviews, coords, email

    `limit` is capped at 500 by the API itself (documented max). Billing is
    per business returned/enriched, not per request, so one call for N
    results costs the same as many smaller calls totalling N — there's no
    quota advantage to splitting this up.
    """
    url = "https://local-business-data.p.rapidapi.com/search"
    headers = {
        "X-RapidAPI-Key":  RAPIDAPI_KEY,
        "X-RapidAPI-Host": "local-business-data.p.rapidapi.com",
    }
    params = {
        "query":    f"{query} in {location}",
        "limit":    min(limit, _MAX_LIMIT_PER_CALL),
        "zoom":     "13",
        "language": "en",
        "region":   "us",
        "extract_emails_and_contacts": "true",
        # NOTE: lat/lng intentionally omitted — hardcoding them to 0,0
        # (Null Island) was actively hurting relevance for every search
        # regardless of target location. The query text itself carries
        # the location; omitting lat/lng lets the API fall back to its
        # own region-based default center instead of a wrong pin.
    }

    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.get(url, params=params, headers=headers)

        # These headers are sent on EVERY response (429 or not) and are the
        # only reliable way to know exactly when a block clears — the
        # RapidAPI dashboard is account-wide and doesn't reflect per-API
        # windows clearly. Log them any time we're not comfortably above
        # zero remaining, so we can see the real reset time instead of
        # guessing at a backoff duration.
        remaining = r.headers.get("X-RateLimit-Requests-Remaining")
        reset_secs = r.headers.get("X-RateLimit-Requests-Reset")
        if remaining is not None:
            logger.info(
                f"[maps_scraper] rate-limit headers for '{query}': "
                f"remaining={remaining} reset_in={reset_secs}s "
                f"limit={r.headers.get('X-RateLimit-Requests-Limit')}"
            )

        if r.status_code == 429:
            # Log the actual body RapidAPI sends back — it distinguishes
            # "rate limit per second" (throughput) from "exceeded the
            # MONTHLY quota" (quota) from "not subscribed" (key/plan
            # mismatch). Without this we're just guessing which one we're
            # hitting. Truncated in case it's ever unexpectedly large.
            logger.warning(f"[maps_scraper] 429 body for '{query}': {r.text[:500]!r}")

            if retry_on_429:
                wait = float(r.headers.get("Retry-After", _RATE_LIMIT_BACKOFF_SEC))
                logger.warning(
                    f"[maps_scraper] 429 for '{query}' — backing off {wait}s before one retry"
                )
                await asyncio.sleep(wait)
                r = await c.get(url, params=params, headers=headers)
                if r.status_code == 429:
                    logger.warning(f"[maps_scraper] retry also 429 for '{query}': {r.text[:500]!r}")

        r.raise_for_status()
        data = r.json()

    results = data.get("data", [])
    logger.info(f"[maps_scraper] {len(results)} results for '{query}' (requested limit={params['limit']})")
    return [_normalize(b) for b in results]


async def _search_searchapi_maps(query: str, location: str, limit: int) -> list[dict]:
    """
    Fallback provider — SearchApi.io "google_maps" engine.
    Docs: https://www.searchapi.io/docs/google-maps

    This is a completely separate account/quota from RapidAPI, so a 429
    (throttle or monthly quota) on Local Business Data doesn't take the
    whole scrape down with it. `q` accepts a plain "term in location"
    string directly — no need to geocode to lat/lng first.
    """
    params = {
        "engine":  "google_maps",
        "q":       f"{query} in {location}",
        "api_key": SEARCHAPI_KEY,
    }

    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.get(_SEARCHAPI_URL, params=params)
        r.raise_for_status()
        data = r.json()

    results = data.get("local_results", [])
    logger.info(f"[maps_scraper] (fallback/searchapi) {len(results)} results for '{query}'")
    return [_normalize_searchapi(b) for b in results[:limit]]


def _normalize_searchapi(r: dict) -> dict:
    """Normalize a SearchApi.io google_maps local_results item to our schema."""
    coords = r.get("gps_coordinates") or {}

    return {
        "name":          str(r.get("title") or ""),
        "address":       str(r.get("address") or ""),
        "phone":         str(r.get("phone") or ""),
        "website":       str(r.get("website") or ""),
        "rating":        float(r.get("rating") or 0),
        "review_count":  int(r.get("reviews") or 0),
        "latitude":      coords.get("latitude"),
        "longitude":     coords.get("longitude"),
        "category":      str(r.get("type") or ""),
        "source":        "searchapi_google_maps",
        # SearchApi doesn't extract emails — enricher.py's website-scrape
        # step fills this in downstream regardless of source.
        "emails":        [],
        "primary_email": "",
        "owner_name":    "",
        "owner_position": "",
        "email_valid":   False,
        "email_verified": False,
        "email_catchall": False,
        "email_status":  "",
        "score":         0,
        "enriched":      False,
        "team_size":          "unknown",
        "specializations":    [],
        "license_detected":   False,
        "idx_detected":       False,
        "testimonial_count":  0,
        "years_in_business":  0,
        "service_area_count": 0,
        "recent_activity":    False,
    }


async def _search_all_terms(location: str, limit: int) -> list[dict]:
    """
    Run each search term one at a time (not concurrently), with a small
    delay between them, so we don't burst past RapidAPI's per-second rate
    limit. RapidAPI Local Business Data is the primary source; if it fails
    for a term (error, 429, monthly quota used up) that same term falls back
    to SearchApi.io, so a block on one provider no longer drops results.
    """
    global _rapidapi_blocked_until
    per_term_limit = max(20, limit // len(_SEARCH_TERMS))
    merged: list[dict] = []

    for i, term in enumerate(_SEARCH_TERMS):
        results = None

        if RAPIDAPI_KEY and time.monotonic() >= _rapidapi_blocked_until:
            try:
                results = await _search_local_business(term, location, per_term_limit)
            except Exception as e:
                logger.warning(f"[maps_scraper] primary (RapidAPI) failed for '{term}': {e}")
                if isinstance(e, httpx.HTTPStatusError) and e.response.status_code == 429:
                    # Still 429 after the backoff retry — quota is used up or
                    # we're throttled. Skip RapidAPI until the window resets so
                    # later terms and graph retries go straight to the fallback.
                    try:
                        cooldown = float(e.response.headers.get("X-RateLimit-Requests-Reset", ""))
                    except ValueError:
                        cooldown = _RAPIDAPI_COOLDOWN_SEC
                    cooldown = min(max(cooldown, 60.0), _RAPIDAPI_MAX_COOLDOWN_SEC)
                    _rapidapi_blocked_until = time.monotonic() + cooldown
                    logger.warning(f"[maps_scraper] RapidAPI paused for {cooldown:.0f}s — using SearchApi")
        elif RAPIDAPI_KEY:
            logger.info(f"[maps_scraper] RapidAPI paused (rate limited) — skipping primary for '{term}'")

        if results is None:
            if SEARCHAPI_KEY:
                try:
                    logger.info(f"[maps_scraper] falling back to SearchApi.io for '{term}'")
                    results = await _search_searchapi_maps(term, location, per_term_limit)
                except Exception as e2:
                    logger.warning(f"[maps_scraper] fallback (SearchApi) also failed for '{term}': {e2}")
            else:
                logger.info("[maps_scraper] no SEARCHAPI_KEY set — skipping fallback, term dropped")

        merged.extend(results or [])

        # Don't sleep after the last term — nothing follows it.
        if i < len(_SEARCH_TERMS) - 1:
            await asyncio.sleep(_DELAY_BETWEEN_REQUESTS_SEC)

    return merged


def _normalize(r: dict) -> dict:
    """Normalize RapidAPI Local Business Data response to our schema."""
    # extract_emails_and_contacts=true puts them under emails_and_contacts.emails
    emails = r.get("emails") or (r.get("emails_and_contacts") or {}).get("emails") or []
    primary_email = emails[0] if emails else ""
    category = str((r.get("subtypes") or [None])[0] or r.get("type") or "")

    return {
        "name":          str(r.get("name") or ""),
        "address":       str(r.get("full_address") or r.get("address") or ""),
        "phone":         str(r.get("phone_number") or r.get("phone") or ""),
        "website":       str(r.get("website") or ""),
        "rating":        float(r.get("rating") or 0),
        "review_count":  int(r.get("reviews") or r.get("review_count") or 0),
        "latitude":      r.get("latitude") or (r.get("coordinates") or {}).get("lat"),
        "longitude":     r.get("longitude") or (r.get("coordinates") or {}).get("lng"),
        "category":      category,
        "source":        "rapidapi_local_business",
        "emails":        emails,
        "primary_email": str(primary_email),
        "owner_name":    "",
        "owner_position": "",
        "email_valid":   False,
        "email_verified": False,
        "email_catchall": False,
        "email_status":  "",
        "score":         0,
        "enriched":      bool(primary_email),
        # real-estate signal fields — filled in by real_estate_signals node
        "team_size":          "unknown",
        "specializations":    [],
        "license_detected":   False,
        "idx_detected":       False,
        "testimonial_count":  0,
        "years_in_business":  0,
        "service_area_count": 0,
        "recent_activity":    False,
    }


# A short list of large countries commonly typed bare (no city, no comma) —
# not exhaustive, just enough to catch the common "searched a whole country"
# mistake and nudge toward a city-level query instead.
_COUNTRY_NAMES = {
    "israel", "usa", "united states", "canada", "uk", "united kingdom",
    "australia", "germany", "france", "spain", "italy", "mexico", "brazil",
    "india", "china", "japan", "south africa", "nigeria", "egypt",
}


def _looks_like_country_or_region(location: str) -> bool:
    loc = location.strip().lower()
    if "," in loc:
        return False  # "City, ST" / "City, Country" already has a city part
    return loc in _COUNTRY_NAMES


def _demo_records(location: str, n: int = 15) -> list[dict]:
    """Synthetic real-estate data for demo / testing without any API keys."""
    import random

    # name, email, rating, reviews, category, team_size, specializations,
    # license, idx, testimonials, years, service_areas, recent_activity
    samples = [
        ("The Sunrise Realty Group",   "team@sunriserealty.com",       4.9, 214, "Real estate agency", "brokerage",  ["luxury", "relocation"],           True,  True,  12, 18, 6, True),
        ("Metro Home Advisors",        "info@metrohomeadvisors.com",   4.6, 98,  "Real estate agency", "large_team", ["new_construction"],               True,  True,  7,  9,  4, True),
        ("Maria Chen Realtor",         "maria@mariachenhomes.com",     4.8, 67,  "Real estate agent",  "solo",       ["first_time_buyer"],               False, False, 3,  4,  2, False),
        ("Valley Estates and Land",    "info@valleyestatesland.com",   4.7, 156, "Real estate agency", "small_team", ["land", "waterfront"],             True,  True,  9,  14, 5, True),
        ("Premier Coastal Properties", "hello@premiercoastal.com",     4.5, 31,  "Real estate agency", "small_team", ["waterfront", "vacation_rental"],  True,  False, 4,  6,  3, False),
        ("Capital City Realtors",      "leads@capitalcityrealtors.com",4.6, 178, "Real estate agency", "brokerage",  ["commercial", "luxury"],           True,  True,  15, 22, 8, True),
        ("Downtown Living Group",      "hello@downtownliving.com",     4.1, 42,  "Real estate agency", "small_team", ["new_construction"],               False, True,  2,  3,  2, True),
        ("James Patel Real Estate",    "james@jamespatelre.com",       4.9, 312, "Real estate agent",  "solo",       ["luxury"],                         True,  True,  20, 11, 3, True),
        ("Regional Realty Partners",   "contact@regionalrealtyp.com",  4.3, 44,  "Real estate agency", "large_team", ["relocation", "first_time_buyer"], True,  True,  5,  7,  5, False),
        ("Sunset Ridge Realtors",      "info@sunsetridgerealtors.com", 4.0, 22,  "Real estate agency", "solo",       [],                                 False, False, 0,  2,  1, False),
    ]
    records = []
    for i in range(n):
        (name, email, rating, reviews, category, team_size, specs,
         license_, idx, testi, years, areas, recent) = samples[i % len(samples)]
        clean_domain = name.lower().replace(" ", "").replace("and", "and")
        records.append({
            "name":          name,
            "address":       f"{100+i} Main St, {location}",
            "phone":         f"+1-555-{100+i:04d}",
            "website":       f"https://www.{clean_domain}.com",
            "rating":        rating,
            "review_count":  reviews,
            "latitude":      40.7 + random.uniform(-0.1, 0.1),
            "longitude":     -74.0 + random.uniform(-0.1, 0.1),
            "category":      category,
            "source":        "demo",
            "emails":        [email],
            "primary_email": email,
            "owner_name":    "",
            "owner_position": "",
            "email_valid":   True,
            "email_verified": True,
            "email_catchall": False,
            "email_status":  "valid",
            "enriched":      True,
            "score":         0,
            "team_size":          team_size,
            "specializations":    specs,
            "license_detected":   license_,
            "idx_detected":       idx,
            "testimonial_count":  testi,
            "years_in_business":  years,
            "service_area_count": areas,
            "recent_activity":    recent,
        })
    return records


def scrape_maps_node(state: LeadState) -> LeadState:
    loc = state["location"]
    lim = state.get("max_results", 100)

    logger.info(f"[maps_scraper] real estate agents & brokerages in '{loc}'")
    errors, businesses = [], []

    if _looks_like_country_or_region(loc):
        errors.append(
            f"'{loc}' looks like a whole country/region rather than a city. "
            "Google Maps-style search is city-centric — searching a country "
            "name typically returns a much smaller, less representative "
            "sample. For full coverage, run this per-city (e.g. 'Tel Aviv', "
            "'Jerusalem', 'Haifa') instead of the country name."
        )

    try:
        if RAPIDAPI_KEY or SEARCHAPI_KEY:
            businesses = asyncio.run(_search_all_terms(loc, lim))
        else:
            logger.warning("[maps_scraper] No RAPIDAPI_KEY or SEARCHAPI_KEY — using demo data")
            businesses = _demo_records(loc)
    except Exception as e:
        errors.append(str(e))
        logger.error(f"[maps_scraper] {e}")
        businesses = _demo_records(loc)

    # Deduplicate — use str() to safely handle None name/address from API
    seen, unique = set(), []
    for b in businesses:
        key = (str(b.get("name") or "").lower().strip(),
               str(b.get("address") or "").lower()[:30])
        if key not in seen:
            seen.add(key)
            unique.append(b)

    logger.info(f"[maps_scraper] {len(unique)} unique records")
    return {**state, "raw_businesses": unique, "scrape_errors": errors}